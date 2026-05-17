from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from sources.open_meteo import FORECAST_HORIZON_DAYS, fetch_open_meteo_payload, normalize_open_meteo_snapshot
from sources.openweather import fetch_openweather_payload, normalize_openweather_snapshot
from sources.api_football import collect_api_football_context
from sources.prematch_news import collect_prematch_context
from sources.the_odds_api import fetch_odds_events, normalize_odds_events

FIXTURES_PATH = ROOT / "data" / "public" / "fixtures.json"
TEAMS_PATH = ROOT / "data" / "public" / "teams.json"
VENUES_PATH = ROOT / "configs" / "venues" / "world_cup_2026.json"
THE_ODDS_API_CONFIG_PATH = ROOT / "configs" / "providers" / "the_odds_api.json"
NORMALIZED_DIR = ROOT / "data" / "normalized"
RUNTIME_DIR = ROOT / "data" / "runtime"
REPORT_PATH = ROOT / "reports" / "world_cup_runtime_collection_report.json"

WEATHER_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_model_weather_master.json"
ODDS_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_model_odds_master.json"
LINEUPS_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_model_lineups_master.json"
INJURIES_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_model_injuries_master.json"
PREMATCH_CONTEXT_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_model_prematch_context_master.json"


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


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def selected_fixtures(fixtures: list[dict], *, window_hours: int | None, limit: int | None) -> list[dict]:
    rows = list(fixtures)
    if window_hours is not None:
        start = now_utc()
        end = start + timedelta(hours=window_hours)
        rows = [
            fixture for fixture in rows
            if (kickoff := parse_datetime(str(fixture.get("date_utc") or ""))) is not None and start <= kickoff <= end
        ]
    if limit is not None:
        rows = rows[: max(0, limit)]
    return rows


def merge_by_match_id(existing: list[dict], updates: list[dict]) -> list[dict]:
    merged = {str(item.get("match_id") or ""): item for item in existing if isinstance(item, dict)}
    for item in updates:
        match_id = str(item.get("match_id") or "")
        if match_id:
            merged[match_id] = item
    return [merged[key] for key in sorted(merged)]


def load_existing_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = load_json(path)
    return payload if isinstance(payload, list) else []


def weather_placeholder(
    *,
    fixture: dict,
    venue: dict,
    fetched_at: str,
    source_status: str,
    status_reason: str,
) -> dict:
    return {
        "match_id": str(fixture.get("match_id") or ""),
        "source": "platform_weather_window",
        "confidence": "low",
        "source_status": source_status,
        "status_reason": status_reason,
        "fetched_at": fetched_at,
        "valid_at": fixture.get("date_utc"),
        "normalized": {
            "venue_id": str(venue.get("venue_id") or fixture.get("venue_id") or ""),
            "venue_name": str(venue.get("name") or fixture.get("venue_name") or ""),
            "city": str(venue.get("city") or fixture.get("host_city") or ""),
            "latitude": venue.get("latitude"),
            "longitude": venue.get("longitude"),
            "condition": "unknown",
            "description": None,
            "temperature_c": None,
            "humidity_percent": None,
            "wind_speed_mps": None,
            "wind_degrees": None,
            "rain_1h_mm": None,
            "cloud_cover_percent": None,
            "risk_flags": [],
        },
        "raw": None,
    }


def weather_window_status(fixture: dict, fetched_at: str) -> str | None:
    kickoff = parse_datetime(str(fixture.get("date_utc") or ""))
    fetched = parse_datetime(fetched_at)
    if kickoff is None or fetched is None:
        return "missing_kickoff_at"
    if kickoff < fetched:
        return "past_kickoff"
    if kickoff > fetched + timedelta(days=FORECAST_HORIZON_DAYS):
        return "outside_forecast_window"
    return None


def collect_weather(*, fixtures: list[dict], venues: dict[str, dict], fetched_at: str, dry_run: bool) -> dict:
    api_key = load_env_value("OPENWEATHER_API_KEY")
    rows: list[dict] = []
    skipped: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    provider_counts = {"openweather": 0, "open_meteo": 0}
    for fixture in fixtures:
        venue_id = str(fixture.get("venue_id") or "")
        venue = venues.get(venue_id)
        if not venue:
            skipped.append({"match_id": str(fixture.get("match_id") or ""), "reason": "missing_venue"})
            continue
        latitude = venue.get("latitude")
        longitude = venue.get("longitude")
        if latitude is None or longitude is None:
            skipped.append({"match_id": str(fixture.get("match_id") or ""), "reason": "missing_coordinates"})
            continue

        forecast_window_reason = weather_window_status(fixture, fetched_at)
        if forecast_window_reason:
            rows.append(
                weather_placeholder(
                    fixture=fixture,
                    venue=venue,
                    fetched_at=fetched_at,
                    source_status="unavailable",
                    status_reason=forecast_window_reason,
                )
            )
            skipped.append({"match_id": str(fixture.get("match_id") or ""), "reason": forecast_window_reason})
            continue

        row: dict | None = None
        if api_key:
            try:
                payload = fetch_openweather_payload(latitude=float(latitude), longitude=float(longitude), api_key=api_key)
            except Exception as exc:  # noqa: BLE001 - collection reports per-fixture provider failures.
                errors.append({"match_id": str(fixture.get("match_id") or ""), "provider": "openweather", "error": str(exc)})
            else:
                if payload is not None:
                    row = normalize_openweather_snapshot(fixture=fixture, venue=venue, payload=payload, fetched_at=fetched_at)
                    provider_counts["openweather"] += 1

        if row is None:
            try:
                payload = fetch_open_meteo_payload(latitude=float(latitude), longitude=float(longitude))
                row = normalize_open_meteo_snapshot(fixture=fixture, venue=venue, payload=payload, fetched_at=fetched_at)
            except Exception as exc:  # noqa: BLE001 - collection reports per-fixture provider failures.
                errors.append({"match_id": str(fixture.get("match_id") or ""), "provider": "open_meteo", "error": str(exc)})

        if row is None:
            rows.append(
                weather_placeholder(
                    fixture=fixture,
                    venue=venue,
                    fetched_at=fetched_at,
                    source_status="provider_empty",
                    status_reason="empty_provider_payload",
                )
            )
            skipped.append({"match_id": str(fixture.get("match_id") or ""), "reason": "empty_provider_payload"})
            continue

        rows.append(row)
        if row.get("source") == "open_meteo":
            provider_counts["open_meteo"] += 1

    if rows and not dry_run:
        existing = load_existing_list(WEATHER_MASTER_PATH)
        write_json(WEATHER_MASTER_PATH, merge_by_match_id(existing, rows))

    return {
        "dataset": "weather",
        "status": "collected" if rows else "no_rows",
        "auth_env": "OPENWEATHER_API_KEY",
        "fallback_provider": "open_meteo",
        "fixtures_considered": len(fixtures),
        "rows_collected": len(rows),
        "provider_counts": provider_counts,
        "skipped": skipped,
        "errors": errors,
        "output": rel(WEATHER_MASTER_PATH) if rows else None,
    }


def collect_odds(*, fixtures: list[dict], teams: list[dict], fetched_at: str, dry_run: bool) -> dict:
    provider_config = load_json(THE_ODDS_API_CONFIG_PATH)
    provider_config = provider_config if isinstance(provider_config, dict) else {}
    soccer_access = provider_config.get("soccer_access") if isinstance(provider_config.get("soccer_access"), dict) else {}
    enabled_env = str(provider_config.get("production_enabled_env") or "THE_ODDS_API_SOCCER_ENABLED")
    soccer_enabled = load_env_value(enabled_env).lower() in {"1", "true", "yes", "enabled"}
    api_key = load_env_value("THE_ODDS_API_KEY")
    sport_key = load_env_value("THE_ODDS_API_SPORT") or "soccer_fifa_world_cup"
    if not soccer_enabled:
        return {
            "dataset": "odds",
            "provider": "the_odds_api",
            "status": "paid_plan_required",
            "status_reason": "TheOddsAPI free tier covers NBA and MLB only; soccer requires a paid Business plan.",
            "auth_env": "THE_ODDS_API_KEY",
            "production_enabled_env": enabled_env,
            "required_plan": soccer_access.get("required_plan") or "business",
            "free_tier_available_for_soccer": bool(soccer_access.get("free_tier_available")),
            "free_tier_supported_sports": soccer_access.get("free_tier_supported_sports") or [],
            "sport_key": sport_key,
            "fixtures_considered": len(fixtures),
            "rows_collected": 0,
        }
    if not api_key:
        return {
            "dataset": "odds",
            "provider": "the_odds_api",
            "status": "missing_auth",
            "auth_env": "THE_ODDS_API_KEY",
            "production_enabled_env": enabled_env,
            "sport_key": sport_key,
            "fixtures_considered": len(fixtures),
            "rows_collected": 0,
        }

    try:
        events = fetch_odds_events(sport_key=sport_key, api_key=api_key)
    except Exception as exc:  # noqa: BLE001 - collection reports provider failures.
        return {
            "dataset": "odds",
            "provider": "the_odds_api",
            "status": "provider_error",
            "auth_env": "THE_ODDS_API_KEY",
            "production_enabled_env": enabled_env,
            "sport_key": sport_key,
            "fixtures_considered": len(fixtures),
            "rows_collected": 0,
            "error": str(exc),
        }

    rows, unmatched = normalize_odds_events(
        events=events,
        fixtures=fixtures,
        teams=teams,
        sport_key=sport_key,
        captured_at=fetched_at,
    )

    if rows and not dry_run:
        existing = load_existing_list(ODDS_MASTER_PATH)
        write_json(ODDS_MASTER_PATH, merge_by_match_id(existing, rows))

    return {
        "dataset": "odds",
        "provider": "the_odds_api",
        "status": "collected" if rows else "no_rows",
        "sport_key": sport_key,
        "fixtures_considered": len(fixtures),
        "provider_events": len(events),
        "rows_collected": len(rows),
        "unmatched_events_count": len(unmatched),
        "unmatched_events": unmatched[:20],
        "output": rel(ODDS_MASTER_PATH) if rows else None,
    }


def collect_api_football(*, fixtures: list[dict], teams: list[dict], fetched_at: str, dry_run: bool) -> list[dict]:
    fixture_map_path = RUNTIME_DIR / "api_football_fixture_map.json"
    injuries_rows, lineups_rows, report = collect_api_football_context(
        fixtures=fixtures,
        teams=teams,
        fetched_at=fetched_at,
        fixture_map_path=fixture_map_path,
        api_key=load_env_value("API_FOOTBALL_KEY"),
        league_id=load_env_value("API_FOOTBALL_LEAGUE_ID") or None,
        season=load_env_value("API_FOOTBALL_SEASON") or None,
    )
    if injuries_rows and not dry_run:
        existing = load_existing_list(INJURIES_MASTER_PATH)
        write_json(INJURIES_MASTER_PATH, merge_by_match_id(existing, injuries_rows))
    if lineups_rows and not dry_run:
        existing = load_existing_list(LINEUPS_MASTER_PATH)
        write_json(LINEUPS_MASTER_PATH, merge_by_match_id(existing, lineups_rows))
    return [
        {
            "dataset": "injuries",
            "provider": "api_football",
            "status": report["status"] if injuries_rows else report["status"],
            "status_reason": report.get("status_reason"),
            "auth_env": report.get("auth_env"),
            "league_id": report.get("league_id"),
            "season": report.get("season"),
            "fixtures_considered": report.get("fixtures_considered", len(fixtures)),
            "fixture_ids_discovered": report.get("fixture_ids_discovered", 0),
            "rows_collected": len(injuries_rows),
            "output": rel(INJURIES_MASTER_PATH) if injuries_rows else None,
            "skipped": report.get("skipped", []),
            "errors": report.get("errors", []),
        },
        {
            "dataset": "lineups",
            "provider": "api_football",
            "status": report["status"] if lineups_rows else report["status"],
            "status_reason": report.get("status_reason"),
            "auth_env": report.get("auth_env"),
            "league_id": report.get("league_id"),
            "season": report.get("season"),
            "fixtures_considered": report.get("fixtures_considered", len(fixtures)),
            "fixture_ids_discovered": report.get("fixture_ids_discovered", 0),
            "rows_collected": len(lineups_rows),
            "output": rel(LINEUPS_MASTER_PATH) if lineups_rows else None,
            "skipped": report.get("skipped", []),
            "errors": report.get("errors", []),
        },
    ]


def collect_prematch_news_context(*, fixtures: list[dict], teams: list[dict], fetched_at: str, dry_run: bool) -> dict:
    existing = load_existing_list(PREMATCH_CONTEXT_MASTER_PATH)
    try:
        rows, provider_report = collect_prematch_context(
            fixtures=fixtures,
            teams=teams,
            existing_context_rows=existing,
            fetched_at=fetched_at,
        )
    except Exception as exc:  # noqa: BLE001 - collection reports provider failures without breaking other datasets.
        return {
            "dataset": "prematch_context",
            "status": "provider_error",
            "fixtures_considered": len(fixtures),
            "rows_collected": 0,
            "rows_existing": len(existing),
            "error": str(exc),
            "output": rel(PREMATCH_CONTEXT_MASTER_PATH),
        }
    if rows and not dry_run:
        write_json(PREMATCH_CONTEXT_MASTER_PATH, merge_by_match_id(existing, rows))
    return {
        "dataset": "prematch_context",
        "status": provider_report.get("status", "no_rows"),
        "fixtures_considered": len(fixtures),
        "rows_collected": len(rows),
        "rows_existing": len(existing),
        "attempted_sources": provider_report.get("attempted_sources"),
        "successful_pages": provider_report.get("successful_pages"),
        "failed_sources": provider_report.get("failed_sources", []),
        "source_freshness": provider_report.get("source_freshness", []),
        "errors": provider_report.get("errors", []),
        "output": rel(PREMATCH_CONTEXT_MASTER_PATH) if rows else None,
    }


def pending_dataset(name: str, path: Path, reason: str, auth_env: str | None = None) -> dict:
    payload = {
        "dataset": name,
        "status": "pending_adapter",
        "rows_existing": len(load_existing_list(path)),
        "reason": reason,
        "output": rel(path),
    }
    if auth_env:
        payload["auth_env"] = auth_env
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect World Cup runtime data in football-data-platform.")
    parser.add_argument("--window-hours", type=int, default=None, help="only collect fixtures within this UTC window")
    parser.add_argument("--limit", type=int, default=None, help="limit selected fixtures")
    parser.add_argument("--dry-run", action="store_true", help="collect and report without writing dataset masters")
    parser.add_argument(
        "--only",
        choices=["all", "weather", "odds", "api_football", "prematch_context"],
        default="all",
        help="collect only one runtime dataset family",
    )
    args = parser.parse_args()

    fixtures = load_json(FIXTURES_PATH)
    teams = load_json(TEAMS_PATH)
    venues = load_json(VENUES_PATH)
    if not isinstance(fixtures, list):
        raise TypeError("fixtures.json must contain a list")
    if not isinstance(teams, list):
        raise TypeError("teams.json must contain a list")
    if not isinstance(venues, dict):
        raise TypeError("world_cup_2026 venues config must contain an object")

    selected = selected_fixtures(fixtures, window_hours=args.window_hours, limit=args.limit)
    fetched_at = now_utc().isoformat()
    datasets: list[dict] = []
    if args.only in {"all", "odds"}:
        datasets.append(collect_odds(fixtures=selected, teams=teams, fetched_at=fetched_at, dry_run=args.dry_run))
    if args.only in {"all", "weather"}:
        datasets.append(collect_weather(fixtures=selected, venues=venues, fetched_at=fetched_at, dry_run=args.dry_run))
    if args.only in {"all", "api_football"}:
        datasets.extend(collect_api_football(fixtures=selected, teams=teams, fetched_at=fetched_at, dry_run=args.dry_run))
    if args.only in {"all", "prematch_context"}:
        datasets.append(collect_prematch_news_context(fixtures=selected, teams=teams, fetched_at=fetched_at, dry_run=args.dry_run))
    report = {
        "generated_at": fetched_at,
        "dry_run": args.dry_run,
        "fixtures_total": len(fixtures),
        "fixtures_selected": len(selected),
        "window_hours": args.window_hours,
        "limit": args.limit,
        "only": args.only,
        "datasets": datasets,
    }
    write_json(REPORT_PATH, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
