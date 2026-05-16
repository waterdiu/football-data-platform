from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "data" / "public"
NORMALIZED_DIR = ROOT / "data" / "normalized"
MODEL_DIR = ROOT / "data" / "model"

FIXTURES_PATH = PUBLIC_DIR / "fixtures.json"
RESULTS_PATH = PUBLIC_DIR / "results.json"
PREDICTIONS_PATH = PUBLIC_DIR / "predictions.json"
EVENTS_PATH = PUBLIC_DIR / "finals-events.json"
LINEUPS_PATH = PUBLIC_DIR / "finals-lineups.json"
MATCH_STATS_PATH = PUBLIC_DIR / "finals-match-stats.json"
ODDS_PATH = MODEL_DIR / "odds_snapshots.json"
INJURIES_PATH = MODEL_DIR / "injuries.json"
WEATHER_PATH = MODEL_DIR / "weather.json"
PREMATCH_CONTEXT_PATH = MODEL_DIR / "prematch_context.json"
ROSTERS_PATH = PUBLIC_DIR / "rosters.json"

NORMALIZED_OUTPUT_PATH = NORMALIZED_DIR / "world_cup_2026_data_coverage.json"
PUBLIC_OUTPUT_PATH = PUBLIC_DIR / "data-coverage.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def coverage_item(
    *,
    status: str,
    confidence: str,
    source: str | None = None,
    last_updated: str | None = None,
    **extra: object,
) -> dict[str, object]:
    item: dict[str, object] = {
        "status": status,
        "confidence": confidence,
    }
    if source:
        item["source"] = source
    if last_updated:
        item["last_updated"] = last_updated
    item.update(extra)
    return item


def file_updated_at(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def confidence_score(item: dict[str, object]) -> float:
    if item.get("status") == "missing":
        return 0.0
    confidence = str(item.get("confidence") or "low")
    return {"high": 1.0, "medium": 0.65, "low": 0.25}.get(confidence, 0.25)


def runtime_summary(fields: dict[str, dict[str, object]]) -> dict[str, object]:
    required = ["odds", "asian_handicap", "over_under", "injuries", "lineups", "weather", "prematch_context"]
    missing = [name for name in required if fields[name].get("status") == "missing"]
    partial = [name for name in required if fields[name].get("status") == "partial"]
    available = [name for name in required if fields[name].get("status") == "available"]
    score = round(sum(confidence_score(fields[name]) for name in required) / len(required), 4)
    if score >= 0.8:
        label = "high"
    elif score >= 0.45:
        label = "medium"
    else:
        label = "low"
    return {
        "status": "available" if not missing and not partial else "partial" if available or partial else "missing",
        "confidence": label,
        "confidence_score": score,
        "available": available,
        "partial": partial,
        "missing": missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build World Cup data coverage report.")
    parser.add_argument("--normalized-output", default=str(NORMALIZED_OUTPUT_PATH), help="normalized coverage output path")
    parser.add_argument("--public-output", default=str(PUBLIC_OUTPUT_PATH), help="public coverage output path")
    args = parser.parse_args()

    fixtures = load_json(FIXTURES_PATH)
    results = load_json(RESULTS_PATH)
    predictions = load_json(PREDICTIONS_PATH)
    events = load_json(EVENTS_PATH)
    lineups = load_json(LINEUPS_PATH)
    match_stats = load_json(MATCH_STATS_PATH)
    odds_rows = load_json(ODDS_PATH)
    injuries_rows = load_json(INJURIES_PATH)
    weather_rows = load_json(WEATHER_PATH)
    prematch_context_rows = load_json(PREMATCH_CONTEXT_PATH)
    roster_rows = load_json(ROSTERS_PATH)

    if not isinstance(fixtures, list):
        raise TypeError("fixtures.json must contain a list")
    if not isinstance(results, list):
        raise TypeError("results.json must contain a list")
    if not isinstance(predictions, list):
        raise TypeError("predictions.json must contain a list")
    if not isinstance(events, list):
        raise TypeError("finals-events.json must contain a list")
    if not isinstance(lineups, list):
        raise TypeError("finals-lineups.json must contain a list")
    if not isinstance(match_stats, list):
        raise TypeError("finals-match-stats.json must contain a list")
    if not isinstance(odds_rows, list):
        raise TypeError("odds_snapshots.json must contain a list")
    if not isinstance(injuries_rows, list):
        raise TypeError("injuries.json must contain a list")
    if not isinstance(weather_rows, list):
        raise TypeError("weather.json must contain a list")
    if not isinstance(prematch_context_rows, list):
        raise TypeError("prematch_context.json must contain a list")
    if not isinstance(roster_rows, list):
        raise TypeError("rosters.json must contain a list")

    updated_at = datetime.now(timezone.utc).isoformat()
    source_updated_at = {
        "fixtures": file_updated_at(FIXTURES_PATH),
        "results": file_updated_at(RESULTS_PATH),
        "predictions": file_updated_at(PREDICTIONS_PATH),
        "events": file_updated_at(EVENTS_PATH),
        "lineups": file_updated_at(LINEUPS_PATH),
        "match_stats": file_updated_at(MATCH_STATS_PATH),
        "odds": file_updated_at(ODDS_PATH),
        "injuries": file_updated_at(INJURIES_PATH),
        "weather": file_updated_at(WEATHER_PATH),
        "prematch_context": file_updated_at(PREMATCH_CONTEXT_PATH),
        "rosters": file_updated_at(ROSTERS_PATH),
    }

    result_by_match_id = {str(item["match_id"]): item for item in results if isinstance(item, dict) and "match_id" in item}
    prediction_by_match_id = {
        str(item["match_id"]): item for item in predictions if isinstance(item, dict) and "match_id" in item
    }
    event_match_ids = {str(item["match_id"]) for item in events if isinstance(item, dict) and "match_id" in item}
    lineup_match_ids = {str(item["match_id"]) for item in lineups if isinstance(item, dict) and "match_id" in item}
    stats_match_ids = {str(item["match_id"]) for item in match_stats if isinstance(item, dict) and "match_id" in item}
    odds_by_match_id = {
        str(item["match_id"]): item for item in odds_rows if isinstance(item, dict) and "match_id" in item
    }
    injuries_by_match_id = {
        str(item["match_id"]): item for item in injuries_rows if isinstance(item, dict) and "match_id" in item
    }
    weather_by_match_id = {
        str(item["match_id"]): item for item in weather_rows if isinstance(item, dict) and "match_id" in item
    }
    prematch_context_by_match_id = {
        str(item["match_id"]): item for item in prematch_context_rows if isinstance(item, dict) and "match_id" in item
    }
    roster_by_team_id = {
        str(item["team_id"]): item for item in roster_rows if isinstance(item, dict) and "team_id" in item
    }

    coverage_rows: list[dict[str, object]] = []
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        match_id = str(fixture["match_id"])
        result = result_by_match_id.get(match_id)
        prediction = prediction_by_match_id.get(match_id)
        odds = odds_by_match_id.get(match_id)
        injuries = injuries_by_match_id.get(match_id)
        weather = weather_by_match_id.get(match_id)

        fixture_source = "football_data_org" if "football_data_org" in (fixture.get("source_refs") or {}) else "bootstrap"
        fixture_confidence = "high" if fixture_source == "football_data_org" else "medium"

        if result:
            result_status = coverage_item(
                status="available",
                confidence="high" if result.get("provider") == "football_data_org" else "medium",
                source=str(result.get("provider") or "unknown"),
                last_updated=source_updated_at["results"],
            )
        else:
            result_status = coverage_item(status="missing", confidence="low")

        if prediction:
            prediction_status = coverage_item(
                status="available",
                confidence="medium",
                source=str(prediction.get("model_name") or "unknown"),
                last_updated=source_updated_at["predictions"],
            )
        else:
            prediction_status = coverage_item(status="missing", confidence="low")

        if odds:
            bookmaker_count = int(odds.get("bookmaker_count") or 0)
            has_1x2 = bool(odds.get("home_win") or odds.get("draw") or odds.get("away_win") or odds.get("markets"))
            odds_status = coverage_item(
                status="available" if bookmaker_count > 0 else "partial",
                confidence="high" if odds.get("has_sharp") else "medium",
                source=str(odds.get("source") or "platform_runtime"),
                last_updated=str(odds.get("captured_at") or odds.get("updated_at") or source_updated_at["odds"] or ""),
                bookmaker_count=bookmaker_count,
                has_sharp=bool(odds.get("has_sharp")),
                has_1x2=has_1x2,
            )
        else:
            odds_status = coverage_item(status="missing", confidence="low", bookmaker_count=0, has_sharp=False)

        asian_handicap_status = coverage_item(
            status="available" if odds and bool(odds.get("asian_handicap") or odds.get("has_asian_handicap")) else "missing",
            confidence="medium" if odds and bool(odds.get("asian_handicap") or odds.get("has_asian_handicap")) else "low",
            source=str(odds.get("source") or "platform_runtime") if odds else None,
            last_updated=str(odds.get("captured_at") or odds.get("updated_at") or source_updated_at["odds"] or "") if odds else None,
        )
        over_under_status = coverage_item(
            status="available" if odds and bool(odds.get("over_under") or odds.get("totals") or odds.get("has_over_under")) else "missing",
            confidence="medium" if odds and bool(odds.get("over_under") or odds.get("totals") or odds.get("has_over_under")) else "low",
            source=str(odds.get("source") or "platform_runtime") if odds else None,
            last_updated=str(odds.get("captured_at") or odds.get("updated_at") or source_updated_at["odds"] or "") if odds else None,
        )

        if injuries:
            injuries_status = coverage_item(
                status="available",
                confidence=str(injuries.get("confidence") or "medium"),
                source=str(injuries.get("source") or "predictor_runtime"),
                last_updated=str(injuries.get("fetched_at") or injuries.get("updated_at") or source_updated_at["injuries"] or ""),
            )
        else:
            injuries_status = coverage_item(status="missing", confidence="low")

        if weather:
            weather_status = coverage_item(
                status="available",
                confidence=str(weather.get("confidence") or "medium"),
                source=str(weather.get("source") or "weather_api"),
                last_updated=str(weather.get("fetched_at") or weather.get("updated_at") or source_updated_at["weather"] or ""),
            )
        else:
            weather_status = coverage_item(status="missing", confidence="low")

        prematch_context = prematch_context_by_match_id.get(match_id)
        if prematch_context:
            source_statuses = prematch_context.get("source_statuses") if isinstance(prematch_context.get("source_statuses"), dict) else {}
            readiness = prematch_context.get("readiness") if isinstance(prematch_context.get("readiness"), dict) else {}
            has_news = source_statuses.get("pre_match_news") == "available" or bool(prematch_context.get("prematch_news_summary"))
            prematch_context_status = coverage_item(
                status="available" if has_news else "partial",
                confidence=str(readiness.get("confidence_label") or "low"),
                source="platform_prematch_context",
                last_updated=str(prematch_context.get("updated_at") or source_updated_at["prematch_context"] or ""),
                readiness_score=readiness.get("score"),
                latest_snapshots_count=prematch_context.get("latest_snapshots_count", 0),
                source_statuses=source_statuses,
            )
        else:
            prematch_context_status = coverage_item(status="missing", confidence="low")

        fixture_team_ids = [str(fixture.get("home_team_id") or ""), str(fixture.get("away_team_id") or "")]
        roster_team_count = sum(1 for team_id in fixture_team_ids if team_id and team_id in roster_by_team_id)
        roster_status = coverage_item(
            status="available" if roster_team_count == 2 else "partial" if roster_team_count == 1 else "missing",
            confidence="medium" if roster_team_count == 2 else "low",
            source="platform_rosters" if roster_team_count else None,
            last_updated=source_updated_at["rosters"] if roster_team_count else None,
            team_count=roster_team_count,
        )

        events_status = coverage_item(
            status="available" if match_id in event_match_ids else "missing",
            confidence="medium" if match_id in event_match_ids else "low",
            source="football_data_org" if match_id in event_match_ids else None,
            last_updated=source_updated_at["events"] if match_id in event_match_ids else None,
        )
        lineups_status = coverage_item(
            status="available" if match_id in lineup_match_ids else "missing",
            confidence="medium" if match_id in lineup_match_ids else "low",
            source="football_data_org" if match_id in lineup_match_ids else None,
            last_updated=source_updated_at["lineups"] if match_id in lineup_match_ids else None,
        )
        technical_stats_status = coverage_item(
            status="available" if match_id in stats_match_ids else "missing",
            confidence="medium" if match_id in stats_match_ids else "low",
            source="football_data_org" if match_id in stats_match_ids else None,
            last_updated=source_updated_at["match_stats"] if match_id in stats_match_ids else None,
        )
        xg_status = coverage_item(status="missing", confidence="low")
        player_ratings_status = coverage_item(status="missing", confidence="low")
        runtime_fields = {
            "odds": odds_status,
            "asian_handicap": asian_handicap_status,
            "over_under": over_under_status,
            "injuries": injuries_status,
            "lineups": lineups_status,
            "weather": weather_status,
            "prematch_context": prematch_context_status,
        }

        coverage_rows.append(
            {
                "match_id": match_id,
                "fixture": coverage_item(
                    status="available",
                    confidence=fixture_confidence,
                    source=fixture_source,
                    last_updated=source_updated_at["fixtures"],
                ),
                "result": result_status,
                "events": events_status,
                "lineups": lineups_status,
                "match_stats": technical_stats_status,
                "technical_stats": technical_stats_status,
                "xg": xg_status,
                "player_ratings": player_ratings_status,
                "odds": odds_status,
                "asian_handicap": asian_handicap_status,
                "over_under": over_under_status,
                "injuries": injuries_status,
                "weather": weather_status,
                "prematch_context": prematch_context_status,
                "rosters": roster_status,
                "prediction": prediction_status,
                "runtime_summary": runtime_summary(runtime_fields),
                "last_checked_at": updated_at,
            }
        )

    coverage_rows = sorted(coverage_rows, key=lambda item: str(item["match_id"]))
    write_json(Path(args.normalized_output), coverage_rows)
    write_json(Path(args.public_output), coverage_rows)

    print(f"Wrote {len(coverage_rows)} coverage rows to {args.normalized_output}")
    print(f"Published {len(coverage_rows)} coverage rows to {args.public_output}")


if __name__ == "__main__":
    main()
