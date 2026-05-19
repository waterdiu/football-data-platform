from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
READINESS_PATH = REPORTS_DIR / "world_cup_pre_tournament_readiness.json"
OUTPUT_PATH = REPORTS_DIR / "world_cup_daily_action_items.json"

GENERATED_AT = "2026-05-19T00:00:00Z"


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def make_item(check: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": check.get("id"),
        "title": check.get("title"),
        "phase": check.get("phase"),
        "severity": check.get("severity"),
        "status": check.get("status"),
        "detail": check.get("detail"),
        "next_action": check.get("next_action"),
    }


def bucket_for(check: dict[str, Any]) -> str:
    status = check.get("status")
    check_id = check.get("id")
    severity = check.get("severity")

    if status == "blocked":
        return "do_now"
    if status == "attention":
        return "do_now" if severity == "P0" else "monitor"
    if status == "pending_plan":
        return "wait_for_plan"
    if status == "pending_window":
        return "wait_for_window"
    if status == "pass":
        if check_id in {
            "coach_profiles",
            "world_cup_referee_profiles",
            "person_profile_snapshot_inputs",
            "core_host_city_venues",
            "team_recent_matches",
        }:
            return "monitor"
        return "no_action"
    return "monitor"


def main() -> None:
    readiness = load_json(READINESS_PATH)
    checks = readiness.get("checks") if isinstance(readiness, dict) else []
    if not isinstance(checks, list):
        checks = []

    buckets: dict[str, list[dict[str, Any]]] = {
        "do_now": [],
        "wait_for_plan": [],
        "wait_for_window": [],
        "monitor": [],
        "handoff": [],
        "no_action": [],
    }

    for check in checks:
        if not isinstance(check, dict):
            continue
        bucket = bucket_for(check)
        buckets.setdefault(bucket, []).append(make_item(check))

    handoff_candidates = []
    for item in buckets["do_now"]:
        item_id = item.get("id")
        if item_id in {"runtime_odds", "person_profile_snapshot_inputs"}:
            handoff_candidates.append(
                {
                    **item,
                    "handoff_target": "world-cup-predictor" if item_id == "person_profile_snapshot_inputs" else "data-platform/odds-source-research",
                }
            )
    buckets["handoff"] = handoff_candidates

    summary = {
        "do_now": len(buckets["do_now"]),
        "wait_for_plan": len(buckets["wait_for_plan"]),
        "wait_for_window": len(buckets["wait_for_window"]),
        "monitor": len(buckets["monitor"]),
        "handoff": len(buckets["handoff"]),
        "no_action": len(buckets["no_action"]),
    }

    payload = {
        "generated_at": GENERATED_AT,
        "source_report": str(READINESS_PATH.relative_to(ROOT)),
        "scope": "worldcup_2026_daily_actions",
        "summary": summary,
        "actions": buckets,
        "recommended_today": [
            item
            for item in buckets["do_now"]
            if item.get("severity") == "P0"
        ],
        "notes": [
            "pending_plan 项等待 API 套餐或 key，不应反复调用受限接口。",
            "pending_window 项等待官方名单、赛前首发、天气预报窗口或比赛窗口。",
            "pass 但仍在 monitor 的项表示基础可用，但仍有增强字段或人工复核任务。",
            "handoff 只列需要跨模型/赔率研究边界沟通的事项，不代表本脚本会修改其他项目。",
        ],
    }
    write_json(OUTPUT_PATH, payload)
    print(f"Wrote daily action items to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
