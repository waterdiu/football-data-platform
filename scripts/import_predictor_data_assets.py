from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREDICTOR_ROOT = ROOT.parent / "world-cup-predictor"
SOURCE_DATA_DIR = PREDICTOR_ROOT / "backend" / "data"
ASSET_ROOT = ROOT / "data" / "predictor-assets" / "files"
MANIFEST_PATH = ROOT / "data" / "normalized" / "predictor_data_assets_manifest.json"
REPORT_PATH = ROOT / "reports" / "predictor_data_assets_import_report.json"

UPDATED_AT = "2026-05-15T00:00:00Z"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify(relative_path: Path) -> str:
    parts = relative_path.parts
    if not parts:
        return "unknown"
    if parts[0] == "processed":
        if len(parts) > 1 and parts[1].startswith("premier_league"):
            return "processed.premier_league"
        if len(parts) > 1 and parts[1].startswith("world_cup"):
            return "processed.world_cup"
        return "processed.training"
    if parts[0] == "runtime":
        if len(parts) > 1 and parts[1] == "context":
            return "runtime.context"
        if len(parts) > 1 and "odds" in parts[1]:
            return "runtime.odds"
        return "runtime"
    if parts[0] == "raw":
        if len(parts) > 1 and parts[1] == "statsbomb_events":
            return "raw.statsbomb_events"
        if len(parts) > 1 and parts[1] == "premier_league":
            return "raw.premier_league_history"
        if len(parts) > 1 and parts[1] == "understat":
            return "raw.understat"
        if len(parts) > 1 and parts[1] == "dcaribou_transfermarkt":
            return "raw.transfermarkt_dcaribou"
        return "raw"
    return parts[0]


def iter_source_files() -> list[Path]:
    if not SOURCE_DATA_DIR.exists():
        raise FileNotFoundError(f"Predictor data directory does not exist: {SOURCE_DATA_DIR}")
    return sorted(path for path in SOURCE_DATA_DIR.rglob("*") if path.is_file())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mirror all existing world-cup-predictor backend/data assets into football-data-platform."
    )
    parser.add_argument("--source", default=str(SOURCE_DATA_DIR), help="predictor backend/data directory")
    parser.add_argument("--asset-root", default=str(ASSET_ROOT), help="platform local asset mirror root")
    parser.add_argument("--manifest-output", default=str(MANIFEST_PATH), help="normalized asset manifest output path")
    parser.add_argument("--report-output", default=str(REPORT_PATH), help="import report output path")
    parser.add_argument("--checksum", action="store_true", help="compute sha256 checksums for every migrated file")
    parser.add_argument("--skip-copy", action="store_true", help="build manifests without copying files")
    args = parser.parse_args()

    source_root = Path(args.source).resolve()
    asset_root = Path(args.asset_root).resolve()
    files = sorted(path for path in source_root.rglob("*") if path.is_file())
    if not files:
        raise FileNotFoundError(f"No predictor data files found under {source_root}")

    entries: list[dict] = []
    summary_by_category: dict[str, dict[str, int]] = defaultdict(lambda: {"file_count": 0, "bytes": 0})
    total_bytes = 0

    for source_path in files:
        relative_path = source_path.relative_to(source_root)
        target_path = asset_root / relative_path
        stat = source_path.stat()
        category = classify(relative_path)
        total_bytes += stat.st_size
        summary_by_category[category]["file_count"] += 1
        summary_by_category[category]["bytes"] += stat.st_size

        if not args.skip_copy:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)

        entry = {
            "relative_path": relative_path.as_posix(),
            "category": category,
            "extension": source_path.suffix.lower(),
            "bytes": stat.st_size,
            "source_path": str(source_path),
            "platform_path": str(target_path),
            "platform_relative_path": target_path.relative_to(ROOT).as_posix(),
            "is_public_payload": False,
        }
        if args.checksum:
            entry["sha256"] = sha256_file(source_path)
        entries.append(entry)

    manifest = {
        "generated_at": UPDATED_AT,
        "source_repository": str(PREDICTOR_ROOT),
        "source_data_dir": str(source_root),
        "platform_asset_root": str(asset_root),
        "platform_asset_root_relative": asset_root.relative_to(ROOT).as_posix(),
        "publication_policy": {
            "full_file_payloads": "local_only",
            "reason": "Predictor backend/data is large and includes raw provider archives; GitHub Pages publishes only manifests and small compatibility bundles.",
        },
        "file_count": len(entries),
        "total_bytes": total_bytes,
        "categories": dict(sorted(summary_by_category.items())),
        "files": entries,
    }

    report = {
        "generated_at": UPDATED_AT,
        "source_data_dir": str(source_root),
        "asset_root": str(asset_root),
        "manifest_output": str(Path(args.manifest_output)),
        "file_count": len(entries),
        "total_bytes": total_bytes,
        "copied": not args.skip_copy,
        "checksummed": bool(args.checksum),
        "categories": manifest["categories"],
    }

    write_json(Path(args.manifest_output), manifest)
    write_json(Path(args.report_output), report)

    print(f"Mirrored {len(entries)} predictor data files into {asset_root}")
    print(f"Total bytes: {total_bytes}")
    print(f"Wrote predictor data asset manifest to {args.manifest_output}")
    print(f"Wrote predictor data asset import report to {args.report_output}")


if __name__ == "__main__":
    main()
