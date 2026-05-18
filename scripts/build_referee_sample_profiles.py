from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = ROOT / "data" / "normalized"
REPORTS_DIR = ROOT / "reports"
SOURCE_PATH = ROOT / "data" / "predictor-assets" / "files" / "processed" / "premier_league_matches.csv"
OFFICIALS_OUTPUT_PATH = NORMALIZED_DIR / "person_officials_master.json"
RATINGS_OUTPUT_PATH = NORMALIZED_DIR / "person_official_ratings_master.json"
REPORT_PATH = REPORTS_DIR / "referee_sample_profiles_report.json"

MIN_REPORT_SAMPLE = 20
MIN_DISTILL_SAMPLE = 30


def slugify(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in slug.split("-") if part)


def int_value(value: object) -> int:
    try:
        if value is None or str(value).strip() == "":
            return 0
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def safe_rate(value: float, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(value / denominator, 4)


def result_label(row: dict) -> str:
    label = str(row.get("result_label") or "").strip()
    if label:
        return label
    home_score = int_value(row.get("home_score"))
    away_score = int_value(row.get("away_score"))
    if home_score > away_score:
        return "home_win"
    if home_score < away_score:
        return "away_win"
    return "draw"


def style_tags(metrics: dict) -> list[str]:
    tags: list[str] = []
    yellow_cards = metrics.get("yellow_cards_per_match")
    red_cards = metrics.get("red_cards_per_match")
    draw_rate = metrics.get("draw_rate")
    avg_goals = metrics.get("avg_goals")
    if yellow_cards is not None:
        if yellow_cards >= 4.2:
            tags.append("card-heavy")
        elif yellow_cards <= 2.8:
            tags.append("low-card")
    if red_cards is not None and red_cards >= 0.2:
        tags.append("red-card-prone")
    if draw_rate is not None and draw_rate >= 0.32:
        tags.append("draw-leaning")
    if avg_goals is not None:
        if avg_goals >= 3.1:
            tags.append("high-scoring-sample")
        elif avg_goals <= 2.3:
            tags.append("low-scoring-sample")
    return tags


def rating_from_metrics(metrics: dict, *, sample_size: int) -> tuple[str, str, float | None, dict]:
    if sample_size < MIN_REPORT_SAMPLE:
        return "low_referee_sample", "low", None, {}
    yellow = float(metrics.get("yellow_cards_per_match") or 0.0)
    red = float(metrics.get("red_cards_per_match") or 0.0)
    cards_score = min(100.0, round((yellow / 5.0) * 75.0 + (red / 0.35) * 25.0, 2))
    home_bias = abs(float(metrics.get("home_win_rate") or 0.0) - float(metrics.get("away_win_rate") or 0.0))
    home_bias_score = min(100.0, round(home_bias * 200.0, 2))
    goal_environment = min(100.0, round((float(metrics.get("avg_goals") or 0.0) / 3.5) * 100.0, 2))
    overall = round((cards_score * 0.45) + (home_bias_score * 0.2) + (goal_environment * 0.35), 2)
    return (
        "available",
        "medium" if sample_size >= 50 else "low",
        overall,
        {
            "card_strictness": cards_score,
            "home_away_asymmetry": home_bias_score,
            "goal_environment": goal_environment,
        },
    )


def build_profiles(source_path: Path, *, generated_at: str) -> tuple[list[dict], list[dict], dict]:
    rows_by_referee: dict[str, list[dict]] = defaultdict(list)
    with source_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            referee = str(row.get("referee") or "").strip()
            if referee:
                rows_by_referee[referee].append(row)

    officials: list[dict] = []
    ratings: list[dict] = []
    for referee, rows in sorted(rows_by_referee.items(), key=lambda item: item[0]):
        sample_size = len(rows)
        yellow_cards = sum(int_value(row.get("home_yellow_cards")) + int_value(row.get("away_yellow_cards")) for row in rows)
        red_cards = sum(int_value(row.get("home_red_cards")) + int_value(row.get("away_red_cards")) for row in rows)
        goals = sum(int_value(row.get("home_score")) + int_value(row.get("away_score")) for row in rows)
        home_wins = sum(1 for row in rows if result_label(row) == "home_win")
        away_wins = sum(1 for row in rows if result_label(row) == "away_win")
        draws = sum(1 for row in rows if result_label(row) == "draw")
        seasons = sorted({str(row.get("season") or "") for row in rows if row.get("season")})
        first_match_date = min(str(row.get("date") or "") for row in rows if row.get("date"))
        last_match_date = max(str(row.get("date") or "") for row in rows if row.get("date"))
        metrics = {
            "matches": sample_size,
            "yellow_cards": yellow_cards,
            "red_cards": red_cards,
            "yellow_cards_per_match": safe_rate(yellow_cards, sample_size),
            "red_cards_per_match": safe_rate(red_cards, sample_size),
            "fouls_per_match": None,
            "penalties_per_match": None,
            "home_win_rate": safe_rate(home_wins, sample_size),
            "away_win_rate": safe_rate(away_wins, sample_size),
            "draw_rate": safe_rate(draws, sample_size),
            "avg_goals": safe_rate(goals, sample_size),
            "first_match_date": first_match_date,
            "last_match_date": last_match_date,
            "seasons": seasons,
        }
        official_id = f"referee:premier-league:{slugify(referee)}"
        tags = style_tags(metrics) if sample_size >= MIN_DISTILL_SAMPLE else []
        status, confidence, overall_rating, dimensions = rating_from_metrics(metrics, sample_size=sample_size)
        source_refs = {
            "source_file": str(source_path.relative_to(ROOT)),
            "competition_scope": "premier_league",
            "sample_size_matches": sample_size,
        }
        officials.append(
            {
                "official_id": official_id,
                "person_id": official_id,
                "name": referee,
                "display_name": referee,
                "country": None,
                "nationality": None,
                "confederation": None,
                "roles": ["referee"],
                "role": "referee",
                "role_zh": "裁判",
                "assigned_matches": [],
                "assignment_status": "missing_referee_assignment",
                "fifa_listed_since": None,
                "competition_id": "premier_league",
                "season_id": "historical",
                "competition_scope": "premier_league",
                "source_status": "historical_sample_only",
                "sources": ["football-data.co.uk", "platform_predictor_migrated_epl_matches"],
                "source_refs": source_refs,
                "source_url": "https://www.football-data.co.uk/",
                "updated_at": generated_at,
                "metrics": metrics,
                "sample_status": "available" if sample_size >= MIN_REPORT_SAMPLE else "low_referee_sample",
                "style_tags": tags,
                "distillation_status": "available" if tags else "insufficient_sample",
            }
        )
        ratings.append(
            {
                "entity_id": official_id,
                "entity_type": "official",
                "rating_type": "referee_officiating_sample",
                "status": status,
                "confidence": confidence,
                "overall_rating": overall_rating,
                "dimension_ratings": dimensions,
                "raw_metrics": metrics,
                "sample_size": sample_size,
                "time_window": f"{first_match_date}/{last_match_date}",
                "competition_scope": "premier_league",
                "position_scope": "referee",
                "sources": ["football-data.co.uk", "platform_predictor_migrated_epl_matches"],
                "source_refs": source_refs,
                "style_tags": tags,
                "updated_at": generated_at,
            }
        )

    report = {
        "status": "published",
        "source": str(source_path.relative_to(ROOT)),
        "officials": len(officials),
        "ratings": len(ratings),
        "matches": sum(len(rows) for rows in rows_by_referee.values()),
        "sample_threshold": MIN_REPORT_SAMPLE,
        "distillation_threshold": MIN_DISTILL_SAMPLE,
        "available_rating_rows": sum(1 for row in ratings if row.get("status") == "available"),
        "low_sample_rows": sum(1 for row in ratings if row.get("status") == "low_referee_sample"),
        "generated_at": generated_at,
        "outputs": {
            "officials": str(OFFICIALS_OUTPUT_PATH.relative_to(ROOT)),
            "official_ratings": str(RATINGS_OUTPUT_PATH.relative_to(ROOT)),
        },
    }
    return officials, ratings, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build referee sample profiles from historical Premier League match CSV.")
    parser.add_argument("--source", default=str(SOURCE_PATH))
    parser.add_argument("--officials-output", default=str(OFFICIALS_OUTPUT_PATH))
    parser.add_argument("--ratings-output", default=str(RATINGS_OUTPUT_PATH))
    parser.add_argument("--report-output", default=str(REPORT_PATH))
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        raise FileNotFoundError(f"Missing referee sample source: {source_path}")

    generated_at = datetime.now(timezone.utc).isoformat()
    officials, ratings, report = build_profiles(source_path, generated_at=generated_at)
    write_json(Path(args.officials_output), officials)
    write_json(Path(args.ratings_output), ratings)
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
