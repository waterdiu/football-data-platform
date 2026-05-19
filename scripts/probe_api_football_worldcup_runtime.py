from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from json_io import write_json

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None

API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
REPORT_PATH = ROOT / "reports" / "api_football_worldcup_runtime_probe.json"


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


def classify_errors(errors: object) -> tuple[str, str | None]:
    if not errors:
        return "ok", None
    if isinstance(errors, dict):
        if errors.get("plan"):
            return "plan_restricted", str(errors["plan"])
        if errors.get("requests"):
            return "quota_exceeded", str(errors["requests"])
        if errors.get("token"):
            return "auth_error", str(errors["token"])
        return "provider_error", json.dumps(errors, ensure_ascii=False, sort_keys=True)
    if isinstance(errors, list) and errors:
        return "provider_error", json.dumps(errors, ensure_ascii=False)
    return "provider_error", str(errors)


def fetch_api_football(endpoint: str, *, api_key: str, params: dict[str, str], timeout: int = 25) -> dict:
    url = f"{API_FOOTBALL_BASE_URL}{endpoint}?{urlencode(params)}"
    request = Request(url, headers={"x-apisports-key": api_key})
    context = ssl.create_default_context(cafile=certifi.where() if certifi else None)
    with urlopen(request, timeout=timeout, context=context) as response:
        raw = response.read().decode("utf-8")
        payload = json.loads(raw)
    if isinstance(payload, dict):
        payload["_http_status"] = getattr(response, "status", None)
    return payload


def safe_fetch(endpoint: str, *, api_key: str, params: dict[str, str], attempts: int = 2) -> dict:
    started_at = utc_now()
    last_error: dict | None = None
    payload: dict | None = None
    for attempt in range(1, attempts + 1):
        try:
            payload = fetch_api_football(endpoint, api_key=api_key, params=params)
            break
        except HTTPError as error:
            last_error = {
                "endpoint": endpoint,
                "params": redact_params(params),
                "checked_at": started_at,
                "http_status": int(error.code),
                "status": "http_error",
                "status_reason": str(error),
                "attempts": attempt,
                "response_count": 0,
                "sample_keys": [],
            }
            break
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            last_error = {
                "endpoint": endpoint,
                "params": redact_params(params),
                "checked_at": started_at,
                "http_status": None,
                "status": "network_or_parse_error",
                "status_reason": str(error),
                "attempts": attempt,
                "response_count": 0,
                "sample_keys": [],
            }
    else:
        payload = None

    if payload is None:
        return last_error or {
            "endpoint": endpoint,
            "params": redact_params(params),
            "checked_at": started_at,
            "http_status": None,
            "status": "network_or_parse_error",
            "status_reason": "No payload returned after retries.",
            "attempts": attempts,
            "response_count": 0,
            "sample_keys": [],
        }

    status, reason = classify_errors(payload.get("errors") if isinstance(payload, dict) else None)
    response = payload.get("response") if isinstance(payload, dict) else None
    response_items = response if isinstance(response, list) else []
    row = {
        "endpoint": endpoint,
        "params": redact_params(params),
        "checked_at": started_at,
        "http_status": payload.get("_http_status") if isinstance(payload, dict) else None,
        "attempts": attempts if last_error else 1,
        "status": status,
        "status_reason": reason,
        "paging": payload.get("paging") if isinstance(payload, dict) else None,
        "results": payload.get("results") if isinstance(payload, dict) else None,
        "response_count": len(response_items),
        "sample_keys": sample_keys(response_items[0]) if response_items else [],
        "sample_summary": summarize_sample(endpoint, response_items[0]) if response_items else None,
    }
    if status == "ok" and not response_items:
        row["status"] = "empty"
        row["status_reason"] = "Provider returned no rows for this query."
    return row


def redact_params(params: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in params.items() if "key" not in key.lower() and "token" not in key.lower()}


def sample_keys(item: object) -> list[str]:
    if not isinstance(item, dict):
        return []
    return sorted(str(key) for key in item.keys())


def summarize_sample(endpoint: str, item: object) -> dict[str, object]:
    if not isinstance(item, dict):
        return {}
    if endpoint == "/fixtures":
        fixture = item.get("fixture") or {}
        league = item.get("league") or {}
        teams = item.get("teams") or {}
        return {
            "fixture_id": fixture.get("id"),
            "date": fixture.get("date"),
            "status": (fixture.get("status") or {}).get("short"),
            "league": league.get("name"),
            "season": league.get("season"),
            "home": (teams.get("home") or {}).get("name"),
            "away": (teams.get("away") or {}).get("name"),
        }
    if endpoint == "/odds":
        bookmakers = item.get("bookmakers") or []
        markets = []
        for bookmaker in bookmakers:
            for bet in (bookmaker.get("bets") or []):
                name = bet.get("name")
                if name:
                    markets.append(str(name))
        return {
            "fixture_id": ((item.get("fixture") or {}).get("id")),
            "league": ((item.get("league") or {}).get("name")),
            "bookmaker_count": len(bookmakers),
            "markets_sample": sorted(set(markets))[:20],
        }
    if endpoint in {"/fixtures/events", "/fixtures/statistics", "/fixtures/lineups", "/injuries"}:
        return {
            "top_level_keys": sample_keys(item),
            "team": ((item.get("team") or {}).get("name")) if isinstance(item.get("team"), dict) else None,
            "player": ((item.get("player") or {}).get("name")) if isinstance(item.get("player"), dict) else None,
            "type": item.get("type"),
        }
    return {"top_level_keys": sample_keys(item)}


def find_sample_fixture_id(fixtures_row: dict) -> str | None:
    summary = fixtures_row.get("sample_summary") if isinstance(fixtures_row, dict) else None
    fixture_id = (summary or {}).get("fixture_id") if isinstance(summary, dict) else None
    return str(fixture_id) if fixture_id else None


def verdict_for_row(row: dict) -> str:
    status = str(row.get("status") or "")
    endpoint = str(row.get("endpoint") or "")
    if status == "ok":
        return "verified_rows"
    if status == "empty":
        if endpoint in {"/fixtures/lineups", "/fixtures/events", "/fixtures/statistics"}:
            return "pending_match_window_or_finished_fixture"
        return "verified_empty"
    if status in {"plan_restricted", "quota_exceeded", "auth_error"}:
        return status
    if status == "skipped_no_fixture_id":
        return "blocked_by_fixture_discovery"
    return "provider_or_network_error"


def build_report(*, league_id: str, season: str, api_key: str) -> dict:
    checked_at = utc_now()
    endpoints: list[dict] = []

    fixtures_row = safe_fetch("/fixtures", api_key=api_key, params={"league": league_id, "season": season})
    endpoints.append(fixtures_row)
    sample_fixture_id = find_sample_fixture_id(fixtures_row)

    endpoints.append(safe_fetch("/odds", api_key=api_key, params={"league": league_id, "season": season}))

    if sample_fixture_id:
        for endpoint in ("/fixtures/events", "/fixtures/statistics", "/fixtures/lineups", "/injuries"):
            endpoints.append(safe_fetch(endpoint, api_key=api_key, params={"fixture": sample_fixture_id}))
    else:
        for endpoint in ("/fixtures/events", "/fixtures/statistics", "/fixtures/lineups", "/injuries"):
            endpoints.append(
                {
                    "endpoint": endpoint,
                    "params": {"fixture": None},
                    "checked_at": checked_at,
                    "status": "skipped_no_fixture_id",
                    "status_reason": "Fixture discovery did not return a sample fixture id.",
                    "response_count": 0,
                    "sample_keys": [],
                    "sample_summary": None,
                }
            )

    for row in endpoints:
        row["verdict"] = verdict_for_row(row)

    return {
        "generated_at": checked_at,
        "provider": "api_football",
        "provider_url": "https://api-football.com/",
        "auth_env": "API_FOOTBALL_KEY",
        "league_id": league_id,
        "season": season,
        "sample_fixture_id": sample_fixture_id,
        "production_write_allowed": False,
        "public_write_allowed": False,
        "report_only": True,
        "endpoints": endpoints,
        "summary": summarize_endpoints(endpoints),
        "next_actions": [
            "If fixtures is plan_restricted, API-FOOTBALL cannot be the World Cup 2026 runtime source on the current plan.",
            "If fixtures works but fixture-scoped endpoints are empty, rerun inside lineup/post-match windows before rejecting the source.",
            "Do not promote this source into normalized/model/public until endpoint status, field coverage, and collection windows are documented.",
        ],
    }


def summarize_endpoints(endpoints: list[dict]) -> dict:
    by_status: dict[str, int] = {}
    by_verdict: dict[str, int] = {}
    for row in endpoints:
        status = str(row.get("status") or "unknown")
        verdict = str(row.get("verdict") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        by_verdict[verdict] = by_verdict.get(verdict, 0) + 1
    return {
        "endpoint_count": len(endpoints),
        "by_status": by_status,
        "by_verdict": by_verdict,
        "has_fixture_discovery": any(row.get("endpoint") == "/fixtures" and row.get("status") == "ok" for row in endpoints),
        "has_odds_rows": any(row.get("endpoint") == "/odds" and row.get("status") == "ok" for row in endpoints),
        "has_lineup_rows": any(row.get("endpoint") == "/fixtures/lineups" and row.get("status") == "ok" for row in endpoints),
        "has_injury_rows": any(row.get("endpoint") == "/injuries" and row.get("status") == "ok" for row in endpoints),
        "has_event_rows": any(row.get("endpoint") == "/fixtures/events" and row.get("status") == "ok" for row in endpoints),
        "has_statistics_rows": any(row.get("endpoint") == "/fixtures/statistics" and row.get("status") == "ok" for row in endpoints),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe API-FOOTBALL World Cup runtime endpoint coverage.")
    parser.add_argument("--league-id", default=os.environ.get("API_FOOTBALL_LEAGUE_ID", "1"))
    parser.add_argument("--season", default=os.environ.get("API_FOOTBALL_SEASON", "2026"))
    parser.add_argument("--output", default=str(REPORT_PATH))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_key = load_env_value("API_FOOTBALL_KEY")
    output_path = Path(args.output)
    if not api_key:
        report = {
            "generated_at": utc_now(),
            "provider": "api_football",
            "provider_url": "https://api-football.com/",
            "auth_env": "API_FOOTBALL_KEY",
            "status": "missing_auth",
            "status_reason": "API_FOOTBALL_KEY is not configured in environment or local .env file.",
            "production_write_allowed": False,
            "public_write_allowed": False,
            "report_only": True,
        }
        write_json(output_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    report = build_report(league_id=str(args.league_id), season=str(args.season), api_key=api_key)
    write_json(output_path, report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
