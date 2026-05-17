from __future__ import annotations

import argparse
import json
from pathlib import Path

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
PUBLIC_API_DIR = ROOT / "data" / "public" / "api" / "worldcup" / "2026"
SOURCE_HEALTH_PATH = REPORTS_DIR / "source-health.json"
MANIFEST_PATH = PUBLIC_API_DIR / "manifest.json"
OUTPUT_PATH = PUBLIC_API_DIR / "health.json"
BASE_URL = "https://waterdiu.github.io/football-data-platform/api/worldcup/2026"
UPDATED_AT = "2026-05-15T00:00:00Z"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a runtime health snapshot for the World Cup 2026 API.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="runtime health output path")
    args = parser.parse_args()

    source_health = load_json(SOURCE_HEALTH_PATH)
    manifest = load_json(MANIFEST_PATH)
    if not isinstance(source_health, dict):
        raise TypeError("source-health.json must contain an object")
    if not isinstance(manifest, dict):
        raise TypeError("manifest.json must contain an object")

    public_datasets = source_health.get("public_datasets") or {}
    model_datasets = source_health.get("model_datasets") or {}
    coverage_summary = source_health.get("coverage_summary") or {}

    warnings: list[str] = []
    if int(public_datasets.get("fixtures", 0) or 0) == 0:
        warnings.append("fixtures dataset is empty")
    if int(public_datasets.get("results", 0) or 0) == 0:
        warnings.append("results dataset is empty")
    if int(public_datasets.get("predictions", 0) or 0) == 0:
        warnings.append("predictions dataset is empty")
    if int(public_datasets.get("qualifier_matches", 0) or 0) == 0:
        warnings.append("qualifier matches dataset is empty")

    payload = {
        "generated_at": UPDATED_AT,
        "competition_id": "fifa_world_cup",
        "season_id": "2026",
        "status": "ok" if not warnings else "degraded",
        "warnings": warnings,
        "runtime_urls": {
            "manifest": f"{BASE_URL}/manifest.json",
            "site_bundle": f"{BASE_URL}/site/bundle.json",
            "core_bundle": f"{BASE_URL}/core/bundle.json",
            "health": f"{BASE_URL}/health.json",
        },
        "counts": {
            "public": public_datasets,
            "model": model_datasets,
            "coverage": coverage_summary,
        },
        "manifest_generated_at": manifest.get("generated_at"),
        "source_health_generated_at": source_health.get("generated_at"),
    }
    write_json(Path(args.output), payload)
    print(f"Wrote World Cup runtime health snapshot to {args.output}")


if __name__ == "__main__":
    main()
