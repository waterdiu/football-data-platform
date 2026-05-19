from __future__ import annotations

import argparse
import json
import os
import ssl
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from json_io import write_json

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "experimental" / "odds-api-io"
REPORT_PATH = ROOT / "reports" / "odds_api_io_sampling_report.json"
SCAN_REPORT_PATH = ROOT / "reports" / "odds_api_io_event_scan_report.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def fetch_json(url: str, *, timeout: int = 20) -> tuple[int | None, object | None, str | None]:
    context = ssl.create_default_context(cafile=certifi.where() if certifi else None)
    request = Request(url)
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


def api_url(path: str, params: dict[str, str | int]) -> str:
    return f"https://api.odds-api.io/v3/{path}?{urlencode(params)}"


def event_summary(event: dict) -> dict:
    return {
        "event_id": event.get("id"),
        "home": event.get("home"),
        "away": event.get("away"),
        "kickoff_at": event.get("date"),
        "status": event.get("status"),
        "sport": (event.get("sport") or {}).get("slug") if isinstance(event.get("sport"), dict) else event.get("sport"),
        "league": (event.get("league") or {}).get("name") if isinstance(event.get("league"), dict) else event.get("league"),
        "league_slug": (event.get("league") or {}).get("slug") if isinstance(event.get("league"), dict) else None,
    }


def normalize_market_name(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def classify_market(name: str) -> str | None:
    normalized = normalize_market_name(name)
    if normalized in {"spread", "alternative_asian_handicap"}:
        return "asian_handicap"
    if normalized in {"totals", "goals_over/under", "alternative_goal_line"}:
        return "over_under"
    if normalized == "ml":
        return "one_x_two"
    return None


def normalize_odds_rows(event: dict, payload: object, *, captured_at: str) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    rows: list[dict] = []
    bookmakers = payload.get("bookmakers") if isinstance(payload.get("bookmakers"), dict) else {}
    for bookmaker, markets in bookmakers.items():
        if not isinstance(markets, list):
            continue
        for market in markets:
            if not isinstance(market, dict):
                continue
            market_name = str(market.get("name") or "")
            market_type = classify_market(market_name)
            if not market_type:
                continue
            updated_at = market.get("updatedAt")
            odds_items = market.get("odds") if isinstance(market.get("odds"), list) else []
            for item in odds_items:
                if not isinstance(item, dict):
                    continue
                base = {
                    **event_summary(event),
                    "provider": "odds_api_io",
                    "bookmaker": bookmaker,
                    "market": market_type,
                    "source_market_name": market_name,
                    "captured_at": captured_at,
                    "updated_at": updated_at,
                    "source_confidence": "experimental_low",
                    "production_allowed": False,
                }
                if market_type == "asian_handicap":
                    rows.append(
                        {
                            **base,
                            "line": item.get("hdp"),
                            "home_odds": item.get("home"),
                            "away_odds": item.get("away"),
                        }
                    )
                elif market_type == "over_under":
                    rows.append(
                        {
                            **base,
                            "line": item.get("hdp"),
                            "over_odds": item.get("over"),
                            "under_odds": item.get("under"),
                        }
                    )
                elif market_type == "one_x_two":
                    rows.append(
                        {
                            **base,
                            "home_odds": item.get("home"),
                            "draw_odds": item.get("draw"),
                            "away_odds": item.get("away"),
                        }
                    )
    return rows


def sample_events(*, key: str, bookmaker: str, limit: int, skip: int = 0) -> tuple[list[dict], dict]:
    url = api_url(
        "events",
        {
            "apiKey": key,
            "sport": "football",
            "status": "pending,live",
            "bookmaker": bookmaker,
            "limit": limit,
            "skip": skip,
        },
    )
    status, payload, error = fetch_json(url)
    events = payload if isinstance(payload, list) else []
    return events[:limit], {"http_status": status, "error": error, "event_count": len(events), "skip": skip, "limit": limit}


def scan_event_pages(*, key: str, bookmaker: str, page_size: int, pages: int) -> tuple[list[dict], list[dict]]:
    events: list[dict] = []
    probes: list[dict] = []
    seen_ids: set[str] = set()
    for page in range(max(0, pages)):
        skip = page * page_size
        page_events, probe = sample_events(key=key, bookmaker=bookmaker, limit=page_size, skip=skip)
        probe["page"] = page
        probes.append(probe)
        for event in page_events:
            if not isinstance(event, dict) or event.get("id") is None:
                continue
            event_id = str(event["id"])
            if event_id in seen_ids:
                continue
            seen_ids.add(event_id)
            events.append(event)
        if probe.get("http_status") and probe.get("http_status") != 200:
            break
        if len(page_events) < page_size:
            break
    return events, probes


def sample_odds_for_events(*, key: str, events: list[dict], bookmakers: list[str], captured_at: str) -> tuple[list[dict], list[dict]]:
    raw_events: list[dict] = []
    normalized_rows: list[dict] = []
    for event in events:
        if not isinstance(event, dict) or event.get("id") is None:
            continue
        params = {
            "apiKey": key,
            "eventId": str(event["id"]),
            "bookmakers": ",".join(bookmakers),
        }
        status, payload, error = fetch_json(api_url("odds", params))
        raw_events.append(
            {
                "event": event_summary(event),
                "http_status": status,
                "error": error,
                "payload": payload if status and 200 <= status < 300 else None,
            }
        )
        if status and 200 <= status < 300:
            normalized_rows.extend(normalize_odds_rows(event, payload, captured_at=captured_at))
    return raw_events, normalized_rows


def build_report(*, captured_at: str, events_probe: dict, raw_events: list[dict], normalized_rows: list[dict], bookmakers: list[str]) -> dict:
    markets: dict[str, int] = {}
    bookmaker_counts: dict[str, int] = {}
    leagues: dict[str, int] = {}
    for row in normalized_rows:
        markets[str(row["market"])] = markets.get(str(row["market"]), 0) + 1
        bookmaker_counts[str(row["bookmaker"])] = bookmaker_counts.get(str(row["bookmaker"]), 0) + 1
        league = str(row.get("league") or "unknown")
        leagues[league] = leagues.get(league, 0) + 1
    rows_by_event: dict[str, int] = {}
    for row in normalized_rows:
        event_id = str(row.get("event_id"))
        rows_by_event[event_id] = rows_by_event.get(event_id, 0) + 1
    return {
        "generated_at": captured_at,
        "provider": "odds_api_io",
        "mode": "experimental_sampling_only",
        "production_write_allowed": False,
        "normalized_write_allowed": False,
        "selected_bookmakers": bookmakers,
        "events_probe": events_probe,
        "sampled_event_count": len(raw_events),
        "normalized_row_count": len(normalized_rows),
        "market_row_counts": markets,
        "bookmaker_row_counts": bookmaker_counts,
        "league_row_counts": leagues,
        "rows_by_event": rows_by_event,
        "schema_mapping": {
            "ML": "one_x_two",
            "Spread": "asian_handicap",
            "Alternative Asian Handicap": "asian_handicap",
            "Totals": "over_under",
            "Goals Over/Under": "over_under",
            "Alternative Goal Line": "over_under",
        },
        "remaining_gates": [
            "verify_world_cup_2026_or_senior_international_coverage",
            "run_repeated_sampling_to_confirm_field_stability",
            "confirm_free_tier_selected_bookmaker_persistence",
            "do_not_use_for_market_consensus_or_clv_with_only_two_bookmakers",
        ],
        "events": [
            {
                "event": raw.get("event"),
                "http_status": raw.get("http_status"),
                "error": raw.get("error"),
                "normalized_rows": rows_by_event.get(str((raw.get("event") or {}).get("event_id")), 0),
            }
            for raw in raw_events
        ],
    }


def build_event_scan(
    events: list[dict],
    *,
    captured_at: str,
    bookmaker: str,
    requested_limit: int,
    events_probe: dict | None = None,
    events_probes: list[dict] | None = None,
    pages: int | None = None,
) -> dict:
    league_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    world_cup_candidates: list[dict] = []
    senior_international_candidates: list[dict] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        summary = event_summary(event)
        league = str(summary.get("league") or "unknown")
        league_slug = str(summary.get("league_slug") or "")
        status = str(summary.get("status") or "unknown")
        league_counts[league] = league_counts.get(league, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
        haystack = " ".join(
            str(value or "")
            for value in (
                summary.get("home"),
                summary.get("away"),
                summary.get("league"),
                summary.get("league_slug"),
            )
        ).lower()
        if "world cup" in haystack or "fifa" in haystack:
            world_cup_candidates.append(summary)
        if (
            "international" in league_slug
            and "youth" not in league_slug
            and "clubs" not in league_slug
            and "u20" not in league_slug
            and "u21" not in league_slug
            and "u23" not in league_slug
        ):
            senior_international_candidates.append(summary)
    return {
        "generated_at": captured_at,
        "provider": "odds_api_io",
        "mode": "event_scan_only",
        "production_write_allowed": False,
        "normalized_write_allowed": False,
        "bookmaker_filter": bookmaker,
        "requested_limit": requested_limit,
        "requested_pages": pages,
        "events_probe": events_probe,
        "events_probes": events_probes or [],
        "event_count": len(events),
        "league_counts": league_counts,
        "status_counts": status_counts,
        "has_world_cup_candidate": bool(world_cup_candidates),
        "world_cup_candidates": world_cup_candidates,
        "has_senior_international_candidate": bool(senior_international_candidates),
        "senior_international_candidates": senior_international_candidates,
        "conclusion": (
            "world_cup_or_senior_international_observed"
            if world_cup_candidates or senior_international_candidates
            else "no_world_cup_or_senior_international_in_current_event_scan"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample Odds-API.io AH/OU odds into raw experimental storage.")
    parser.add_argument("--limit", type=int, default=5, help="Number of football events to sample.")
    parser.add_argument("--pages", type=int, default=1, help="Number of event pages to scan when --scan-events is enabled.")
    parser.add_argument("--page-size", type=int, default=None, help="Event page size for --scan-events; defaults to --limit.")
    parser.add_argument("--bookmakers", default="Sbobet,Bet365", help="Comma-separated bookmaker names.")
    parser.add_argument("--scan-events", action="store_true", help="Only scan event coverage; do not fetch event odds.")
    parser.add_argument("--output-report", default=None)
    parser.add_argument("--raw-dir", default=str(RAW_DIR))
    args = parser.parse_args()

    key = load_env_value("ODDS_API_IO_KEY")
    captured_at = utc_now()
    report_path = Path(args.output_report) if args.output_report else (SCAN_REPORT_PATH if args.scan_events else REPORT_PATH)
    raw_dir = Path(args.raw_dir)
    bookmakers = [item.strip() for item in args.bookmakers.split(",") if item.strip()]
    if not key:
        write_json(
            report_path,
            {
                "generated_at": captured_at,
                "provider": "odds_api_io",
                "mode": "experimental_sampling_only",
                "probe_status": "skipped_missing_key",
                "required_env": "ODDS_API_IO_KEY",
                "production_write_allowed": False,
                "normalized_write_allowed": False,
            },
        )
        print(json.dumps({"probe_status": "skipped_missing_key", "report": str(report_path)}, ensure_ascii=False, indent=2))
        return

    if args.scan_events:
        page_size = args.page_size or args.limit
        events, events_probes = scan_event_pages(key=key, bookmaker=bookmakers[0], page_size=page_size, pages=args.pages)
        report = build_event_scan(
            events,
            captured_at=captured_at,
            bookmaker=bookmakers[0],
            requested_limit=page_size,
            events_probe=events_probes[0] if events_probes else None,
            events_probes=events_probes,
            pages=args.pages,
        )
        write_json(report_path, report)
        print(
            json.dumps(
                {
                    "probe_status": "event_scan_complete",
                    "event_count": len(events),
                    "has_world_cup_candidate": report["has_world_cup_candidate"],
                    "has_senior_international_candidate": report["has_senior_international_candidate"],
                    "report": str(report_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    events, events_probe = sample_events(key=key, bookmaker=bookmakers[0], limit=args.limit)
    raw_events, normalized_rows = sample_odds_for_events(key=key, events=events, bookmakers=bookmakers, captured_at=captured_at)
    stamp = captured_at.replace(":", "").replace("+", "Z")
    write_json(raw_dir / f"odds-api-io-{stamp}.raw.json", {"captured_at": captured_at, "events": raw_events})
    write_json(raw_dir / f"odds-api-io-{stamp}.mapped.json", {"captured_at": captured_at, "rows": normalized_rows})
    report = build_report(
        captured_at=captured_at,
        events_probe=events_probe,
        raw_events=raw_events,
        normalized_rows=normalized_rows,
        bookmakers=bookmakers,
    )
    write_json(report_path, report)
    print(
        json.dumps(
            {
                "probe_status": "sampled",
                "sampled_event_count": len(raw_events),
                "normalized_row_count": len(normalized_rows),
                "market_row_counts": report["market_row_counts"],
                "report": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
