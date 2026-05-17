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

HISTORY_MASTER_PATH = NORMALIZED_DIR / "team_world_cup_history_master.json"
RECENT_MASTER_PATH = NORMALIZED_DIR / "team_recent_matches_master.json"
HISTORY_PUBLIC_PATH = PUBLIC_DIR / "team-world-cup-history.json"
RECENT_PUBLIC_PATH = PUBLIC_DIR / "team-recent-matches.json"

UPDATED_AT = "2026-05-17T00:00:00Z"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def empty_history(team_id: str, team: dict) -> dict:
    return {
        "team_id": team_id,
        "team_name": team.get("name") or team_id,
        "competition_id": "fifa_world_cup",
        "source_status": "pending_source",
        "source": None,
        "summary": {
            "appearances": 0,
            "best_finish": None,
            "matches_played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "goals_for": 0,
            "goals_against": 0,
        },
        "editions": [],
        "notes": "Contract placeholder. Populate from audited historical World Cup results before using as production facts.",
        "updated_at": UPDATED_AT,
    }


def match_id_for_row(row: dict) -> str:
    raw = "|".join(
        [
            str(row.get("date") or ""),
            str(row.get("home_team") or ""),
            str(row.get("away_team") or ""),
            str(row.get("tournament") or ""),
        ]
    )
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in raw)
    slug = "-".join(part for part in slug.split("-") if part)
    return f"historical:{slug}"


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


def build_world_cup_history(
    *,
    team_by_id: dict[str, dict],
    alias_to_id: dict[str, str],
    source_path: Path,
) -> list[dict]:
    stats_by_team: dict[str, dict[int, dict[str, object]]] = {team_id: {} for team_id in team_by_id}
    if not source_path.exists():
        return [empty_history(team_id, team) for team_id, team in sorted(team_by_id.items())]

    with source_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("competition_group") or "") != "world_cup" and str(row.get("tournament") or "") != "FIFA World Cup":
                continue
            year = parse_int(str(row.get("date") or "")[:4])
            if year is None:
                continue
            home_id = alias_to_id.get(normalize_name(str(row.get("home_team") or "")))
            away_id = alias_to_id.get(normalize_name(str(row.get("away_team") or "")))
            for team_id, side in ((home_id, "home"), (away_id, "away")):
                if not team_id:
                    continue
                item = row_for_team(row, team_id, team_by_id[team_id].get("name") or team_id, side)
                if not item:
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
                edition["matches_played"] = int(edition["matches_played"]) + 1
                if item["result"] == "win":
                    edition["won"] = int(edition["won"]) + 1
                elif item["result"] == "draw":
                    edition["drawn"] = int(edition["drawn"]) + 1
                else:
                    edition["lost"] = int(edition["lost"]) + 1
                edition["goals_for"] = int(edition["goals_for"]) + int(item["score_for"])
                edition["goals_against"] = int(edition["goals_against"]) + int(item["score_against"])
                edition["goal_difference"] = int(edition["goals_for"]) - int(edition["goals_against"])
                edition["matches"].append(item)

    output: list[dict] = []
    for team_id, team in sorted(team_by_id.items()):
        editions = sorted(stats_by_team.get(team_id, {}).values(), key=lambda item: int(item["year"]))
        if not editions:
            output.append(empty_history(team_id, team))
            continue
        summary = {
            "appearances": len(editions),
            "best_finish": None,
            "matches_played": sum(int(item["matches_played"]) for item in editions),
            "won": sum(int(item["won"]) for item in editions),
            "drawn": sum(int(item["drawn"]) for item in editions),
            "lost": sum(int(item["lost"]) for item in editions),
            "goals_for": sum(int(item["goals_for"]) for item in editions),
            "goals_against": sum(int(item["goals_against"]) for item in editions),
        }
        output.append(
            {
                "team_id": team_id,
                "team_name": team.get("name") or team_id,
                "competition_id": "fifa_world_cup",
                "source_status": "available_partial",
                "source": str(source_path),
                "summary": summary,
                "editions": editions,
                "notes": "Derived from migrated historical international results. Coverage currently includes FIFA World Cup matches present in normalized_matches.csv (2002-2022); stage/finish labels are not asserted until an audited full-history source is connected.",
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
    if not source_path.exists():
        return [
            {
                "team_id": team_id,
                "team_name": team.get("name") or team_id,
                "source": str(source_path),
                "source_status": "missing_source",
                "match_count": 0,
                "latest_match_date": None,
                "form_summary": summarize_form([]),
                "matches": [],
                "updated_at": UPDATED_AT,
            }
            for team_id, team in sorted(team_by_id.items())
        ]

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

    output: list[dict] = []
    for team_id, team in sorted(team_by_id.items()):
        matches = sorted(rows_by_team.get(team_id, []), key=lambda item: item["date"], reverse=True)[:limit]
        output.append(
            {
                "team_id": team_id,
                "team_name": team.get("name") or team_id,
                "source": str(source_path),
                "source_status": "available" if matches else "missing",
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
    history = build_world_cup_history(team_by_id=team_by_id, alias_to_id=alias_to_id, source_path=NORMALIZED_MATCHES_PATH)
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
        "history_source_status": "available_partial",
        "history_available_rows": sum(1 for row in history if row.get("source_status") == "available_partial"),
        "recent_rows": len(recent),
        "recent_available_rows": sum(1 for row in recent if row.get("source_status") == "available"),
        "recent_limit": args.recent_limit,
        "recent_source": str(NORMALIZED_MATCHES_PATH),
        "outputs": {
            "history_master": str(HISTORY_MASTER_PATH),
            "recent_master": str(RECENT_MASTER_PATH),
            "history_public": str(HISTORY_PUBLIC_PATH),
            "recent_public": str(RECENT_PUBLIC_PATH),
        },
    }
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
