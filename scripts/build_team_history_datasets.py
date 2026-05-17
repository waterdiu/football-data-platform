from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "data" / "public"
NORMALIZED_DIR = ROOT / "data" / "normalized"
REPORTS_DIR = ROOT / "reports"
PREDICTOR_ASSETS_DIR = ROOT / "data" / "predictor-assets" / "files"

TEAMS_PATH = PUBLIC_DIR / "teams.json"
FIXTURES_PATH = PUBLIC_DIR / "fixtures.json"
NORMALIZED_MATCHES_PATH = PREDICTOR_ASSETS_DIR / "processed" / "normalized_matches.csv"
QUALIFIER_MATCHES_PATH = PUBLIC_DIR / "qualifier-matches.json"
OPENFOOTBALL_WORLDCUP_DIR = ROOT / "data" / "raw" / "openfootball" / "worldcup-json"
NORMALIZED_MATCHES_SOURCE_LABEL = "predictor-assets/processed/normalized_matches.csv"
QUALIFIER_MATCHES_SOURCE_LABEL = "public/qualifier-matches.json"

HISTORY_MASTER_PATH = NORMALIZED_DIR / "team_world_cup_history_master.json"
RECENT_MASTER_PATH = NORMALIZED_DIR / "team_recent_matches_master.json"
HISTORY_PUBLIC_PATH = PUBLIC_DIR / "team-world-cup-history.json"
RECENT_PUBLIC_PATH = PUBLIC_DIR / "team-recent-matches.json"

UPDATED_AT = "2026-05-17T00:00:00Z"
CURRENT_EDITION_YEAR = 2026


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def normalize_name(value: str) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def active_team_ids(fixtures: list[dict]) -> set[str]:
    ids: set[str] = set()
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        for field in ("home_team_id", "away_team_id"):
            team_id = str(fixture.get(field) or "")
            if team_id and not team_id.startswith("slot-"):
                ids.add(team_id)
    return ids


def team_indexes(teams: list[dict], selected_ids: set[str]) -> tuple[dict[str, dict], dict[str, str]]:
    by_id: dict[str, dict] = {}
    alias_to_id: dict[str, str] = {}
    for team in teams:
        if not isinstance(team, dict):
            continue
        team_id = str(team.get("team_id") or "")
        if team_id not in selected_ids:
            continue
        by_id[team_id] = team
        names = [team.get("name"), team.get("short_name"), *(team.get("aliases") or [])]
        for name in names:
            key = normalize_name(str(name or ""))
            if key:
                alias_to_id[key] = team_id
    return by_id, alias_to_id


def add_historical_aliases(alias_to_id: dict[str, str]) -> None:
    replacements = {
        "bosniaherzegovina": "bosnia-and-herzegovina",
        "cotedivoire": "cote-divoire",
        "côtedivoire": "cote-divoire",
        "ivorycoast": "cote-divoire",
        "czechrepublic": "czechia",
        "czechoslovakia": "czechia",
        "korearepublic": "korea-republic",
        "southkorea": "korea-republic",
        "usa": "united-states",
        "unitedstates": "united-states",
        "unitedstatesofamerica": "united-states",
        "westgermany": "germany",
        "zaire": "congo-dr",
        "drcongo": "congo-dr",
        "democraticrepublicofthecongo": "congo-dr",
        "serbiaandmontenegro": "serbia",
        "yugoslavia": "serbia",
    }
    for name, team_id in replacements.items():
        alias_to_id.setdefault(name, team_id)


def empty_history(team_id: str, team: dict) -> dict:
    return {
        "team_id": team_id,
        "team_name": team.get("name") or team_id,
        "competition_id": "fifa_world_cup",
        "source_status": "available_no_prior_appearances",
        "source": "openfootball/worldcup.json",
        "summary": {
            "appearances": 1,
            "completed_appearances": 0,
            "current_qualified": True,
            "best_finish": None,
            "matches_played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "goals_for": 0,
            "goals_against": 0,
        },
        "editions": [
            {
                "year": CURRENT_EDITION_YEAR,
                "status": "qualified",
                "stage_reached": "qualified_not_started",
                "finish": None,
                "matches_played": 0,
                "won": 0,
                "drawn": 0,
                "lost": 0,
                "goals_for": 0,
                "goals_against": 0,
                "goal_difference": 0,
                "matches": [],
            }
        ],
        "notes": "No completed FIFA World Cup finals matches found in the audited openfootball history source through 2022. The 2026 qualified edition is counted as an appearance but not in match totals.",
        "updated_at": UPDATED_AT,
    }


def slugify(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in slug.split("-") if part)


def match_id_for_row(row: dict) -> str:
    raw = "|".join(
        [
            str(row.get("date") or ""),
            str(row.get("home_team") or ""),
            str(row.get("away_team") or ""),
            str(row.get("tournament") or ""),
        ]
    )
    return f"historical:{slugify(raw)}"


def match_id_for_openfootball(year: int, match: dict) -> str:
    raw = "|".join(
        [
            str(year),
            str(match.get("date") or ""),
            str(match.get("team1") or ""),
            str(match.get("team2") or ""),
            str(match.get("round") or ""),
        ]
    )
    return f"openfootball:worldcup:{slugify(raw)}"


def parse_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_bool(value: object) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes"}


def result_for(score_for: int, score_against: int) -> str:
    if score_for > score_against:
        return "win"
    if score_for < score_against:
        return "loss"
    return "draw"


def score_for_stats(score: dict) -> tuple[list[int], str]:
    if not isinstance(score, dict):
        return [0, 0], "missing"
    if "p" in score and "et" in score:
        return list(score["et"]), "draw_after_penalties"
    if "et" in score:
        return list(score["et"]), "after_extra_time"
    return list(score.get("ft") or [0, 0]), "full_time"


def row_for_team(row: dict, team_id: str, team_name: str, side: str) -> dict | None:
    home_score = parse_int(row.get("home_score"))
    away_score = parse_int(row.get("away_score"))
    if home_score is None or away_score is None:
        return None
    is_home = side == "home"
    score_for = home_score if is_home else away_score
    score_against = away_score if is_home else home_score
    opponent = row.get("away_team") if is_home else row.get("home_team")
    city = str(row.get("city") or "")
    country = str(row.get("country") or "")
    venue = ", ".join(part for part in [city, country] if part)
    return {
        "match_id": match_id_for_row(row),
        "date": str(row.get("date") or ""),
        "team_id": team_id,
        "team_name": team_name,
        "home_team": str(row.get("home_team") or ""),
        "away_team": str(row.get("away_team") or ""),
        "opponent_name": str(opponent or ""),
        "home_away": "neutral" if parse_bool(row.get("neutral")) else side,
        "home_score": home_score,
        "away_score": away_score,
        "score_for": score_for,
        "score_against": score_against,
        "result": result_for(score_for, score_against),
        "tournament": str(row.get("tournament") or ""),
        "competition_group": str(row.get("competition_group") or ""),
        "competition_weight": parse_float(row.get("competition_weight")),
        "city": city,
        "country": country,
        "venue": venue or None,
        "neutral": parse_bool(row.get("neutral")),
    }


def row_for_qualifier_team(row: dict, team_id: str, team_name: str, side: str) -> dict | None:
    home_score = parse_int(row.get("homeScore"))
    away_score = parse_int(row.get("awayScore"))
    if home_score is None or away_score is None:
        return None
    is_home = side == "home"
    score_for = home_score if is_home else away_score
    score_against = away_score if is_home else home_score
    opponent = row.get("awayTeam") if is_home else row.get("homeTeam")
    return {
        "match_id": str(row.get("id") or match_id_for_row({
            "date": row.get("dateLabel"),
            "home_team": row.get("homeTeam"),
            "away_team": row.get("awayTeam"),
            "tournament": row.get("stage") or row.get("confederationName"),
        })),
        "date": str(row.get("dateLabel") or ""),
        "team_id": team_id,
        "team_name": team_name,
        "home_team": str(row.get("homeTeam") or ""),
        "away_team": str(row.get("awayTeam") or ""),
        "opponent_name": str(opponent or ""),
        "home_away": side,
        "home_score": home_score,
        "away_score": away_score,
        "score_for": score_for,
        "score_against": score_against,
        "result": result_for(score_for, score_against),
        "tournament": str(row.get("confederationName") or "FIFA World Cup qualifying"),
        "competition_group": "world_cup_qualifying",
        "competition_weight": 0.85,
        "round": str(row.get("stage") or ""),
        "city": "",
        "country": "",
        "venue": row.get("venue") or None,
        "neutral": False,
        "source_label": row.get("sourceLabel"),
    }


def summarize_form(matches: list[dict]) -> dict:
    won = sum(1 for match in matches if match.get("result") == "win")
    drawn = sum(1 for match in matches if match.get("result") == "draw")
    lost = sum(1 for match in matches if match.get("result") == "loss")
    goals_for = sum(int(match.get("score_for") or 0) for match in matches)
    goals_against = sum(int(match.get("score_against") or 0) for match in matches)
    return {
        "played": len(matches),
        "won": won,
        "drawn": drawn,
        "lost": lost,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "goal_difference": goals_for - goals_against,
    }


def stage_from_round(round_name: str, *, is_group: bool) -> str:
    label = round_name.casefold()
    if "final" == label:
        return "final"
    if "match for third place" in label or "third place" in label:
        return "third_place_match"
    if "semi" in label:
        return "semi_finals"
    if "quarter" in label:
        return "quarter_finals"
    if "round of 16" in label:
        return "round_of_16"
    if "second round" in label or "second group" in label:
        return "second_group_stage"
    if is_group or "matchday" in label or "group" in label:
        return "group_stage"
    return round_name or "unknown"


STAGE_RANK = {
    "winner": 1,
    "runner_up": 2,
    "third_place": 3,
    "fourth_place": 4,
    "semi_finals": 5,
    "quarter_finals": 6,
    "round_of_16": 7,
    "second_group_stage": 8,
    "group_stage": 9,
    "qualified_not_started": 10,
}


def better_stage(current: str | None, candidate: str) -> str:
    if current is None:
        return candidate
    return candidate if STAGE_RANK.get(candidate, 99) < STAGE_RANK.get(current, 99) else current


def update_stage_after_match(edition: dict[str, object], side: int, match: dict, score_stats: list[int]) -> None:
    stage = stage_from_round(str(match.get("round") or ""), is_group=bool(match.get("group")))
    if stage == "final":
        stage = "winner" if score_stats[side] > score_stats[1 - side] else "runner_up"
    elif stage == "third_place_match":
        stage = "third_place" if score_stats[side] > score_stats[1 - side] else "fourth_place"
    edition["stage_reached"] = better_stage(edition.get("stage_reached"), stage)
    edition["finish"] = edition["stage_reached"]


def build_world_cup_history_from_openfootball(
    *,
    team_by_id: dict[str, dict],
    alias_to_id: dict[str, str],
    source_dir: Path,
) -> list[dict]:
    stats_by_team: dict[str, dict[int, dict[str, object]]] = {team_id: {} for team_id in team_by_id}
    if not source_dir.exists():
        return [empty_history(team_id, team) for team_id, team in sorted(team_by_id.items())]

    for path in sorted(source_dir.glob("*/worldcup.json")):
        year = parse_int(path.parent.name)
        if year is None or year > 2022:
            continue
        payload = load_json(path)
        if not isinstance(payload, dict):
            continue
        for match in payload.get("matches") or []:
            if not isinstance(match, dict):
                continue
            score_stats, result_basis = score_for_stats(match.get("score") or {})
            team_ids = [
                alias_to_id.get(normalize_name(str(match.get("team1") or ""))),
                alias_to_id.get(normalize_name(str(match.get("team2") or ""))),
            ]
            for side, team_id in enumerate(team_ids):
                if not team_id or team_id not in stats_by_team:
                    continue
                edition = stats_by_team[team_id].setdefault(
                    year,
                    {
                        "year": year,
                        "matches_played": 0,
                        "won": 0,
                        "drawn": 0,
                        "lost": 0,
                        "goals_for": 0,
                        "goals_against": 0,
                        "goal_difference": 0,
                        "matches": [],
                        "stage_reached": None,
                        "finish": None,
                    },
                )
                score_for = int(score_stats[side])
                score_against = int(score_stats[1 - side])
                edition["matches_played"] = int(edition["matches_played"]) + 1
                match_result = result_for(score_for, score_against)
                if result_basis == "draw_after_penalties":
                    match_result = "draw"
                if match_result == "win":
                    edition["won"] = int(edition["won"]) + 1
                elif match_result == "draw":
                    edition["drawn"] = int(edition["drawn"]) + 1
                else:
                    edition["lost"] = int(edition["lost"]) + 1
                edition["goals_for"] = int(edition["goals_for"]) + score_for
                edition["goals_against"] = int(edition["goals_against"]) + score_against
                edition["goal_difference"] = int(edition["goals_for"]) - int(edition["goals_against"])
                update_stage_after_match(edition, side, match, score_stats)
                edition["matches"].append(
                    {
                        "match_id": match_id_for_openfootball(year, match),
                        "date": str(match.get("date") or ""),
                        "team_id": team_id,
                        "team_name": team_by_id[team_id].get("name") or team_id,
                        "home_team": str(match.get("team1") or ""),
                        "away_team": str(match.get("team2") or ""),
                        "opponent_name": str(match.get("team2") if side == 0 else match.get("team1") or ""),
                        "home_away": "neutral",
                        "home_score": int(score_stats[0]),
                        "away_score": int(score_stats[1]),
                        "score_for": score_for,
                        "score_against": score_against,
                        "result": match_result,
                        "result_basis": result_basis,
                        "tournament": "FIFA World Cup",
                        "competition_group": "world_cup",
                        "competition_weight": 1.0,
                        "round": str(match.get("round") or ""),
                        "group": match.get("group"),
                        "city": "",
                        "country": "",
                        "venue": match.get("ground"),
                        "neutral": True,
                    }
                )

    output: list[dict] = []
    for team_id, team in sorted(team_by_id.items()):
        editions = sorted(stats_by_team.get(team_id, {}).values(), key=lambda item: int(item["year"]))
        if not editions:
            output.append(empty_history(team_id, team))
            continue
        editions.append(
            {
                "year": CURRENT_EDITION_YEAR,
                "status": "qualified",
                "stage_reached": "qualified_not_started",
                "finish": None,
                "matches_played": 0,
                "won": 0,
                "drawn": 0,
                "lost": 0,
                "goals_for": 0,
                "goals_against": 0,
                "goal_difference": 0,
                "matches": [],
            }
        )
        best_finish = None
        for edition in editions:
            stage = edition.get("stage_reached")
            if stage and stage != "qualified_not_started":
                best_finish = better_stage(best_finish, str(stage))
        summary = {
            "appearances": len(editions),
            "completed_appearances": len(editions) - 1,
            "current_qualified": True,
            "best_finish": best_finish,
            "matches_played": sum(int(item["matches_played"]) for item in editions if int(item["year"]) != CURRENT_EDITION_YEAR),
            "won": sum(int(item["won"]) for item in editions if int(item["year"]) != CURRENT_EDITION_YEAR),
            "drawn": sum(int(item["drawn"]) for item in editions if int(item["year"]) != CURRENT_EDITION_YEAR),
            "lost": sum(int(item["lost"]) for item in editions if int(item["year"]) != CURRENT_EDITION_YEAR),
            "goals_for": sum(int(item["goals_for"]) for item in editions if int(item["year"]) != CURRENT_EDITION_YEAR),
            "goals_against": sum(int(item["goals_against"]) for item in editions if int(item["year"]) != CURRENT_EDITION_YEAR),
        }
        output.append(
            {
                "team_id": team_id,
                "team_name": team.get("name") or team_id,
                "competition_id": "fifa_world_cup",
                "source_status": "available",
                "source": "openfootball/worldcup.json",
                "summary": summary,
                "editions": editions,
                "notes": "Derived from openfootball/worldcup.json completed FIFA World Cup finals through 2022. The 2026 qualified edition is counted as an appearance but not in match totals.",
                "updated_at": UPDATED_AT,
            }
        )
    return output


def build_recent_matches(
    *,
    team_by_id: dict[str, dict],
    alias_to_id: dict[str, str],
    source_path: Path,
    limit: int,
) -> list[dict]:
    rows_by_team: dict[str, list[dict]] = {team_id: [] for team_id in team_by_id}
    source_label = NORMALIZED_MATCHES_SOURCE_LABEL

    if source_path.exists():
        source_status_when_available = "available"
        with source_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                home_id = alias_to_id.get(normalize_name(str(row.get("home_team") or "")))
                away_id = alias_to_id.get(normalize_name(str(row.get("away_team") or "")))
                if home_id:
                    item = row_for_team(row, home_id, str(row.get("home_team") or ""), "home")
                    if item:
                        rows_by_team[home_id].append(item)
                if away_id:
                    item = row_for_team(row, away_id, str(row.get("away_team") or ""), "away")
                    if item:
                        rows_by_team[away_id].append(item)
    elif RECENT_PUBLIC_PATH.exists():
        existing = load_json(RECENT_PUBLIC_PATH)
        if isinstance(existing, list) and any((row.get("match_count") or 0) > 0 for row in existing if isinstance(row, dict)):
            return existing
        source_status_when_available = "available_from_qualifier_matches"
        source_label = QUALIFIER_MATCHES_SOURCE_LABEL
    else:
        source_status_when_available = "available_from_qualifier_matches"
        source_label = QUALIFIER_MATCHES_SOURCE_LABEL

    if not source_path.exists() and QUALIFIER_MATCHES_PATH.exists():
        qualifier_rows = load_json(QUALIFIER_MATCHES_PATH)
        if isinstance(qualifier_rows, list):
            for row in qualifier_rows:
                if not isinstance(row, dict):
                    continue
                home_id = alias_to_id.get(normalize_name(str(row.get("homeTeam") or "")))
                away_id = alias_to_id.get(normalize_name(str(row.get("awayTeam") or "")))
                if home_id:
                    item = row_for_qualifier_team(row, home_id, str(row.get("homeTeam") or ""), "home")
                    if item:
                        rows_by_team[home_id].append(item)
                if away_id:
                    item = row_for_qualifier_team(row, away_id, str(row.get("awayTeam") or ""), "away")
                    if item:
                        rows_by_team[away_id].append(item)
    elif not source_path.exists():
        source_label = NORMALIZED_MATCHES_SOURCE_LABEL
        source_status_when_available = "missing_source"

    output: list[dict] = []
    for team_id, team in sorted(team_by_id.items()):
        matches = sorted(rows_by_team.get(team_id, []), key=lambda item: item["date"], reverse=True)[:limit]
        output.append(
            {
                "team_id": team_id,
                "team_name": team.get("name") or team_id,
                "source": source_label,
                "source_status": source_status_when_available if matches else "missing",
                "match_count": len(matches),
                "latest_match_date": matches[0]["date"] if matches else None,
                "form_summary": summarize_form(matches),
                "matches": matches,
                "updated_at": UPDATED_AT,
            }
        )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build team World Cup history and recent match datasets.")
    parser.add_argument("--recent-limit", type=int, default=10, help="recent matches per team")
    parser.add_argument("--report-output", default=str(REPORTS_DIR / "team_history_publish_report.json"))
    args = parser.parse_args()

    teams = load_json(TEAMS_PATH)
    fixtures = load_json(FIXTURES_PATH)
    if not isinstance(teams, list):
        raise TypeError("teams.json must contain a list")
    if not isinstance(fixtures, list):
        raise TypeError("fixtures.json must contain a list")

    selected_ids = active_team_ids(fixtures)
    team_by_id, alias_to_id = team_indexes(teams, selected_ids)
    add_historical_aliases(alias_to_id)
    history = build_world_cup_history_from_openfootball(
        team_by_id=team_by_id,
        alias_to_id=alias_to_id,
        source_dir=OPENFOOTBALL_WORLDCUP_DIR,
    )
    recent = build_recent_matches(
        team_by_id=team_by_id,
        alias_to_id=alias_to_id,
        source_path=NORMALIZED_MATCHES_PATH,
        limit=args.recent_limit,
    )

    write_json(HISTORY_MASTER_PATH, history)
    write_json(RECENT_MASTER_PATH, recent)
    write_json(HISTORY_PUBLIC_PATH, history)
    write_json(RECENT_PUBLIC_PATH, recent)

    report = {
        "status": "published_contract_and_recent_matches",
        "teams_considered": len(team_by_id),
        "history_rows": len(history),
        "history_source_status": "available",
        "history_available_rows": sum(1 for row in history if row.get("source_status") == "available"),
        "history_no_prior_appearance_rows": sum(
            1 for row in history if row.get("source_status") == "available_no_prior_appearances"
        ),
        "recent_rows": len(recent),
        "recent_available_rows": sum(1 for row in recent if row.get("source_status") == "available"),
        "recent_limit": args.recent_limit,
        "recent_source": NORMALIZED_MATCHES_SOURCE_LABEL,
        "outputs": {
            "history_master": rel(HISTORY_MASTER_PATH),
            "recent_master": rel(RECENT_MASTER_PATH),
            "history_public": rel(HISTORY_PUBLIC_PATH),
            "recent_public": rel(RECENT_PUBLIC_PATH),
        },
    }
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
