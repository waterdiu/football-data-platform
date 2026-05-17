from __future__ import annotations

import argparse
import json
from pathlib import Path

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
PREDICTOR_API_DIR = ROOT / "data" / "public" / "api" / "worldcup" / "2026" / "predictor"
SOURCE_HEALTH_PATH = REPORTS_DIR / "source-health.json"
IMPORT_REPORT_PATH = REPORTS_DIR / "world_cup_predictor_local_import_report.json"
PUBLISH_REPORT_PATH = REPORTS_DIR / "world_cup_predictor_api_publish_report.json"
MANIFEST_PATH = PREDICTOR_API_DIR / "manifest.json"
OUTPUT_PATH = PREDICTOR_API_DIR / "health.json"
BASE_URL = "https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor"
UPDATED_AT = "2026-05-15T00:00:00Z"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a runtime health snapshot for the World Cup predictor API.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="predictor runtime health output path")
    args = parser.parse_args()

    source_health = load_json(SOURCE_HEALTH_PATH)
    manifest = load_json(MANIFEST_PATH)
    import_report = load_json(IMPORT_REPORT_PATH) if IMPORT_REPORT_PATH.exists() else {}
    publish_report = load_json(PUBLISH_REPORT_PATH) if PUBLISH_REPORT_PATH.exists() else {}

    if not isinstance(source_health, dict):
        raise TypeError("source-health.json must contain an object")
    if not isinstance(manifest, dict):
        raise TypeError("predictor manifest.json must contain an object")
    if not isinstance(import_report, dict):
        import_report = {}
    if not isinstance(publish_report, dict):
        publish_report = {}

    imported_masters = import_report.get("imported_masters") or {}
    counts = publish_report.get("counts") or {}

    warnings: list[str] = []
    if int(counts.get("shared_fixtures", 0) or 0) == 0:
        warnings.append("predictor shared_fixtures dataset is empty")
    if int(counts.get("feature_inputs_rows", 0) or 0) == 0:
        warnings.append("predictor feature_inputs dataset is empty")
    if int(counts.get("predictions_source", 0) or 0) == 0:
        warnings.append("predictor predictions_source dataset is empty")
    if int(counts.get("odds_source", 0) or 0) == 0:
        warnings.append("predictor odds_source has no World Cup rows")
    context_source_meta = imported_masters.get("context_source") or {}
    if not bool(context_source_meta.get("exists")):
        warnings.append("predictor world_cup_context_snapshots.jsonl does not exist")

    payload = {
        "generated_at": UPDATED_AT,
        "competition_id": "fifa_world_cup",
        "season_id": "2026",
        "contract_version": manifest.get("contract_version"),
        "status": "ok" if not warnings else "degraded",
        "warnings": warnings,
        "runtime_urls": {
            "manifest": f"{BASE_URL}/manifest.json",
            "bundle": f"{BASE_URL}/bundle.json",
            "health": f"{BASE_URL}/health.json",
        },
        "predictor_dataset_counts": counts,
        "imported_master_summary": imported_masters,
        "source_health_generated_at": source_health.get("generated_at"),
        "manifest_generated_at": manifest.get("generated_at"),
    }
    write_json(Path(args.output), payload)
    print(f"Wrote World Cup predictor runtime health snapshot to {args.output}")


if __name__ == "__main__":
    main()
