from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH_PATH = ROOT / "data" / "patches" / "world_cup_2026_rosters.manual.json"
TEAM_PATH = ROOT / "data" / "public" / "teams.json"
ROSTER_SOURCES_PATH = ROOT / "configs" / "roster_sources" / "world_cup_2026.json"
ROSTERS_MASTER_PATH = ROOT / "data" / "normalized" / "world_cup_2026_rosters_master.json"
PLAYERS_MASTER_PATH = ROOT / "data" / "normalized" / "world_cup_2026_players_master.json"
REPORT_PATH = ROOT / "reports" / "world_cup_roster_import_report.json"

ACCEPTED_SOURCE_STATUSES = {
    "official_fifa",
    "official_fa",
    "official_club_or_league_correction",
    "manual_official_patch",
}


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def stable_player_id(team_id: str, player: dict) -> str:
    source_refs = player.get("source_refs") if isinstance(player.get("source_refs"), dict) else {}
    for key in ("fifa", "api_football", "transfermarkt", "official"):
        value = source_refs.get(key)
        if value:
            return f"{key}:{value}"
    name = str(player.get("name") or "").strip()
    dob = str(player.get("date_of_birth") or "").strip()
    return f"{team_id}:player:{slugify(name + '-' + dob)}"


def load_team_index(path: Path) -> dict[str, dict]:
    payload = load_json(path)
    if not isinstance(payload, list):
        raise TypeError("teams.json must contain a list")
    return {str(item.get("team_id")): item for item in payload if isinstance(item, dict) and item.get("team_id")}


def validate_patch_entry(entry: dict, team_index: dict[str, dict], accepted_statuses: set[str]) -> list[str]:
    errors: list[str] = []
    team_id = str(entry.get("team_id") or "")
    source_status = str(entry.get("source_status") or "")
    source_url = str(entry.get("source_url") or "")
    players = entry.get("players")
    if team_id not in team_index:
        errors.append(f"unknown team_id: {team_id}")
    if source_status not in accepted_statuses:
        errors.append(f"unaccepted source_status for {team_id}: {source_status}")
    if not source_url.startswith("https://"):
        errors.append(f"missing official https source_url for {team_id}")
    if not isinstance(players, list):
        errors.append(f"players must be a list for {team_id}")
    return errors


def normalize_entry(entry: dict, team_index: dict[str, dict], imported_at: str) -> tuple[dict, list[dict]]:
    team_id = str(entry["team_id"])
    team = team_index[team_id]
    source_status = str(entry["source_status"])
    confidence = str(entry.get("confidence") or ("high" if source_status in {"official_fifa", "official_fa"} else "medium"))
    source_url = str(entry["source_url"])
    roster_players: list[dict] = []
    player_rows: list[dict] = []
    for raw_player in entry["players"]:
        if not isinstance(raw_player, dict):
            continue
        name = str(raw_player.get("name") or "").strip()
        if not name:
            continue
        player_id = str(raw_player.get("player_id") or stable_player_id(team_id, raw_player))
        roster_player = {
            "player_id": player_id,
            "name": name,
            "position": raw_player.get("position"),
            "shirt_number": raw_player.get("shirt_number"),
            "club": raw_player.get("club"),
            "status": raw_player.get("status") or "selected",
        }
        roster_players.append(roster_player)
        player_rows.append(
            {
                "player_id": player_id,
                "name": name,
                "display_name": raw_player.get("display_name") or name,
                "name_zh": raw_player.get("name_zh"),
                "date_of_birth": raw_player.get("date_of_birth"),
                "age": raw_player.get("age"),
                "nationality": raw_player.get("nationality") or team.get("name"),
                "team_id": team_id,
                "club": raw_player.get("club"),
                "position": raw_player.get("position"),
                "shirt_number": raw_player.get("shirt_number"),
                "source_status": source_status,
                "sources": [source_status],
                "source_refs": raw_player.get("source_refs") if isinstance(raw_player.get("source_refs"), dict) else {},
                "source_url": source_url,
                "updated_at": imported_at,
            }
        )
    roster = {
        "competition_id": str(entry.get("competition_id") or "fifa_world_cup"),
        "season_id": str(entry.get("season_id") or "2026"),
        "team_id": team_id,
        "team_name": team.get("name"),
        "roster_type": str(entry.get("roster_type") or "preliminary_or_announced"),
        "source_status": source_status,
        "confidence": confidence,
        "published_at": entry.get("published_at"),
        "updated_at": imported_at,
        "source_url": source_url,
        "sources": [source_status],
        "source_refs": entry.get("source_refs") if isinstance(entry.get("source_refs"), dict) else {},
        "players": roster_players,
    }
    return roster, player_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Import audited World Cup roster manual patches into normalized masters.")
    parser.add_argument("--patch", default=str(PATCH_PATH), help="manual roster patch file")
    parser.add_argument("--teams", default=str(TEAM_PATH), help="canonical team file")
    parser.add_argument("--sources", default=str(ROSTER_SOURCES_PATH), help="roster source policy config")
    parser.add_argument("--rosters-output", default=str(ROSTERS_MASTER_PATH), help="normalized rosters output")
    parser.add_argument("--players-output", default=str(PLAYERS_MASTER_PATH), help="normalized players output")
    parser.add_argument("--report-output", default=str(REPORT_PATH), help="import report output")
    args = parser.parse_args()

    team_index = load_team_index(Path(args.teams))
    source_policy = load_json(Path(args.sources))
    accepted_statuses = set(ACCEPTED_SOURCE_STATUSES)
    if isinstance(source_policy, dict):
        policy = source_policy.get("policy")
        if isinstance(policy, dict) and isinstance(policy.get("accepted_source_statuses"), list):
            accepted_statuses = {str(item) for item in policy["accepted_source_statuses"]}

    patch = load_json(Path(args.patch))
    if not isinstance(patch, dict) or not isinstance(patch.get("entries"), list):
        raise TypeError("manual roster patch must contain an entries list")

    imported_at = datetime.now(timezone.utc).isoformat()
    errors: list[dict[str, object]] = []
    rosters: list[dict] = []
    players_by_id: dict[str, dict] = {}
    for index, entry in enumerate(patch["entries"]):
        if not isinstance(entry, dict):
            errors.append({"index": index, "errors": ["entry must be an object"]})
            continue
        entry_errors = validate_patch_entry(entry, team_index, accepted_statuses)
        if entry_errors:
            errors.append({"index": index, "team_id": entry.get("team_id"), "errors": entry_errors})
            continue
        roster, player_rows = normalize_entry(entry, team_index, imported_at)
        rosters.append(roster)
        for player in player_rows:
            players_by_id[str(player["player_id"])] = player

    if errors:
        report = {
            "status": "failed_validation",
            "patch": str(args.patch),
            "errors": errors,
            "rosters_imported": 0,
            "players_imported": 0,
        }
        write_json(Path(args.report_output), report)
        raise SystemExit(json.dumps(report, ensure_ascii=False, indent=2))

    rosters = sorted(rosters, key=lambda item: str(item.get("team_id") or ""))
    players = sorted(players_by_id.values(), key=lambda item: (str(item.get("team_id") or ""), str(item.get("name") or "")))
    write_json(Path(args.rosters_output), rosters)
    write_json(Path(args.players_output), players)
    report = {
        "status": "imported" if rosters or players else "empty_patch",
        "patch": str(args.patch),
        "rosters_output": str(args.rosters_output),
        "players_output": str(args.players_output),
        "rosters_imported": len(rosters),
        "players_imported": len(players),
    }
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
