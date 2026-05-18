from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "providers" / "sofascore_wrapper_probe.json"
REPORT_PATH = ROOT / "reports" / "sofascore_wrapper_isolated_probe.json"
WRAPPER_PROBE_SCRIPT = ROOT / "scripts" / "probe_sofascore_wrappers.py"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run_command(cmd: list[str], *, cwd: Path, timeout: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd),
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        return {
            "cmd": cmd,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": cmd,
            "returncode": None,
            "timeout": True,
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
        }


def wrapper_by_id(config: dict[str, Any], wrapper_id: str) -> dict[str, Any]:
    for row in config.get("wrappers") or []:
        if isinstance(row, dict) and row.get("wrapper_id") == wrapper_id:
            return row
    raise SystemExit(f"Unknown wrapper_id: {wrapper_id}")


def venv_python(venv_dir: Path) -> Path:
    return venv_dir / "bin" / "python"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Sofascore wrapper probe in an isolated temporary venv.")
    parser.add_argument("--wrapper", required=True, help="wrapper_id from configs/providers/sofascore_wrapper_probe.json")
    parser.add_argument("--install", action="store_true", help="create a temporary venv and install the wrapper package before probing")
    parser.add_argument("--keep-venv", action="store_true", help="keep the temporary venv for manual inspection")
    parser.add_argument("--timeout", type=int, default=180, help="timeout per subprocess command in seconds")
    parser.add_argument("--output", default=str(REPORT_PATH), help="isolated probe report output path")
    args = parser.parse_args()

    config = load_json(CONFIG_PATH)
    if not isinstance(config, dict):
        raise TypeError("Sofascore wrapper probe config must be an object")
    wrapper = wrapper_by_id(config, args.wrapper)
    package_names = [str(item) for item in wrapper.get("package_names") or [] if str(item)]

    report: dict[str, Any] = {
        "generated_at": utc_now(),
        "scope": "sofascore_wrapper_isolated_probe",
        "policy": config.get("policy"),
        "classification": "experimental_only",
        "production_write_allowed": False,
        "normalized_write_allowed": False,
        "public_api_write_allowed": False,
        "wrapper": wrapper,
        "install_requested": bool(args.install),
        "status": "not_run",
        "commands": [],
        "probe_report": None,
        "notes": [
            "This runner must not add Sofascore wrappers to project dependencies.",
            "It may install packages only into a temporary venv for isolated diagnostics.",
            "Do not run live scraping from this runner; it only checks package/API surface through probe_sofascore_wrappers.py.",
        ],
    }

    if not args.install:
        report["status"] = "skipped_install_not_requested"
        report["reason"] = "Pass --install to create a temporary venv and install the allowlisted wrapper package."
        write_json(Path(args.output), report)
        print(json.dumps({"status": report["status"], "wrapper": args.wrapper}, ensure_ascii=False, indent=2))
        return

    if not package_names:
        report["status"] = "blocked_no_pypi_package"
        report["reason"] = "This wrapper has no configured PyPI package name; use a separate manual clone review if needed."
        write_json(Path(args.output), report)
        print(json.dumps({"status": report["status"], "wrapper": args.wrapper}, ensure_ascii=False, indent=2))
        return

    temp_root = Path(tempfile.mkdtemp(prefix="sofascore-wrapper-probe-"))
    venv_dir = temp_root / "venv"
    isolated_report = temp_root / "wrapper_probe.json"
    report["temp_root"] = str(temp_root)
    report["venv_dir"] = str(venv_dir)
    try:
        venv_cmd = [sys.executable, "-m", "venv", str(venv_dir)]
        venv_result = run_command(venv_cmd, cwd=ROOT, timeout=args.timeout)
        report["commands"].append(venv_result)
        if venv_result.get("returncode") != 0:
            report["status"] = "venv_failed"
            return

        python = venv_python(venv_dir)
        pip_cmd = [str(python), "-m", "pip", "install", "--disable-pip-version-check", *package_names]
        pip_result = run_command(pip_cmd, cwd=ROOT, timeout=args.timeout)
        report["commands"].append(pip_result)
        if pip_result.get("returncode") != 0:
            report["status"] = "install_failed"
            return

        probe_cmd = [str(python), str(WRAPPER_PROBE_SCRIPT), "--output", str(isolated_report)]
        probe_result = run_command(probe_cmd, cwd=ROOT, timeout=args.timeout)
        report["commands"].append(probe_result)
        if probe_result.get("returncode") != 0:
            report["status"] = "probe_failed"
            return

        report["status"] = "completed"
        report["probe_report"] = load_json(isolated_report) if isolated_report.exists() else None
    finally:
        if not args.keep_venv and temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)
            report["temp_root_removed"] = True
        write_json(Path(args.output), report)

    print(json.dumps({"status": report["status"], "wrapper": args.wrapper}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
