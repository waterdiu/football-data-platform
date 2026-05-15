from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_PATH = ROOT / "data" / "public" / "fixtures.json"
LOCAL_FINALS_RESULTS_PATH = ROOT / "data" / "public" / "worldcup-site-finals-results.json"

EVENTS_OUTPUT_PATH = ROOT / "data" / "public" / "finals-events.json"
LINEUPS_OUTPUT_PATH = ROOT / "data" / "public" / "finals-lineups.json"
STATS_OUTPUT_PATH = ROOT / "data" / "public" / "finals-match-stats.json"
REPORT_PATH = ROOT / "reports" / "world_cup_detail_extract_report.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fixture_index(fixtures: list[dict]) -> dict[str, dict]:
    return {str(item["match_id"]): item for item in fixtures if isinstance(item, dict) and "match_id" in item}


def local_fixture_index(fixtures: list[dict]) -> dict[str, str]:
    index: dict[str, str] = {}
    for item in fixtures:
        if not isinstance(item, dict):
            continue
        source_refs = item.get("source_refs") or {}
        local_id = source_refs.get("worldcup_2026_schedule_csv")
        match_id = item.get("match_id")
        if local_id and match_id:
            index[str(local_id)] = str(match_id)
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description="Build World Cup detail datasets from local World Cup site data.")
    parser.add_argument("--events-output", default=str(EVENTS_OUTPUT_PATH), help="events output path")
    parser.add_argument("--lineups-output", default=str(LINEUPS_OUTPUT_PATH), help="lineups output path")
    parser.add_argument("--stats-output", default=str(STATS_OUTPUT_PATH), help="match stats output path")
    parser.add_argument("--report-output", default=str(REPORT_PATH), help="detail extraction report path")
    args = parser.parse_args()

    fixtures = load_json(FIXTURES_PATH)
    local_results = load_json(LOCAL_FINALS_RESULTS_PATH)
    if not isinstance(fixtures, list):
        raise TypeError("fixtures.json must contain a list")
    if not isinstance(local_results, list):
        raise TypeError("worldcup-site-finals-results.json must contain a list")

    fixtures_by_id = fixture_index(fixtures)
    local_to_match_id = local_fixture_index(fixtures)

    events: list[dict[str, object]] = []
    lineups: list[dict[str, object]] = []
    stats: list[dict[str, object]] = []

    for match in local_results:
        if not isinstance(match, dict):
            continue
        target_match_id = local_to_match_id.get(str(match.get("id") or ""))
        if not target_match_id or target_match_id not in fixtures_by_id:
            continue
        for goal in match.get("goals") or []:
            if not isinstance(goal, dict):
                continue
            events.append(
                {
                    "match_id": target_match_id,
                    "team_name": goal.get("team"),
                    "player_name": goal.get("player"),
                    "event_type": "goal",
                    "minute": str(goal.get("minute") or ""),
                    "detail": "penalty" if goal.get("penalty") else "own_goal" if goal.get("ownGoal") else None,
                    "provider": "worldcup_2026_local",
                }
            )

    report = {
        "generated_at": "2026-05-15T00:00:00Z",
        "source": str(LOCAL_FINALS_RESULTS_PATH),
        "fixture_count": len(fixtures),
        "provider_match_count": len(local_results),
        "events_count": len(events),
        "lineups_count": len(lineups),
        "stats_count": len(stats),
        "matches_with_events": len({item["match_id"] for item in events}),
        "matches_with_lineups": len({item["match_id"] for item in lineups}),
        "matches_with_stats": len({item["match_id"] for item in stats}),
        "note": "Current local worldcup/2026 finals results provide goal events only. Lineups and match stats remain unavailable in the migrated local dataset.",
    }

    write_json(Path(args.events_output), events)
    write_json(Path(args.lineups_output), lineups)
    write_json(Path(args.stats_output), stats)
    write_json(Path(args.report_output), report)

    print(f"Wrote {len(events)} finals events to {args.events_output}")
    print(f"Wrote {len(lineups)} finals lineups to {args.lineups_output}")
    print(f"Wrote {len(stats)} finals match stats to {args.stats_output}")
    print(f"Wrote detail extraction report to {args.report_output}")


if __name__ == "__main__":
    main()
