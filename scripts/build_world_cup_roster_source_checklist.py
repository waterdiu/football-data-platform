from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
TEAMS_PATH = ROOT / "data" / "public" / "teams.json"
FIXTURES_PATH = ROOT / "data" / "public" / "fixtures.json"
PATCH_PATH = ROOT / "data" / "patches" / "world_cup_2026_rosters.manual.json"
ROSTER_SOURCES_PATH = ROOT / "configs" / "roster_sources" / "world_cup_2026.json"
REPORT_PATH = ROOT / "reports" / "world_cup_roster_source_checklist.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_config_by_team(source_config: dict) -> dict[str, list[dict]]:
    sources = source_config.get("sources") if isinstance(source_config.get("sources"), dict) else {}
    by_team: dict[str, list[dict]] = {}
    for source_key, source in sources.items():
        if not isinstance(source, dict):
            continue
        team_id = str(source.get("team_id") or "")
        if not team_id:
            continue
        by_team.setdefault(team_id, []).append(
            {
                "source_key": source_key,
                "label": source.get("label"),
                "url": source.get("url"),
                "source_status": source.get("source_status"),
                "confidence": source.get("confidence"),
                "notes": source.get("notes"),
            }
        )
    return by_team


def patch_entries_by_team(patch: dict) -> dict[str, dict]:
    entries = patch.get("entries") if isinstance(patch.get("entries"), list) else []
    result: dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        team_id = str(entry.get("team_id") or "")
        if team_id:
            result[team_id] = entry
    return result


def fixture_team_ids(fixtures: list[dict]) -> set[str]:
    team_ids: set[str] = set()
    for fixture in fixtures:
        for key in ("home_team_id", "away_team_id"):
            value = str(fixture.get(key) or "").strip()
            if value and value.upper() != "TBD" and not value.startswith("slot-"):
                team_ids.add(value)
    return team_ids


def build_checklist(*, teams: list[dict], fixtures: list[dict], patch: dict, source_config: dict) -> dict:
    generated_at = utc_now()
    config_sources_by_team = source_config_by_team(source_config)
    imported_by_team = patch_entries_by_team(patch)
    world_cup_team_ids = fixture_team_ids(fixtures)
    fifa_source = ((source_config.get("sources") or {}).get("fifa") or {}) if isinstance(source_config.get("sources"), dict) else {}
    policy = source_config.get("policy") if isinstance(source_config.get("policy"), dict) else {}
    final_authority_url = fifa_source.get("url")

    rows: list[dict] = []
    for team in sorted(teams, key=lambda item: str(item.get("team_id") or "")):
        team_id = str(team.get("team_id") or "")
        if not team_id or team_id not in world_cup_team_ids:
            continue
        imported = imported_by_team.get(team_id)
        player_count = len(imported.get("players") or []) if isinstance(imported, dict) else 0
        imported_url = imported.get("source_url") if isinstance(imported, dict) else None
        imported_status = imported.get("source_status") if isinstance(imported, dict) else None
        monitoring_sources = []
        if final_authority_url:
            monitoring_sources.append(
                {
                    "source_key": "fifa_final_squad_lists",
                    "label": fifa_source.get("label") or "FIFA official squad lists",
                    "url": final_authority_url,
                    "source_status": fifa_source.get("source_status") or "official_fifa",
                    "confidence": fifa_source.get("confidence") or "high",
                    "role": "final_authority",
                }
            )
        monitoring_sources.extend(config_sources_by_team.get(team_id, []))
        roster_status = "imported_official_or_audited" if imported else "pending_official_final_squad"
        rows.append(
            {
                "team_id": team_id,
                "team_name": team.get("name"),
                "team_name_zh": ((team.get("localized_name") or {}).get("zh-CN") if isinstance(team.get("localized_name"), dict) else None),
                "short_name": team.get("short_name"),
                "roster_status": roster_status,
                "player_count": player_count,
                "current_source_status": imported_status,
                "current_source_url": imported_url,
                "published_at": imported.get("published_at") if isinstance(imported, dict) else None,
                "monitoring_sources": monitoring_sources,
                "allowed_master_sources": policy.get("accepted_source_statuses") or [],
                "rejected_master_sources": policy.get("rejected_as_master_sources") or [],
                "next_action": (
                    "Review against FIFA final squad list when it is published; update if final squad differs."
                    if imported
                    else "Wait for FIFA final squad list or official FA squad announcement, then add audited manual patch."
                ),
            }
        )

    imported_count = sum(1 for row in rows if row["roster_status"] == "imported_official_or_audited")
    return {
        "generated_at": generated_at,
        "competition_id": "fifa_world_cup",
        "season_id": "2026",
        "source_policy": {
            "final_authority": policy.get("final_authority") or "fifa",
            "final_26_expected_date": policy.get("final_26_expected_date"),
            "accepted_source_statuses": policy.get("accepted_source_statuses") or [],
            "rejected_as_master_sources": policy.get("rejected_as_master_sources") or [],
        },
        "summary": {
            "teams": len(rows),
            "imported_teams": imported_count,
            "pending_teams": len(rows) - imported_count,
            "imported_player_rows": sum(int(row.get("player_count") or 0) for row in rows),
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build World Cup 2026 official roster source checklist.")
    parser.add_argument("--teams", default=str(TEAMS_PATH))
    parser.add_argument("--fixtures", default=str(FIXTURES_PATH))
    parser.add_argument("--patch", default=str(PATCH_PATH))
    parser.add_argument("--sources", default=str(ROSTER_SOURCES_PATH))
    parser.add_argument("--output", default=str(REPORT_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    teams = load_json(Path(args.teams))
    fixtures = load_json(Path(args.fixtures))
    patch = load_json(Path(args.patch))
    source_config = load_json(Path(args.sources))
    if not isinstance(teams, list):
        raise TypeError("teams file must contain a list")
    if not isinstance(fixtures, list):
        raise TypeError("fixtures file must contain a list")
    if not isinstance(patch, dict):
        raise TypeError("roster patch must contain an object")
    if not isinstance(source_config, dict):
        raise TypeError("roster source config must contain an object")
    report = build_checklist(
        teams=[row for row in teams if isinstance(row, dict)],
        fixtures=[row for row in fixtures if isinstance(row, dict)],
        patch=patch,
        source_config=source_config,
    )
    write_json(Path(args.output), report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
