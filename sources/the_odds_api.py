from __future__ import annotations

import json
import os
import ssl
from urllib.parse import urlencode
from urllib.request import urlopen

try:
    import certifi
except ImportError:  # pragma: no cover - fallback for minimal Python runtimes.
    certifi = None

THE_ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4/sports"
DEFAULT_MARKETS = "h2h,spreads,totals"
DEFAULT_REGIONS = "eu,us"
DEFAULT_ODDS_FORMAT = "decimal"
SHARP_BOOKMAKERS = {"pinnacle", "betfair", "matchbook"}
MARKET_ALIASES = {
    "h2h": "h2h",
    "spreads": "asian_handicap",
    "totals": "over_under",
}


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
    context = ssl.create_default_context(cafile=certifi.where() if certifi else None)
    with urlopen(url, timeout=30, context=context) as response:
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
    markets = summarize_markets(bookmakers)
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
        "markets": markets,
        "h2h": markets.get("h2h"),
        "over_under": markets.get("over_under"),
        "asian_handicap": markets.get("asian_handicap"),
        "has_1x2": bool(markets.get("h2h", {}).get("bookmaker_count")),
        "has_over_under": bool(markets.get("over_under", {}).get("bookmaker_count")),
        "has_asian_handicap": bool(markets.get("asian_handicap", {}).get("bookmaker_count")),
        "raw_event_id": event.get("id"),
    }


def summarize_markets(bookmakers: list[dict]) -> dict[str, dict]:
    summaries = {
        "h2h": empty_market_summary("h2h"),
        "over_under": empty_market_summary("over_under"),
        "asian_handicap": empty_market_summary("asian_handicap"),
    }
    for bookmaker in bookmakers:
        if not isinstance(bookmaker, dict):
            continue
        bookmaker_key = str(bookmaker.get("key") or bookmaker.get("title") or "unknown")
        bookmaker_title = str(bookmaker.get("title") or bookmaker_key)
        for market in bookmaker.get("markets") or []:
            if not isinstance(market, dict):
                continue
            normalized_key = MARKET_ALIASES.get(str(market.get("key") or ""), str(market.get("key") or ""))
            if normalized_key not in summaries:
                continue
            append_market_outcomes(
                summaries[normalized_key],
                bookmaker_key=bookmaker_key,
                bookmaker_title=bookmaker_title,
                last_update=str(market.get("last_update") or bookmaker.get("last_update") or ""),
                outcomes=market.get("outcomes") if isinstance(market.get("outcomes"), list) else [],
            )
    for summary in summaries.values():
        finalize_market_summary(summary)
    return summaries


def empty_market_summary(market_key: str) -> dict:
    return {
        "market": market_key,
        "bookmaker_count": 0,
        "bookmakers": [],
        "outcomes": [],
        "best_prices": {},
        "last_update": None,
    }


def append_market_outcomes(
    summary: dict,
    *,
    bookmaker_key: str,
    bookmaker_title: str,
    last_update: str,
    outcomes: list[dict],
) -> None:
    if bookmaker_key not in summary["bookmakers"]:
        summary["bookmakers"].append(bookmaker_key)
    if last_update and (summary["last_update"] is None or last_update > summary["last_update"]):
        summary["last_update"] = last_update
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            continue
        normalized = {
            "bookmaker_key": bookmaker_key,
            "bookmaker_title": bookmaker_title,
            "name": outcome.get("name"),
            "price": outcome.get("price"),
        }
        if "point" in outcome:
            normalized["point"] = outcome.get("point")
        summary["outcomes"].append(normalized)


def finalize_market_summary(summary: dict) -> None:
    summary["bookmaker_count"] = len(summary["bookmakers"])
    best_prices: dict[str, dict] = {}
    for outcome in summary["outcomes"]:
        if not isinstance(outcome, dict):
            continue
        name = str(outcome.get("name") or "")
        if not name:
            continue
        point = outcome.get("point")
        key = f"{name}:{point}" if point is not None else name
        price = outcome.get("price")
        try:
            numeric_price = float(price)
        except (TypeError, ValueError):
            continue
        existing = best_prices.get(key)
        if existing is None or numeric_price > float(existing.get("price") or 0):
            best_prices[key] = {
                "name": name,
                "point": point,
                "price": numeric_price,
                "bookmaker_key": outcome.get("bookmaker_key"),
                "bookmaker_title": outcome.get("bookmaker_title"),
            }
    summary["best_prices"] = best_prices


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
