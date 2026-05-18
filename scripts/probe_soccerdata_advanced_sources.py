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
CONFIG_PATH = ROOT / "configs" / "providers" / "soccerdata_advanced_sources_probe.json"
REPORT_PATH = ROOT / "reports" / "soccerdata_advanced_sources_probe.json"
RAW_DIR = ROOT / "data" / "raw" / "experimental" / "soccerdata"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def configure_soccerdata_dir() -> None:
    os.environ.setdefault("SOCCERDATA_DIR", str(RAW_DIR))


def import_soccerdata() -> tuple[Any | None, dict[str, Any]]:
    configure_soccerdata_dir()
    try:
        module = importlib.import_module("soccerdata")
    except Exception as exc:  # noqa: BLE001 - capability probe must report import failures.
        return None, {"available": False, "error": str(exc)}
    return module, {
        "available": True,
        "version": getattr(module, "__version__", None),
        "module_path": getattr(module, "__file__", None),
    }


def method_signature(cls: Any, method: str) -> str | None:
    fn = getattr(cls, method, None)
    if fn is None:
        return None
    try:
        return str(inspect.signature(fn))
    except (TypeError, ValueError):
        return None


def infer_field_support(provider: str, methods: set[str], known_stat_types: dict[str, list[str]]) -> dict[str, str]:
    if provider == "fbref":
        team_match = set(known_stat_types.get("team_match_stats") or [])
        team_season = set(known_stat_types.get("team_season_stats") or [])
        return {
            "possession": "season_level_possible" if "standard" in team_season else "not_exposed",
            "shots": "match_level_possible" if "shooting" in team_match else "not_exposed",
            "shots_on_target": "match_level_possible" if "shooting" in team_match else "not_exposed",
            "passes": "season_level_possible" if "standard" in team_season else "not_exposed",
            "pass_accuracy": "season_level_possible" if "standard" in team_season else "not_exposed",
            "xg": "season_or_match_possible_but_must_live_verify",
            "shotmap": "not_exposed",
            "lineups": "method_available" if "read_lineup" in methods else "not_exposed",
            "player_ratings": "not_exposed",
            "ppda": "not_exposed",
        }
    if provider == "whoscored":
        return {
            "possession": "event_derived_possible_but_requires_live_verify" if "read_events" in methods else "not_exposed",
            "shots": "event_derived_possible_but_requires_live_verify" if "read_events" in methods else "not_exposed",
            "shots_on_target": "event_derived_possible_but_requires_live_verify" if "read_events" in methods else "not_exposed",
            "passes": "event_derived_possible_but_requires_live_verify" if "read_events" in methods else "not_exposed",
            "pass_accuracy": "event_derived_possible_but_requires_live_verify" if "read_events" in methods else "not_exposed",
            "xg": "not_exposed",
            "shotmap": "not_exposed",
            "lineups": "not_exposed",
            "player_ratings": "not_exposed_by_reader",
            "ppda": "event_derived_possible_but_requires_live_verify" if "read_events" in methods else "not_exposed",
        }
    if provider == "fotmob":
        return {
            "possession": "reader_missing_in_installed_soccerdata",
            "shots": "reader_missing_in_installed_soccerdata",
            "shots_on_target": "reader_missing_in_installed_soccerdata",
            "passes": "reader_missing_in_installed_soccerdata",
            "pass_accuracy": "reader_missing_in_installed_soccerdata",
            "xg": "reader_missing_in_installed_soccerdata",
            "shotmap": "reader_missing_in_installed_soccerdata",
            "lineups": "reader_missing_in_installed_soccerdata",
            "player_ratings": "reader_missing_in_installed_soccerdata",
            "ppda": "reader_missing_in_installed_soccerdata",
        }
    return {}


def probe_provider(sd: Any | None, provider: dict[str, Any]) -> dict[str, Any]:
    reader_name = str(provider.get("reader") or "")
    cls = getattr(sd, reader_name, None) if sd is not None else None
    expected_methods = [str(name) for name in provider.get("expected_methods") or []]
    known_stat_types = provider.get("known_stat_types") if isinstance(provider.get("known_stat_types"), dict) else {}
    if cls is None:
        return {
            "provider": provider.get("provider"),
            "display_name": provider.get("display_name"),
            "reader": reader_name,
            "reader_available": False,
            "method_coverage": {name: False for name in expected_methods},
            "field_support": infer_field_support(str(provider.get("provider") or ""), set(), known_stat_types),
            "classification": "experimental_only",
            "conclusion": "reader_not_available_in_installed_soccerdata",
        }

    methods = {name for name in dir(cls) if not name.startswith("_")}
    method_coverage = {name: name in methods for name in expected_methods}
    signatures = {
        name: method_signature(cls, name)
        for name, present in method_coverage.items()
        if present
    }
    field_support = infer_field_support(str(provider.get("provider") or ""), methods, known_stat_types)
    return {
        "provider": provider.get("provider"),
        "display_name": provider.get("display_name"),
        "reader": reader_name,
        "reader_available": True,
        "reader_signature": str(inspect.signature(cls)),
        "methods": sorted(methods),
        "method_coverage": method_coverage,
        "method_signatures": signatures,
        "known_stat_types": known_stat_types,
        "field_support": field_support,
        "classification": "experimental_only",
        "conclusion": conclusion_for_provider(str(provider.get("provider") or ""), field_support),
    }


def conclusion_for_provider(provider: str, field_support: dict[str, str]) -> str:
    if provider == "fbref":
        return "usable_for_experimental_fbref_stats_probe; not a World Cup production source and xG/pass fields require live verification"
    if provider == "whoscored":
        return "usable_for_experimental_events_probe; high scraping/selenium risk and not a direct xG/player-rating source through soccerdata"
    if provider == "fotmob":
        return "not_available_in_installed_soccerdata; evaluate separate FotMob package or direct experimental probe if needed"
    return "experimental_only"


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe soccerdata readers for FBref/FotMob/WhoScored advanced data capability.")
    parser.add_argument("--output", default=str(REPORT_PATH), help="probe report output path")
    args = parser.parse_args()

    config = load_json(CONFIG_PATH)
    if not isinstance(config, dict):
        raise TypeError("advanced source probe config must be an object")
    sd, import_report = import_soccerdata()
    providers = [row for row in config.get("providers") or [] if isinstance(row, dict)]
    rows = [probe_provider(sd, provider) for provider in providers]
    summary = {
        "classification": "experimental_only",
        "production_write_allowed": False,
        "normalized_write_allowed": False,
        "public_api_write_allowed": False,
        "soccerdata_available": bool(import_report.get("available")),
        "provider_count": len(rows),
        "reader_available_count": sum(1 for row in rows if row.get("reader_available")),
        "providers_with_match_stats_probe_path": [
            row["provider"]
            for row in rows
            if row.get("reader_available")
            and (
                row.get("method_coverage", {}).get("read_team_match_stats")
                or row.get("method_coverage", {}).get("read_events")
            )
        ],
        "providers_without_installed_reader": [
            row["provider"] for row in rows if not row.get("reader_available")
        ],
    }
    report = {
        "generated_at": utc_now(),
        "scope": "soccerdata_fbref_fotmob_whoscored_capability_probe",
        "policy": config.get("policy"),
        "soccerdata_import": import_report,
        "summary": summary,
        "providers": rows,
        "target_fields": config.get("target_fields") or [],
        "recommended_next_steps": [
            "Use FBref only for experimental/statistical feasibility; live scrape must remain outside normalized/public until verified.",
            "Do not rely on installed soccerdata for FotMob; no FotMob reader is present in soccerdata 1.9.0.",
            "Use WhoScored only as a high-risk experimental events probe; Selenium/anti-bot and authorization risks remain.",
            "Keep PPDA null unless event-level pass and defensive-action data are verified and the calculation window is documented.",
        ],
        "raw_dir": rel(RAW_DIR),
    }
    write_json(Path(args.output), report)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
