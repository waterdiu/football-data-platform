from __future__ import annotations

import json
from pathlib import Path

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
REPORTS_DIR = ROOT / "reports"
OUTPUT_PATH = REPORTS_DIR / "automation-readiness.json"

UPDATED_AT = "2026-05-15T00:00:00Z"

SCRIPT_DEPENDENCIES = {
    "import_worldcup_site_local_data.mjs": {
        "external_repos": ["worldcup/2026"],
        "reason": "Imports local TypeScript data modules from the worldcup site repository.",
    },
    "build_worldcup_site_runtime_datasets.py": {
        "external_repos": [],
        "reason": "Publishes worldcup/2026-compatible site datasets from platform-owned master files.",
    },
    "build_world_cup_fixtures.py": {
        "external_repos": [],
        "reason": "Rebuilds fixtures from platform-owned public mirrors and teams.",
    },
    "build_world_cup_results.py": {
        "external_repos": [],
        "reason": "Builds results from platform-owned local mirrors and normalized fixtures.",
    },
    "build_world_cup_standings.py": {
        "external_repos": [],
        "reason": "Builds standings from platform-owned fixtures and results.",
    },
    "build_world_cup_detail_datasets.py": {
        "external_repos": [],
        "reason": "Extracts finals detail datasets from platform-owned migrated finals results.",
    },
    "build_world_cup_model_datasets.py": {
        "external_repos": ["world-cup-predictor"],
        "reason": "Reads predictor outputs and context snapshots from the predictor repository.",
    },
    "build_world_cup_model_runtime_datasets.py": {
        "external_repos": [],
        "reason": "Publishes model runtime datasets from platform-owned model master files.",
    },
    "build_world_cup_injury_evidence.py": {
        "external_repos": [],
        "reason": "Derives low-confidence injury/suspension evidence from platform-owned prematch context rows.",
    },
    "build_world_cup_coverage.py": {
        "external_repos": [],
        "reason": "Builds coverage from platform-owned public and model datasets.",
    },
    "publish_worldcup_2026_api.py": {
        "external_repos": [],
        "reason": "Publishes runtime API from platform-owned public datasets.",
    },
    "publish_world_cup_predictor_api.py": {
        "external_repos": [],
        "reason": "Publishes predictor-facing compatibility and standard datasets from platform-owned masters.",
    },
    "build_source_health_report.py": {
        "external_repos": [],
        "reason": "Aggregates platform-owned reports and datasets into a health report.",
    },
    "build_data_quality_report.py": {
        "external_repos": [],
        "reason": "Summarizes World Cup data quality checks and human runbooks from platform-owned reports.",
    },
    "build_worldcup_2026_runtime_health.py": {
        "external_repos": [],
        "reason": "Builds runtime health from platform-owned manifest and source health report.",
    },
    "build_world_cup_predictor_runtime_health.py": {
        "external_repos": [],
        "reason": "Builds predictor runtime health from platform-owned predictor manifest and reports.",
    },
    "publish_qualifier_data.py": {
        "external_repos": [],
        "reason": "Publishes qualifier public datasets from the platform-owned master source.",
    },
    "capture_world_cup_context_from_predictor.py": {
        "external_repos": ["world-cup-predictor"],
        "reason": "Triggers context capture inside the predictor repository.",
    },
    "import_qualifier_matches.mjs": {
        "external_repos": ["worldcup/2026"],
        "reason": "Imports qualifier source data from the worldcup site repository.",
    },
    "import_world_cup_predictions.py": {
        "external_repos": ["world-cup-predictor"],
        "reason": "Imports processed predictions from the predictor repository.",
    },
}

WORLD_CUP_PIPELINE = [
    "build_worldcup_site_runtime_datasets.py",
    "build_world_cup_fixtures.py",
    "build_world_cup_results.py",
    "build_world_cup_standings.py",
    "build_world_cup_detail_datasets.py",
    "build_world_cup_injury_evidence.py",
    "build_world_cup_model_runtime_datasets.py",
    "build_world_cup_coverage.py",
    "publish_qualifier_data.py",
    "publish_worldcup_2026_api.py",
    "publish_world_cup_predictor_api.py",
    "build_source_health_report.py",
    "build_data_quality_report.py",
    "build_worldcup_2026_runtime_health.py",
    "build_world_cup_predictor_runtime_health.py",
]


def main() -> None:
    script_rows = []
    blocking_scripts = []
    for script_name, meta in SCRIPT_DEPENDENCIES.items():
        external_repos = list(meta["external_repos"])
        row = {
            "script": script_name,
            "exists": (SCRIPTS_DIR / script_name).exists(),
            "external_repos": external_repos,
            "self_contained": len(external_repos) == 0,
            "reason": meta["reason"],
        }
        script_rows.append(row)
        if external_repos:
            blocking_scripts.append(script_name)

    world_cup_pipeline = []
    pipeline_blockers = []
    for script_name in WORLD_CUP_PIPELINE:
        external_repos = SCRIPT_DEPENDENCIES.get(script_name, {}).get("external_repos", [])
        row = {
            "script": script_name,
            "self_contained": len(external_repos) == 0,
            "external_repos": external_repos,
        }
        world_cup_pipeline.append(row)
        if external_repos:
            pipeline_blockers.append(row)

    blocking_repositories = sorted(
        {
            repo
            for row in pipeline_blockers
            for repo in row["external_repos"]
        }
    )
    optional_external_repositories = sorted(
        {
            repo
            for row in script_rows
            for repo in row["external_repos"]
        }
    )

    payload = {
        "generated_at": UPDATED_AT,
        "repository": "waterdiu/football-data-platform",
        "automation_readiness": {
            "pages_runtime_monitoring_ready": True,
            "github_actions_full_rebuild_ready": len(pipeline_blockers) == 0,
            "blocking_script_count": len(pipeline_blockers),
        },
        "blocking_repositories": blocking_repositories,
        "optional_external_repositories": optional_external_repositories,
        "world_cup_pipeline": world_cup_pipeline,
        "pipeline_blockers": pipeline_blockers,
        "script_inventory": script_rows,
        "recommended_next_steps": [
            "Use .github/workflows/rebuild-worldcup-data.yml as the serial scheduled rebuild workflow.",
            "Keep its concurrency group enabled so overlapping publish jobs cannot write the same JSON outputs concurrently.",
            "Configure provider secrets when paid or useful sources are available: API_FOOTBALL_KEY, OPENWEATHER_API_KEY, FOOTBALL_DATA_API_KEY, THE_ODDS_API_KEY, THE_ODDS_API_SOCCER_ENABLED.",
            "Keep import_worldcup_site_local_data.mjs and build_world_cup_model_datasets.py only as optional manual backfill tools.",
            "If future datasets add sibling-repo dependencies again, update this report and keep them out of the default publish pipeline.",
        ],
    }
    write_json(OUTPUT_PATH, payload)
    print(f"Wrote automation readiness report to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
