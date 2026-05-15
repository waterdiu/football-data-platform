from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "data" / "public"
MODEL_DIR = ROOT / "data" / "model"
REPORTS_DIR = ROOT / "reports"

OUTPUT_PATH = REPORTS_DIR / "source-health.json"
QUALIFIER_REPORT_PATH = REPORTS_DIR / "qualifier_matches_import_report.json"
QUALIFIER_DETAIL_REPORT_PATH = REPORTS_DIR / "qualifier_detail_extract_report.json"
WORLD_CUP_DETAIL_REPORT_PATH = REPORTS_DIR / "world_cup_detail_extract_report.json"
WORLD_CUP_MODEL_REPORT_PATH = REPORTS_DIR / "world_cup_model_dataset_report.json"


def load_json(path: Path) -> object:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dataset_count(path: Path) -> int:
    payload = load_json(path)
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        return len(payload)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Build source health report for football-data-platform.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="source health report output path")
    args = parser.parse_args()

    coverage_rows = load_json(PUBLIC_DIR / "data-coverage.json")
    if not isinstance(coverage_rows, list):
        coverage_rows = []

    available_predictions = sum(
        1 for row in coverage_rows if isinstance(row, dict) and ((row.get("prediction") or {}).get("status") == "available")
    )
    available_events = sum(
        1 for row in coverage_rows if isinstance(row, dict) and ((row.get("events") or {}).get("status") == "available")
    )
    available_lineups = sum(
        1 for row in coverage_rows if isinstance(row, dict) and ((row.get("lineups") or {}).get("status") == "available")
    )
    available_match_stats = sum(
        1 for row in coverage_rows if isinstance(row, dict) and ((row.get("match_stats") or {}).get("status") == "available")
    )
    available_odds = sum(
        1 for row in coverage_rows if isinstance(row, dict) and ((row.get("odds") or {}).get("status") == "available")
    )
    available_injuries = sum(
        1 for row in coverage_rows if isinstance(row, dict) and ((row.get("injuries") or {}).get("status") == "available")
    )
    available_weather = sum(
        1 for row in coverage_rows if isinstance(row, dict) and ((row.get("weather") or {}).get("status") == "available")
    )

    world_cup_detail_report = load_json(WORLD_CUP_DETAIL_REPORT_PATH) or {}
    world_cup_model_report = load_json(WORLD_CUP_MODEL_REPORT_PATH) or {}
    qualifier_report = load_json(QUALIFIER_REPORT_PATH) or {}
    qualifier_detail_report = load_json(QUALIFIER_DETAIL_REPORT_PATH) or {}

    report = {
        "generated_at": "2026-05-15T00:00:00Z",
        "public_datasets": {
            "teams": dataset_count(PUBLIC_DIR / "teams.json"),
            "fixtures": dataset_count(PUBLIC_DIR / "fixtures.json"),
            "results": dataset_count(PUBLIC_DIR / "results.json"),
            "standings": dataset_count(PUBLIC_DIR / "standings.json"),
            "predictions": dataset_count(PUBLIC_DIR / "predictions.json"),
            "finals_events": dataset_count(PUBLIC_DIR / "finals-events.json"),
            "finals_lineups": dataset_count(PUBLIC_DIR / "finals-lineups.json"),
            "finals_match_stats": dataset_count(PUBLIC_DIR / "finals-match-stats.json"),
            "qualifier_matches": dataset_count(PUBLIC_DIR / "qualifier-matches.json"),
            "qualifier_events": dataset_count(PUBLIC_DIR / "qualifier-events.json"),
            "qualifier_lineups": dataset_count(PUBLIC_DIR / "qualifier-lineups.json"),
            "qualifier_match_stats": dataset_count(PUBLIC_DIR / "qualifier-match-stats.json"),
            "coverage": dataset_count(PUBLIC_DIR / "data-coverage.json"),
        },
        "model_datasets": {
            "odds_snapshots": dataset_count(MODEL_DIR / "odds_snapshots.json"),
            "lineups": dataset_count(MODEL_DIR / "lineups.json"),
            "injuries": dataset_count(MODEL_DIR / "injuries.json"),
            "prematch_context": dataset_count(MODEL_DIR / "prematch_context.json"),
            "weather": dataset_count(MODEL_DIR / "weather.json"),
        },
        "coverage_summary": {
            "matches": len(coverage_rows),
            "prediction_available": available_predictions,
            "events_available": available_events,
            "lineups_available": available_lineups,
            "match_stats_available": available_match_stats,
            "odds_available": available_odds,
            "injuries_available": available_injuries,
            "weather_available": available_weather,
        },
        "world_cup_sources": {
            "detail_extract": world_cup_detail_report,
            "model_extract": world_cup_model_report,
        },
        "qualifier_sources": {
            "matches_import": qualifier_report,
            "detail_extract": qualifier_detail_report,
        },
    }
    write_json(Path(args.output), report)
    print(f"Wrote source health report to {args.output}")


if __name__ == "__main__":
    main()
