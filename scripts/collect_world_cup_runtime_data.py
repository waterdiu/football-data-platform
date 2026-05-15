from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from sources.openweather import fetch_openweather_payload, normalize_openweather_snapshot
from sources.the_odds_api import fetch_odds_events, normalize_odds_events

FIXTURES_PATH = ROOT / "data" / "public" / "fixtures.json"
TEAMS_PATH = ROOT / "data" / "public" / "teams.json"
VENUES_PATH = ROOT / "configs" / "venues" / "world_cup_2026.json"
NORMALIZED_DIR = ROOT / "data" / "normalized"
REPORT_PATH = ROOT / "reports" / "world_cup_runtime_collection_report.json"

WEATHER_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_model_weather_master.json"
ODDS_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_model_odds_master.json"
LINEUPS_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_model_lineups_master.json"
INJURIES_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_model_injuries_master.json"
PREMATCH_CONTEXT_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_model_prematch_context_master.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def collect_weather(*, fixtures: list[dict], venues: dict[str, dict], fetched_at: str, dry_run: bool) -> dict:
    api_key = os.environ.get("OPENWEATHER_API_KEY", "").strip()
    if not api_key:
        return {
            "dataset": "weather",
            "status": "missing_auth",
            "auth_env": "OPENWEATHER_API_KEY",
            "fixtures_considered": len(fixtures),
            "rows_collected": 0,
        }

    rows: list[dict] = []
    skipped: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
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
        try:
            payload = fetch_openweather_payload(latitude=float(latitude), longitude=float(longitude), api_key=api_key)
        except Exception as exc:  # noqa: BLE001 - collection reports per-fixture provider failures.
            errors.append({"match_id": str(fixture.get("match_id") or ""), "error": str(exc)})
            continue
        if payload is None:
            skipped.append({"match_id": str(fixture.get("match_id") or ""), "reason": "empty_provider_payload"})
            continue
        rows.append(normalize_openweather_snapshot(fixture=fixture, venue=venue, payload=payload, fetched_at=fetched_at))

    if rows and not dry_run:
        existing = load_existing_list(WEATHER_MASTER_PATH)
        write_json(WEATHER_MASTER_PATH, merge_by_match_id(existing, rows))

    return {
        "dataset": "weather",
        "status": "collected" if rows else "no_rows",
        "fixtures_considered": len(fixtures),
        "rows_collected": len(rows),
        "skipped": skipped,
        "errors": errors,
        "output": str(WEATHER_MASTER_PATH) if rows else None,
    }


def collect_odds(*, fixtures: list[dict], teams: list[dict], fetched_at: str, dry_run: bool) -> dict:
    api_key = os.environ.get("THE_ODDS_API_KEY", "").strip()
    sport_key = os.environ.get("THE_ODDS_API_SPORT", "soccer_fifa_world_cup")
    if not api_key:
        return {
            "dataset": "odds",
            "status": "missing_auth",
            "auth_env": "THE_ODDS_API_KEY",
            "sport_key": sport_key,
            "fixtures_considered": len(fixtures),
            "rows_collected": 0,
        }

    try:
        events = fetch_odds_events(sport_key=sport_key, api_key=api_key)
    except Exception as exc:  # noqa: BLE001 - collection reports provider failures.
        return {
            "dataset": "odds",
            "status": "provider_error",
            "auth_env": "THE_ODDS_API_KEY",
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
        "status": "collected" if rows else "no_rows",
        "sport_key": sport_key,
        "fixtures_considered": len(fixtures),
        "provider_events": len(events),
        "rows_collected": len(rows),
        "unmatched_events_count": len(unmatched),
        "unmatched_events": unmatched[:20],
        "output": str(ODDS_MASTER_PATH) if rows else None,
    }


def pending_dataset(name: str, path: Path, reason: str, auth_env: str | None = None) -> dict:
    payload = {
        "dataset": name,
        "status": "pending_adapter",
        "rows_existing": len(load_existing_list(path)),
        "reason": reason,
        "output": str(path),
    }
    if auth_env:
        payload["auth_env"] = auth_env
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect World Cup runtime data in football-data-platform.")
    parser.add_argument("--window-hours", type=int, default=None, help="only collect fixtures within this UTC window")
    parser.add_argument("--limit", type=int, default=None, help="limit selected fixtures")
    parser.add_argument("--dry-run", action="store_true", help="collect and report without writing dataset masters")
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
    datasets = [
        collect_odds(fixtures=selected, teams=teams, fetched_at=fetched_at, dry_run=args.dry_run),
        collect_weather(fixtures=selected, venues=venues, fetched_at=fetched_at, dry_run=args.dry_run),
        pending_dataset("lineups", LINEUPS_MASTER_PATH, "platform lineup adapter not migrated yet", "API_FOOTBALL_KEY"),
        pending_dataset("injuries", INJURIES_MASTER_PATH, "platform injury adapter not migrated yet", "API_FOOTBALL_KEY"),
        pending_dataset("prematch_context", PREMATCH_CONTEXT_MASTER_PATH, "platform news/context adapter not migrated yet"),
    ]
    report = {
        "generated_at": fetched_at,
        "dry_run": args.dry_run,
        "fixtures_total": len(fixtures),
        "fixtures_selected": len(selected),
        "window_hours": args.window_hours,
        "limit": args.limit,
        "datasets": datasets,
    }
    write_json(REPORT_PATH, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
