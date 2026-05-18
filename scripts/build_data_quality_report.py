from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "data" / "public"
MODEL_DIR = ROOT / "data" / "model"
REPORTS_DIR = ROOT / "reports"
OUTPUT_PATH = REPORTS_DIR / "data-quality.json"

GENERATED_AT = "2026-05-17T00:00:00Z"
EXPECTED_WORLD_CUP_FIXTURES = 104


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def row_count(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("fixtures", "matches", "data"):
            if isinstance(payload.get(key), list):
                return len(payload[key])
        return len(payload)
    return 0


def status_counts(rows: Any, field: str = "source_status") -> dict[str, int]:
    counts: dict[str, int] = {}
    if not isinstance(rows, list):
        return counts
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = str(row.get(field) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def add_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    status: str,
    severity: str,
    title: str,
    detail: str,
    runbook: str,
    evidence: dict[str, Any] | None = None,
) -> None:
    checks.append(
        {
            "id": check_id,
            "status": status,
            "severity": severity,
            "title": title,
            "detail": detail,
            "evidence": evidence or {},
            "runbook": runbook,
        }
    )


def runtime_dataset(report: Any, dataset: str) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    for row in report.get("datasets") or []:
        if isinstance(row, dict) and row.get("dataset") == dataset:
            return row
    return {}


def main() -> None:
    fixtures = load_json(PUBLIC_DIR / "fixtures.json")
    coverage = load_json(PUBLIC_DIR / "data-coverage.json")
    predictions = load_json(PUBLIC_DIR / "predictions.json")
    odds = load_json(MODEL_DIR / "odds_snapshots.json")
    lineups = load_json(MODEL_DIR / "lineups.json")
    injuries = load_json(MODEL_DIR / "injuries.json")
    weather = load_json(MODEL_DIR / "weather.json")
    prematch_context = load_json(MODEL_DIR / "prematch_context.json")
    team_advanced_stats = load_json(PUBLIC_DIR / "team-advanced-stats.json")
    runtime_collection = load_json(REPORTS_DIR / "world_cup_runtime_collection_report.json")
    automation_readiness = load_json(REPORTS_DIR / "automation-readiness.json")
    free_odds_probe = load_json(REPORTS_DIR / "free_odds_source_probe.json")

    checks: list[dict[str, Any]] = []

    fixture_count = row_count(fixtures)
    add_check(
        checks,
        check_id="world_cup_fixture_count",
        status="pass" if fixture_count == EXPECTED_WORLD_CUP_FIXTURES else "blocked",
        severity="P0",
        title="World Cup fixture count",
        detail=f"Expected {EXPECTED_WORLD_CUP_FIXTURES} canonical fixtures; found {fixture_count}.",
        evidence={"expected": EXPECTED_WORLD_CUP_FIXTURES, "actual": fixture_count},
        runbook="If this fails, stop publishing consumers and rebuild fixtures from the canonical platform fixture source.",
    )

    coverage_count = row_count(coverage)
    add_check(
        checks,
        check_id="world_cup_coverage_count",
        status="pass" if coverage_count == EXPECTED_WORLD_CUP_FIXTURES else "attention",
        severity="P0",
        title="World Cup coverage row count",
        detail=f"Coverage should have one row per fixture; found {coverage_count}.",
        evidence={"expected": EXPECTED_WORLD_CUP_FIXTURES, "actual": coverage_count},
        runbook="Run scripts/build_world_cup_coverage.py after model/public datasets are published.",
    )

    prediction_count = row_count(predictions)
    add_check(
        checks,
        check_id="world_cup_prediction_count",
        status="pass" if prediction_count == EXPECTED_WORLD_CUP_FIXTURES else "attention",
        severity="P1",
        title="Published prediction count",
        detail=f"Published predictions should cover all fixtures; found {prediction_count}.",
        evidence={"expected": EXPECTED_WORLD_CUP_FIXTURES, "actual": prediction_count},
        runbook="Ask the predictor project to regenerate predictions and write them to platform inbox, then run scripts/publish_predictor_inbox.py.",
    )

    readiness = {}
    if isinstance(automation_readiness, dict):
        readiness = automation_readiness.get("automation_readiness") or {}
    automation_ready = bool(readiness.get("github_actions_full_rebuild_ready"))
    add_check(
        checks,
        check_id="automation_full_rebuild_ready",
        status="pass" if automation_ready else "attention",
        severity="P1",
        title="Full rebuild automation readiness",
        detail="Default World Cup publish pipeline must be self-contained and runnable in GitHub Actions.",
        evidence=readiness,
        runbook="Run scripts/build_automation_readiness_report.py and remove any default pipeline dependency on sibling repositories.",
    )

    odds_count = row_count(odds)
    free_odds_summary = free_odds_probe.get("summary") if isinstance(free_odds_probe, dict) else {}
    free_odds_providers = free_odds_probe.get("providers") if isinstance(free_odds_probe, dict) else []
    bsd_probe = {}
    if isinstance(free_odds_providers, list):
        for provider in free_odds_providers:
            if isinstance(provider, dict) and provider.get("provider") == "bsd_bzzoiro":
                bsd_probe = provider
                break
    add_check(
        checks,
        check_id="world_cup_runtime_odds",
        status="attention" if odds_count == 0 else "pass",
        severity="P0",
        title="World Cup runtime odds snapshots",
        detail=f"World Cup odds snapshots currently contain {odds_count} rows.",
        evidence={
            "rows": odds_count,
            "free_odds_probe_summary": free_odds_summary,
            "bsd_probe_status": bsd_probe.get("probe_status"),
            "bsd_classification": bsd_probe.get("probe_classification"),
            "bsd_market_verdict": bsd_probe.get("market_verdict"),
        },
        runbook="Only enable a soccer-capable paid or approved odds provider. TheOddsAPI free key is not soccer-capable. For free-source validation, get BSD_API_TOKEN and run scripts/probe_free_odds_sources.py --live; do not write probe rows into normalized/model until approved.",
    )

    lineup_counts = status_counts(lineups)
    add_check(
        checks,
        check_id="world_cup_lineups",
        status="pass" if lineup_counts.get("available", 0) else "info",
        severity="P1",
        title="World Cup lineup availability",
        detail="Confirmed lineup rows are expected only inside the pre-match lineup window.",
        evidence={"rows": row_count(lineups), "source_status_counts": lineup_counts},
        runbook="If inside T-90/T-60/T-30 and still unavailable, check API-FOOTBALL plan coverage or official FIFA match centre fallback.",
    )

    injury_counts = status_counts(injuries)
    injury_runtime = runtime_dataset(runtime_collection, "injuries")
    injury_status = injury_runtime.get("status") or next(iter(injury_counts), "unknown")
    add_check(
        checks,
        check_id="world_cup_injuries",
        status="attention" if injury_status in {"missing_auth", "plan_restricted", "provider_error"} else "pass",
        severity="P0",
        title="World Cup injury source status",
        detail=f"Injury source status is {injury_status}. Placeholder rows are not proof of no injuries.",
        evidence={
            "rows": row_count(injuries),
            "source_status_counts": injury_counts,
            "runtime_status": injury_runtime.get("status"),
            "runtime_status_reason": injury_runtime.get("status_reason"),
        },
        runbook="Use official/FIFA/news manual evidence for critical absences until a provider plan with World Cup coverage is approved.",
    )

    weather_counts = status_counts(weather)
    weather_available = weather_counts.get("available", 0)
    weather_unavailable = weather_counts.get("unavailable", 0)
    weather_status = "pass" if weather_available else "info" if weather_unavailable else "attention"
    add_check(
        checks,
        check_id="world_cup_weather",
        status=weather_status,
        severity="P1",
        title="World Cup weather forecast coverage",
        detail="Weather rows before forecast windows should be explicit placeholders, not missing data.",
        evidence={"rows": row_count(weather), "source_status_counts": weather_counts},
        runbook="When matches enter the forecast window, run scripts/collect_world_cup_runtime_data.py with weather provider keys or Open-Meteo fallback.",
    )

    prematch_rows = row_count(prematch_context)
    add_check(
        checks,
        check_id="world_cup_prematch_context",
        status="pass" if prematch_rows == EXPECTED_WORLD_CUP_FIXTURES else "attention",
        severity="P1",
        title="World Cup prematch context rows",
        detail=f"Prematch context should publish one row per fixture; found {prematch_rows}.",
        evidence={"expected": EXPECTED_WORLD_CUP_FIXTURES, "actual": prematch_rows},
        runbook="Run scripts/collect_world_cup_runtime_data.py and scripts/build_world_cup_model_runtime_datasets.py; inspect source freshness in source-health.json.",
    )

    advanced_count = row_count(team_advanced_stats)
    advanced_status_counts = status_counts(team_advanced_stats)
    process_available = 0
    if isinstance(team_advanced_stats, list):
        for row in team_advanced_stats:
            if not isinstance(row, dict):
                continue
            if any(row.get(field) is not None for field in ("possession_pct", "pass_accuracy_pct", "shots_per_match", "ppda", "xg_for_per_match")):
                process_available += 1
    add_check(
        checks,
        check_id="world_cup_team_advanced_stats",
        status="pass" if process_available else "info" if advanced_count else "attention",
        severity="P1",
        title="World Cup team advanced stats baseline",
        detail=(
            f"Team advanced stats contain {advanced_count} team rows; process-data fields are available for "
            f"{process_available} teams."
        ),
        evidence={
            "rows": advanced_count,
            "source_status_counts": advanced_status_counts,
            "process_data_team_count": process_available,
        },
        runbook="Baseline rows may use recent-score form proxy. Keep possession/pass/PPDA/shots/xG null until a verified process-data source is approved.",
    )

    status_summary: dict[str, int] = {}
    severity_summary: dict[str, int] = {}
    for check in checks:
        status_summary[check["status"]] = status_summary.get(check["status"], 0) + 1
        severity_summary[check["severity"]] = severity_summary.get(check["severity"], 0) + 1

    payload = {
        "generated_at": GENERATED_AT,
        "scope": "worldcup_2026",
        "summary": {
            "checks": len(checks),
            "status_counts": dict(sorted(status_summary.items())),
            "severity_counts": dict(sorted(severity_summary.items())),
            "blocking_count": status_summary.get("blocked", 0),
            "attention_count": status_summary.get("attention", 0),
        },
        "checks": checks,
    }
    write_json(OUTPUT_PATH, payload)
    print(f"Wrote data quality report to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
