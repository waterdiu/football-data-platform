from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREDICTOR_ROOT = ROOT.parent / "world-cup-predictor"

FIXTURES_PATH = ROOT / "data" / "public" / "fixtures.json"
CANONICAL_TEAMS_PATH = ROOT / "data" / "public" / "canonical_teams.json"
OUTPUT_PATH = PREDICTOR_ROOT / "backend" / "data" / "raw" / "world_cup_2026_shared_fixtures.json"

PREDICTOR_TEAM_NAMES = {
    "Korea Republic": "South Korea",
    "IR Iran": "Iran",
    "Czechia": "Czech Republic",
    "Cote d'Ivoire": "Ivory Coast",
    "Turkiye": "Turkey",
    "Congo DR": "DR Congo",
    "Cabo Verde": "Cape Verde",
}

HOST_TEAMS = {"Mexico", "United States", "Canada"}


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def predictor_team_name(shared_name: str) -> str:
    return PREDICTOR_TEAM_NAMES.get(shared_name, shared_name)


def export_fixture(fixture: dict, team_name_by_id: dict[str, str]) -> dict[str, object]:
    home_name = predictor_team_name(str(team_name_by_id[str(fixture["home_team_id"])]))
    away_name = predictor_team_name(str(team_name_by_id[str(fixture["away_team_id"])]))
    return {
        "match_id": fixture["match_id"],
        "date": str(fixture["date_utc"])[:10],
        "home_team": home_name,
        "away_team": away_name,
        "competition_group": "world_cup",
        "competition_weight": 1.0,
        "neutral": home_name not in HOST_TEAMS,
    }


def main() -> None:
    fixtures = load_json(FIXTURES_PATH)
    canonical_teams = load_json(CANONICAL_TEAMS_PATH)
    if not isinstance(fixtures, list):
        raise TypeError("fixtures.json must contain a list")
    if not isinstance(canonical_teams, list):
        raise TypeError("canonical_teams.json must contain a list")

    team_name_by_id = {
        str(team["team_id"]): str(team["name"])
        for team in canonical_teams
        if isinstance(team, dict) and "team_id" in team and "name" in team
    }

    exported = {
        "generated_at": "2026-05-15T00:00:00Z",
        "source": str(FIXTURES_PATH),
        "fixtures": [export_fixture(fixture, team_name_by_id) for fixture in fixtures if isinstance(fixture, dict)],
    }
    write_json(OUTPUT_PATH, exported)
    print(f"Exported {len(exported['fixtures'])} fixtures to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
