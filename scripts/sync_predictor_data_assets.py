from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_script(script_name: str, extra_args: list[str] | None = None) -> None:
    command = [sys.executable, str(ROOT / "scripts" / script_name)]
    if extra_args:
        command.extend(extra_args)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync predictor-owned data updates back into football-data-platform."
    )
    parser.add_argument(
        "--skip-full-copy",
        action="store_true",
        help="refresh manifests from predictor data without copying files into data/predictor-assets/files",
    )
    parser.add_argument(
        "--checksum",
        action="store_true",
        help="compute sha256 checksums while rebuilding the full asset manifest",
    )
    args = parser.parse_args()

    import_args: list[str] = []
    if args.skip_full_copy:
        import_args.append("--skip-copy")
    if args.checksum:
        import_args.append("--checksum")

    pipeline: list[tuple[str, list[str] | None]] = [
        ("import_predictor_data_assets.py", import_args),
        ("publish_predictor_data_assets_api.py", None),
        ("import_world_cup_predictor_local_data.py", None),
        ("publish_world_cup_predictor_api.py", None),
        ("build_source_health_report.py", None),
        ("build_world_cup_predictor_runtime_health.py", None),
    ]

    for script_name, extra_args in pipeline:
        print(f"Running {script_name}")
        run_script(script_name, extra_args)

    print("Predictor data assets and predictor runtime API are synced.")


if __name__ == "__main__":
    main()
