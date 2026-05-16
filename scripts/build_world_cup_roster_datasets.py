from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = ROOT / "data" / "normalized"
PUBLIC_DIR = ROOT / "data" / "public"
REPORTS_DIR = ROOT / "reports"

ROSTERS_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_rosters_master.json"
PLAYERS_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_players_master.json"
ROSTERS_PUBLIC_PATH = PUBLIC_DIR / "rosters.json"
PLAYERS_PUBLIC_PATH = PUBLIC_DIR / "players.json"


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
    parser = argparse.ArgumentParser(description="Publish World Cup roster/player datasets from normalized masters.")
    parser.add_argument("--rosters-master", default=str(ROSTERS_MASTER_PATH), help="normalized rosters master")
    parser.add_argument("--players-master", default=str(PLAYERS_MASTER_PATH), help="normalized players master")
    parser.add_argument("--rosters-output", default=str(ROSTERS_PUBLIC_PATH), help="public rosters output")
    parser.add_argument("--players-output", default=str(PLAYERS_PUBLIC_PATH), help="public players output")
    parser.add_argument(
        "--report-output",
        default=str(REPORTS_DIR / "world_cup_roster_publish_report.json"),
        help="publish report output",
    )
    args = parser.parse_args()

    rosters = ensure_list(load_json(Path(args.rosters_master)), "rosters master")
    players = ensure_list(load_json(Path(args.players_master)), "players master")

    rosters = sorted(rosters, key=lambda item: (str(item.get("team_id") or ""), str(item.get("roster_type") or "")))
    players = sorted(players, key=lambda item: (str(item.get("team_id") or ""), str(item.get("name") or "")))

    write_json(Path(args.rosters_output), rosters)
    write_json(Path(args.players_output), players)
    report = {
        "rosters_master": str(args.rosters_master),
        "players_master": str(args.players_master),
        "rosters_output": str(args.rosters_output),
        "players_output": str(args.players_output),
        "rosters_count": len(rosters),
        "players_count": len(players),
        "status": "empty_contract_ready" if not rosters and not players else "published",
    }
    write_json(Path(args.report_output), report)
    print(f"Published {len(rosters)} rosters to {args.rosters_output}")
    print(f"Published {len(players)} players to {args.players_output}")


if __name__ == "__main__":
    main()
