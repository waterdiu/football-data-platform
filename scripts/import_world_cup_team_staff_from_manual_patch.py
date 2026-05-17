from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "data" / "public"
NORMALIZED_DIR = ROOT / "data" / "normalized"
PATCH_PATH = ROOT / "data" / "patches" / "world_cup_2026_team_staff.manual.json"
OUTPUT_PATH = NORMALIZED_DIR / "person_team_staff_master.json"
REPORT_PATH = ROOT / "reports" / "world_cup_team_staff_import_report.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return text or "unknown"


def age_from_date_of_birth(date_of_birth: str | None, *, as_of_year: int = 2026) -> int | None:
    if not date_of_birth:
        return None
    year = date_of_birth[:4]
    try:
        return as_of_year - int(year)
    except ValueError:
        return None


def team_names() -> dict[str, str]:
    teams = load_json(PUBLIC_DIR / "teams.json")
    if not isinstance(teams, list):
        return {}
    return {
        str(team.get("team_id") or ""): str(team.get("name") or team.get("team_id") or "")
        for team in teams
        if isinstance(team, dict)
    }


def normalize_entry(entry: dict, *, competition_id: str, season_id: str, updated_at: str, names_by_team_id: dict[str, str]) -> dict:
    team_id = str(entry.get("team_id") or "")
    name = str(entry.get("name") or "").strip()
    role = str(entry.get("role") or "head_coach")
    date_of_birth = entry.get("date_of_birth")
    date_of_birth = str(date_of_birth) if date_of_birth else None
    source_status = str(entry.get("source_status") or "manual_official_patch")
    source_url = entry.get("source_url")
    source_url = str(source_url) if source_url else None
    return {
        "competition_id": competition_id,
        "season_id": season_id,
        "team_id": team_id,
        "team_name": names_by_team_id.get(team_id, team_id),
        "staff_id": f"{team_id}:staff:{slugify(name)}",
        "name": name,
        "display_name": name,
        "name_zh": entry.get("name_zh"),
        "role": role,
        "role_zh": entry.get("role_zh") or "主教练",
        "status": entry.get("status") or "active",
        "nationality": entry.get("nationality"),
        "date_of_birth": date_of_birth,
        "age": entry.get("age") if entry.get("age") is not None else age_from_date_of_birth(date_of_birth),
        "appointed_at": entry.get("appointed_at"),
        "contract_until": entry.get("contract_until"),
        "source_status": source_status,
        "sources": [source_status],
        "source_refs": {
            "source_url": source_url,
        },
        "source_url": source_url,
        "updated_at": updated_at,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import World Cup team staff from audited manual patch.")
    parser.add_argument("--patch", default=str(PATCH_PATH), help="manual patch path")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="normalized team staff master output")
    parser.add_argument("--report-output", default=str(REPORT_PATH), help="import report output")
    args = parser.parse_args()

    patch = load_json(Path(args.patch))
    if not isinstance(patch, dict):
        raise TypeError("team staff patch must contain an object")
    entries = patch.get("entries")
    if not isinstance(entries, list):
        raise TypeError("team staff patch entries must contain a list")

    competition_id = str(patch.get("competition_id") or "fifa_world_cup")
    season_id = str(patch.get("season_id") or "2026")
    updated_at = str(patch.get("updated_at") or "2026-05-17T00:00:00Z")
    names_by_team_id = team_names()
    rows = [
        normalize_entry(
            entry,
            competition_id=competition_id,
            season_id=season_id,
            updated_at=updated_at,
            names_by_team_id=names_by_team_id,
        )
        for entry in entries
        if isinstance(entry, dict)
    ]
    rows = sorted(rows, key=lambda row: (str(row.get("team_id") or ""), str(row.get("role") or ""), str(row.get("name") or "")))
    write_json(Path(args.output), rows)

    report = {
        "status": "published",
        "patch": str(args.patch),
        "output": str(args.output),
        "rows": len(rows),
        "teams": sorted({str(row.get("team_id") or "") for row in rows}),
        "source_statuses": sorted({str(row.get("source_status") or "") for row in rows}),
    }
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
