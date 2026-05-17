from __future__ import annotations

import json
import os
import ssl
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    import certifi
except ImportError:  # pragma: no cover - fallback for minimal Python runtimes.
    certifi = None

API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
DEFAULT_LEAGUE_IDS = {
    "fifa_world_cup": "1",
}


def canonical_name(value: str) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def compact_name(value: str) -> str:
    return "".join(ch for ch in canonical_name(value) if ch.isalnum())


def team_names(team_id: str, team_name_by_id: dict[str, str], aliases_by_team_id: dict[str, list[str]]) -> set[str]:
    names = {team_name_by_id.get(team_id, "")}
    names.update(aliases_by_team_id.get(team_id, []))
    return {compact_name(name) for name in names if name}


def team_side(team_name: str, fixture: dict, team_name_by_id: dict[str, str], aliases_by_team_id: dict[str, list[str]]) -> str | None:
    name = compact_name(team_name)
    if name in team_names(str(fixture.get("home_team_id") or ""), team_name_by_id, aliases_by_team_id):
        return "home"
    if name in team_names(str(fixture.get("away_team_id") or ""), team_name_by_id, aliases_by_team_id):
        return "away"
    return None


def request_api_football(endpoint: str, *, api_key: str, params: dict[str, str]) -> dict:
    query = urlencode(params)
    request = Request(
        f"{API_FOOTBALL_BASE_URL}{endpoint}?{query}",
        headers={"x-apisports-key": api_key},
    )
    context = ssl.create_default_context(cafile=certifi.where() if certifi else None)
    with urlopen(request, timeout=30, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def fixture_match_key_from_platform(
    fixture: dict,
    team_name_by_id: dict[str, str],
    aliases_by_team_id: dict[str, list[str]],
) -> tuple[str, str, str] | None:
    date_value = str(fixture.get("date_utc") or "")[:10]
    home_names = sorted(team_names(str(fixture.get("home_team_id") or ""), team_name_by_id, aliases_by_team_id))
    away_names = sorted(team_names(str(fixture.get("away_team_id") or ""), team_name_by_id, aliases_by_team_id))
    if not date_value or not home_names or not away_names:
        return None
    return (date_value, home_names[0], away_names[0])


def fixture_match_key_from_api(item: dict) -> tuple[str, str, str] | None:
    fixture = item.get("fixture") or {}
    teams = item.get("teams") or {}
    date_value = str(fixture.get("date") or "")[:10]
    home = compact_name(str((teams.get("home") or {}).get("name") or ""))
    away = compact_name(str((teams.get("away") or {}).get("name") or ""))
    if not date_value or not home or not away:
        return None
    return (date_value, home, away)


def discover_fixture_ids(
    *,
    fixtures: list[dict],
    teams: list[dict],
    api_key: str,
    league_id: str,
    season: str,
) -> dict[str, str]:
    team_name_by_id = {str(team.get("team_id") or ""): str(team.get("name") or "") for team in teams if isinstance(team, dict)}
    aliases_by_team_id = {
        str(team.get("team_id") or ""): [str(alias) for alias in team.get("aliases", []) if alias]
        for team in teams
        if isinstance(team, dict)
    }
    payload = request_api_football(
        "/fixtures",
        api_key=api_key,
        params={"league": league_id, "season": season},
    )
    api_items_by_key = {
        key: item
        for item in payload.get("response", [])
        if (key := fixture_match_key_from_api(item)) is not None
    }
    discovered: dict[str, str] = {}
    for fixture in fixtures:
        match_id = str(fixture.get("match_id") or "")
        key = fixture_match_key_from_platform(fixture, team_name_by_id, aliases_by_team_id)
        api_item = api_items_by_key.get(key) if key else None
        api_fixture_id = ((api_item or {}).get("fixture") or {}).get("id")
        if match_id and api_fixture_id:
            discovered[match_id] = str(api_fixture_id)
    return discovered


def load_fixture_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(key): str(value) for key, value in payload.items()} if isinstance(payload, dict) else {}


def save_fixture_map(path: Path, mapping: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def player_name(item: dict) -> str:
    player = item.get("player") or {}
    return str(player.get("name") or item.get("name") or "").strip()


def player_id(item: dict) -> str:
    player = item.get("player") or {}
    return str(player.get("id") or item.get("id") or "")


def injury_bucket(item: dict) -> str:
    text = f"{item.get('type') or ''} {item.get('reason') or ''}".casefold()
    if any(token in text for token in ("questionable", "doubt", "doubtful", "50%")):
        return "doubtful"
    return "unavailable"


def empty_team_context(team_name: str) -> dict:
    return {
        "team_name": team_name,
        "doubtful_players": 0,
        "unavailable_players": 0,
        "key_absences": [],
    }


def injury_player_summary(item: dict) -> dict:
    return {
        "id": player_id(item),
        "name": player_name(item),
        "bucket": injury_bucket(item),
        "type": str(item.get("type") or "").strip(),
        "reason": str(item.get("reason") or "").strip(),
    }


def lineup_players(items: list[dict]) -> list[dict]:
    players: list[dict] = []
    for item in items:
        player = item.get("player") or item
        players.append(
            {
                "id": str(player.get("id") or ""),
                "name": str(player.get("name") or "").strip(),
                "position": str(player.get("pos") or player.get("position") or "").strip(),
            }
        )
    return players


def lineup_team_context(item: dict) -> dict:
    start_xi = lineup_players(item.get("startXI") or item.get("start_xi") or [])
    substitutes = lineup_players(item.get("substitutes") or [])
    return {
        "team_name": str((item.get("team") or {}).get("name") or "").strip(),
        "formation": str(item.get("formation") or "").strip(),
        "start_xi_count": len(start_xi),
        "substitute_count": len(substitutes),
        "start_xi": start_xi,
        "substitutes": substitutes,
    }


def normalize_api_football_context(
    *,
    fixture: dict,
    teams: list[dict],
    api_fixture_id: str,
    injuries_payload: dict,
    lineups_payload: dict,
    fetched_at: str,
) -> tuple[dict, dict]:
    team_name_by_id = {str(team.get("team_id") or ""): str(team.get("name") or "") for team in teams if isinstance(team, dict)}
    aliases_by_team_id = {
        str(team.get("team_id") or ""): [str(alias) for alias in team.get("aliases", []) if alias]
        for team in teams
        if isinstance(team, dict)
    }
    match_id = str(fixture.get("match_id") or "")
    home_name = team_name_by_id.get(str(fixture.get("home_team_id") or ""), str(fixture.get("home_team_id") or ""))
    away_name = team_name_by_id.get(str(fixture.get("away_team_id") or ""), str(fixture.get("away_team_id") or ""))

    injuries = {
        "home": empty_team_context(home_name),
        "away": empty_team_context(away_name),
        "api_football_fixture_id": str(api_fixture_id),
    }
    for item in injuries_payload.get("response", []):
        side = team_side(str((item.get("team") or {}).get("name") or ""), fixture, team_name_by_id, aliases_by_team_id)
        if side is None:
            continue
        player = injury_player_summary(item)
        injuries[side]["key_absences"].append(player)
        if player["bucket"] == "doubtful":
            injuries[side]["doubtful_players"] += 1
        else:
            injuries[side]["unavailable_players"] += 1

    lineups = {
        "home": {"team_name": home_name, "formation": "", "start_xi_count": 0, "substitute_count": 0, "start_xi": [], "substitutes": []},
        "away": {"team_name": away_name, "formation": "", "start_xi_count": 0, "substitute_count": 0, "start_xi": [], "substitutes": []},
        "api_football_fixture_id": str(api_fixture_id),
    }
    for item in lineups_payload.get("response", []):
        side = team_side(str((item.get("team") or {}).get("name") or ""), fixture, team_name_by_id, aliases_by_team_id)
        if side is not None:
            lineups[side] = lineup_team_context(item)

    injuries_row = {
        "match_id": match_id,
        "source": "api_football",
        "confidence": "medium",
        "source_status": "available" if injuries_payload.get("response") is not None else "unknown",
        "fetched_at": fetched_at,
        "valid_at": fixture.get("date_utc"),
        "injury_summary": injuries,
        "raw": injuries_payload,
    }
    lineup_available = lineups["home"]["start_xi_count"] > 0 and lineups["away"]["start_xi_count"] > 0
    lineups_row = {
        "match_id": match_id,
        "provider": "api_football",
        "home": lineups["home"],
        "away": lineups["away"],
        "captured_at": fetched_at,
        "confidence": "confirmed" if lineup_available else "partial",
        "source_status": "available" if lineup_available else "partial",
        "api_football_fixture_id": str(api_fixture_id),
        "raw": lineups_payload,
    }
    return injuries_row, lineups_row


def collect_api_football_context(
    *,
    fixtures: list[dict],
    teams: list[dict],
    fetched_at: str,
    fixture_map_path: Path,
    league_id: str | None = None,
    season: str | None = None,
    api_key: str | None = None,
) -> tuple[list[dict], list[dict], dict]:
    key = (api_key or os.environ.get("API_FOOTBALL_KEY") or "").strip()
    resolved_league_id = league_id or os.environ.get("API_FOOTBALL_LEAGUE_ID") or DEFAULT_LEAGUE_IDS["fifa_world_cup"]
    resolved_season = season or os.environ.get("API_FOOTBALL_SEASON") or "2026"
    if not key:
        return [], [], {
            "status": "missing_auth",
            "status_reason": "API_FOOTBALL_KEY is not configured in environment or local .env file.",
            "provider": "api_football",
            "auth_env": "API_FOOTBALL_KEY",
            "league_id": resolved_league_id,
            "season": resolved_season,
        }

    mapping = load_fixture_map(fixture_map_path)
    missing = [fixture for fixture in fixtures if str(fixture.get("match_id") or "") not in mapping]
    errors: list[dict[str, str]] = []
    try:
        discovered = discover_fixture_ids(
            fixtures=missing,
            teams=teams,
            api_key=key,
            league_id=resolved_league_id,
            season=resolved_season,
        ) if missing else {}
    except Exception as exc:  # noqa: BLE001 - report fixture discovery failures without crashing all runtime collectors.
        discovered = {}
        errors.append({"stage": "discover_fixture_ids", "error": str(exc)})
    if discovered:
        mapping = {**mapping, **discovered}
        save_fixture_map(fixture_map_path, mapping)

    injuries_rows: list[dict] = []
    lineups_rows: list[dict] = []
    skipped: list[dict[str, str]] = []
    for fixture in fixtures:
        match_id = str(fixture.get("match_id") or "")
        api_fixture_id = mapping.get(match_id)
        if not api_fixture_id:
            skipped.append({"match_id": match_id, "reason": "missing_api_fixture_id"})
            continue
        try:
            injuries_payload = request_api_football("/injuries", api_key=key, params={"fixture": api_fixture_id})
            lineups_payload = request_api_football("/fixtures/lineups", api_key=key, params={"fixture": api_fixture_id})
        except Exception as exc:  # noqa: BLE001 - collection reports per-fixture provider failures.
            errors.append({"match_id": match_id, "api_fixture_id": api_fixture_id, "error": str(exc)})
            continue
        injuries_row, lineups_row = normalize_api_football_context(
            fixture=fixture,
            teams=teams,
            api_fixture_id=api_fixture_id,
            injuries_payload=injuries_payload,
            lineups_payload=lineups_payload,
            fetched_at=fetched_at,
        )
        injuries_rows.append(injuries_row)
        lineups_rows.append(lineups_row)

    report = {
        "status": "collected" if injuries_rows or lineups_rows else "no_rows",
        "status_reason": None if injuries_rows or lineups_rows else "No API-FOOTBALL lineups or injuries rows were available for selected fixtures.",
        "provider": "api_football",
        "auth_env": "API_FOOTBALL_KEY",
        "league_id": resolved_league_id,
        "season": resolved_season,
        "fixtures_considered": len(fixtures),
        "fixture_ids_existing": len(mapping) - len(discovered),
        "fixture_ids_discovered": len(discovered),
        "injuries_rows_collected": len(injuries_rows),
        "lineups_rows_collected": len(lineups_rows),
        "skipped": skipped,
        "errors": errors,
        "fixture_map_path": str(fixture_map_path),
    }
    return injuries_rows, lineups_rows, report
