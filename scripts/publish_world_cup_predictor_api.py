from __future__ import annotations

import argparse
import json
from pathlib import Path

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


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def payload_size(payload: object) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        return len(payload)
    return 0


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
    predictions = load_json(PUBLIC_DIR / "predictions.json")
    data_coverage = load_json(PUBLIC_DIR / "data-coverage.json")

    odds_runtime = load_json(MODEL_DIR / "odds_snapshots.json")
    lineups_runtime = load_json(MODEL_DIR / "lineups.json")
    injuries_runtime = load_json(MODEL_DIR / "injuries.json")
    prematch_context_runtime = load_json(MODEL_DIR / "prematch_context.json")
    weather_runtime = load_json(MODEL_DIR / "weather.json")

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
        "predictions.json": predictions,
        "data-coverage.json": data_coverage,
        "odds-snapshots.json": odds_runtime,
        "lineups.json": lineups_runtime,
        "injuries.json": injuries_runtime,
        "prematch-context.json": prematch_context_runtime,
        "weather.json": weather_runtime,
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
            "predictions": predictions,
            "data_coverage": data_coverage,
            "odds_snapshots": odds_runtime,
            "lineups": lineups_runtime,
            "injuries": injuries_runtime,
            "prematch_context": prematch_context_runtime,
            "weather": weather_runtime,
        },
    }

    write_json(API_DIR / "manifest.json", manifest)
    write_json(API_DIR / "bundle.json", bundle)

    report = {
        "generated_at": UPDATED_AT,
        "manifest_path": str(API_DIR / "manifest.json"),
        "bundle_path": str(API_DIR / "bundle.json"),
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
            "predictions": payload_size(predictions),
            "prematch_context": payload_size(prematch_context_runtime),
        },
    }
    write_json(Path(args.report_output), report)

    print(f"Published World Cup predictor manifest to {API_DIR / 'manifest.json'}")
    print(f"Published World Cup predictor bundle to {API_DIR / 'bundle.json'}")
    print(f"Wrote predictor API publish report to {args.report_output}")


if __name__ == "__main__":
    main()
