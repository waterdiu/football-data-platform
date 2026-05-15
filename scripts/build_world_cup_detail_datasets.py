from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_MATCHES_PATH = ROOT / "data" / "raw" / "football-data-org" / "world_cup_2026_matches.json"
FIXTURES_PATH = ROOT / "data" / "public" / "fixtures.json"

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Build World Cup detail datasets from current provider payloads.")
    parser.add_argument("--events-output", default=str(EVENTS_OUTPUT_PATH), help="events output path")
    parser.add_argument("--lineups-output", default=str(LINEUPS_OUTPUT_PATH), help="lineups output path")
    parser.add_argument("--stats-output", default=str(STATS_OUTPUT_PATH), help="match stats output path")
    parser.add_argument("--report-output", default=str(REPORT_PATH), help="detail extraction report path")
    args = parser.parse_args()

    payload = load_json(RAW_MATCHES_PATH)
    fixtures = load_json(FIXTURES_PATH)
    if not isinstance(payload, dict):
        raise TypeError("Raw football-data payload must be an object")
    if not isinstance(fixtures, list):
        raise TypeError("fixtures.json must contain a list")

    matches = payload.get("matches", [])
    fixtures_by_id = fixture_index(fixtures)

    events: list[dict[str, object]] = []
    lineups: list[dict[str, object]] = []
    stats: list[dict[str, object]] = []

    for match in matches:
        football_data_id = str(match.get("id") or "")
        target_match_id = None
        for fixture in fixtures:
            source_refs = fixture.get("source_refs") or {}
            if str(source_refs.get("football_data_org") or "") == football_data_id:
                target_match_id = str(fixture["match_id"])
                break
        if not target_match_id or target_match_id not in fixtures_by_id:
            continue

        # football-data.org free payload does not currently provide finals events, lineups, or match stats here.
        # Keep extraction pipeline in place so later provider enrichment can populate these datasets without
        # changing consumer contracts.
        _ = match

    report = {
        "generated_at": "2026-05-15T00:00:00Z",
        "source": str(RAW_MATCHES_PATH),
        "fixture_count": len(fixtures),
        "provider_match_count": len(matches),
        "events_count": len(events),
        "lineups_count": len(lineups),
        "stats_count": len(stats),
        "matches_with_events": len({item["match_id"] for item in events}),
        "matches_with_lineups": len({item["match_id"] for item in lineups}),
        "matches_with_stats": len({item["match_id"] for item in stats}),
        "note": "Current football-data.org World Cup payload provides fixtures and results, but no finals events, lineups, or match stats yet.",
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
