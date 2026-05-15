from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREDICTOR_DIR = ROOT.parent / "world-cup-predictor"
SCRIPT_PATH = PREDICTOR_DIR / "backend" / "scripts" / "run_scheduled_maintenance.py"


def main() -> None:
    parser = argparse.ArgumentParser(description="Trigger World Cup context capture in world-cup-predictor.")
    parser.add_argument("--context-limit", type=int, default=None, help="optional fixture limit for context capture")
    args = parser.parse_args()

    cmd = [
        sys.executable,
        str(SCRIPT_PATH),
        "--competition",
        "world_cup",
        "--skip-odds",
        "--skip-predictions",
        "--skip-evaluation",
    ]
    if args.context_limit is not None:
        cmd.extend(["--context-limit", str(args.context_limit)])

    result = subprocess.run(cmd, cwd=str(PREDICTOR_DIR), check=False, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
