from __future__ import annotations

import argparse
import json
from pathlib import Path

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = ROOT / "data" / "normalized"
MODEL_DIR = ROOT / "data" / "model"
REPORTS_DIR = ROOT / "reports"

UPDATED_AT = "2026-05-15T00:00:00Z"

MASTER_TO_MODEL = {
    "world_cup_2026_model_odds_master.json": "odds_snapshots.json",
    "world_cup_2026_model_lineups_master.json": "lineups.json",
    "world_cup_2026_model_injuries_master.json": "injuries.json",
    "world_cup_2026_model_prematch_context_master.json": "prematch_context.json",
    "world_cup_2026_model_weather_master.json": "weather.json",
}

REPORT_PATH = REPORTS_DIR / "world_cup_model_dataset_report.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def payload_size(payload: object) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        return len(payload)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish World Cup model runtime datasets from platform-owned masters.")
    parser.add_argument("--report-output", default=str(REPORT_PATH), help="model dataset report output path")
    args = parser.parse_args()

    counts: dict[str, int] = {}
    for master_name, output_name in MASTER_TO_MODEL.items():
        payload = load_json(NORMALIZED_DIR / master_name)
        write_json(MODEL_DIR / output_name, payload)
        counts[output_name] = payload_size(payload)

    report = {
        "generated_at": UPDATED_AT,
        "source_type": "platform_owned_model_masters",
        "world_cup_odds_rows": counts["odds_snapshots.json"],
        "world_cup_lineups_rows": counts["lineups.json"],
        "world_cup_injuries_rows": counts["injuries.json"],
        "world_cup_prematch_context_rows": counts["prematch_context.json"],
        "world_cup_weather_rows": counts["weather.json"],
        "note": (
            "当前共享层主发布流水线已经从平台 own 的 model master 文件发布运行时模型数据。"
            "predictor 仓库现在只应作为可选回灌来源，而不是主发布阻塞项。"
        ),
    }
    write_json(Path(args.report_output), report)

    print(f"Wrote {counts['odds_snapshots.json']} World Cup odds rows to {MODEL_DIR / 'odds_snapshots.json'}")
    print(f"Wrote {counts['lineups.json']} World Cup model lineups to {MODEL_DIR / 'lineups.json'}")
    print(f"Wrote {counts['injuries.json']} World Cup injuries rows to {MODEL_DIR / 'injuries.json'}")
    print(f"Wrote {counts['prematch_context.json']} World Cup prematch context rows to {MODEL_DIR / 'prematch_context.json'}")
    print(f"Wrote {counts['weather.json']} World Cup weather rows to {MODEL_DIR / 'weather.json'}")
    print(f"Wrote model dataset report to {args.report_output}")


if __name__ == "__main__":
    main()
