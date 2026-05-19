from __future__ import annotations

import argparse
import json
from pathlib import Path

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "data" / "public"
MODEL_DIR = ROOT / "data" / "model"
NORMALIZED_DIR = ROOT / "data" / "normalized"
REPORTS_DIR = ROOT / "reports"
API_DIR = PUBLIC_DIR / "api" / "worldcup" / "2026" / "predictor"

UPDATED_AT = "2026-05-15T00:00:00Z"
PAGES_BASE = "https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def payload_size(payload: object) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        if isinstance(payload.get("fixtures"), list):
            return len(payload["fixtures"])
        if isinstance(payload.get("matches"), list):
            return len(payload["matches"])
        if isinstance(payload.get("data"), list):
            return len(payload["data"])
        return len(payload)
    return 0


def team_name_by_id(teams: object) -> dict[str, str]:
    if not isinstance(teams, list):
        return {}
    result: dict[str, str] = {}
    for team in teams:
        if not isinstance(team, dict):
            continue
        team_id = str(team.get("team_id") or "")
        name = str(team.get("name") or "")
        if team_id and name:
            result[team_id] = name
    return result


VENUE_COUNTRY_BY_ID = {
    "bc-place-vancouver": "canada",
    "bmo-field": "canada",
    "estadio-akron": "mexico",
    "estadio-azteca": "mexico",
    "estadio-bbva": "mexico",
    "arrowhead-stadium": "united-states",
    "at-and-t-stadium": "united-states",
    "gillette-stadium": "united-states",
    "hard-rock-stadium": "united-states",
    "levis-stadium": "united-states",
    "lincoln-financial-field": "united-states",
    "lumen-field": "united-states",
    "mercedes-benz-stadium": "united-states",
    "metlife-stadium": "united-states",
    "nrg-stadium": "united-states",
    "sofi-stadium": "united-states",
}


def fixture_key(date: object, home_team: object, away_team: object) -> tuple[str, str, str]:
    return (str(date or "")[:10], str(home_team or ""), str(away_team or ""))


def standard_fixture_indexes(fixtures: object, teams: object) -> tuple[dict[str, dict], dict[tuple[str, str, str], dict]]:
    by_match_id: dict[str, dict] = {}
    by_key: dict[tuple[str, str, str], dict] = {}
    names = team_name_by_id(teams)
    if not isinstance(fixtures, list):
        return by_match_id, by_key
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        match_id = str(fixture.get("match_id") or "")
        if match_id:
            by_match_id[match_id] = fixture
        key = fixture_key(
            fixture.get("date_utc"),
            names.get(str(fixture.get("home_team_id") or ""), fixture.get("home_team_id")),
            names.get(str(fixture.get("away_team_id") or ""), fixture.get("away_team_id")),
        )
        if all(key):
            by_key[key] = fixture
    return by_match_id, by_key


def venue_type_for_fixture(standard: dict) -> str:
    venue_country = VENUE_COUNTRY_BY_ID.get(str(standard.get("venue_id") or ""))
    if venue_country and venue_country in {
        str(standard.get("home_team_id") or ""),
        str(standard.get("away_team_id") or ""),
    }:
        return "host_home"
    return "neutral"


def enrich_fixture_row(row: dict, *, by_match_id: dict[str, dict], by_key: dict[tuple[str, str, str], dict]) -> bool:
    standard = by_match_id.get(str(row.get("match_id") or ""))
    if standard is None:
        standard = by_key.get(fixture_key(row.get("date"), row.get("home_team"), row.get("away_team")))
    if standard is None:
        return False

    kickoff_at = standard.get("kickoff_at") or standard.get("date_utc")
    if kickoff_at:
        row.setdefault("kickoff_at", kickoff_at)
        row.setdefault("date_utc", kickoff_at)
    for field in ("venue_id", "venue_name", "host_city", "host_city_id", "stage", "round", "group"):
        if standard.get(field) is not None:
            row.setdefault(field, standard[field])
    row.setdefault("venue_type", venue_type_for_fixture(standard))
    if "neutral" not in row:
        row["neutral"] = row["venue_type"] != "host_home"
    return bool(kickoff_at)


def enrich_fixture_payload(payload: object, *, by_match_id: dict[str, dict], by_key: dict[tuple[str, str, str], dict]) -> int:
    if not isinstance(payload, dict):
        return 0
    enriched = 0
    fixtures = payload.get("fixtures") if isinstance(payload.get("fixtures"), list) else []
    for row in fixtures:
        if isinstance(row, dict) and enrich_fixture_row(row, by_match_id=by_match_id, by_key=by_key):
            enriched += 1
    features = payload.get("features") if isinstance(payload.get("features"), list) else []
    for index, row in enumerate(features):
        if not isinstance(row, dict):
            continue
        source_fixture = fixtures[index] if index < len(fixtures) and isinstance(fixtures[index], dict) else None
        if source_fixture and source_fixture.get("match_id"):
            row.setdefault("match_id", source_fixture.get("match_id"))
        if enrich_fixture_row(row, by_match_id=by_match_id, by_key=by_key):
            enriched += 1
    return enriched


def missing_kickoff_count(payload: object) -> int:
    if not isinstance(payload, dict):
        return 0
    fixtures = payload.get("fixtures") if isinstance(payload.get("fixtures"), list) else []
    return sum(1 for row in fixtures if isinstance(row, dict) and not row.get("kickoff_at"))


def list_by_match_id(rows: object) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        match_id = str(row.get("match_id") or "")
        if match_id:
            result.setdefault(match_id, []).append(row)
    return result


def first_by_match_id(rows: object) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for match_id, items in list_by_match_id(rows).items():
        if items:
            result[match_id] = items[0]
    return result


def first_by_team_id(rows: object) -> dict[str, dict]:
    result: dict[str, dict] = {}
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        team_id = str(row.get("team_id") or "")
        if team_id and team_id not in result:
            result[team_id] = row
    return result


def coverage_status(coverage: dict, field: str) -> str:
    item = coverage.get(field)
    if isinstance(item, dict):
        return str(item.get("status") or "missing")
    if isinstance(item, str):
        return item
    return "missing"


def split_odds_snapshots(rows: list[dict]) -> dict[str, list[dict]]:
    output = {"ah": [], "ou": [], "one_x_two": []}
    for row in rows:
        market = str(row.get("market") or row.get("market_key") or "").casefold()
        if market in {"asian_handicap", "spreads", "ah"} or row.get("asian_handicap"):
            output["ah"].append(row)
        elif market in {"over_under", "totals", "ou"} or row.get("over_under") or row.get("totals"):
            output["ou"].append(row)
        elif market in {"h2h", "1x2", "one_x_two"} or row.get("h2h"):
            output["one_x_two"].append(row)
    return output


def empty_advanced_stats(team_id: str, team_name: str) -> dict:
    return {
        "team_id": team_id,
        "team_name": team_name,
        "competition": "world_cup",
        "scope": "last_10",
        "matches": 0,
        "possession_pct": None,
        "pass_accuracy_pct": None,
        "passes_completed_per_match": None,
        "progressive_passes_per_match": None,
        "shots_per_match": None,
        "shots_on_target_per_match": None,
        "ppda": None,
        "xg_for_per_match": None,
        "xga_per_match": None,
        "source": None,
        "last_updated": None,
        "source_status": "missing",
    }


def build_runtime_summary(
    *,
    fixtures: object,
    teams: object,
    lineups: object,
    injuries: object,
    weather: object,
    odds: object,
    schedule_load: object,
    team_home_away_splits: object,
    team_advanced_stats: object,
    coverage: object,
) -> list[dict]:
    if not isinstance(fixtures, list):
        return []
    names = team_name_by_id(teams)
    lineups_by_match = list_by_match_id(lineups)
    injuries_by_match = list_by_match_id(injuries)
    weather_by_match = first_by_match_id(weather)
    odds_by_match = list_by_match_id(odds)
    schedule_load_by_match = first_by_match_id(schedule_load)
    home_away_by_team = first_by_team_id(team_home_away_splits)
    advanced_by_team = first_by_team_id(team_advanced_stats)
    coverage_by_match = first_by_match_id(coverage)

    rows: list[dict] = []
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        match_id = str(fixture.get("match_id") or "")
        if not match_id:
            continue
        coverage_row = coverage_by_match.get(match_id, {})
        odds_rows = odds_by_match.get(match_id, [])
        home_team_id = str(fixture.get("home_team_id") or "")
        away_team_id = str(fixture.get("away_team_id") or "")
        rows.append(
            {
                "match_id": match_id,
                "competition": "world_cup",
                "kickoff_at": fixture.get("kickoff_at") or fixture.get("date_utc"),
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "home_team": names.get(home_team_id, home_team_id),
                "away_team": names.get(away_team_id, away_team_id),
                "lineups": lineups_by_match.get(match_id, []),
                "injuries": injuries_by_match.get(match_id, []),
                "weather": weather_by_match.get(match_id) or {},
                "schedule_load": schedule_load_by_match.get(match_id) or {},
                "home_away_splits": {
                    "home": home_away_by_team.get(home_team_id) or {},
                    "away": home_away_by_team.get(away_team_id) or {},
                },
                "referee_profile": {
                    "status": "missing_referee_assignment",
                    "referee_id": None,
                    "referee_name": None,
                    "sample_size": 0,
                },
                "team_advanced_stats": {
                    "home": advanced_by_team.get(home_team_id)
                    or empty_advanced_stats(home_team_id, names.get(home_team_id, home_team_id)),
                    "away": advanced_by_team.get(away_team_id)
                    or empty_advanced_stats(away_team_id, names.get(away_team_id, away_team_id)),
                },
                "odds_snapshots": split_odds_snapshots(odds_rows),
                "data_coverage": {
                    "lineups": coverage_status(coverage_row, "lineups"),
                    "injuries": coverage_status(coverage_row, "injuries"),
                    "weather": coverage_status(coverage_row, "weather"),
                    "referee_profile": "missing",
                    "advanced_stats": "partial"
                    if advanced_by_team.get(home_team_id) and advanced_by_team.get(away_team_id)
                    else "missing",
                    "ah_odds": coverage_status(coverage_row, "asian_handicap"),
                    "ou_odds": coverage_status(coverage_row, "over_under"),
                    "one_x_two_odds": coverage_status(coverage_row, "odds"),
                    "prematch_context": coverage_status(coverage_row, "prematch_context"),
                    "schedule_load": "partial" if schedule_load_by_match.get(match_id) else "missing",
                    "home_away_splits": "available"
                    if home_away_by_team.get(home_team_id) and home_away_by_team.get(away_team_id)
                    else "partial",
                },
                "coverage_detail": coverage_row,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a World Cup predictor-facing static API and bundle.")
    parser.add_argument(
        "--report-output",
        default=str(REPORTS_DIR / "world_cup_predictor_api_publish_report.json"),
        help="publish report output path",
    )
    args = parser.parse_args()

    shared_fixtures = load_json(NORMALIZED_DIR / "world_cup_2026_predictor_shared_fixtures_master.json")
    feature_inputs = load_json(NORMALIZED_DIR / "world_cup_2026_predictor_feature_inputs_master.json")
    predictions_source = load_json(NORMALIZED_DIR / "world_cup_2026_predictor_predictions_source_master.json")
    odds_source = load_json(NORMALIZED_DIR / "world_cup_2026_predictor_odds_source_master.json")
    context_source = load_json(NORMALIZED_DIR / "world_cup_2026_predictor_context_source_master.json")

    canonical_teams = load_json(PUBLIC_DIR / "canonical_teams.json")
    teams = load_json(PUBLIC_DIR / "teams.json")
    fixtures = load_json(PUBLIC_DIR / "fixtures.json")
    results = load_json(PUBLIC_DIR / "results.json")
    standings = load_json(PUBLIC_DIR / "standings.json")
    venues = load_json(PUBLIC_DIR / "venues.json")
    host_city_profiles = load_json(PUBLIC_DIR / "host-city-profiles.json")
    players = load_json(PUBLIC_DIR / "players.json")
    rosters = load_json(PUBLIC_DIR / "rosters.json")
    team_world_cup_history = load_json(PUBLIC_DIR / "team-world-cup-history.json")
    team_recent_matches = load_json(PUBLIC_DIR / "team-recent-matches.json")
    schedule_load = load_json(PUBLIC_DIR / "schedule-load.json")
    team_home_away_splits = load_json(PUBLIC_DIR / "team-home-away-splits.json")
    team_advanced_stats = load_json(PUBLIC_DIR / "team-advanced-stats.json")
    team_staff = load_json(PUBLIC_DIR / "team-staff.json")
    staff_external_facts = load_json(PUBLIC_DIR / "staff-external-facts.json")
    officials = load_json(PUBLIC_DIR / "officials.json")
    official_external_facts = load_json(PUBLIC_DIR / "official-external-facts.json")
    player_external_facts = load_json(PUBLIC_DIR / "player-external-facts.json")
    player_ratings = load_json(PUBLIC_DIR / "player-ratings.json")
    staff_ratings = load_json(PUBLIC_DIR / "staff-ratings.json")
    official_ratings = load_json(PUBLIC_DIR / "official-ratings.json")
    person_style_profiles = load_json(PUBLIC_DIR / "person-style-profiles.json")
    predictions = load_json(PUBLIC_DIR / "predictions.json")
    data_coverage = load_json(PUBLIC_DIR / "data-coverage.json")

    standard_by_match_id, standard_by_key = standard_fixture_indexes(fixtures, teams)
    shared_fixtures_enriched = enrich_fixture_payload(
        shared_fixtures, by_match_id=standard_by_match_id, by_key=standard_by_key
    )
    feature_inputs_enriched = enrich_fixture_payload(
        feature_inputs, by_match_id=standard_by_match_id, by_key=standard_by_key
    )
    predictions_source_enriched = enrich_fixture_payload(
        predictions_source, by_match_id=standard_by_match_id, by_key=standard_by_key
    )

    odds_runtime = load_json(MODEL_DIR / "odds_snapshots.json")
    lineups_runtime = load_json(MODEL_DIR / "lineups.json")
    injuries_runtime = load_json(MODEL_DIR / "injuries.json")
    prematch_context_runtime = load_json(MODEL_DIR / "prematch_context.json")
    weather_runtime = load_json(MODEL_DIR / "weather.json")
    runtime_summary = build_runtime_summary(
        fixtures=fixtures,
        teams=teams,
        lineups=lineups_runtime,
        injuries=injuries_runtime,
        weather=weather_runtime,
        odds=odds_runtime,
        schedule_load=schedule_load,
        team_home_away_splits=team_home_away_splits,
        team_advanced_stats=team_advanced_stats,
        coverage=data_coverage,
    )

    datasets = {
        "shared-fixtures.json": shared_fixtures,
        "feature-inputs.json": feature_inputs,
        "predictions-source.json": predictions_source,
        "odds-source.json": odds_source,
        "context-source.json": context_source,
        "canonical-teams.json": canonical_teams,
        "teams.json": teams,
        "fixtures.json": fixtures,
        "results.json": results,
        "standings.json": standings,
        "venues.json": venues,
        "host-city-profiles.json": host_city_profiles,
        "players.json": players,
        "rosters.json": rosters,
        "team-world-cup-history.json": team_world_cup_history,
        "team-recent-matches.json": team_recent_matches,
        "schedule-load.json": schedule_load,
        "team-home-away-splits.json": team_home_away_splits,
        "team-advanced-stats.json": team_advanced_stats,
        "team-staff.json": team_staff,
        "staff-external-facts.json": staff_external_facts,
        "officials.json": officials,
        "official-external-facts.json": official_external_facts,
        "player-external-facts.json": player_external_facts,
        "player-ratings.json": player_ratings,
        "staff-ratings.json": staff_ratings,
        "official-ratings.json": official_ratings,
        "person-style-profiles.json": person_style_profiles,
        "predictions.json": predictions,
        "data-coverage.json": data_coverage,
        "odds-snapshots.json": odds_runtime,
        "lineups.json": lineups_runtime,
        "injuries.json": injuries_runtime,
        "prematch-context.json": prematch_context_runtime,
        "weather.json": weather_runtime,
        "runtime-summary.json": runtime_summary,
    }

    for filename, payload in datasets.items():
        write_json(API_DIR / filename, payload)

    manifest = {
        "generated_at": UPDATED_AT,
        "competition_id": "fifa_world_cup",
        "season_id": "2026",
        "contract_version": "2026-05-15.world-cup-predictor.v1",
        "recommended_migration_order": [
            "shared-fixtures.json",
            "feature-inputs.json",
            "fixtures.json",
            "results.json",
            "data-coverage.json",
            "predictions.json",
            "prematch-context.json",
            "odds-snapshots.json",
        ],
        "bundle_url": f"{PAGES_BASE}/bundle.json",
        "datasets": {
            filename.replace(".json", "").replace("-", "_"): {
                "path": f"api/worldcup/2026/predictor/{filename}",
                "url": f"{PAGES_BASE}/{filename}",
            }
            for filename in datasets
        },
        "notes": [
            "predictor 兼容层优先提供旧格式 shared_fixtures / feature_inputs / predictions_source，降低首轮切换风险。",
            "platform 标准层仍以 fixtures / results / standings / predictions / data_coverage 为长期契约。",
        ],
    }

    bundle = {
        "generated_at": UPDATED_AT,
        "contract_version": manifest["contract_version"],
        "datasets": {
            "shared_fixtures": shared_fixtures,
            "feature_inputs": feature_inputs,
            "predictions_source": predictions_source,
            "odds_source": odds_source,
            "context_source": context_source,
            "canonical_teams": canonical_teams,
            "teams": teams,
            "fixtures": fixtures,
            "results": results,
            "standings": standings,
            "venues": venues,
            "host_city_profiles": host_city_profiles,
            "players": players,
            "rosters": rosters,
            "team_world_cup_history": team_world_cup_history,
            "team_recent_matches": team_recent_matches,
            "schedule_load": schedule_load,
            "team_home_away_splits": team_home_away_splits,
            "team_advanced_stats": team_advanced_stats,
            "team_staff": team_staff,
            "officials": officials,
            "player_ratings": player_ratings,
            "staff_ratings": staff_ratings,
            "official_ratings": official_ratings,
            "person_style_profiles": person_style_profiles,
            "predictions": predictions,
            "data_coverage": data_coverage,
            "odds_snapshots": odds_runtime,
            "lineups": lineups_runtime,
            "injuries": injuries_runtime,
            "prematch_context": prematch_context_runtime,
            "weather": weather_runtime,
            "runtime_summary": runtime_summary,
        },
    }

    write_json(API_DIR / "manifest.json", manifest)
    write_json(API_DIR / "bundle.json", bundle)

    report = {
        "generated_at": UPDATED_AT,
        "manifest_path": rel(API_DIR / "manifest.json"),
        "bundle_path": rel(API_DIR / "bundle.json"),
        "counts": {
            "shared_fixtures": payload_size(shared_fixtures.get("fixtures", [])) if isinstance(shared_fixtures, dict) else payload_size(shared_fixtures),
            "feature_inputs_fixtures": payload_size(feature_inputs.get("fixtures", [])) if isinstance(feature_inputs, dict) else 0,
            "feature_inputs_rows": payload_size(feature_inputs.get("features", [])) if isinstance(feature_inputs, dict) else 0,
            "predictions_source": payload_size(predictions_source.get("fixtures", [])) if isinstance(predictions_source, dict) else 0,
            "odds_source": payload_size(odds_source),
            "context_source": payload_size(context_source),
            "fixtures": payload_size(fixtures),
            "results": payload_size(results),
            "standings": payload_size(standings),
            "venues": payload_size(venues),
            "host_city_profiles": payload_size(host_city_profiles),
            "players": payload_size(players),
            "rosters": payload_size(rosters),
            "team_world_cup_history": payload_size(team_world_cup_history),
            "team_recent_matches": payload_size(team_recent_matches),
            "schedule_load": payload_size(schedule_load),
            "team_home_away_splits": payload_size(team_home_away_splits),
            "team_advanced_stats": payload_size(team_advanced_stats),
            "team_staff": payload_size(team_staff),
            "officials": payload_size(officials),
            "player_ratings": payload_size(player_ratings),
            "staff_ratings": payload_size(staff_ratings),
            "official_ratings": payload_size(official_ratings),
            "person_style_profiles": payload_size(person_style_profiles),
            "predictions": payload_size(predictions),
            "prematch_context": payload_size(prematch_context_runtime),
            "runtime_summary": payload_size(runtime_summary),
            "shared_fixtures_enriched_with_kickoff_at": shared_fixtures_enriched,
            "feature_inputs_enriched_with_kickoff_at": feature_inputs_enriched,
            "predictions_source_enriched_with_kickoff_at": predictions_source_enriched,
            "shared_fixtures_missing_kickoff_at": missing_kickoff_count(shared_fixtures),
            "feature_inputs_missing_kickoff_at": missing_kickoff_count(feature_inputs),
            "predictions_source_missing_kickoff_at": missing_kickoff_count(predictions_source),
        },
    }
    write_json(Path(args.report_output), report)

    print(f"Published World Cup predictor manifest to {API_DIR / 'manifest.json'}")
    print(f"Published World Cup predictor bundle to {API_DIR / 'bundle.json'}")
    print(f"Wrote predictor API publish report to {args.report_output}")


if __name__ == "__main__":
    main()
