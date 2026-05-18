from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "data" / "public"
NORMALIZED_DIR = ROOT / "data" / "normalized"
REPORTS_DIR = ROOT / "reports"

FIXTURES_PATH = PUBLIC_DIR / "fixtures.json"
TEAMS_PATH = PUBLIC_DIR / "teams.json"
TEAM_RECENT_MATCHES_PATH = PUBLIC_DIR / "team-recent-matches.json"
VENUES_PATH = PUBLIC_DIR / "venues.json"

SCHEDULE_LOAD_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_predictor_schedule_load_master.json"
HOME_AWAY_SPLITS_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_predictor_team_home_away_splits_master.json"
TEAM_ADVANCED_STATS_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_predictor_team_advanced_stats_master.json"
SCHEDULE_LOAD_PUBLIC_PATH = PUBLIC_DIR / "schedule-load.json"
HOME_AWAY_SPLITS_PUBLIC_PATH = PUBLIC_DIR / "team-home-away-splits.json"
TEAM_ADVANCED_STATS_PUBLIC_PATH = PUBLIC_DIR / "team-advanced-stats.json"
REPORT_PATH = REPORTS_DIR / "predictor_context_metrics_report.json"

WINDOW_DAYS = (7, 14, 30)
RECENT_MATCH_LIMITS = (10, 20)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_dt(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value)
    try:
        if len(text) == 10:
            return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def team_name_by_id(teams: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(row.get("team_id")): str(row.get("name") or row.get("team_name") or row.get("team_id"))
        for row in teams
        if isinstance(row, dict) and row.get("team_id")
    }


def venue_by_id(venues: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("venue_id")): row
        for row in venues
        if isinstance(row, dict) and row.get("venue_id")
    }


def recent_by_team(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("team_id")): row
        for row in rows
        if isinstance(row, dict) and row.get("team_id")
    }


def empty_result_summary() -> dict[str, int]:
    return {
        "played": 0,
        "won": 0,
        "drawn": 0,
        "lost": 0,
        "goals_for": 0,
        "goals_against": 0,
        "goal_difference": 0,
    }


def add_match_to_summary(summary: dict[str, int], match: dict[str, Any]) -> None:
    summary["played"] += 1
    result = str(match.get("result") or "")
    if result == "win":
        summary["won"] += 1
    elif result == "draw":
        summary["drawn"] += 1
    elif result == "loss":
        summary["lost"] += 1
    summary["goals_for"] += int(match.get("score_for") or 0)
    summary["goals_against"] += int(match.get("score_against") or 0)
    summary["goal_difference"] = summary["goals_for"] - summary["goals_against"]


def pct(value: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round((value / total) * 100, 2)


def with_rates(summary: dict[str, int]) -> dict[str, Any]:
    played = int(summary.get("played") or 0)
    return {
        **summary,
        "win_rate_pct": pct(int(summary.get("won") or 0), played),
        "draw_rate_pct": pct(int(summary.get("drawn") or 0), played),
        "loss_rate_pct": pct(int(summary.get("lost") or 0), played),
        "goals_for_per_match": round(summary["goals_for"] / played, 3) if played else None,
        "goals_against_per_match": round(summary["goals_against"] / played, 3) if played else None,
    }


def split_recent_matches(matches: list[dict[str, Any]], limit: int) -> dict[str, Any]:
    scoped = matches[:limit]
    splits = {
        "home": empty_result_summary(),
        "away": empty_result_summary(),
        "neutral": empty_result_summary(),
        "unknown": empty_result_summary(),
    }
    overall = empty_result_summary()
    for match in scoped:
        add_match_to_summary(overall, match)
        key = str(match.get("home_away") or "unknown")
        if key not in splits:
            key = "unknown"
        add_match_to_summary(splits[key], match)
    return {
        "scope": f"last_{limit}",
        "matches": len(scoped),
        "overall": with_rates(overall),
        "splits": {key: with_rates(value) for key, value in splits.items()},
    }


def build_team_advanced_stats(
    *,
    teams: list[dict[str, Any]],
    team_recent_matches: list[dict[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    names = team_name_by_id(teams)
    rows: list[dict[str, Any]] = []
    for team_id in sorted(recent_by_team(team_recent_matches)):
        recent = recent_by_team(team_recent_matches).get(team_id, {})
        matches = recent.get("matches") if isinstance(recent.get("matches"), list) else []
        window = split_recent_matches(matches, 10)
        overall = window["overall"]
        rows.append(
            {
                "team_id": team_id,
                "team_name": str(recent.get("team_name") or names.get(team_id, team_id)),
                "competition": "world_cup",
                "competition_id": "fifa_world_cup",
                "season_id": "2026",
                "scope": "last_10",
                "matches": window["matches"],
                "goals_for_per_match": overall["goals_for_per_match"],
                "goals_against_per_match": overall["goals_against_per_match"],
                "goal_difference_per_match": round(
                    overall["goal_difference"] / window["matches"], 3
                )
                if window["matches"]
                else None,
                "win_rate_pct": overall["win_rate_pct"],
                "draw_rate_pct": overall["draw_rate_pct"],
                "loss_rate_pct": overall["loss_rate_pct"],
                "possession_pct": None,
                "pass_accuracy_pct": None,
                "passes_completed_per_match": None,
                "progressive_passes_per_match": None,
                "shots_per_match": None,
                "shots_on_target_per_match": None,
                "ppda": None,
                "xg_for_per_match": None,
                "xga_per_match": None,
                "source": recent.get("source") or "data/public/team-recent-matches.json",
                "last_updated": generated_at,
                "source_status": "partial" if matches else "missing",
                "missing_advanced_fields_reason": (
                    "team-recent-matches provides scores and locations only; possession, passing, "
                    "PPDA, shots and xG require a verified process-data source."
                ),
                "basis": {
                    "source_dataset": "team-recent-matches.json",
                    "window": "last_10",
                    "sample_size_matches": window["matches"],
                    "competition_scope": "international_recent_matches",
                    "advanced_fields_policy": "null means unavailable; never infer as zero",
                },
                "data_coverage": {
                    "basic_form": "available" if matches else "missing",
                    "possession": "missing",
                    "passing": "missing",
                    "shots": "missing",
                    "ppda": "missing",
                    "xg": "missing",
                },
            }
        )
    return rows


def build_team_home_away_splits(
    *,
    teams: list[dict[str, Any]],
    team_recent_matches: list[dict[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    names = team_name_by_id(teams)
    recent_index = recent_by_team(team_recent_matches)
    rows: list[dict[str, Any]] = []
    target_team_ids = sorted(recent_index)
    for team_id in target_team_ids:
        recent = recent_index.get(team_id, {})
        matches = recent.get("matches") if isinstance(recent.get("matches"), list) else []
        rows.append(
            {
                "team_id": team_id,
                "team_name": str(recent.get("team_name") or names.get(team_id, team_id)),
                "competition_id": "fifa_world_cup",
                "season_id": "2026",
                "source": recent.get("source") or "data/public/team-recent-matches.json",
                "source_status": "available" if matches else "missing",
                "generated_at": generated_at,
                "basis": {
                    "source_dataset": "team-recent-matches.json",
                    "neutral_policy": "National-team neutral-site matches remain neutral and are not forced into home/away buckets.",
                    "minimum_matches_for_strong_signal": 10,
                },
                "windows": [split_recent_matches(matches, limit) for limit in RECENT_MATCH_LIMITS],
            }
        )
    return rows


def team_load_before_match(
    *,
    team_id: str,
    kickoff: datetime,
    recent_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    recent = recent_index.get(team_id, {})
    matches = recent.get("matches") if isinstance(recent.get("matches"), list) else []
    prior_matches = []
    for match in matches:
        match_dt = parse_dt(match.get("date"))
        if match_dt and match_dt < kickoff:
            prior_matches.append((match_dt, match))
    prior_matches.sort(key=lambda item: item[0], reverse=True)

    last_match_dt = prior_matches[0][0] if prior_matches else None
    last_match = prior_matches[0][1] if prior_matches else None
    counts = {
        f"matches_last_{days}_days": sum(
            1 for match_dt, _ in prior_matches if 0 <= (kickoff - match_dt).days <= days
        )
        for days in WINDOW_DAYS
    }
    return {
        "team_id": team_id,
        "source_status": "available" if prior_matches else "missing_recent_match",
        "last_match": last_match,
        "last_match_date": last_match_dt.date().isoformat() if last_match_dt else None,
        "days_since_last_match": (kickoff.date() - last_match_dt.date()).days if last_match_dt else None,
        **counts,
        "travel": {
            "travel_distance_km": None,
            "travel_origin": last_match.get("venue") if isinstance(last_match, dict) else None,
            "travel_origin_city": last_match.get("city") if isinstance(last_match, dict) else None,
            "travel_origin_country": last_match.get("country") if isinstance(last_match, dict) else None,
            "travel_destination_venue_id": None,
            "travel_origin_assumption": "previous national-team match venue from team-recent-matches",
            "source_status": "missing_previous_match_coordinates",
            "status_reason": "team-recent-matches currently includes previous venue text but not latitude/longitude.",
        },
    }


def build_schedule_load(
    *,
    fixtures: list[dict[str, Any]],
    teams: list[dict[str, Any]],
    team_recent_matches: list[dict[str, Any]],
    venues: list[dict[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    names = team_name_by_id(teams)
    recent_index = recent_by_team(team_recent_matches)
    venues_index = venue_by_id(venues)
    rows: list[dict[str, Any]] = []

    for fixture in sorted(fixtures, key=lambda row: str(row.get("date_utc") or row.get("kickoff_at") or "")):
        kickoff = parse_dt(fixture.get("kickoff_at") or fixture.get("date_utc"))
        match_id = str(fixture.get("match_id") or "")
        if not match_id or not kickoff:
            continue
        home_team_id = str(fixture.get("home_team_id") or "")
        away_team_id = str(fixture.get("away_team_id") or "")
        venue_id = str(fixture.get("venue_id") or "")
        venue = venues_index.get(venue_id, {})

        home_load = team_load_before_match(
            team_id=home_team_id,
            kickoff=kickoff,
            recent_index=recent_index,
        )
        away_load = team_load_before_match(
            team_id=away_team_id,
            kickoff=kickoff,
            recent_index=recent_index,
        )
        for load in (home_load, away_load):
            load["travel"]["travel_destination_venue_id"] = venue_id or None

        rows.append(
            {
                "match_id": match_id,
                "competition_id": "fifa_world_cup",
                "season_id": "2026",
                "kickoff_at": kickoff.isoformat().replace("+00:00", "Z"),
                "venue_id": venue_id or None,
                "venue_name": fixture.get("venue_name") or venue.get("display_name"),
                "host_city_id": fixture.get("host_city_id") or venue.get("host_city_id"),
                "host_city": fixture.get("host_city") or venue.get("city_name_en"),
                "source": "fixtures.json + team-recent-matches.json",
                "source_status": "partial",
                "generated_at": generated_at,
                "basis": {
                    "recent_match_source": "team-recent-matches.json",
                    "fixture_source": "fixtures.json",
                    "window_days": list(WINDOW_DAYS),
                    "load_scope": "national-team recent matches before kickoff",
                    "travel_distance_policy": "travel distance is null until previous match coordinates are available",
                },
                "home": {
                    **home_load,
                    "team_name": names.get(home_team_id, home_team_id),
                },
                "away": {
                    **away_load,
                    "team_name": names.get(away_team_id, away_team_id),
                },
                "data_coverage": {
                    "schedule_load": "partial",
                    "rest_days": "available"
                    if home_load.get("days_since_last_match") is not None
                    and away_load.get("days_since_last_match") is not None
                    else "partial",
                    "travel_distance": "missing",
                    "travel_reason": "missing_previous_match_coordinates",
                },
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build predictor schedule-load and home/away split datasets.")
    parser.add_argument("--report-output", default=str(REPORT_PATH))
    args = parser.parse_args()

    generated_at = now_utc()
    fixtures = [row for row in load_json(FIXTURES_PATH) if isinstance(row, dict)]
    teams = [row for row in load_json(TEAMS_PATH) if isinstance(row, dict)]
    team_recent_matches = [
        row for row in load_json(TEAM_RECENT_MATCHES_PATH) if isinstance(row, dict)
    ]
    venues = [row for row in load_json(VENUES_PATH) if isinstance(row, dict)]

    home_away_splits = build_team_home_away_splits(
        teams=teams,
        team_recent_matches=team_recent_matches,
        generated_at=generated_at,
    )
    team_advanced_stats = build_team_advanced_stats(
        teams=teams,
        team_recent_matches=team_recent_matches,
        generated_at=generated_at,
    )
    schedule_load = build_schedule_load(
        fixtures=fixtures,
        teams=teams,
        team_recent_matches=team_recent_matches,
        venues=venues,
        generated_at=generated_at,
    )

    write_json(SCHEDULE_LOAD_MASTER_PATH, schedule_load)
    write_json(HOME_AWAY_SPLITS_MASTER_PATH, home_away_splits)
    write_json(TEAM_ADVANCED_STATS_MASTER_PATH, team_advanced_stats)
    write_json(SCHEDULE_LOAD_PUBLIC_PATH, schedule_load)
    write_json(HOME_AWAY_SPLITS_PUBLIC_PATH, home_away_splits)
    write_json(TEAM_ADVANCED_STATS_PUBLIC_PATH, team_advanced_stats)

    report = {
        "generated_at": generated_at,
        "status": "published",
        "source": "fixtures.json + team-recent-matches.json",
        "policy": "Baseline model-context proxy. Travel distance is intentionally null until previous-match coordinates are available.",
        "counts": {
            "schedule_load_rows": len(schedule_load),
            "team_home_away_split_rows": len(home_away_splits),
            "team_advanced_stats_rows": len(team_advanced_stats),
            "team_advanced_stats_partial_rows": sum(
                1 for row in team_advanced_stats if row.get("source_status") == "partial"
            ),
            "schedule_load_partial_rows": sum(
                1 for row in schedule_load if row.get("source_status") == "partial"
            ),
            "rest_days_available_rows": sum(
                1
                for row in schedule_load
                if row.get("data_coverage", {}).get("rest_days") == "available"
            ),
            "travel_distance_missing_rows": sum(
                1
                for row in schedule_load
                if row.get("data_coverage", {}).get("travel_distance") == "missing"
            ),
        },
        "outputs": {
            "schedule_load_master": rel(SCHEDULE_LOAD_MASTER_PATH),
            "team_home_away_splits_master": rel(HOME_AWAY_SPLITS_MASTER_PATH),
            "team_advanced_stats_master": rel(TEAM_ADVANCED_STATS_MASTER_PATH),
            "schedule_load_public": rel(SCHEDULE_LOAD_PUBLIC_PATH),
            "team_home_away_splits_public": rel(HOME_AWAY_SPLITS_PUBLIC_PATH),
            "team_advanced_stats_public": rel(TEAM_ADVANCED_STATS_PUBLIC_PATH),
        },
    }
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
