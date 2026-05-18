from __future__ import annotations

import argparse
import importlib
import inspect
import json
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "providers" / "sofascore_wrapper_probe.json"
REPORT_PATH = ROOT / "reports" / "sofascore_wrapper_probe.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def import_module_candidate(module_name: str) -> tuple[Any | None, str | None]:
    try:
        return importlib.import_module(module_name), None
    except Exception as exc:  # noqa: BLE001 - package probe must report all import failures.
        return None, str(exc)


def package_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def public_methods(obj: Any) -> list[str]:
    methods: set[str] = set()
    for name in dir(obj):
        if name.startswith("_"):
            continue
        value = getattr(obj, name, None)
        if callable(value):
            methods.add(name)
    return sorted(methods)


def class_reports(module: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, value in inspect.getmembers(module, inspect.isclass):
        if getattr(value, "__module__", "").split(".")[0] != module.__name__.split(".")[0]:
            continue
        try:
            signature = str(inspect.signature(value))
        except (TypeError, ValueError):
            signature = None
        rows.append(
            {
                "class_name": name,
                "signature": signature,
                "methods": public_methods(value),
            }
        )
    return rows


def method_name_support(methods: set[str], expected_methods: list[str]) -> dict[str, bool]:
    lowered = {method.casefold(): method for method in methods}
    return {
        method: method.casefold() in lowered
        for method in expected_methods
    }


def infer_target_support(methods: set[str], documented_capabilities: list[str]) -> dict[str, str]:
    haystack = " ".join(sorted(methods | {cap.casefold() for cap in documented_capabilities})).casefold()

    def has_any(tokens: list[str]) -> bool:
        return any(token.casefold() in haystack for token in tokens)

    return {
        "match_statistics": "possible" if has_any(["statistic", "stats"]) else "not_observed",
        "possession": "possible_via_statistics" if has_any(["statistic", "stats"]) else "not_observed",
        "shots": "possible_via_statistics_or_shotmap" if has_any(["statistic", "stats", "shotmap"]) else "not_observed",
        "shots_on_target": "possible_via_statistics" if has_any(["statistic", "stats"]) else "not_observed",
        "passes": "possible_via_statistics" if has_any(["statistic", "stats"]) else "not_observed",
        "pass_accuracy": "possible_via_statistics" if has_any(["statistic", "stats"]) else "not_observed",
        "lineups": "possible" if has_any(["lineup", "match_player_ids"]) else "not_observed",
        "incidents": "possible" if has_any(["incident"]) else "not_observed",
        "shotmap": "possible" if has_any(["shotmap"]) else "not_observed",
        "xg": "possible_via_shotmap" if has_any(["xg", "shotmap"]) else "not_observed",
        "player_ratings": "possible_via_best_players_or_player_stats" if has_any(["best_players", "rating", "player_stats"]) else "not_observed",
        "ppda": "not_observed",
    }


def probe_wrapper(wrapper: dict[str, Any]) -> dict[str, Any]:
    module_candidates = [str(item) for item in wrapper.get("module_candidates") or []]
    package_names = [str(item) for item in wrapper.get("package_names") or []]
    expected_methods = [str(item) for item in wrapper.get("expected_methods") or []]
    documented_capabilities = [str(item) for item in wrapper.get("documented_capabilities") or []]

    versions = {
        package_name: package_version(package_name)
        for package_name in package_names
    }
    module_attempts: list[dict[str, Any]] = []
    imported_module: Any | None = None
    imported_module_name: str | None = None
    for module_name in module_candidates:
        module, error = import_module_candidate(module_name)
        module_attempts.append(
            {
                "module": module_name,
                "available": module is not None,
                "error": error,
                "module_path": getattr(module, "__file__", None) if module is not None else None,
            }
        )
        if module is not None and imported_module is None:
            imported_module = module
            imported_module_name = module_name

    classes = class_reports(imported_module) if imported_module is not None else []
    module_methods = public_methods(imported_module) if imported_module is not None else []
    all_methods = set(module_methods)
    for row in classes:
        all_methods.update(str(method) for method in row.get("methods") or [])

    installed = imported_module is not None or any(version is not None for version in versions.values())
    return {
        "wrapper_id": wrapper.get("wrapper_id"),
        "display_name": wrapper.get("display_name"),
        "project_url": wrapper.get("project_url"),
        "classification": "experimental_only",
        "installed": installed,
        "status": "available" if imported_module is not None else "not_installed",
        "package_versions": versions,
        "module_attempts": module_attempts,
        "imported_module": imported_module_name,
        "module_methods": module_methods,
        "classes": classes,
        "expected_method_coverage": method_name_support(all_methods, expected_methods),
        "documented_capabilities": documented_capabilities,
        "target_field_support_inferred": infer_target_support(all_methods, documented_capabilities),
        "notes": wrapper.get("notes"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe optional Sofascore wrapper packages without live scraping.")
    parser.add_argument("--output", default=str(REPORT_PATH), help="probe report output path")
    args = parser.parse_args()

    config = load_json(CONFIG_PATH)
    if not isinstance(config, dict):
        raise TypeError("Sofascore wrapper probe config must be an object")
    wrappers = [row for row in config.get("wrappers") or [] if isinstance(row, dict)]
    rows = [probe_wrapper(wrapper) for wrapper in wrappers]
    summary = {
        "classification": "experimental_only",
        "production_write_allowed": False,
        "normalized_write_allowed": False,
        "public_api_write_allowed": False,
        "wrapper_count": len(rows),
        "installed_wrapper_count": sum(1 for row in rows if row.get("installed")),
        "available_module_count": sum(1 for row in rows if row.get("status") == "available"),
        "wrappers_requiring_isolated_install": [
            row["wrapper_id"] for row in rows if row.get("status") == "not_installed"
        ],
    }
    report = {
        "generated_at": utc_now(),
        "scope": "sofascore_wrapper_capability_probe",
        "policy": config.get("policy"),
        "summary": summary,
        "target_fields": config.get("target_fields") or [],
        "wrappers": rows,
        "recommended_next_steps": [
            "Do not add any wrapper to platform runtime dependencies until license, maintenance, and anti-bot behavior are reviewed.",
            "If a wrapper is tested, install it only in an isolated environment and write any payloads under data/raw/experimental/sofascore.",
            "Only promote a Sofascore-derived field after proving authorization, stability, field semantics, and match/team/player id mapping.",
            "Keep PPDA null unless pass and defensive-action event inputs are verified with a documented calculation window.",
        ],
    }
    write_json(Path(args.output), report)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
