from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX_ROOT = ROOT / "data" / "inbox" / "predictor"
NORMALIZED_DIR = ROOT / "data" / "normalized"
MODEL_DIR = ROOT / "data" / "model"
PUBLIC_DIR = ROOT / "data" / "public"
REPORTS_DIR = ROOT / "reports"

UPDATED_AT = "2026-05-15T00:00:00Z"

WORLD_CUP_INBOX_FILES = {
    "worldcup-2026/predictions.json": {
        "normalized": "world_cup_2026_predictor_predictions_source_master.json",
        "public": "predictions.json",
    },
    "worldcup-2026/odds-snapshots.json": {
        "normalized": "world_cup_2026_model_odds_master.json",
        "model": "odds_snapshots.json",
    },
    "worldcup-2026/lineups.json": {
        "normalized": "world_cup_2026_model_lineups_master.json",
        "model": "lineups.json",
    },
    "worldcup-2026/injuries.json": {
        "normalized": "world_cup_2026_model_injuries_master.json",
        "model": "injuries.json",
    },
    "worldcup-2026/prematch-context.json": {
        "normalized": "world_cup_2026_model_prematch_context_master.json",
        "model": "prematch_context.json",
    },
    "worldcup-2026/weather.json": {
        "normalized": "world_cup_2026_model_weather_master.json",
        "model": "weather.json",
    },
}

PREMIER_LEAGUE_INBOX_FILES = {
    "premier-league/predictions.json": {
        "normalized": "premier_league_predictor_predictions_master.json",
    },
    "premier-league/odds-snapshots.json": {
        "normalized": "premier_league_predictor_odds_master.json",
    },
    "premier-league/context-snapshots.jsonl": {
        "normalized": "premier_league_predictor_context_snapshots_master.jsonl",
    },
}


def ensure_json(path: Path) -> None:
    json.loads(path.read_text(encoding="utf-8"))


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def publish_mapping(mapping: dict[str, dict[str, str]]) -> list[dict[str, object]]:
    published: list[dict[str, object]] = []
    for relative_path, destinations in mapping.items():
        source = INBOX_ROOT / relative_path
        if not source.exists():
            published.append(
                {
                    "source": str(source),
                    "status": "missing",
                    "destinations": destinations,
                }
            )
            continue

        if source.suffix == ".json":
            ensure_json(source)

        copied_to: dict[str, str] = {}
        normalized_name = destinations.get("normalized")
        if normalized_name:
            target = NORMALIZED_DIR / normalized_name
            copy_file(source, target)
            copied_to["normalized"] = str(target)

        model_name = destinations.get("model")
        if model_name:
            target = MODEL_DIR / model_name
            copy_file(source, target)
            copied_to["model"] = str(target)

        public_name = destinations.get("public")
        if public_name:
            target = PUBLIC_DIR / public_name
            copy_file(source, target)
            copied_to["public"] = str(target)

        published.append(
            {
                "source": str(source),
                "status": "published",
                "bytes": source.stat().st_size,
                "destinations": copied_to,
            }
        )
    return published


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish predictor write-back inbox files into platform datasets.")
    parser.add_argument(
        "--report-output",
        default=str(REPORTS_DIR / "predictor_inbox_publish_report.json"),
        help="inbox publish report output path",
    )
    args = parser.parse_args()

    world_cup_results = publish_mapping(WORLD_CUP_INBOX_FILES)
    premier_league_results = publish_mapping(PREMIER_LEAGUE_INBOX_FILES)

    report = {
        "generated_at": UPDATED_AT,
        "inbox_root": str(INBOX_ROOT),
        "world_cup": world_cup_results,
        "premier_league": premier_league_results,
        "published_count": sum(
            1
            for item in [*world_cup_results, *premier_league_results]
            if item.get("status") == "published"
        ),
        "missing_count": sum(
            1
            for item in [*world_cup_results, *premier_league_results]
            if item.get("status") == "missing"
        ),
    }
    Path(args.report_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote predictor inbox publish report to {args.report_output}")


if __name__ == "__main__":
    main()
