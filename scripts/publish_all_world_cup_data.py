from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"

LOCAL_IMPORT_SCRIPT = "import_worldcup_site_local_data.mjs"
PIPELINE = [
    "build_world_cup_fixtures.py",
    "build_world_cup_results.py",
    "build_world_cup_standings.py",
    "build_world_cup_detail_datasets.py",
    "build_world_cup_model_datasets.py",
    "build_world_cup_coverage.py",
    "publish_worldcup_2026_api.py",
]
CONTEXT_CAPTURE_SCRIPT = "capture_world_cup_context_from_predictor.py"


def run_script(script_name: str) -> None:
    script_path = SCRIPTS_DIR / script_name
    command = [sys.executable, str(script_path)]
    if script_path.suffix == ".mjs":
        command = ["node", str(script_path)]
    result = subprocess.run(command, cwd=str(ROOT), check=False, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish all World Cup shared datasets.")
    parser.add_argument(
        "--skip-model",
        action="store_true",
        help="skip model dataset build and only publish public competition datasets",
    )
    parser.add_argument(
        "--capture-context",
        action="store_true",
        help="capture World Cup context snapshots in predictor before building model datasets",
    )
    parser.add_argument(
        "--context-limit",
        type=int,
        default=None,
        help="optional fixture limit passed to the predictor context capture step",
    )
    args = parser.parse_args()

    print(f"[pipeline] {LOCAL_IMPORT_SCRIPT}")
    run_script(LOCAL_IMPORT_SCRIPT)

    if args.capture_context:
        print(f"[pipeline] {CONTEXT_CAPTURE_SCRIPT}")
        extra_args = []
        if args.context_limit is not None:
            extra_args = ["--context-limit", str(args.context_limit)]
        script_path = SCRIPTS_DIR / CONTEXT_CAPTURE_SCRIPT
        result = subprocess.run(
            [sys.executable, str(script_path), *extra_args],
            cwd=str(ROOT),
            check=False,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout.strip())
        if result.returncode != 0:
            if result.stderr:
                print(result.stderr.strip(), file=sys.stderr)
            raise SystemExit(result.returncode)

    pipeline = [step for step in PIPELINE if not (args.skip_model and step == "build_world_cup_model_datasets.py")]
    for step in pipeline:
        print(f"[pipeline] {step}")
        run_script(step)


if __name__ == "__main__":
    main()
