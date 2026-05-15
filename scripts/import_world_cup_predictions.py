from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREDICTOR_ROOT = ROOT.parent / "world-cup-predictor"

SOURCE_PREDICTIONS_PATH = PREDICTOR_ROOT / "backend" / "data" / "processed" / "predictions.json"
CANONICAL_TEAMS_PATH = ROOT / "data" / "public" / "canonical_teams.json"
FIXTURES_PATH = ROOT / "data" / "public" / "fixtures.json"

MODEL_OUTPUT_PATH = ROOT / "data" / "model" / "predictions.json"
PUBLIC_OUTPUT_PATH = ROOT / "data" / "public" / "predictions.json"
REPORT_OUTPUT_PATH = ROOT / "reports" / "world_cup_predictions_import_report.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def alias_to_team_id_map(canonical_teams: list[dict]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for team in canonical_teams:
        team_id = str(team["team_id"])
        aliases = set(team.get("aliases", []))
        aliases.add(str(team.get("name", "")))
        localized_name = ((team.get("localized_name") or {}).get("zh-CN")) if isinstance(team.get("localized_name"), dict) else None
        if localized_name:
            aliases.add(str(localized_name))
        for alias in aliases:
            normalized = alias.strip().casefold()
            if normalized:
                mapping[normalized] = team_id
    return mapping


def team_id_from_name(name: str, alias_map: dict[str, str]) -> str | None:
    return alias_map.get(str(name or "").strip().casefold())


def build_fixture_index(fixtures: list[dict]) -> dict[tuple[str, str, str], dict]:
    index: dict[tuple[str, str, str], dict] = {}
    for fixture in fixtures:
        date_key = str(fixture.get("date_utc", ""))[:10]
        home_team_id = str(fixture.get("home_team_id") or "")
        away_team_id = str(fixture.get("away_team_id") or "")
        if date_key and home_team_id and away_team_id:
            index[(date_key, home_team_id, away_team_id)] = fixture
    return index


def build_prediction_record(
    source_prediction: dict,
    fixture: dict,
    model_name: str,
    generated_at: str,
) -> dict[str, object]:
    return {
        "match_id": fixture["match_id"],
        "model_name": model_name,
        "generated_at": generated_at,
        "probabilities": {
            "home_win": float(source_prediction["home_win_probability"]),
            "draw": float(source_prediction["draw_probability"]),
            "away_win": float(source_prediction["away_win_probability"]),
        },
        "predicted_score": None,
        "confidence": "medium",
        "summary": source_prediction.get("summary") or "",
        "inputs": {
            "source_match_id": str(source_prediction.get("match_id") or ""),
            "feature_snapshot_available": bool(source_prediction.get("feature_snapshot")),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import World Cup predictions from the predictor project into the shared data layer.")
    parser.add_argument("--source", default=str(SOURCE_PREDICTIONS_PATH), help="source predictions.json path")
    parser.add_argument("--model-output", default=str(MODEL_OUTPUT_PATH), help="model predictions output path")
    parser.add_argument("--public-output", default=str(PUBLIC_OUTPUT_PATH), help="public predictions output path")
    parser.add_argument("--report-output", default=str(REPORT_OUTPUT_PATH), help="import report output path")
    args = parser.parse_args()

    source_payload = load_json(Path(args.source))
    canonical_teams = load_json(CANONICAL_TEAMS_PATH)
    fixtures = load_json(FIXTURES_PATH)

    if not isinstance(source_payload, dict):
        raise TypeError("source predictions payload must be an object")
    if not isinstance(canonical_teams, list):
        raise TypeError("canonical_teams.json must contain a list")
    if not isinstance(fixtures, list):
        raise TypeError("fixtures.json must contain a list")

    alias_map = alias_to_team_id_map(canonical_teams)
    fixture_index = build_fixture_index(fixtures)

    generated_at = str(source_payload.get("generated_at") or "")
    model_name = str(source_payload.get("model_name") or "unknown")
    source_fixtures = source_payload.get("fixtures", [])
    if not isinstance(source_fixtures, list):
        raise TypeError("source predictions payload fixtures must be a list")

    imported_predictions: list[dict[str, object]] = []
    unmatched_predictions: list[dict[str, object]] = []

    for item in source_fixtures:
        if not isinstance(item, dict):
            continue
        date_key = str(item.get("date") or "")[:10]
        home_team_id = team_id_from_name(str(item.get("home_team") or ""), alias_map)
        away_team_id = team_id_from_name(str(item.get("away_team") or ""), alias_map)
        fixture = fixture_index.get((date_key, home_team_id or "", away_team_id or "")) if date_key and home_team_id and away_team_id else None

        if not fixture:
            unmatched_predictions.append(
                {
                    "source_match_id": str(item.get("match_id") or ""),
                    "date": date_key,
                    "home_team": item.get("home_team"),
                    "away_team": item.get("away_team"),
                    "home_team_id": home_team_id,
                    "away_team_id": away_team_id,
                    "reason": "no authoritative fixture matched by date/home/away",
                }
            )
            continue

        imported_predictions.append(build_prediction_record(item, fixture, model_name, generated_at))

    imported_predictions = sorted(imported_predictions, key=lambda item: str(item["match_id"]))

    report = {
        "generated_at": "2026-05-15T00:00:00Z",
        "source": str(Path(args.source)),
        "source_generated_at": generated_at,
        "source_model_name": model_name,
        "source_fixture_count": len(source_fixtures),
        "imported_prediction_count": len(imported_predictions),
        "unmatched_prediction_count": len(unmatched_predictions),
        "unmatched_predictions": unmatched_predictions,
    }

    write_json(Path(args.model_output), imported_predictions)
    write_json(Path(args.public_output), imported_predictions)
    write_json(Path(args.report_output), report)

    print(f"Imported {len(imported_predictions)} predictions to {args.model_output}")
    print(f"Published {len(imported_predictions)} predictions to {args.public_output}")
    print(f"Wrote import report to {args.report_output}")
    print(f"Unmatched source predictions: {len(unmatched_predictions)}")


if __name__ == "__main__":
    main()
