from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "data" / "public"
MODEL_DIR = ROOT / "data" / "model"
REPORTS_DIR = ROOT / "reports"
PREDICTOR_BACKEND_DIR = ROOT.parent / "world-cup-predictor" / "backend"

FIXTURES_PATH = PUBLIC_DIR / "fixtures.json"
FINALS_LINEUPS_PATH = PUBLIC_DIR / "finals-lineups.json"
PREDICTOR_ODDS_PATH = (
    PREDICTOR_BACKEND_DIR / "data" / "runtime" / "odds_snapshots.json"
)
PREDICTOR_PREDICTIONS_PATH = PREDICTOR_BACKEND_DIR / "data" / "processed" / "predictions.json"
PREDICTOR_CONTEXT_PATH = PREDICTOR_BACKEND_DIR / "data" / "runtime" / "context" / "world_cup_context_snapshots.jsonl"

ODDS_OUTPUT_PATH = MODEL_DIR / "odds_snapshots.json"
LINEUPS_OUTPUT_PATH = MODEL_DIR / "lineups.json"
INJURIES_OUTPUT_PATH = MODEL_DIR / "injuries.json"
PREMATCH_CONTEXT_OUTPUT_PATH = MODEL_DIR / "prematch_context.json"
WEATHER_OUTPUT_PATH = MODEL_DIR / "weather.json"
REPORT_PATH = REPORTS_DIR / "world_cup_model_dataset_report.json"

SHARP_BOOKMAKERS = {"pinnacle", "circa", "matchbook", "betfair_ex_eu"}


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_fixture_lookup(fixtures: object) -> tuple[set[str], set[tuple[str, str]]]:
    if not isinstance(fixtures, list):
        raise TypeError("fixtures.json must contain a list")

    match_ids: set[str] = set()
    pair_lookup: set[tuple[str, str]] = set()
    for item in fixtures:
        if not isinstance(item, dict):
            continue
        match_id = str(item.get("match_id") or "").strip()
        home = str(item.get("home_team_name") or item.get("home_team") or "").strip().casefold()
        away = str(item.get("away_team_name") or item.get("away_team") or "").strip().casefold()
        if match_id:
            match_ids.add(match_id)
        if home and away:
            pair_lookup.add((home, away))
    return match_ids, pair_lookup


def match_world_cup_odds(
    odds_payload: object,
    *,
    match_ids: set[str],
    pair_lookup: set[tuple[str, str]],
) -> list[dict[str, object]]:
    if not isinstance(odds_payload, list):
        return []

    matched: list[dict[str, object]] = []
    for item in odds_payload:
        if not isinstance(item, dict):
            continue
        raw_match_id = str(item.get("match_id") or "").strip()
        home = str(item.get("home_team") or "").strip()
        away = str(item.get("away_team") or "").strip()
        pair = (home.casefold(), away.casefold())
        if raw_match_id and raw_match_id in match_ids:
            matched.append(item)
            continue
        if pair in pair_lookup:
            matched.append(item)
    return matched


def normalize_odds_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for item in rows:
        bookmakers = item.get("bookmakers")
        if not isinstance(bookmakers, list):
            bookmakers = []
        normalized.append(
            {
                "match_id": item.get("match_id"),
                "sport_key": item.get("sport_key"),
                "date": item.get("date"),
                "home_team": item.get("home_team"),
                "away_team": item.get("away_team"),
                "commence_time": item.get("commence_time"),
                "captured_at": item.get("captured_at"),
                "snapshot_kind": item.get("snapshot_kind"),
                "bookmakers": bookmakers,
                "bookmaker_count": len(bookmakers),
                "has_sharp": any(
                    isinstance(bookmaker, dict)
                    and str(bookmaker.get("key") or "").strip().casefold() in SHARP_BOOKMAKERS
                    for bookmaker in bookmakers
                ),
            }
        )
    return normalized


def normalize_lineups(rows: object, valid_match_ids: set[str]) -> list[dict[str, object]]:
    if not isinstance(rows, list):
        return []
    normalized: list[dict[str, object]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        match_id = str(item.get("match_id") or "").strip()
        if match_id and match_id in valid_match_ids:
            normalized.append(item)
    return normalized


def build_context_status_rows() -> tuple[list[dict[str, object]], dict[str, dict[str, int]], bool]:
    if not PREDICTOR_PREDICTIONS_PATH.exists():
        return [], {}, False
    if str(PREDICTOR_BACKEND_DIR) not in sys.path:
        sys.path.append(str(PREDICTOR_BACKEND_DIR))
    from app.services.context.summary import build_fixture_context_status

    predictions_payload = load_json(PREDICTOR_PREDICTIONS_PATH)
    fixtures = predictions_payload.get("fixtures") if isinstance(predictions_payload, dict) else []
    if not isinstance(fixtures, list):
        fixtures = []
    summary = build_fixture_context_status(fixtures=fixtures, snapshot_path=PREDICTOR_CONTEXT_PATH)
    return (
        summary.get("fixtures") if isinstance(summary.get("fixtures"), list) else [],
        summary.get("source_health") if isinstance(summary.get("source_health"), dict) else {},
        PREDICTOR_CONTEXT_PATH.exists(),
    )


def build_prematch_context_rows(context_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for item in context_rows:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "match_id": item.get("match_id"),
                "date": item.get("date"),
                "home_team": item.get("home_team"),
                "away_team": item.get("away_team"),
                "source_statuses": item.get("source_statuses"),
                "readiness": item.get("readiness"),
                "injury_summary": item.get("injury_summary"),
                "prematch_news_summary": item.get("prematch_news_summary"),
                "predicted_lineup_risk_summary": item.get("predicted_lineup_risk_summary"),
                "absence_evidence_summary": item.get("absence_evidence_summary"),
                "squad_strength_summary": item.get("squad_strength_summary"),
                "lineup_summary": item.get("lineup_summary"),
                "lineup_strength_summary": item.get("lineup_strength_summary"),
                "latest_snapshots_count": len(item.get("latest_snapshots") or []),
            }
        )
    return normalized


def build_injury_rows(context_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in context_rows:
        if not isinstance(item, dict):
            continue
        injury_summary = item.get("injury_summary")
        absence_evidence = item.get("absence_evidence_summary")
        if not injury_summary and not absence_evidence:
            continue
        source_statuses = item.get("source_statuses") or {}
        rows.append(
            {
                "match_id": item.get("match_id"),
                "source": "predictor_context_summary",
                "confidence": "high" if source_statuses.get("injuries") == "available" else "medium",
                "source_status": source_statuses.get("injuries") or "unknown",
                "injury_summary": injury_summary,
                "absence_evidence_summary": absence_evidence,
            }
        )
    return rows


def build_weather_rows(context_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in context_rows:
        if not isinstance(item, dict):
            continue
        match_id = item.get("match_id")
        for snapshot in item.get("latest_snapshots") or []:
            if not isinstance(snapshot, dict) or snapshot.get("entity_type") != "weather":
                continue
            rows.append(
                {
                    "match_id": match_id,
                    "source": snapshot.get("provider") or "openweather",
                    "confidence": "medium" if snapshot.get("source_status") == "available" else "low",
                    "source_status": snapshot.get("source_status") or "unknown",
                    "fetched_at": snapshot.get("fetched_at"),
                    "normalized": snapshot.get("normalized"),
                }
            )
            break
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build World Cup model datasets.")
    parser.add_argument("--odds-output", default=str(ODDS_OUTPUT_PATH), help="odds output path")
    parser.add_argument("--lineups-output", default=str(LINEUPS_OUTPUT_PATH), help="lineups output path")
    parser.add_argument("--injuries-output", default=str(INJURIES_OUTPUT_PATH), help="injuries output path")
    parser.add_argument(
        "--prematch-context-output",
        default=str(PREMATCH_CONTEXT_OUTPUT_PATH),
        help="prematch context output path",
    )
    parser.add_argument("--weather-output", default=str(WEATHER_OUTPUT_PATH), help="weather output path")
    parser.add_argument("--report-output", default=str(REPORT_PATH), help="model dataset report output path")
    args = parser.parse_args()

    fixtures = load_json(FIXTURES_PATH)
    finals_lineups = load_json(FINALS_LINEUPS_PATH)
    fixture_match_ids, fixture_pairs = build_fixture_lookup(fixtures)

    predictor_odds_exists = PREDICTOR_ODDS_PATH.exists()
    predictor_odds_rows = load_json(PREDICTOR_ODDS_PATH) if predictor_odds_exists else []
    matched_odds = match_world_cup_odds(
        predictor_odds_rows,
        match_ids=fixture_match_ids,
        pair_lookup=fixture_pairs,
    )
    normalized_odds = normalize_odds_rows(matched_odds)
    normalized_lineups = normalize_lineups(finals_lineups, fixture_match_ids)
    context_rows, context_source_health, context_snapshot_exists = build_context_status_rows()
    injuries = build_injury_rows(context_rows)
    prematch_context = build_prematch_context_rows(context_rows)
    weather = build_weather_rows(context_rows)

    write_json(Path(args.odds_output), normalized_odds)
    write_json(Path(args.lineups_output), normalized_lineups)
    write_json(Path(args.injuries_output), injuries)
    write_json(Path(args.prematch_context_output), prematch_context)
    write_json(Path(args.weather_output), weather)

    report = {
        "generated_at": "2026-05-15T00:00:00Z",
        "fixtures_total": len(fixture_match_ids),
        "predictor_odds_source_exists": predictor_odds_exists,
        "predictor_odds_source_path": str(PREDICTOR_ODDS_PATH),
        "predictor_odds_source_rows": len(predictor_odds_rows) if isinstance(predictor_odds_rows, list) else 0,
        "predictor_context_source_exists": context_snapshot_exists,
        "predictor_context_source_path": str(PREDICTOR_CONTEXT_PATH),
        "predictor_context_source_health": context_source_health,
        "world_cup_odds_rows": len(normalized_odds),
        "world_cup_lineups_rows": len(normalized_lineups),
        "world_cup_injuries_rows": len(injuries),
        "world_cup_prematch_context_rows": len(prematch_context),
        "world_cup_weather_rows": len(weather),
        "note": (
            "当前共享层会优先读取预测项目的 processed predictions 和 world_cup context snapshots。"
            "如果还没有世界杯专项快照，prematch_context 仍会产出 readiness/source_statuses，"
            "但 injuries、weather、live lineups、world_cup odds 可能为空。"
        ),
    }
    write_json(Path(args.report_output), report)

    print(f"Wrote {len(normalized_odds)} World Cup odds rows to {args.odds_output}")
    print(f"Wrote {len(normalized_lineups)} World Cup model lineups to {args.lineups_output}")
    print(f"Wrote {len(injuries)} World Cup injuries rows to {args.injuries_output}")
    print(f"Wrote {len(prematch_context)} World Cup prematch context rows to {args.prematch_context_output}")
    print(f"Wrote {len(weather)} World Cup weather rows to {args.weather_output}")
    print(f"Wrote model dataset report to {args.report_output}")


if __name__ == "__main__":
    main()
