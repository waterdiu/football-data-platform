from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "data" / "public"
NORMALIZED_DIR = ROOT / "data" / "normalized"

FIXTURES_PATH = PUBLIC_DIR / "fixtures.json"
RESULTS_PATH = PUBLIC_DIR / "results.json"
TEAMS_PATH = PUBLIC_DIR / "teams.json"
NORMALIZED_OUTPUT_PATH = NORMALIZED_DIR / "world_cup_2026_standings.json"
PUBLIC_OUTPUT_PATH = PUBLIC_DIR / "standings.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _score_value(result: dict[str, object], key: str) -> int | None:
    score = result.get("score")
    if not isinstance(score, dict):
        return None
    value = score.get(key)
    return int(value) if isinstance(value, int) else None


def _team_name_lookup(teams: object) -> dict[str, str]:
    if not isinstance(teams, list):
        raise TypeError("teams.json must contain a list")
    lookup: dict[str, str] = {}
    for item in teams:
        if not isinstance(item, dict):
            continue
        team_id = str(item.get("team_id") or "").strip()
        name = str(item.get("name") or "").strip()
        if team_id and name:
            lookup[team_id] = name
    return lookup


def _sort_group_table(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        rows,
        key=lambda item: (
            -int(item["points"]),
            -int(item["goal_difference"]),
            -int(item["goals_for"]),
            str(item["team_name"]),
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build World Cup group standings.")
    parser.add_argument("--normalized-output", default=str(NORMALIZED_OUTPUT_PATH), help="normalized standings output path")
    parser.add_argument("--public-output", default=str(PUBLIC_OUTPUT_PATH), help="public standings output path")
    args = parser.parse_args()

    fixtures = load_json(FIXTURES_PATH)
    results = load_json(RESULTS_PATH)
    teams = load_json(TEAMS_PATH)

    if not isinstance(fixtures, list):
        raise TypeError("fixtures.json must contain a list")
    if not isinstance(results, list):
        raise TypeError("results.json must contain a list")

    team_names = _team_name_lookup(teams)
    results_by_match_id = {str(item["match_id"]): item for item in results if isinstance(item, dict) and "match_id" in item}

    group_table: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)

    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        if str(fixture.get("stage") or "").strip().lower() != "group":
            continue

        group = str(fixture.get("group") or "").strip()
        home_team_id = str(fixture.get("home_team_id") or "").strip()
        away_team_id = str(fixture.get("away_team_id") or "").strip()
        if not group or not home_team_id or not away_team_id:
            continue

        for team_id in (home_team_id, away_team_id):
            if team_id not in group_table[group]:
                group_table[group][team_id] = {
                    "team_id": team_id,
                    "team_name": team_names.get(team_id, team_id),
                    "played": 0,
                    "won": 0,
                    "drawn": 0,
                    "lost": 0,
                    "goals_for": 0,
                    "goals_against": 0,
                    "goal_difference": 0,
                    "points": 0,
                }

        result = results_by_match_id.get(str(fixture.get("match_id") or ""))
        if not isinstance(result, dict):
            continue
        if str(result.get("status") or "").strip().lower() != "finished":
            continue

        home_goals = _score_value(result, "home")
        away_goals = _score_value(result, "away")
        if home_goals is None or away_goals is None:
            continue

        home_row = group_table[group][home_team_id]
        away_row = group_table[group][away_team_id]

        home_row["played"] = int(home_row["played"]) + 1
        away_row["played"] = int(away_row["played"]) + 1
        home_row["goals_for"] = int(home_row["goals_for"]) + home_goals
        home_row["goals_against"] = int(home_row["goals_against"]) + away_goals
        away_row["goals_for"] = int(away_row["goals_for"]) + away_goals
        away_row["goals_against"] = int(away_row["goals_against"]) + home_goals

        if home_goals > away_goals:
            home_row["won"] = int(home_row["won"]) + 1
            away_row["lost"] = int(away_row["lost"]) + 1
            home_row["points"] = int(home_row["points"]) + 3
        elif home_goals < away_goals:
            away_row["won"] = int(away_row["won"]) + 1
            home_row["lost"] = int(home_row["lost"]) + 1
            away_row["points"] = int(away_row["points"]) + 3
        else:
            home_row["drawn"] = int(home_row["drawn"]) + 1
            away_row["drawn"] = int(away_row["drawn"]) + 1
            home_row["points"] = int(home_row["points"]) + 1
            away_row["points"] = int(away_row["points"]) + 1

    standings: list[dict[str, object]] = []
    for group in sorted(group_table):
        rows = list(group_table[group].values())
        for row in rows:
            row["goal_difference"] = int(row["goals_for"]) - int(row["goals_against"])
        sorted_rows = _sort_group_table(rows)
        for index, row in enumerate(sorted_rows, start=1):
            standings.append(
                {
                    "competition_id": "fifa_world_cup",
                    "season_id": "2026",
                    "stage": "group",
                    "group": group,
                    "rank": index,
                    **row,
                }
            )

    write_json(Path(args.normalized_output), standings)
    write_json(Path(args.public_output), standings)

    print(f"Wrote {len(standings)} standings rows to {args.normalized_output}")
    print(f"Published {len(standings)} standings rows to {args.public_output}")


if __name__ == "__main__":
    main()
