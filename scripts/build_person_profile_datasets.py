from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = ROOT / "data" / "normalized"
PUBLIC_DIR = ROOT / "data" / "public"
REPORTS_DIR = ROOT / "reports"

DATASETS = {
    "person_team_staff_master.json": "team-staff.json",
    "person_officials_master.json": "officials.json",
    "person_player_ratings_master.json": "player-ratings.json",
    "person_staff_ratings_master.json": "staff-ratings.json",
    "person_official_ratings_master.json": "official-ratings.json",
    "person_style_profiles_master.json": "person-style-profiles.json",
}


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_list(payload: object, label: str) -> list[dict]:
    if not isinstance(payload, list):
        raise TypeError(f"{label} must contain a list")
    return [item for item in payload if isinstance(item, dict)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish person profile datasets from normalized masters.")
    parser.add_argument(
        "--report-output",
        default=str(REPORTS_DIR / "person_profile_publish_report.json"),
        help="publish report output path",
    )
    args = parser.parse_args()

    counts: dict[str, int] = {}
    outputs: dict[str, str] = {}
    for master_filename, public_filename in DATASETS.items():
        rows = ensure_list(load_json(NORMALIZED_DIR / master_filename), master_filename)
        write_json(PUBLIC_DIR / public_filename, rows)
        counts[public_filename] = len(rows)
        outputs[public_filename] = str(PUBLIC_DIR / public_filename)

    report = {
        "status": "published",
        "counts": counts,
        "outputs": outputs,
    }
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
