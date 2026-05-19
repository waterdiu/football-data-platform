from __future__ import annotations

import argparse
import json
import ssl
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = ROOT / "data" / "normalized"
REPORTS_DIR = ROOT / "reports"

OFFICIALS_PATH = NORMALIZED_DIR / "world_cup_2026_match_officials_master.json"
REPORT_PATH = REPORTS_DIR / "wikidata_official_identity_probe_report.json"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "football-data-platform/0.1 (https://github.com/waterdiu/football-data-platform)"

ROLE_KEYWORDS = {
    "referee",
    "football referee",
    "association football referee",
    "soccer referee",
    "match official",
    "assistant referee",
    "video assistant referee",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(ascii_text.lower().replace("-", " ").replace("_", " ").split())


def reorder_fifa_name(name: str) -> str:
    parts = [part for part in str(name or "").strip().split() if part]
    if len(parts) <= 1:
        return str(name or "").strip()
    leading_surname_parts: list[str] = []
    remaining_parts: list[str] = []
    for part in parts:
        if not remaining_parts and part.isupper():
            leading_surname_parts.append(part.title())
        else:
            remaining_parts.append(part)
    if leading_surname_parts and remaining_parts:
        return " ".join([*remaining_parts, *leading_surname_parts])
    return str(name or "").strip()


def candidate_queries(name: str) -> list[str]:
    display = reorder_fifa_name(name)
    queries = [
        display,
        f"{display} referee",
        f"{display} football referee",
        str(name or "").strip(),
    ]
    output: list[str] = []
    seen: set[str] = set()
    for query in queries:
        key = normalize_text(query)
        if query and key not in seen:
            seen.add(key)
            output.append(query)
    return output


def ssl_context(*, insecure: bool) -> ssl.SSLContext:
    if insecure:
        return ssl._create_unverified_context()  # noqa: SLF001 - explicit probe-only fallback.
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def wikidata_get(params: dict[str, str], *, timeout: float, insecure: bool) -> dict:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{WIKIDATA_API}?{query}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout, context=ssl_context(insecure=insecure)) as response:
        return json.loads(response.read().decode("utf-8"))


def search_entities(query: str, *, limit: int, timeout: float, insecure: bool) -> list[dict]:
    payload = wikidata_get(
        {
            "action": "wbsearchentities",
            "format": "json",
            "language": "en",
            "type": "item",
            "limit": str(limit),
            "search": query,
        },
        timeout=timeout,
        insecure=insecure,
    )
    rows = payload.get("search")
    return rows if isinstance(rows, list) else []


def entity_details(qids: list[str], *, timeout: float, insecure: bool) -> dict[str, dict]:
    if not qids:
        return {}
    payload = wikidata_get(
        {
            "action": "wbgetentities",
            "format": "json",
            "languages": "en",
            "props": "labels|descriptions|claims",
            "ids": "|".join(qids),
        },
        timeout=timeout,
        insecure=insecure,
    )
    entities = payload.get("entities")
    return entities if isinstance(entities, dict) else {}


def claim_time(entity: dict, property_id: str) -> str | None:
    claims = entity.get("claims") if isinstance(entity.get("claims"), dict) else {}
    rows = claims.get(property_id)
    if not isinstance(rows, list) or not rows:
        return None
    mainsnak = rows[0].get("mainsnak") if isinstance(rows[0], dict) else {}
    datavalue = mainsnak.get("datavalue") if isinstance(mainsnak, dict) else {}
    value = datavalue.get("value") if isinstance(datavalue, dict) else {}
    raw_time = value.get("time") if isinstance(value, dict) else None
    if not isinstance(raw_time, str):
        return None
    return raw_time.lstrip("+").split("T")[0]


def claim_qids(entity: dict, property_id: str) -> list[str]:
    claims = entity.get("claims") if isinstance(entity.get("claims"), dict) else {}
    rows = claims.get(property_id)
    if not isinstance(rows, list):
        return []
    qids: list[str] = []
    for row in rows:
        mainsnak = row.get("mainsnak") if isinstance(row, dict) else {}
        datavalue = mainsnak.get("datavalue") if isinstance(mainsnak, dict) else {}
        value = datavalue.get("value") if isinstance(datavalue, dict) else {}
        numeric_id = value.get("numeric-id") if isinstance(value, dict) else None
        if numeric_id is not None:
            qids.append(f"Q{numeric_id}")
    return qids


def label_for(entity: dict) -> str | None:
    labels = entity.get("labels") if isinstance(entity.get("labels"), dict) else {}
    english = labels.get("en") if isinstance(labels.get("en"), dict) else {}
    value = english.get("value")
    return value if isinstance(value, str) else None


def description_for(entity: dict) -> str | None:
    descriptions = entity.get("descriptions") if isinstance(entity.get("descriptions"), dict) else {}
    english = descriptions.get("en") if isinstance(descriptions.get("en"), dict) else {}
    value = english.get("value")
    return value if isinstance(value, str) else None


def entity_labels(qids: list[str], *, timeout: float, insecure: bool) -> dict[str, str]:
    entities = entity_details(qids, timeout=timeout, insecure=insecure)
    labels: dict[str, str] = {}
    for qid, entity in entities.items():
        label = label_for(entity)
        if label:
            labels[qid] = label
    return labels


def score_candidate(official: dict, candidate: dict, entity: dict, occupation_labels: list[str], country_labels: list[str]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    official_name = normalize_text(reorder_fifa_name(str(official.get("name") or "")))
    label = normalize_text(label_for(entity) or candidate.get("label") or "")
    description = normalize_text(description_for(entity) or candidate.get("description") or "")
    aliases = normalize_text(" ".join(str(alias) for alias in candidate.get("aliases", []))) if isinstance(candidate.get("aliases"), list) else ""
    official_country = normalize_text(official.get("country") or official.get("nationality") or official.get("country_code") or "")
    country_text = normalize_text(" ".join(country_labels))
    occupation_text = normalize_text(" ".join(occupation_labels))

    if official_name and (official_name == label or official_name in label or label in official_name):
        score += 45
        reasons.append("name_match")
    elif official_name and official_name in aliases:
        score += 35
        reasons.append("alias_match")

    if any(keyword in description for keyword in ROLE_KEYWORDS) or any(keyword in occupation_text for keyword in ROLE_KEYWORDS):
        score += 35
        reasons.append("referee_context")

    if official_country and (official_country in country_text or official_country in description):
        score += 15
        reasons.append("country_context")

    if claim_time(entity, "P569"):
        score += 5
        reasons.append("has_dob")

    return score, reasons


def confidence_from_score(score: int, candidates_with_same_score: int) -> str:
    if score >= 80 and candidates_with_same_score == 1:
        return "high"
    if score >= 65:
        return "medium"
    if score >= 45:
        return "low"
    return "none"


def probe_official(official: dict, *, search_limit: int, timeout: float, sleep_seconds: float, insecure: bool) -> dict:
    seen_qids: set[str] = set()
    search_rows: list[dict] = []
    errors: list[str] = []
    for query in candidate_queries(str(official.get("name") or "")):
        try:
            rows = search_entities(query, limit=search_limit, timeout=timeout, insecure=insecure)
            for row in rows:
                qid = row.get("id")
                if isinstance(qid, str) and qid not in seen_qids:
                    seen_qids.add(qid)
                    row["query"] = query
                    search_rows.append(row)
        except Exception as exc:  # noqa: BLE001 - report probe failures instead of failing the whole run.
            errors.append(f"{query}: {type(exc).__name__}: {exc}")
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    try:
        entities = entity_details(sorted(seen_qids), timeout=timeout, insecure=insecure) if seen_qids else {}
    except Exception as exc:  # noqa: BLE001 - keep batch probes running through transient network failures.
        errors.append(f"entity_details: {type(exc).__name__}: {exc}")
        entities = {}
    all_related_qids: set[str] = set()
    for entity in entities.values():
        all_related_qids.update(claim_qids(entity, "P106"))
        all_related_qids.update(claim_qids(entity, "P27"))
    try:
        related_labels = entity_labels(sorted(all_related_qids), timeout=timeout, insecure=insecure) if all_related_qids else {}
    except Exception as exc:  # noqa: BLE001
        errors.append(f"entity_labels: {type(exc).__name__}: {exc}")
        related_labels = {}

    candidates: list[dict] = []
    for row in search_rows:
        qid = row.get("id")
        entity = entities.get(qid, {}) if isinstance(qid, str) else {}
        occupation_qids = claim_qids(entity, "P106")
        country_qids = claim_qids(entity, "P27")
        occupation_labels = [related_labels.get(qid, qid) for qid in occupation_qids]
        country_labels = [related_labels.get(qid, qid) for qid in country_qids]
        score, reasons = score_candidate(official, row, entity, occupation_labels, country_labels)
        candidates.append(
            {
                "qid": qid,
                "label": label_for(entity) or row.get("label"),
                "description": description_for(entity) or row.get("description"),
                "url": f"https://www.wikidata.org/wiki/{qid}" if isinstance(qid, str) else None,
                "date_of_birth": claim_time(entity, "P569"),
                "occupation_qids": occupation_qids,
                "occupation_labels": occupation_labels,
                "country_qids": country_qids,
                "country_labels": country_labels,
                "score": score,
                "score_reasons": reasons,
                "query": row.get("query"),
            }
        )

    candidates.sort(key=lambda row: (-int(row.get("score") or 0), str(row.get("label") or "")))
    best_score = int(candidates[0].get("score") or 0) if candidates else 0
    same_score_count = sum(1 for row in candidates if int(row.get("score") or 0) == best_score)
    confidence = confidence_from_score(best_score, same_score_count)
    best_candidate = candidates[0] if candidates else None
    return {
        "official_id": official.get("official_id") or official.get("person_id"),
        "name": official.get("name"),
        "display_name": official.get("display_name"),
        "role": official.get("role"),
        "country": official.get("country"),
        "country_code": official.get("country_code"),
        "association_code": official.get("association_code"),
        "probe_status": "matched" if best_candidate else "no_candidate",
        "confidence": confidence,
        "best_candidate": best_candidate,
        "candidate_count": len(candidates),
        "candidates": candidates[:5],
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Wikidata DOB/age identity coverage for FIFA World Cup 2026 match officials.")
    parser.add_argument("--officials", default=str(OFFICIALS_PATH))
    parser.add_argument("--output", default=str(REPORT_PATH))
    parser.add_argument("--role", default="referee", help="Role filter, or 'all'. Default: referee")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--search-limit", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--sleep", type=float, default=0.15)
    parser.add_argument("--insecure", action="store_true", help="Probe-only fallback: disable TLS verification if local CA store is broken.")
    args = parser.parse_args()

    officials = [row for row in load_json(Path(args.officials)) if isinstance(row, dict)]
    if args.role != "all":
        officials = [row for row in officials if row.get("role") == args.role]
    if args.offset and args.offset > 0:
        officials = officials[args.offset :]
    if args.limit and args.limit > 0:
        officials = officials[: args.limit]

    rows = [
        probe_official(
            row,
            search_limit=args.search_limit,
            timeout=args.timeout,
            sleep_seconds=args.sleep,
            insecure=args.insecure,
        )
        for row in officials
    ]
    summary = {
        "officials_considered": len(officials),
        "matched": sum(1 for row in rows if row.get("probe_status") == "matched"),
        "dob_available": sum(1 for row in rows if isinstance(row.get("best_candidate"), dict) and row["best_candidate"].get("date_of_birth")),
        "high_confidence": sum(1 for row in rows if row.get("confidence") == "high"),
        "medium_confidence": sum(1 for row in rows if row.get("confidence") == "medium"),
        "low_confidence": sum(1 for row in rows if row.get("confidence") == "low"),
        "none_confidence": sum(1 for row in rows if row.get("confidence") == "none"),
        "error_rows": sum(1 for row in rows if row.get("errors")),
    }
    report = {
        "generated_at": now_utc(),
        "status": "report_only",
        "source": "wikidata",
        "source_url": "https://www.wikidata.org/",
        "policy": "Identity probe only. Do not write DOB/age to normalized/public until high-confidence candidate review passes.",
        "scope": {
            "officials": str(Path(args.officials)),
            "role": args.role,
            "offset": args.offset,
            "limit": args.limit,
            "insecure_tls": args.insecure,
        },
        "summary": summary,
        "rows": rows,
    }
    write_json(Path(args.output), report)
    print(json.dumps({"status": report["status"], "summary": summary, "output": str(Path(args.output))}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
