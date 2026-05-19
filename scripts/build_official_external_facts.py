from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = ROOT / "data" / "normalized"
REPORTS_DIR = ROOT / "reports"

WIKIDATA_PROBE_REPORT = REPORTS_DIR / "wikidata_official_identity_probe_report.json"
OUTPUT_PATH = NORMALIZED_DIR / "person_official_external_facts_master.json"
REPORT_PATH = REPORTS_DIR / "official_external_facts_report.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def age_from_dob(dob: str | None, today: date) -> int | None:
    if not dob:
        return None
    try:
        parsed = date.fromisoformat(dob)
    except ValueError:
        return None
    return today.year - parsed.year - ((today.month, today.day) < (parsed.month, parsed.day))


def is_full_iso_date(value: object) -> bool:
    try:
        date.fromisoformat(str(value or ""))
        return True
    except ValueError:
        return False


def build_facts(report: dict, *, generated_at: str) -> tuple[list[dict], dict]:
    rows = report.get("rows") if isinstance(report.get("rows"), list) else []
    today = datetime.now(timezone.utc).date()
    facts: list[dict] = []
    skipped: list[dict] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        candidate = row.get("best_candidate") if isinstance(row.get("best_candidate"), dict) else {}
        dob = candidate.get("date_of_birth")
        confidence = row.get("confidence")
        if confidence != "high" or not dob or not is_full_iso_date(dob):
            skipped.append(
                {
                    "official_id": row.get("official_id"),
                    "name": row.get("name"),
                    "reason": "not_high_confidence_or_missing_or_partial_dob",
                    "confidence": confidence,
                    "candidate_label": candidate.get("label"),
                    "candidate_url": candidate.get("url"),
                    "date_of_birth": dob,
                }
            )
            continue
        facts.append(
            {
                "official_id": row.get("official_id"),
                "person_id": row.get("official_id"),
                "person_type": "referee",
                "competition_id": "fifa_world_cup",
                "season_id": "2026",
                "name": row.get("name"),
                "display_name": row.get("display_name"),
                "role": row.get("role"),
                "country_code": row.get("country_code"),
                "association_code": row.get("association_code"),
                "source_status": "third_party_wikidata_identity",
                "source": "wikidata",
                "source_url": candidate.get("url"),
                "source_refs": {
                    "wikidata_qid": candidate.get("qid"),
                    "wikidata_label": candidate.get("label"),
                    "probe_confidence": confidence,
                    "score": candidate.get("score"),
                    "score_reasons": candidate.get("score_reasons"),
                    "probe_report": "reports/wikidata_official_identity_probe_report.json",
                },
                "confidence": "high",
                "direct": {
                    "date_of_birth": dob,
                    "age": age_from_dob(str(dob), today),
                    "wikidata_label": candidate.get("label"),
                    "wikidata_description": candidate.get("description"),
                    "wikidata_country_labels": candidate.get("country_labels"),
                    "wikidata_occupation_labels": candidate.get("occupation_labels"),
                },
                "updated_at": generated_at,
            }
        )

    counts = {
        "probe_rows": len(rows),
        "facts_written": len(facts),
        "skipped": len(skipped),
        "skipped_rows": skipped,
    }
    return facts, counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Build official external identity facts from reviewed Wikidata probe results.")
    parser.add_argument("--probe-report", default=str(WIKIDATA_PROBE_REPORT))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--report-output", default=str(REPORT_PATH))
    args = parser.parse_args()

    generated_at = now_utc()
    probe_report = load_json(Path(args.probe_report))
    facts, counts = build_facts(probe_report, generated_at=generated_at)
    write_json(Path(args.output), facts)
    report = {
        "generated_at": generated_at,
        "status": "published",
        "source": "wikidata",
        "policy": "Only high-confidence Wikidata referee identity matches with DOB are published. Low/medium/no-candidate rows stay in report-only review.",
        "counts": counts,
        "outputs": {
            "normalized": str(Path(args.output)),
        },
    }
    write_json(Path(args.report_output), report)
    print(json.dumps({"status": report["status"], "counts": {key: value for key, value in counts.items() if key != "skipped_rows"}, "output": str(Path(args.output))}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
