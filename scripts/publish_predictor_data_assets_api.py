from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SOURCE = ROOT / "data" / "normalized" / "predictor_data_assets_manifest.json"
API_DIR = ROOT / "data" / "public" / "api" / "predictor" / "data-assets"
REPORT_PATH = ROOT / "reports" / "predictor_data_assets_api_publish_report.json"

UPDATED_AT = "2026-05-15T00:00:00Z"
PAGES_BASE = "https://waterdiu.github.io/football-data-platform/api/predictor/data-assets"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish lightweight API manifests for predictor data assets.")
    parser.add_argument("--manifest-source", default=str(MANIFEST_SOURCE), help="normalized asset manifest path")
    parser.add_argument("--report-output", default=str(REPORT_PATH), help="publish report output path")
    args = parser.parse_args()

    source_manifest = load_json(Path(args.manifest_source))
    if not isinstance(source_manifest, dict):
        raise TypeError("predictor data asset manifest must contain an object")

    files = source_manifest.get("files") or []
    if not isinstance(files, list):
        raise TypeError("predictor data asset manifest files must be a list")

    category_files: dict[str, list[dict]] = defaultdict(list)
    for item in files:
        if isinstance(item, dict):
            category_files[str(item.get("category") or "unknown")].append(item)

    category_indexes = {}
    for category, entries in sorted(category_files.items()):
        filename = f"{category.replace('.', '-')}.json"
        payload = {
            "generated_at": UPDATED_AT,
            "category": category,
            "file_count": len(entries),
            "total_bytes": sum(int(entry.get("bytes", 0) or 0) for entry in entries),
            "files": entries,
        }
        write_json(API_DIR / "categories" / filename, payload)
        category_indexes[category] = {
            "path": f"api/predictor/data-assets/categories/{filename}",
            "url": f"{PAGES_BASE}/categories/{filename}",
            "file_count": payload["file_count"],
            "total_bytes": payload["total_bytes"],
        }

    summary = {
        "generated_at": UPDATED_AT,
        "source_repository": source_manifest.get("source_repository"),
        "source_data_dir": source_manifest.get("source_data_dir"),
        "platform_asset_root": source_manifest.get("platform_asset_root"),
        "file_count": source_manifest.get("file_count", 0),
        "total_bytes": source_manifest.get("total_bytes", 0),
        "categories": source_manifest.get("categories", {}),
        "publication_policy": source_manifest.get("publication_policy", {}),
    }

    public_manifest = {
        **summary,
        "contract_version": "2026-05-15.predictor-data-assets.v1",
        "summary_url": f"{PAGES_BASE}/summary.json",
        "category_indexes": category_indexes,
        "notes": [
            "This API publishes asset manifests only. Large raw files remain local under platform_asset_root.",
            "Predictor should use these manifests to resolve platform-local asset paths during local runs.",
            "World Cup runtime compatibility data remains under /api/worldcup/2026/predictor/.",
        ],
    }

    write_json(API_DIR / "summary.json", summary)
    write_json(API_DIR / "manifest.json", public_manifest)

    report = {
        "generated_at": UPDATED_AT,
        "manifest_path": str(API_DIR / "manifest.json"),
        "summary_path": str(API_DIR / "summary.json"),
        "category_count": len(category_indexes),
        "file_count": source_manifest.get("file_count", 0),
        "total_bytes": source_manifest.get("total_bytes", 0),
    }
    write_json(Path(args.report_output), report)

    print(f"Published predictor data asset API manifest to {API_DIR / 'manifest.json'}")
    print(f"Wrote predictor data asset API report to {args.report_output}")


if __name__ == "__main__":
    main()
