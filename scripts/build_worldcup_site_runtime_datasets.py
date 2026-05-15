from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = ROOT / "data" / "normalized"
PUBLIC_DIR = ROOT / "data" / "public"
REPORTS_DIR = ROOT / "reports"

UPDATED_AT = "2026-05-15T00:00:00Z"

MASTER_TO_PUBLIC = {
    "world_cup_2026_site_groups_master.json": "worldcup-site-groups.json",
    "world_cup_2026_site_group_fixtures_master.json": "worldcup-site-group-fixtures.json",
    "world_cup_2026_site_group_stage_matches_master.json": "worldcup-site-group-stage-matches.json",
    "world_cup_2026_site_bracket_master.json": "worldcup-site-bracket.json",
    "world_cup_2026_site_full_schedule_master.json": "worldcup-site-full-schedule.json",
    "world_cup_2026_site_finals_results_master.json": "worldcup-site-finals-results.json",
    "world_cup_2026_site_finals_coverage_master.json": "worldcup-site-finals-coverage.json",
    "world_cup_2026_site_qualifier_matches_master.json": "worldcup-site-qualifier-matches.json",
    "world_cup_2026_site_qualifier_missing_data_master.json": "worldcup-site-qualifier-missing-data.json",
    "world_cup_2026_site_qualifier_source_reports_master.json": "worldcup-site-qualifier-source-reports.json",
}

REPORT_PATH = REPORTS_DIR / "worldcup_site_runtime_publish_report.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def payload_size(payload: object) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        return len(payload)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish platform-owned worldcup/2026 compatible site datasets.")
    parser.add_argument("--report-output", default=str(REPORT_PATH), help="runtime site dataset publish report path")
    args = parser.parse_args()

    dataset_counts: dict[str, int] = {}
    for master_name, public_name in MASTER_TO_PUBLIC.items():
        master_path = NORMALIZED_DIR / master_name
        public_path = PUBLIC_DIR / public_name
        payload = load_json(master_path)
        write_json(public_path, payload)
        dataset_counts[public_name] = payload_size(payload)

    report = {
        "generated_at": UPDATED_AT,
        "source_type": "platform_owned_site_masters",
        "datasets": dataset_counts,
    }
    write_json(Path(args.report_output), report)
    print(f"Published {len(dataset_counts)} worldcup site runtime datasets from platform-owned masters")
    print(f"Wrote worldcup site runtime publish report to {args.report_output}")


if __name__ == "__main__":
    main()
