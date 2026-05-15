from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
PREDICTOR_DIR = ROOT.parent / "world-cup-predictor"
PREDICTOR_MAINTENANCE_SCRIPT = PREDICTOR_DIR / "backend" / "scripts" / "run_scheduled_maintenance.py"


def run_command(command: list[str], *, cwd: Path) -> None:
    result = subprocess.run(command, cwd=str(cwd), check=False, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        raise SystemExit(result.returncode)


def run_platform_script(script_name: str) -> None:
    print(f"[platform] {script_name}")
    run_command([sys.executable, str(SCRIPTS_DIR / script_name)], cwd=ROOT)


def import_world_cup_predictions_from_inbox() -> None:
    print("[platform] import_world_cup_predictions.py")
    run_command(
        [
            sys.executable,
            str(SCRIPTS_DIR / "import_world_cup_predictions.py"),
            "--source",
            str(ROOT / "data" / "inbox" / "predictor" / "worldcup-2026" / "predictions.json"),
        ],
        cwd=ROOT,
    )


def run_predictor_maintenance(args: argparse.Namespace) -> None:
    if not PREDICTOR_MAINTENANCE_SCRIPT.exists():
        raise SystemExit(f"predictor maintenance script does not exist: {PREDICTOR_MAINTENANCE_SCRIPT}")

    command = [
        sys.executable,
        str(PREDICTOR_MAINTENANCE_SCRIPT),
        "--competition",
        args.competition,
    ]
    if args.skip_odds:
        command.append("--skip-odds")
    if args.skip_context:
        command.append("--skip-context")
    if not args.include_predictions:
        command.append("--skip-predictions")
    command.append("--skip-evaluation")
    if args.context_limit is not None:
        command.extend(["--context-limit", str(args.context_limit)])

    print("[predictor] run_scheduled_maintenance.py")
    run_command(command, cwd=PREDICTOR_DIR)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture predictor runtime outputs into inbox and republish platform runtime APIs."
    )
    parser.add_argument("--competition", choices=["world_cup", "premier_league", "all"], default="all")
    parser.add_argument("--skip-capture", action="store_true", help="only publish existing inbox files")
    parser.add_argument("--skip-odds", action="store_true", help="skip predictor odds capture")
    parser.add_argument("--skip-context", action="store_true", help="skip predictor context capture")
    parser.add_argument(
        "--collect-platform-runtime",
        action="store_true",
        help="also run platform-owned runtime collectors before publishing model datasets",
    )
    parser.add_argument("--platform-window-hours", type=int, default=None)
    parser.add_argument("--platform-limit", type=int, default=None)
    parser.add_argument(
        "--include-predictions",
        action="store_true",
        help="also let predictor regenerate Premier League predictions during maintenance",
    )
    parser.add_argument("--context-limit", type=int, default=None)
    args = parser.parse_args()

    if not args.skip_capture:
        run_predictor_maintenance(args)

    run_platform_script("publish_predictor_inbox.py")
    import_world_cup_predictions_from_inbox()
    if args.collect_platform_runtime:
        command = [sys.executable, str(SCRIPTS_DIR / "collect_world_cup_runtime_data.py")]
        if args.platform_window_hours is not None:
            command.extend(["--window-hours", str(args.platform_window_hours)])
        if args.platform_limit is not None:
            command.extend(["--limit", str(args.platform_limit)])
        print("[platform] collect_world_cup_runtime_data.py")
        run_command(command, cwd=ROOT)
    for script_name in [
        "build_world_cup_model_runtime_datasets.py",
        "build_world_cup_coverage.py",
        "publish_worldcup_2026_api.py",
        "publish_world_cup_predictor_api.py",
        "build_source_health_report.py",
        "build_worldcup_2026_runtime_health.py",
        "build_world_cup_predictor_runtime_health.py",
        "build_migration_status.py",
    ]:
        run_platform_script(script_name)

    print("Predictor runtime inbox and platform runtime APIs are synced.")


if __name__ == "__main__":
    main()
