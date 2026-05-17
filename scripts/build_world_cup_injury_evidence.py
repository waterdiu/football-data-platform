from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = ROOT / "data" / "normalized"
REPORTS_DIR = ROOT / "reports"

INJURIES_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_model_injuries_master.json"
PREMATCH_CONTEXT_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_model_prematch_context_master.json"
REPORT_PATH = REPORTS_DIR / "world_cup_injury_evidence_report.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def evidence_items(context: dict, *, side: str) -> list[dict]:
    items: list[dict] = []
    for signal_type in ("injury", "suspension"):
        for mention in context.get(f"{signal_type}_mentions", []):
            if not isinstance(mention, dict):
                continue
            entities = mention.get("entities") if isinstance(mention.get("entities"), list) else []
            players = [str(entity) for entity in entities if entity]
            items.append(
                {
                    "side": side,
                    "team_name": context.get("team_name"),
                    "signal_type": signal_type,
                    "status": "suspended" if signal_type == "suspension" else "injury_reported",
                    "certainty": mention.get("certainty") or "reported",
                    "keyword": mention.get("keyword"),
                    "players": players,
                    "source": mention.get("source"),
                    "source_url": mention.get("url"),
                    "evidence_text": mention.get("text"),
                }
            )
    return items


def summarize_prematch_absences(row: dict, *, generated_at: str) -> dict:
    summary = row.get("prematch_news_summary") if isinstance(row.get("prematch_news_summary"), dict) else {}
    evidence: list[dict] = []
    for side in ("home", "away"):
        context = summary.get(side) if isinstance(summary.get(side), dict) else {}
        evidence.extend(evidence_items(context, side=side))
    source_urls = sorted({str(item.get("source_url") or "") for item in evidence if item.get("source_url")})
    sources = sorted({str(item.get("source") or "") for item in evidence if item.get("source")})
    return {
        "status": "available" if evidence else "no_news_absence_evidence",
        "source": "platform_prematch_news",
        "generated_at": generated_at,
        "evidence_count": len(evidence),
        "sources": sources,
        "source_urls": source_urls,
        "evidence": evidence,
        "note": (
            "News evidence is not a final injury list. It is used for model/report downgrades "
            "until official injury, suspension, or lineup sources are available."
        ),
    }


def merge_source_status(existing_status: str, absence_summary: dict) -> str:
    if existing_status in {"available", "partial"}:
        return existing_status
    if absence_summary.get("status") == "available":
        return "partial"
    return existing_status or "unavailable"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build World Cup injury evidence from prematch news context.")
    parser.add_argument("--injuries-master", default=str(INJURIES_MASTER_PATH))
    parser.add_argument("--prematch-context-master", default=str(PREMATCH_CONTEXT_MASTER_PATH))
    parser.add_argument("--report-output", default=str(REPORT_PATH))
    args = parser.parse_args()

    injuries = load_json(Path(args.injuries_master))
    prematch_context = load_json(Path(args.prematch_context_master))
    if not isinstance(injuries, list):
        raise TypeError("injuries master must contain a list")
    if not isinstance(prematch_context, list):
        raise TypeError("prematch context master must contain a list")

    generated_at = datetime.now(timezone.utc).isoformat()
    context_by_match = {
        str(row.get("match_id") or ""): row
        for row in prematch_context
        if isinstance(row, dict) and row.get("match_id")
    }

    updated_rows: list[dict] = []
    evidence_match_count = 0
    evidence_count = 0
    for injury_row in injuries:
        if not isinstance(injury_row, dict):
            continue
        match_id = str(injury_row.get("match_id") or "")
        context_row = context_by_match.get(match_id, {})
        absence_summary = summarize_prematch_absences(context_row, generated_at=generated_at)
        row = dict(injury_row)
        row["absence_evidence_summary"] = absence_summary
        row["source_status"] = merge_source_status(str(row.get("source_status") or ""), absence_summary)
        if absence_summary["status"] == "available":
            row["status_reason"] = "prematch_news_absence_evidence"
            evidence_match_count += 1
            evidence_count += int(absence_summary.get("evidence_count") or 0)
        updated_rows.append(row)

    write_json(Path(args.injuries_master), updated_rows)
    report = {
        "generated_at": generated_at,
        "injuries_rows": len(updated_rows),
        "prematch_context_rows": len(prematch_context),
        "matches_with_absence_evidence": evidence_match_count,
        "absence_evidence_count": evidence_count,
        "output": str(Path(args.injuries_master).relative_to(ROOT)),
    }
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
