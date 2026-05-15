from __future__ import annotations

import argparse
import json
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
    **extra: object,
) -> dict[str, object]:
    item: dict[str, object] = {
        "status": status,
        "confidence": confidence,
    }
    if source:
        item["source"] = source
    item.update(extra)
    return item


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
            )
        else:
            result_status = coverage_item(status="missing", confidence="low")

        if prediction:
            prediction_status = coverage_item(
                status="available",
                confidence="medium",
                source=str(prediction.get("model_name") or "unknown"),
            )
        else:
            prediction_status = coverage_item(status="missing", confidence="low")

        if odds:
            bookmaker_count = int(odds.get("bookmaker_count") or 0)
            odds_status = coverage_item(
                status="available" if bookmaker_count > 0 else "partial",
                confidence="high" if odds.get("has_sharp") else "medium",
                source="predictor_runtime",
                bookmaker_count=bookmaker_count,
                has_sharp=bool(odds.get("has_sharp")),
            )
        else:
            odds_status = coverage_item(status="missing", confidence="low", bookmaker_count=0, has_sharp=False)

        if injuries:
            injuries_status = coverage_item(
                status="available",
                confidence=str(injuries.get("confidence") or "medium"),
                source=str(injuries.get("source") or "predictor_runtime"),
            )
        else:
            injuries_status = coverage_item(status="missing", confidence="low")

        if weather:
            weather_status = coverage_item(
                status="available",
                confidence=str(weather.get("confidence") or "medium"),
                source=str(weather.get("source") or "weather_api"),
            )
        else:
            weather_status = coverage_item(status="missing", confidence="low")

        coverage_rows.append(
            {
                "match_id": match_id,
                "fixture": coverage_item(
                    status="available",
                    confidence=fixture_confidence,
                    source=fixture_source,
                ),
                "result": result_status,
                "events": coverage_item(
                    status="available" if match_id in event_match_ids else "missing",
                    confidence="medium" if match_id in event_match_ids else "low",
                    source="football_data_org" if match_id in event_match_ids else None,
                ),
                "lineups": coverage_item(
                    status="available" if match_id in lineup_match_ids else "missing",
                    confidence="medium" if match_id in lineup_match_ids else "low",
                    source="football_data_org" if match_id in lineup_match_ids else None,
                ),
                "match_stats": coverage_item(
                    status="available" if match_id in stats_match_ids else "missing",
                    confidence="medium" if match_id in stats_match_ids else "low",
                    source="football_data_org" if match_id in stats_match_ids else None,
                ),
                "odds": odds_status,
                "injuries": injuries_status,
                "weather": weather_status,
                "prediction": prediction_status,
                "last_checked_at": "2026-05-15T00:00:00Z",
            }
        )

    coverage_rows = sorted(coverage_rows, key=lambda item: str(item["match_id"]))
    write_json(Path(args.normalized_output), coverage_rows)
    write_json(Path(args.public_output), coverage_rows)

    print(f"Wrote {len(coverage_rows)} coverage rows to {args.normalized_output}")
    print(f"Published {len(coverage_rows)} coverage rows to {args.public_output}")


if __name__ == "__main__":
    main()
