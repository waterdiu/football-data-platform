from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREDICTOR_ROOT = ROOT.parent / "world-cup-predictor"
PUBLIC_DIR = ROOT / "data" / "public"
NORMALIZED_DIR = ROOT / "data" / "normalized"
REPORTS_DIR = ROOT / "reports"

SHARED_FIXTURES_SOURCE = PREDICTOR_ROOT / "backend" / "data" / "raw" / "world_cup_2026_shared_fixtures.json"
FEATURE_INPUTS_SOURCE = PREDICTOR_ROOT / "backend" / "data" / "processed" / "world_cup_2026_fixtures.json"
PREDICTIONS_SOURCE = PREDICTOR_ROOT / "backend" / "data" / "processed" / "predictions.json"
ODDS_SOURCE = PREDICTOR_ROOT / "backend" / "data" / "runtime" / "odds_snapshots.json"
CONTEXT_SOURCE = PREDICTOR_ROOT / "backend" / "data" / "runtime" / "context" / "world_cup_context_snapshots.jsonl"

UPDATED_AT = "2026-05-15T00:00:00Z"

MASTER_PATHS = {
    "shared_fixtures": NORMALIZED_DIR / "world_cup_2026_predictor_shared_fixtures_master.json",
    "feature_inputs": NORMALIZED_DIR / "world_cup_2026_predictor_feature_inputs_master.json",
    "predictions_source": NORMALIZED_DIR / "world_cup_2026_predictor_predictions_source_master.json",
    "odds_source": NORMALIZED_DIR / "world_cup_2026_predictor_odds_source_master.json",
    "context_source": NORMALIZED_DIR / "world_cup_2026_predictor_context_source_master.json",
}

REPORT_PATH = REPORTS_DIR / "world_cup_predictor_local_import_report.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def payload_size(payload: object) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        return len(payload)
    return 0


def is_world_cup_snapshot(snapshot: dict) -> bool:
    match_id = str(snapshot.get("match_id") or "")
    sport_key = str(snapshot.get("sport_key") or "")
    if match_id.startswith("fifa_world_cup:2026:"):
        return True
    if sport_key in {"soccer_world_cup", "world_cup"}:
        return True
    return False


def load_context_snapshots(path: Path) -> list[dict]:
    if not path.exists():
        return []
    snapshots: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            snapshots.append(payload)
    return snapshots


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import already-downloaded World Cup predictor datasets into platform-owned master files."
    )
    parser.add_argument("--report-output", default=str(REPORT_PATH), help="report output path")
    args = parser.parse_args()

    shared_fixtures = load_json(SHARED_FIXTURES_SOURCE)
    feature_inputs = load_json(FEATURE_INPUTS_SOURCE)
    predictions_source = load_json(PREDICTIONS_SOURCE)
    standard_fixtures = load_json(PUBLIC_DIR / "fixtures.json")
    standard_teams = load_json(PUBLIC_DIR / "teams.json")
    standard_by_match_id, standard_by_key = standard_fixture_indexes(standard_fixtures, standard_teams)
    shared_fixtures_enriched = enrich_fixture_payload(
        shared_fixtures, by_match_id=standard_by_match_id, by_key=standard_by_key
    )
    feature_inputs_enriched = enrich_fixture_payload(
        feature_inputs, by_match_id=standard_by_match_id, by_key=standard_by_key
    )
    predictions_source_enriched = enrich_fixture_payload(
        predictions_source, by_match_id=standard_by_match_id, by_key=standard_by_key
    )
    odds_payload = load_json(ODDS_SOURCE)
    if not isinstance(odds_payload, list):
        raise TypeError("odds_snapshots.json must contain a list")
    world_cup_odds = [item for item in odds_payload if isinstance(item, dict) and is_world_cup_snapshot(item)]
    context_snapshots = load_context_snapshots(CONTEXT_SOURCE)

    write_json(MASTER_PATHS["shared_fixtures"], shared_fixtures)
    write_json(MASTER_PATHS["feature_inputs"], feature_inputs)
    write_json(MASTER_PATHS["predictions_source"], predictions_source)
    write_json(MASTER_PATHS["odds_source"], world_cup_odds)
    write_json(MASTER_PATHS["context_source"], context_snapshots)

    report = {
        "generated_at": UPDATED_AT,
        "source_repository": str(PREDICTOR_ROOT),
        "imported_masters": {
            "shared_fixtures": {
                "source": str(SHARED_FIXTURES_SOURCE),
                "target": str(MASTER_PATHS["shared_fixtures"]),
                "rows": payload_size(shared_fixtures.get("fixtures", [])) if isinstance(shared_fixtures, dict) else payload_size(shared_fixtures),
                "rows_enriched_with_kickoff_at": shared_fixtures_enriched,
            },
            "feature_inputs": {
                "source": str(FEATURE_INPUTS_SOURCE),
                "target": str(MASTER_PATHS["feature_inputs"]),
                "fixture_rows": payload_size(feature_inputs.get("fixtures", [])) if isinstance(feature_inputs, dict) else 0,
                "feature_rows": payload_size(feature_inputs.get("features", [])) if isinstance(feature_inputs, dict) else 0,
                "rows_enriched_with_kickoff_at": feature_inputs_enriched,
            },
            "predictions_source": {
                "source": str(PREDICTIONS_SOURCE),
                "target": str(MASTER_PATHS["predictions_source"]),
                "rows": payload_size(predictions_source.get("fixtures", [])) if isinstance(predictions_source, dict) else 0,
                "rows_enriched_with_kickoff_at": predictions_source_enriched,
            },
            "odds_source": {
                "source": str(ODDS_SOURCE),
                "target": str(MASTER_PATHS["odds_source"]),
                "rows": len(world_cup_odds),
                "note": "当前 predictor 本地 odds snapshots 中未发现 World Cup 2026 条目时会导入为空数组。",
            },
            "context_source": {
                "source": str(CONTEXT_SOURCE),
                "target": str(MASTER_PATHS["context_source"]),
                "rows": len(context_snapshots),
                "exists": CONTEXT_SOURCE.exists(),
                "note": "当前 predictor 若尚未生成 world_cup_context_snapshots.jsonl，则平台只记录缺失状态，不伪造上下文数据。",
            },
        },
    }
    write_json(Path(args.report_output), report)

    print(f"Imported predictor shared fixtures master to {MASTER_PATHS['shared_fixtures']}")
    print(f"Imported predictor feature inputs master to {MASTER_PATHS['feature_inputs']}")
    print(f"Imported predictor predictions source master to {MASTER_PATHS['predictions_source']}")
    print(f"Imported {len(world_cup_odds)} World Cup odds snapshots to {MASTER_PATHS['odds_source']}")
    print(f"Imported {len(context_snapshots)} World Cup context snapshots to {MASTER_PATHS['context_source']}")
    print(f"Wrote predictor local import report to {args.report_output}")


if __name__ == "__main__":
    main()
