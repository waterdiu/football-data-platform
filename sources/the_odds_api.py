from __future__ import annotations

import json
import os
from urllib.parse import urlencode
from urllib.request import urlopen

THE_ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4/sports"
DEFAULT_MARKETS = "h2h"
DEFAULT_REGIONS = "eu,us"
DEFAULT_ODDS_FORMAT = "decimal"
SHARP_BOOKMAKERS = {"pinnacle", "betfair", "matchbook"}


def normalize_team_name(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


def fetch_odds_events(
    *,
    sport_key: str,
    api_key: str | None = None,
    regions: str | None = None,
    markets: str | None = None,
    odds_format: str | None = None,
) -> list[dict]:
    key = (api_key or os.environ.get("THE_ODDS_API_KEY") or "").strip()
    if not key:
        return []
    query = urlencode(
        {
            "apiKey": key,
            "regions": regions or os.environ.get("THE_ODDS_API_REGIONS", DEFAULT_REGIONS),
            "markets": markets or os.environ.get("THE_ODDS_API_MARKETS", DEFAULT_MARKETS),
            "oddsFormat": odds_format or os.environ.get("THE_ODDS_API_ODDS_FORMAT", DEFAULT_ODDS_FORMAT),
        }
    )
    url = f"{THE_ODDS_API_BASE_URL}/{sport_key}/odds?{query}"
    with urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, list) else []


def event_team_key(event: dict) -> set[str]:
    return {
        normalize_team_name(str(event.get("home_team") or "")),
        normalize_team_name(str(event.get("away_team") or "")),
    }


def fixture_team_key(fixture: dict, team_name_by_id: dict[str, str], aliases_by_team_id: dict[str, list[str]]) -> set[str]:
    keys: set[str] = set()
    for side in ("home_team_id", "away_team_id"):
        team_id = str(fixture.get(side) or "")
        names = [team_name_by_id.get(team_id, ""), *aliases_by_team_id.get(team_id, [])]
        keys.update(normalize_team_name(name) for name in names if name)
    return {key for key in keys if key}


def _matching_fixture(event: dict, fixtures: list[dict], team_name_by_id: dict[str, str], aliases_by_team_id: dict[str, list[str]]) -> dict | None:
    event_key = event_team_key(event)
    if not event_key:
        return None
    for fixture in fixtures:
        fixture_keys = fixture_team_key(fixture, team_name_by_id, aliases_by_team_id)
        if event_key.issubset(fixture_keys):
            return fixture
    return None


def normalize_odds_event(
    *,
    event: dict,
    fixture: dict,
    sport_key: str,
    captured_at: str,
) -> dict:
    bookmakers = event.get("bookmakers") if isinstance(event.get("bookmakers"), list) else []
    bookmaker_keys = {
        str(bookmaker.get("key") or bookmaker.get("title") or "").casefold()
        for bookmaker in bookmakers
        if isinstance(bookmaker, dict)
    }
    return {
        "match_id": fixture["match_id"],
        "sport_key": sport_key,
        "date": str(fixture.get("date_utc") or "")[:10],
        "home_team": event.get("home_team"),
        "away_team": event.get("away_team"),
        "commence_time": event.get("commence_time"),
        "captured_at": captured_at,
        "snapshot_kind": "platform_runtime",
        "provider": "the_odds_api",
        "bookmakers": bookmakers,
        "bookmaker_count": len(bookmakers),
        "has_sharp": bool(bookmaker_keys & SHARP_BOOKMAKERS),
        "raw_event_id": event.get("id"),
    }


def normalize_odds_events(
    *,
    events: list[dict],
    fixtures: list[dict],
    teams: list[dict],
    sport_key: str,
    captured_at: str,
) -> tuple[list[dict], list[dict]]:
    team_name_by_id = {str(team.get("team_id") or ""): str(team.get("name") or "") for team in teams if isinstance(team, dict)}
    aliases_by_team_id = {
        str(team.get("team_id") or ""): [str(alias) for alias in team.get("aliases", []) if alias]
        for team in teams
        if isinstance(team, dict)
    }
    rows: list[dict] = []
    unmatched: list[dict] = []
    for event in events:
        fixture = _matching_fixture(event, fixtures, team_name_by_id, aliases_by_team_id)
        if fixture is None:
            unmatched.append(
                {
                    "event_id": event.get("id"),
                    "home_team": event.get("home_team"),
                    "away_team": event.get("away_team"),
                    "commence_time": event.get("commence_time"),
                }
            )
            continue
        rows.append(normalize_odds_event(event=event, fixture=fixture, sport_key=sport_key, captured_at=captured_at))
    return rows, unmatched
