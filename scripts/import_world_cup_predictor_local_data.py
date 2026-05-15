from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREDICTOR_ROOT = ROOT.parent / "world-cup-predictor"
NORMALIZED_DIR = ROOT / "data" / "normalized"
REPORTS_DIR = ROOT / "reports"

SHARED_FIXTURES_SOURCE = PREDICTOR_ROOT / "backend" / "data" / "raw" / "world_cup_2026_shared_fixtures.json"
FEATURE_INPUTS_SOURCE = PREDICTOR_ROOT / "backend" / "data" / "processed" / "world_cup_2026_fixtures.json"
PREDICTIONS_SOURCE = PREDICTOR_ROOT / "backend" / "data" / "processed" / "predictions.json"
ODDS_SOURCE = PREDICTOR_ROOT / "backend" / "data" / "runtime" / "odds_snapshots.json"
CONTEXT_SOURCE = PREDICTOR_ROOT / "backend" / "data" / "runtime" / "context" / "world_cup_context_snapshots.jsonl"

UPDATED_AT = "2026-05-15T00:00:00Z"

MASTER_PATHS = {
    "shared_fixtures": NORMALIZED_DIR / "world_cup_2026_predictor_shared_fixtures_master.json",
    "feature_inputs": NORMALIZED_DIR / "world_cup_2026_predictor_feature_inputs_master.json",
    "predictions_source": NORMALIZED_DIR / "world_cup_2026_predictor_predictions_source_master.json",
    "odds_source": NORMALIZED_DIR / "world_cup_2026_predictor_odds_source_master.json",
    "context_source": NORMALIZED_DIR / "world_cup_2026_predictor_context_source_master.json",
}

REPORT_PATH = REPORTS_DIR / "world_cup_predictor_local_import_report.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def payload_size(payload: object) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        return len(payload)
    return 0


def is_world_cup_snapshot(snapshot: dict) -> bool:
    match_id = str(snapshot.get("match_id") or "")
    sport_key = str(snapshot.get("sport_key") or "")
    if match_id.startswith("fifa_world_cup:2026:"):
        return True
    if sport_key in {"soccer_world_cup", "world_cup"}:
        return True
    return False


def load_context_snapshots(path: Path) -> list[dict]:
    if not path.exists():
        return []
    snapshots: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            snapshots.append(payload)
    return snapshots


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import already-downloaded World Cup predictor datasets into platform-owned master files."
    )
    parser.add_argument("--report-output", default=str(REPORT_PATH), help="report output path")
    args = parser.parse_args()

    shared_fixtures = load_json(SHARED_FIXTURES_SOURCE)
    feature_inputs = load_json(FEATURE_INPUTS_SOURCE)
    predictions_source = load_json(PREDICTIONS_SOURCE)
    odds_payload = load_json(ODDS_SOURCE)
    if not isinstance(odds_payload, list):
        raise TypeError("odds_snapshots.json must contain a list")
    world_cup_odds = [item for item in odds_payload if isinstance(item, dict) and is_world_cup_snapshot(item)]
    context_snapshots = load_context_snapshots(CONTEXT_SOURCE)

    write_json(MASTER_PATHS["shared_fixtures"], shared_fixtures)
    write_json(MASTER_PATHS["feature_inputs"], feature_inputs)
    write_json(MASTER_PATHS["predictions_source"], predictions_source)
    write_json(MASTER_PATHS["odds_source"], world_cup_odds)
    write_json(MASTER_PATHS["context_source"], context_snapshots)

    report = {
        "generated_at": UPDATED_AT,
        "source_repository": str(PREDICTOR_ROOT),
        "imported_masters": {
            "shared_fixtures": {
                "source": str(SHARED_FIXTURES_SOURCE),
                "target": str(MASTER_PATHS["shared_fixtures"]),
                "rows": payload_size(shared_fixtures.get("fixtures", [])) if isinstance(shared_fixtures, dict) else payload_size(shared_fixtures),
            },
            "feature_inputs": {
                "source": str(FEATURE_INPUTS_SOURCE),
                "target": str(MASTER_PATHS["feature_inputs"]),
                "fixture_rows": payload_size(feature_inputs.get("fixtures", [])) if isinstance(feature_inputs, dict) else 0,
                "feature_rows": payload_size(feature_inputs.get("features", [])) if isinstance(feature_inputs, dict) else 0,
            },
            "predictions_source": {
                "source": str(PREDICTIONS_SOURCE),
                "target": str(MASTER_PATHS["predictions_source"]),
                "rows": payload_size(predictions_source.get("fixtures", [])) if isinstance(predictions_source, dict) else 0,
            },
            "odds_source": {
                "source": str(ODDS_SOURCE),
                "target": str(MASTER_PATHS["odds_source"]),
                "rows": len(world_cup_odds),
                "note": "当前 predictor 本地 odds snapshots 中未发现 World Cup 2026 条目时会导入为空数组。",
            },
            "context_source": {
                "source": str(CONTEXT_SOURCE),
                "target": str(MASTER_PATHS["context_source"]),
                "rows": len(context_snapshots),
                "exists": CONTEXT_SOURCE.exists(),
                "note": "当前 predictor 若尚未生成 world_cup_context_snapshots.jsonl，则平台只记录缺失状态，不伪造上下文数据。",
            },
        },
    }
    write_json(Path(args.report_output), report)

    print(f"Imported predictor shared fixtures master to {MASTER_PATHS['shared_fixtures']}")
    print(f"Imported predictor feature inputs master to {MASTER_PATHS['feature_inputs']}")
    print(f"Imported predictor predictions source master to {MASTER_PATHS['predictions_source']}")
    print(f"Imported {len(world_cup_odds)} World Cup odds snapshots to {MASTER_PATHS['odds_source']}")
    print(f"Imported {len(context_snapshots)} World Cup context snapshots to {MASTER_PATHS['context_source']}")
    print(f"Wrote predictor local import report to {args.report_output}")


if __name__ == "__main__":
    main()
