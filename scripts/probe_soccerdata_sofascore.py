from __future__ import annotations

import argparse
import importlib
import inspect
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "providers" / "soccerdata_sofascore_probe.json"
REPORT_PATH = ROOT / "reports" / "soccerdata_sofascore_probe.json"
RAW_DIR = ROOT / "data" / "raw" / "experimental" / "soccerdata"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def configure_soccerdata_dir() -> None:
    os.environ.setdefault("SOCCERDATA_DIR", str(RAW_DIR))
    os.environ.setdefault("SOCCERDATA_NOSTORE", "False")


def import_soccerdata() -> tuple[Any | None, dict[str, Any]]:
    configure_soccerdata_dir()
    try:
        module = importlib.import_module("soccerdata")
    except Exception as exc:  # noqa: BLE001 - report import failure, do not fail the probe.
        return None, {
            "available": False,
            "error": str(exc),
        }
    return module, {
        "available": True,
        "version": getattr(module, "__version__", None),
        "module_path": getattr(module, "__file__", None),
    }


def dataframe_summary(frame: Any) -> dict[str, Any]:
    try:
        columns = [str(column) for column in frame.columns]
        rows = int(len(frame))
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "invalid_dataframe",
            "error": str(exc),
        }
    return {
        "status": "ok",
        "rows": rows,
        "columns": columns,
        "columns_sample": columns[:30],
    }


def live_schedule_probe(sd: Any, *, leagues: list[str], seasons: list[Any]) -> dict[str, Any]:
    try:
        reader = sd.Sofascore(leagues=leagues, seasons=seasons, no_cache=True, no_store=False)
        schedule = reader.read_schedule()
    except Exception as exc:  # noqa: BLE001 - this is a provider feasibility probe.
        return {
            "status": "provider_error",
            "error": str(exc),
            "leagues": leagues,
            "seasons": seasons,
        }
    return {
        "status": "checked",
        "leagues": leagues,
        "seasons": seasons,
        "schedule": dataframe_summary(schedule),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe soccerdata's Sofascore reader capabilities.")
    parser.add_argument("--live", action="store_true", help="attempt a low-frequency soccerdata Sofascore schedule probe")
    parser.add_argument("--output", default=str(REPORT_PATH), help="probe report output path")
    args = parser.parse_args()

    config = load_json(CONFIG_PATH)
    if not isinstance(config, dict):
        raise TypeError("soccerdata Sofascore probe config must be an object")
    sd, import_report = import_soccerdata()
    live_config = config.get("live_probe") if isinstance(config.get("live_probe"), dict) else {}
    expected = [str(name) for name in config.get("expected_capabilities") or []]
    required_missing = [str(name) for name in config.get("required_but_not_expected") or []]

    class_report: dict[str, Any] = {
        "available": False,
        "methods": [],
        "signature": None,
        "method_coverage": {},
    }
    live_report: dict[str, Any] = {
        "status": "not_requested",
    }
    if sd is not None and hasattr(sd, "Sofascore"):
        cls = sd.Sofascore
        methods = [name for name in dir(cls) if not name.startswith("_")]
        class_report = {
            "available": True,
            "signature": str(inspect.signature(cls)),
            "methods": methods,
            "method_coverage": {
                "expected_present": {name: name in methods for name in expected},
                "advanced_required_present": {name: name in methods for name in required_missing},
            },
        }
        if args.live:
            live_report = live_schedule_probe(
                sd,
                leagues=[str(value) for value in live_config.get("sample_leagues") or []],
                seasons=list(live_config.get("sample_seasons") or []),
            )

    advanced_present = (
        class_report.get("method_coverage", {})
        .get("advanced_required_present", {})
    )
    advanced_available = any(bool(value) for value in advanced_present.values()) if isinstance(advanced_present, dict) else False
    report = {
        "generated_at": utc_now(),
        "scope": "soccerdata_sofascore_experimental_probe",
        "provider": config.get("provider"),
        "policy": config.get("policy"),
        "live": args.live,
        "soccerdata_import": import_report,
        "sofascore_class": class_report,
        "live_probe": live_report,
        "summary": {
            "classification": "experimental_only",
            "production_write_allowed": False,
            "normalized_write_allowed": False,
            "public_api_write_allowed": False,
            "soccerdata_available": bool(import_report.get("available")),
            "sofascore_reader_available": bool(class_report.get("available")),
            "schedule_or_table_capable": bool(
                class_report.get("method_coverage", {})
                .get("expected_present", {})
                .get("read_schedule")
            ),
            "advanced_match_data_capable": advanced_available,
            "conclusion": (
                "soccerdata Sofascore can help with schedule/table feasibility checks, "
                "but it does not expose match statistics, lineups, shotmap/xG, player ratings, or PPDA inputs."
            ),
        },
        "recommended_next_steps": [
            "Do not use soccerdata Sofascore as the source for possession/passing/PPDA/shots/xG.",
            "If a live probe is needed, keep it low-frequency and only under data/raw/experimental/soccerdata.",
            "Use soccerdata for endpoint/library feasibility only; continue API-FOOTBALL or authorized providers for production stats.",
            "Evaluate tunjayoff/sofascore_scraper separately if match statistics endpoints need to be tested through a specialized scraper.",
        ],
        "raw_dir": rel(RAW_DIR),
    }
    write_json(Path(args.output), report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
