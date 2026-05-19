from __future__ import annotations

import argparse
import json
import os
import ssl
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from json_io import write_json

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "providers" / "free_odds_probe.json"
REPORT_PATH = ROOT / "reports" / "free_odds_source_probe.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_env_value(name: str) -> str:
    direct = os.environ.get(name, "").strip()
    if direct:
        return direct
    for env_path in (ROOT / ".env.local", ROOT / ".env"):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == name and value.strip():
                return value.strip().strip('"').strip("'")
    return ""


def fetch_json(url: str, *, headers: dict[str, str] | None = None, timeout: int = 20) -> tuple[int | None, object | None, str | None]:
    context = ssl.create_default_context(cafile=certifi.where() if certifi else None)
    request = Request(url, headers=headers or {})
    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            status = int(response.status)
            raw = response.read().decode("utf-8")
    except HTTPError as error:
        return int(error.code), None, str(error)
    except (URLError, TimeoutError, OSError) as error:
        return None, None, str(error)
    try:
        return status, json.loads(raw), None
    except json.JSONDecodeError:
        return status, None, "response was not JSON"


def market_coverage_from_events(payload: object) -> dict[str, object]:
    events = payload if isinstance(payload, list) else []
    bookmaker_keys: set[str] = set()
    market_keys: set[str] = set()
    event_count = len(events)
    for event in events:
        if not isinstance(event, dict):
            continue
        for bookmaker in event.get("bookmakers") or []:
            if not isinstance(bookmaker, dict):
                continue
            bookmaker_key = str(bookmaker.get("key") or bookmaker.get("title") or "").strip()
            if bookmaker_key:
                bookmaker_keys.add(bookmaker_key)
            for market in bookmaker.get("markets") or []:
                if isinstance(market, dict) and market.get("key"):
                    market_keys.add(str(market["key"]))
    return {
        "event_count": event_count,
        "bookmaker_count": len(bookmaker_keys),
        "bookmakers_sample": sorted(bookmaker_keys)[:10],
        "market_keys": sorted(market_keys),
        "has_1x2": "h2h" in market_keys or "1x2" in market_keys,
        "has_over_under": "totals" in market_keys or "over_under" in market_keys,
        "has_asian_handicap": "spreads" in market_keys or "asian_handicap" in market_keys,
    }


def summarize_odds_api_io_event(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {"event_seen": False}
    bookmakers = payload.get("bookmakers") if isinstance(payload.get("bookmakers"), dict) else {}
    bookmaker_names = sorted(str(name) for name in bookmakers.keys())
    market_names: set[str] = set()
    for markets in bookmakers.values():
        if not isinstance(markets, list):
            continue
        for market in markets:
            if isinstance(market, dict) and market.get("name"):
                market_names.add(str(market["name"]))
    normalized_market_names = {name.lower().replace(" ", "_").replace("-", "_") for name in market_names}
    return {
        "event_seen": True,
        "event_id": payload.get("id"),
        "home": payload.get("home"),
        "away": payload.get("away"),
        "date": payload.get("date"),
        "status": payload.get("status"),
        "sport": payload.get("sport"),
        "league": payload.get("league"),
        "bookmaker_count": len(bookmaker_names),
        "bookmakers_sample": bookmaker_names[:10],
        "market_names": sorted(market_names),
        "has_1x2": any(name in normalized_market_names for name in ("ml", "moneyline", "match_winner")),
        "has_over_under": any(name in normalized_market_names for name in ("over/under", "over_under", "totals")),
        "has_asian_handicap": any(name in normalized_market_names for name in ("asian_handicap", "spread", "spreads")),
    }


def probe_odds_api_io(provider: dict, *, live: bool) -> dict:
    key = load_env_value(str(provider.get("auth_env") or ""))
    row = base_probe_row(provider, live=live)
    row["probe_status"] = "skipped_missing_key" if live and not key else "metadata_only"
    row["live_probe_enabled"] = bool(live and key)
    row["production_classification"] = provider.get("probe_classification")
    row["market_verdict"] = {
        "one_x_two": "claimed_or_unknown",
        "over_under": "claimed_or_unknown",
        "asian_handicap": "unknown",
        "world_cup_2026": "unknown",
    }
    if not live or not key:
        return row

    bookmakers = provider.get("probe_bookmakers") or ["Sbobet", "Bet365"]
    event_url = (
        "https://api.odds-api.io/v3/events?apiKey="
        + key
        + "&sport=football&status=pending,live&bookmaker="
        + str(bookmakers[0])
        + "&limit=10"
    )
    status, payload, error = fetch_json(event_url)
    row["events_probe"] = {
        "http_status": status,
        "error": error,
        "observed": market_coverage_from_events(payload),
    }
    events = payload if isinstance(payload, list) else []
    event = next(
        (
            item
            for item in events
            if isinstance(item, dict)
            and item.get("id") is not None
            and str(item.get("status") or "").lower() not in {"cancelled", "canceled", "finished", "ended"}
        ),
        None,
    )
    if event is None:
        event = next((item for item in events if isinstance(item, dict) and item.get("id") is not None), None)
    event_id = str(event["id"]) if isinstance(event, dict) and event.get("id") is not None else None
    row["selected_event"] = {
        key: event.get(key)
        for key in ("id", "home", "away", "date", "status", "sport", "league")
    } if isinstance(event, dict) else None
    row["probe_bookmakers"] = bookmakers
    if not event_id:
        row["probe_status"] = "live_checked_no_events" if status and 200 <= status < 300 else "provider_error"
        row["market_verdict"] = {
            "one_x_two": "not_observed",
            "over_under": "not_observed",
            "asian_handicap": "not_observed",
            "world_cup_2026": "unknown",
        }
        return row
    odds_url = (
        "https://api.odds-api.io/v3/odds?apiKey="
        + key
        + "&eventId="
        + event_id
        + "&bookmakers="
        + ",".join(str(bookmaker) for bookmaker in bookmakers)
    )
    status, payload, error = fetch_json(odds_url)
    row["odds_probe"] = {
        "http_status": status,
        "error": error,
        "observed": summarize_odds_api_io_event(payload),
    }
    observed = row["odds_probe"]["observed"]
    row["market_verdict"] = {
        "one_x_two": "observed" if observed.get("has_1x2") else "not_observed",
        "over_under": "observed" if observed.get("has_over_under") else "not_observed",
        "asian_handicap": "observed" if observed.get("has_asian_handicap") else "not_observed",
        "world_cup_2026": "unknown",
    }
    row["probe_status"] = "live_checked" if status and 200 <= status < 300 else "provider_error"
    return row


def probe_sharpapi(provider: dict, *, live: bool) -> dict:
    key = load_env_value(str(provider.get("auth_env") or ""))
    row = base_probe_row(provider, live=live)
    row["probe_status"] = "skipped_missing_key" if live and not key else "metadata_only"
    row["live_probe_enabled"] = bool(live and key)
    row["production_classification"] = provider.get("probe_classification")
    row["market_verdict"] = {
        "one_x_two": "claimed",
        "over_under": "claimed",
        "asian_handicap": "claimed",
        "world_cup_2026": "unknown",
    }
    if not live or not key:
        return row

    row["probe_status"] = "manual_endpoint_required"
    row["error"] = "SharpAPI endpoint path/auth header must be confirmed from account docs before live probing."
    return row


def probe_bsd(provider: dict, *, live: bool) -> dict:
    token = load_env_value(str(provider.get("auth_env") or ""))
    row = base_probe_row(provider, live=live)
    row["probe_status"] = "skipped_missing_key" if live and not token else "metadata_only"
    row["live_probe_enabled"] = bool(live and token)
    row["production_classification"] = provider.get("probe_classification")
    row["market_verdict"] = {
        "one_x_two": "claimed",
        "over_under": "claimed",
        "asian_handicap": "not_documented",
        "world_cup_2026": "claimed",
    }
    row["confirmed_public_docs"] = {
        "base_url": "https://sports.bzzoiro.com/api/",
        "auth": "Authorization: Token <token>",
        "odds_endpoints": [
            "/api/v2/odds/",
            "/api/v2/events/{id}/odds/",
            "/api/v2/events/{id}/odds/comparison/",
            "/api/v2/bookmakers/",
        ],
        "consensus_markets": ["1x2", "over_1.5", "over_2.5", "over_3.5", "under_1.5", "under_2.5", "under_3.5", "btts"],
        "multi_bookmaker_claim": "~15 books according to public v2 docs",
        "asian_handicap": "not documented in public v2 odds consensus docs",
        "world_cup_hint": "public docs use league_id=16 and season_id=82 in World Cup venue examples; live probe verifies these ids separately",
    }
    row["next_probe_required"] = "Run --live with BSD_API_TOKEN, verify league_id=16&season_id=82 events and odds rows, then confirm terms before adapter promotion."
    if not live or not token:
        return row

    headers = {"Authorization": f"Token {token}"}
    status, payload, error = fetch_json("https://sports.bzzoiro.com/api/v2/bookmakers/", headers=headers)
    row["bookmakers_probe"] = summarize_bsd_list_payload(status, payload, error)
    status, payload, error = fetch_json("https://sports.bzzoiro.com/api/v2/odds/?limit=20", headers=headers)
    row["odds_probe"] = summarize_bsd_list_payload(status, payload, error)
    status, payload, error = fetch_json("https://sports.bzzoiro.com/api/v2/events/?league_id=16&season_id=82&limit=20", headers=headers)
    row["world_cup_events_probe"] = summarize_bsd_list_payload(status, payload, error)
    status, payload, error = fetch_json("https://sports.bzzoiro.com/api/v2/odds/?league_id=16&season_id=82&limit=20", headers=headers)
    row["world_cup_odds_probe"] = summarize_bsd_list_payload(status, payload, error)
    promotion_blockers = []
    if row["world_cup_events_probe"]["row_count_sample"] == 0:
        promotion_blockers.append("world_cup_events_not_found_for_league_16_season_82")
    if row["world_cup_odds_probe"]["row_count_sample"] == 0:
        promotion_blockers.append("world_cup_odds_not_found_for_league_16_season_82")
    if not row["odds_probe"]["market_keys_sample"]:
        promotion_blockers.append("market_keys_not_observed")
    if not any(str(market).startswith("over_under") for market in row["odds_probe"]["market_keys_sample"]):
        promotion_blockers.append("over_under_not_observed")
    if "1x2" not in row["odds_probe"]["market_keys_sample"]:
        promotion_blockers.append("one_x_two_not_observed")
    promotion_blockers.append("asian_handicap_not_documented")
    row["promotion_blockers"] = promotion_blockers
    row["market_verdict"] = {
        "one_x_two": "observed" if "1x2" in row["odds_probe"]["market_keys_sample"] else "not_observed",
        "over_under": "observed" if any(str(market).startswith("over_under") for market in row["odds_probe"]["market_keys_sample"]) else "not_observed",
        "asian_handicap": "not_documented",
        "world_cup_2026": "not_observed_in_live_probe" if row["world_cup_events_probe"]["row_count_sample"] == 0 and row["world_cup_odds_probe"]["row_count_sample"] == 0 else "observed",
    }
    row["probe_status"] = "live_checked" if any(
        probe.get("http_status") == 200
        for probe in (
            row["bookmakers_probe"],
            row["odds_probe"],
            row["world_cup_events_probe"],
            row["world_cup_odds_probe"],
        )
    ) else "provider_error"
    return row


def summarize_bsd_list_payload(status: int | None, payload: object | None, error: str | None) -> dict:
    results = payload.get("results") if isinstance(payload, dict) else payload if isinstance(payload, list) else []
    if not isinstance(results, list):
        results = []
    keys: set[str] = set()
    market_keys: set[str] = set()
    bookmaker_keys: set[str] = set()
    event_ids: list[object] = []
    league_ids: set[str] = set()
    season_ids: set[str] = set()
    for item in results[:20]:
        if not isinstance(item, dict):
            continue
        keys.update(str(key) for key in item.keys())
        if item.get("id") is not None:
            event_ids.append(item.get("id"))
        for key in ("market", "market_key", "market_type"):
            if item.get(key):
                market_keys.add(str(item[key]))
        for key in ("bookmaker", "bookmaker_slug", "bookmaker_key"):
            if item.get(key):
                bookmaker_keys.add(str(item[key]))
        for key in ("league_id", "league"):
            if item.get(key) is not None:
                league_ids.add(str(item[key]))
        for key in ("season_id", "season"):
            if item.get(key) is not None:
                season_ids.add(str(item[key]))
    return {
        "http_status": status,
        "error": error,
        "row_count_sample": len(results),
        "top_level_keys_sample": sorted(keys)[:30],
        "market_keys_sample": sorted(market_keys)[:20],
        "bookmaker_keys_sample": sorted(bookmaker_keys)[:20],
        "event_ids_sample": event_ids[:10],
        "league_ids_sample": sorted(league_ids)[:10],
        "season_ids_sample": sorted(season_ids)[:10],
    }


def base_probe_row(provider: dict, *, live: bool) -> dict:
    return {
        "provider": provider.get("provider"),
        "display_name": provider.get("display_name"),
        "category": provider.get("category"),
        "probe_classification": provider.get("probe_classification"),
        "live_requested": live,
        "homepage": provider.get("homepage"),
        "docs_url": provider.get("docs_url"),
        "auth_env": provider.get("auth_env"),
        "free_tier": provider.get("free_tier"),
        "soccer_coverage_claim": provider.get("soccer_coverage_claim"),
        "markets_claimed": provider.get("markets_claimed") or [],
        "markets_unknown": provider.get("markets_unknown") or [],
        "production_gate": provider.get("production_gate"),
    }


def probe_provider(provider: dict, *, live: bool) -> dict:
    provider_key = provider.get("provider")
    if provider_key == "odds_api_io":
        return probe_odds_api_io(provider, live=live)
    if provider_key == "sharpapi_soccer":
        return probe_sharpapi(provider, live=live)
    if provider_key == "bsd_bzzoiro":
        return probe_bsd(provider, live=live)
    row = base_probe_row(provider, live=live)
    row["probe_status"] = "policy_only"
    row["production_classification"] = provider.get("probe_classification")
    row["market_verdict"] = {
        "one_x_two": "unknown",
        "over_under": "unknown",
        "asian_handicap": "unknown",
        "world_cup_2026": "unknown",
    }
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe free or open football odds source feasibility.")
    parser.add_argument("--live", action="store_true", help="attempt live API probes when the required env key exists")
    parser.add_argument("--output", default=str(REPORT_PATH), help="probe report output path")
    args = parser.parse_args()

    config = load_json(CONFIG_PATH)
    if not isinstance(config, dict):
        raise TypeError("free odds probe config must be an object")
    providers = [row for row in config.get("providers") or [] if isinstance(row, dict)]
    rows = [probe_provider(provider, live=args.live) for provider in providers]

    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("probe_classification") or "unknown")
        counts[key] = counts.get(key, 0) + 1

    report = {
        "generated_at": utc_now(),
        "scope": "free_or_open_football_odds_sources",
        "live": args.live,
        "policy": config.get("policy") or {},
        "summary": {
            "provider_count": len(rows),
            "classification_counts": dict(sorted(counts.items())),
            "production_write_allowed": False,
            "normalized_write_allowed": False,
        },
        "providers": rows,
        "recommended_next_steps": [
            "Keep all scraper/reverse-engineered sources experimental only.",
            "Get BSD_API_TOKEN and run scripts/probe_free_odds_sources.py --live to verify World Cup/international events and bookmaker-level 1X2/OU rows.",
            "Confirm BSD terms before treating it as a production candidate; AH is not documented in the public v2 odds consensus docs.",
            "Confirm SharpAPI account endpoint path before live probing; public page claims AH/OU but World Cup coverage is still unknown.",
            "Use Odds-API.io and SharpAPI only as probe-only until live checks confirm World Cup/international football, bookmaker detail, and AH/OU line structure.",
            "Do not write probe rows into data/normalized or data/model.",
        ],
    }
    write_json(Path(args.output), report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
