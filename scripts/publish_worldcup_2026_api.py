from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "data" / "public"
API_ROOT = PUBLIC_DIR / "api" / "worldcup" / "2026"
UPDATED_AT = "2026-05-15T00:00:00Z"
BASE_URL = "https://waterdiu.github.io/football-data-platform"

CORE_DATASETS = {
    "canonical_teams": "canonical_teams.json",
    "teams": "teams.json",
    "fixtures": "fixtures.json",
    "results": "results.json",
    "standings": "standings.json",
    "predictions": "predictions.json",
    "data_coverage": "data-coverage.json",
    "qualifier_events": "qualifier-events.json",
    "qualifier_lineups": "qualifier-lineups.json",
    "qualifier_match_stats": "qualifier-match-stats.json",
}

SITE_DATASETS = {
    "groups": "worldcup-site-groups.json",
    "group_fixtures": "worldcup-site-group-fixtures.json",
    "group_stage_matches": "worldcup-site-group-stage-matches.json",
    "bracket": "worldcup-site-bracket.json",
    "full_schedule": "worldcup-site-full-schedule.json",
    "finals_results": "worldcup-site-finals-results.json",
    "finals_coverage": "worldcup-site-finals-coverage.json",
    "qualifier_matches": "qualifier-matches.json",
    "qualifier_missing_data": "worldcup-site-qualifier-missing-data.json",
    "qualifier_source_reports": "worldcup-site-qualifier-source-reports.json",
}


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_dataset(source_filename: str, target_path: Path) -> object:
    payload = load_json(PUBLIC_DIR / source_filename)
    write_json(target_path, payload)
    return payload


def payload_count(payload: object) -> int | None:
    if isinstance(payload, list):
        return len(payload)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a runtime-facing static API for worldcup/2026.")
    parser.add_argument("--output-root", default=str(API_ROOT), help="API output root path")
    args = parser.parse_args()

    output_root = Path(args.output_root)
    core_dir = output_root / "core"
    site_dir = output_root / "site"

    core_payloads: dict[str, object] = {}
    for key, filename in CORE_DATASETS.items():
        target_name = filename
        core_payloads[key] = copy_dataset(filename, core_dir / target_name)

    site_payloads: dict[str, object] = {}
    for key, filename in SITE_DATASETS.items():
        target_name = filename.replace("worldcup-site-", "")
        site_payloads[key] = copy_dataset(filename, site_dir / target_name)

    write_json(
        core_dir / "bundle.json",
        {
            "generated_at": UPDATED_AT,
            "competition_id": "fifa_world_cup",
            "season_id": "2026",
            "datasets": core_payloads,
        },
    )
    write_json(
        site_dir / "bundle.json",
        {
            "generated_at": UPDATED_AT,
            "competition_id": "fifa_world_cup",
            "season_id": "2026",
            "datasets": site_payloads,
        },
    )

    manifest = {
        "generated_at": UPDATED_AT,
        "competition_id": "fifa_world_cup",
        "season_id": "2026",
        "version": "v1",
        "runtime_contract": {
            "preferred_site_entrypoint": "./site/bundle.json",
            "preferred_core_entrypoint": "./core/bundle.json",
            "preferred_site_url": f"{BASE_URL}/api/worldcup/2026/site/bundle.json",
            "preferred_core_url": f"{BASE_URL}/api/worldcup/2026/core/bundle.json",
            "site": {
                key: {
                    "path": f"./site/{filename.replace('worldcup-site-', '')}",
                    "url": f"{BASE_URL}/api/worldcup/2026/site/{filename.replace('worldcup-site-', '')}",
                    "count": payload_count(site_payloads[key]),
                }
                for key, filename in SITE_DATASETS.items()
            },
            "core": {
                key: {
                    "path": f"./core/{filename}",
                    "url": f"{BASE_URL}/api/worldcup/2026/core/{filename}",
                    "count": payload_count(core_payloads[key]),
                }
                for key, filename in CORE_DATASETS.items()
            },
        },
        "integration_notes": [
            "worldcup/2026 should fetch this static JSON API at runtime instead of syncing TS files for freshness-sensitive pages.",
            "site endpoints preserve the shape of migrated worldcup/2026 datasets for low-risk adoption.",
            "core endpoints expose normalized platform datasets for longer-term page and model convergence.",
        ],
        "counts": {
            "core": {key: payload_count(payload) for key, payload in core_payloads.items()},
            "site": {key: payload_count(payload) for key, payload in site_payloads.items()},
        },
    }
    write_json(output_root / "manifest.json", manifest)

    print(f"Published World Cup 2026 API manifest to {output_root / 'manifest.json'}")
    print(f"Published World Cup 2026 site bundle to {site_dir / 'bundle.json'}")
    print(f"Published World Cup 2026 core bundle to {core_dir / 'bundle.json'}")


if __name__ == "__main__":
    main()
