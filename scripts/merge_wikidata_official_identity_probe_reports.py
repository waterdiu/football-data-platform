from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
OUTPUT_PATH = REPORTS_DIR / "wikidata_official_identity_probe_report.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize(rows: list[dict]) -> dict:
    return {
        "officials_considered": len(rows),
        "matched": sum(1 for row in rows if row.get("probe_status") == "matched"),
        "dob_available": sum(
            1
            for row in rows
            if isinstance(row.get("best_candidate"), dict) and row["best_candidate"].get("date_of_birth")
        ),
        "high_confidence": sum(1 for row in rows if row.get("confidence") == "high"),
        "medium_confidence": sum(1 for row in rows if row.get("confidence") == "medium"),
        "low_confidence": sum(1 for row in rows if row.get("confidence") == "low"),
        "none_confidence": sum(1 for row in rows if row.get("confidence") == "none"),
        "error_rows": sum(1 for row in rows if row.get("errors")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge batched Wikidata official identity probe reports.")
    parser.add_argument("reports", nargs="+")
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args()

    rows_by_id: dict[str, dict] = {}
    inputs: list[str] = []
    for report_path in args.reports:
        path = Path(report_path)
        payload = load_json(path)
        inputs.append(str(path))
        for row in payload.get("rows", []):
            if not isinstance(row, dict):
                continue
            official_id = str(row.get("official_id") or "")
            if official_id:
                rows_by_id[official_id] = row

    rows = sorted(rows_by_id.values(), key=lambda row: str(row.get("official_id") or ""))
    report = {
        "generated_at": now_utc(),
        "status": "report_only",
        "source": "wikidata",
        "source_url": "https://www.wikidata.org/",
        "policy": "Identity probe only. Do not write DOB/age to normalized/public until high-confidence candidate review passes.",
        "scope": {
            "merged_inputs": inputs,
        },
        "summary": summarize(rows),
        "rows": rows,
    }
    write_json(Path(args.output), report)
    print(json.dumps({"status": report["status"], "summary": report["summary"], "output": str(Path(args.output))}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
