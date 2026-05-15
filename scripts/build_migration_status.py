from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_API_DIR = ROOT / "data" / "public" / "api"
REPORTS_DIR = ROOT / "reports"

SOURCE_HEALTH_PATH = REPORTS_DIR / "source-health.json"
PREDICTOR_HEALTH_PATH = PUBLIC_API_DIR / "worldcup" / "2026" / "predictor" / "health.json"
PREDICTOR_INBOX_REPORT_PATH = REPORTS_DIR / "predictor_inbox_publish_report.json"
RUNTIME_COLLECTION_REPORT_PATH = REPORTS_DIR / "world_cup_runtime_collection_report.json"
ASSET_SUMMARY_PATH = PUBLIC_API_DIR / "predictor" / "data-assets" / "summary.json"
OUTPUT_PATH = PUBLIC_API_DIR / "migration-status.json"

UPDATED_AT = "2026-05-15T00:00:00Z"


EXPECTED_INBOX_OUTPUTS = [
    "worldcup-2026/predictions.json",
    "worldcup-2026/odds-snapshots.json",
    "worldcup-2026/lineups.json",
    "worldcup-2026/injuries.json",
    "worldcup-2026/prematch-context.json",
    "worldcup-2026/weather.json",
    "premier-league/predictions.json",
    "premier-league/odds-snapshots.json",
    "premier-league/context-snapshots.jsonl",
]


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_optional_json(path: Path) -> object:
    if not path.exists():
        return {}
    return load_json(path)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def inbox_statuses(inbox_report: dict) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for section in ("world_cup", "premier_league"):
        for item in inbox_report.get(section, []):
            source = str(item.get("source") or "")
            for expected in EXPECTED_INBOX_OUTPUTS:
                if source.endswith(expected):
                    statuses[expected] = str(item.get("status") or "unknown")
    return statuses


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a public migration status report for consumer projects.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="migration status output path")
    args = parser.parse_args()

    source_health = load_json(SOURCE_HEALTH_PATH)
    predictor_health = load_json(PREDICTOR_HEALTH_PATH)
    inbox_report = load_json(PREDICTOR_INBOX_REPORT_PATH)
    runtime_collection_report = load_optional_json(RUNTIME_COLLECTION_REPORT_PATH)
    asset_summary = load_json(ASSET_SUMMARY_PATH)

    public_datasets = source_health.get("public_datasets", {}) if isinstance(source_health, dict) else {}
    model_datasets = source_health.get("model_datasets", {}) if isinstance(source_health, dict) else {}
    predictor_counts = (
        predictor_health.get("predictor_dataset_counts", {}) if isinstance(predictor_health, dict) else {}
    )
    inbox_by_output = inbox_statuses(inbox_report if isinstance(inbox_report, dict) else {})
    published_outputs = [
        output for output in EXPECTED_INBOX_OUTPUTS if inbox_by_output.get(output) == "published"
    ]
    pending_outputs = [
        output for output in EXPECTED_INBOX_OUTPUTS if inbox_by_output.get(output) != "published"
    ]

    payload = {
        "generated_at": UPDATED_AT,
        "overall_status": "platform_strict_complete_with_runtime_gaps",
        "summary": {
            "site_runtime_api": "complete",
            "predictor_platform_read": "complete",
            "predictor_data_assets": "complete",
            "predictor_inbox_writeback": "partial",
            "runtime_enrichment": "pending_source_data",
        },
        "worldcup_2026_site": {
            "status": "complete",
            "public_api": "https://waterdiu.github.io/football-data-platform/api/worldcup/2026/manifest.json",
            "datasets": {
                "fixtures": public_datasets.get("fixtures"),
                "results": public_datasets.get("results"),
                "standings": public_datasets.get("standings"),
                "predictions": public_datasets.get("predictions"),
                "qualifier_matches": public_datasets.get("qualifier_matches"),
            },
        },
        "world_cup_predictor": {
            "phase_1_platform_read": {
                "status": "complete",
                "mode": "platform_strict",
                "local_fallback": "disabled_by_default",
                "fallback_override_env": "FOOTBALL_DATA_PLATFORM_ALLOW_LOCAL_FALLBACK=1",
            },
            "phase_2_inbox_writeback": {
                "status": "complete" if not pending_outputs else "partial",
                "published_count": inbox_report.get("published_count"),
                "empty_count": inbox_report.get("empty_count", 0),
                "missing_count": inbox_report.get("missing_count"),
                "published_outputs": published_outputs,
                "pending_outputs": pending_outputs,
                "output_statuses": inbox_by_output,
            },
            "runtime_api": {
                "status": predictor_health.get("status"),
                "health_url": "https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor/health.json",
                "warnings": predictor_health.get("warnings", []),
                "counts": {
                    "shared_fixtures": predictor_counts.get("shared_fixtures"),
                    "feature_inputs_rows": predictor_counts.get("feature_inputs_rows"),
                    "predictions": predictor_counts.get("predictions"),
                    "odds_source": predictor_counts.get("odds_source"),
                    "context_source": predictor_counts.get("context_source"),
                    "prematch_context": predictor_counts.get("prematch_context"),
                },
            },
            "data_assets": {
                "status": "complete",
                "manifest_url": "https://waterdiu.github.io/football-data-platform/api/predictor/data-assets/manifest.json",
                "file_count": asset_summary.get("file_count"),
                "total_bytes": asset_summary.get("total_bytes"),
            },
        },
        "runtime_enrichment_gaps": {
            "world_cup_odds_rows": model_datasets.get("odds_snapshots"),
            "world_cup_lineups_rows": model_datasets.get("lineups"),
            "world_cup_injuries_rows": model_datasets.get("injuries"),
            "world_cup_weather_rows": model_datasets.get("weather"),
            "note": "These remain pending until platform collectors or predictor inbox files produce rows.",
        },
        "platform_runtime_collectors": {
            "status": "available" if runtime_collection_report else "not_run",
            "report_path": "reports/world_cup_runtime_collection_report.json",
            "datasets": runtime_collection_report.get("datasets", []) if isinstance(runtime_collection_report, dict) else [],
        },
    }

    write_json(Path(args.output), payload)
    print(f"Wrote migration status to {args.output}")


if __name__ == "__main__":
    main()
