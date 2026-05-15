from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "data" / "public"

QUALIFIER_MATCHES_PATH = PUBLIC_DIR / "qualifier-matches.json"
QUALIFIER_EVENTS_PATH = PUBLIC_DIR / "qualifier-events.json"
QUALIFIER_LINEUPS_PATH = PUBLIC_DIR / "qualifier-lineups.json"
QUALIFIER_STATS_PATH = PUBLIC_DIR / "qualifier-match-stats.json"
REPORT_PATH = ROOT / "reports" / "qualifier_detail_extract_report.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def extract_details(matches: list[object]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    events: list[dict[str, object]] = []
    lineups: list[dict[str, object]] = []
    stats: list[dict[str, object]] = []

    for match in matches:
        if not isinstance(match, dict):
            continue

        match_id = str(match.get("id") or "")
        base = {
            "match_id": match_id,
            "confederation_id": match.get("confederationId"),
            "stage": match.get("stage"),
            "date_label": match.get("dateLabel"),
            "home_team": match.get("homeTeam"),
            "away_team": match.get("awayTeam"),
            "source_label": match.get("sourceLabel"),
        }

        for event in match.get("events") or []:
            events.append(
                {
                    **base,
                    "minute": event.get("minute"),
                    "team": event.get("team"),
                    "type": event.get("type"),
                    "player": event.get("player"),
                    "detail": event.get("detail"),
                }
            )

        for lineup in match.get("lineups") or []:
            lineups.append(
                {
                    **base,
                    "team": lineup.get("team"),
                    "formation": lineup.get("formation"),
                    "starters": lineup.get("starters") or [],
                    "substitutes": lineup.get("substitutes") or [],
                }
            )

        for stat in match.get("stats") or []:
            stats.append(
                {
                    **base,
                    "label": stat.get("label"),
                    "home": stat.get("home"),
                    "away": stat.get("away"),
                }
            )

    report = {
        "generated_at": "2026-05-15T00:00:00Z",
        "match_count": len(matches),
        "events_count": len(events),
        "lineups_count": len(lineups),
        "stats_count": len(stats),
        "matches_with_events": len({item["match_id"] for item in events}),
        "matches_with_lineups": len({item["match_id"] for item in lineups}),
        "matches_with_stats": len({item["match_id"] for item in stats}),
    }
    return events, lineups, stats, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract qualifier events, lineups, and match stats from qualifier-matches.json")
    parser.add_argument("--input", default=str(QUALIFIER_MATCHES_PATH), help="qualifier matches input path")
    parser.add_argument("--events-output", default=str(QUALIFIER_EVENTS_PATH), help="qualifier events output path")
    parser.add_argument("--lineups-output", default=str(QUALIFIER_LINEUPS_PATH), help="qualifier lineups output path")
    parser.add_argument("--stats-output", default=str(QUALIFIER_STATS_PATH), help="qualifier match stats output path")
    parser.add_argument("--report-output", default=str(REPORT_PATH), help="detail extraction report path")
    args = parser.parse_args()

    matches = load_json(Path(args.input))
    if not isinstance(matches, list):
        raise TypeError("qualifier-matches.json must contain a list")

    events, lineups, stats, report = extract_details(matches)
    report["source"] = str(Path(args.input))

    write_json(Path(args.events_output), events)
    write_json(Path(args.lineups_output), lineups)
    write_json(Path(args.stats_output), stats)
    write_json(Path(args.report_output), report)

    print(f"Wrote {len(events)} qualifier events to {args.events_output}")
    print(f"Wrote {len(lineups)} qualifier lineups to {args.lineups_output}")
    print(f"Wrote {len(stats)} qualifier match stats to {args.stats_output}")
    print(f"Wrote detail extraction report to {args.report_output}")


if __name__ == "__main__":
    main()
