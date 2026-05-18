from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = ROOT / "data" / "normalized"
REPORTS_DIR = ROOT / "reports"
TEAM_STAFF_PATH = NORMALIZED_DIR / "person_team_staff_master.json"
OUTPUT_PATH = NORMALIZED_DIR / "person_staff_external_facts_master.json"
REPORT_PATH = REPORTS_DIR / "staff_external_facts_report.json"

RE_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
RE_SPACES = re.compile(r"\s+")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_string(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def strip_accents(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch)
    )


def norm_name(value: str) -> str:
    lowered = strip_accents(value).lower().strip()
    normalized = RE_NON_ALNUM.sub(" ", lowered)
    return RE_SPACES.sub(" ", normalized).strip()


def age_from_dob(dob: str | None, today: date) -> int | None:
    if not dob:
        return None
    try:
        parsed = date.fromisoformat(dob)
    except ValueError:
        return None
    return today.year - parsed.year - ((today.month, today.day) < (parsed.month, parsed.day))


def compact_provider_refs(row: dict[str, str]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for field in (
        "reep_id",
        "key_wikidata",
        "key_transfermarkt_manager",
        "key_transfermarkt",
        "key_national_football_teams",
        "key_worldfootball",
        "key_api_football",
    ):
        value = clean_string(row.get(field))
        if value:
            refs[field] = value
    return refs


def coach_index(people_csv: Path) -> dict[str, list[dict[str, str]]]:
    index: dict[str, list[dict[str, str]]] = defaultdict(list)
    with people_csv.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if clean_string(row.get("type")) != "coach":
                continue
            name = clean_string(row.get("name") or row.get("full_name"))
            if name:
                index[norm_name(name)].append(row)
    return dict(index)


def build_staff_facts(
    *,
    staff_rows: list[dict[str, Any]],
    reep_coaches: dict[str, list[dict[str, str]]],
    generated_at: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    today = datetime.now(timezone.utc).date()
    facts: list[dict[str, Any]] = []
    counts = {
        "staff_considered": 0,
        "matched_reep_coach_rows": 0,
        "ambiguous_rows": 0,
        "date_of_birth_available": 0,
        "age_available": 0,
        "nationality_available": 0,
    }
    for staff in staff_rows:
        if staff.get("role") != "head_coach":
            continue
        counts["staff_considered"] += 1
        staff_id = clean_string(staff.get("staff_id"))
        name = clean_string(staff.get("name") or staff.get("display_name"))
        if not staff_id or not name:
            continue
        candidates = reep_coaches.get(norm_name(name), [])
        if len(candidates) != 1:
            counts["ambiguous_rows"] += int(len(candidates) > 1)
            continue
        row = candidates[0]
        dob = clean_string(row.get("date_of_birth"))
        age = age_from_dob(dob, today)
        nationality = clean_string(row.get("nationality"))
        provider_refs = compact_provider_refs(row)
        facts.append(
            {
                "staff_id": staff_id,
                "team_id": staff.get("team_id"),
                "name": name,
                "source_status": "third_party_reep_identity_dataset",
                "source": "withqwerty/reep people.csv",
                "source_license": "CC0-1.0",
                "source_refs": provider_refs,
                "confidence": "medium",
                "direct": {
                    "nationality": nationality,
                    "date_of_birth": dob,
                    "age": age,
                },
                "updated_at": generated_at,
            }
        )
        counts["matched_reep_coach_rows"] += 1
        counts["date_of_birth_available"] += int(dob is not None)
        counts["age_available"] += int(age is not None)
        counts["nationality_available"] += int(nationality is not None)
    return facts, counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Build third-party staff external facts from Reep coach records.")
    parser.add_argument("--reep-people-csv", required=True)
    parser.add_argument("--team-staff", default=str(TEAM_STAFF_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--report-output", default=str(REPORT_PATH))
    args = parser.parse_args()

    generated_at = now_utc()
    staff_rows = [row for row in load_json(Path(args.team_staff)) if isinstance(row, dict)]
    facts, counts = build_staff_facts(
        staff_rows=staff_rows,
        reep_coaches=coach_index(Path(args.reep_people_csv)),
        generated_at=generated_at,
    )
    write_json(Path(args.output), facts)
    report = {
        "generated_at": generated_at,
        "status": "published",
        "source": "withqwerty/reep people.csv",
        "source_license": "CC0-1.0",
        "policy": "External staff facts supplement public profiles and do not overwrite official FIFA/FA team-staff masters.",
        "counts": counts,
        "outputs": {"normalized": str(Path(args.output))},
    }
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
