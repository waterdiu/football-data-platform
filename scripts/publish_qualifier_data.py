from __future__ import annotations

import argparse
import json
from pathlib import Path

from extract_qualifier_detail_datasets import extract_details, write_json

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = ROOT / "data" / "normalized"
PUBLIC_DIR = ROOT / "data" / "public"
REPORTS_DIR = ROOT / "reports"

MASTER_INPUT_PATH = NORMALIZED_DIR / "world_cup_2026_qualifier_matches_master.json"
PUBLIC_MATCHES_PATH = PUBLIC_DIR / "qualifier-matches.json"
PUBLIC_EVENTS_PATH = PUBLIC_DIR / "qualifier-events.json"
PUBLIC_LINEUPS_PATH = PUBLIC_DIR / "qualifier-lineups.json"
PUBLIC_STATS_PATH = PUBLIC_DIR / "qualifier-match-stats.json"
PUBLISH_REPORT_PATH = REPORTS_DIR / "qualifier_publish_report.json"
DETAIL_REPORT_PATH = REPORTS_DIR / "qualifier_detail_extract_report.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish qualifier public datasets from the platform-owned master source.")
    parser.add_argument("--input", default=str(MASTER_INPUT_PATH), help="platform-owned qualifier master source path")
    parser.add_argument("--matches-output", default=str(PUBLIC_MATCHES_PATH), help="public qualifier matches output path")
    parser.add_argument("--events-output", default=str(PUBLIC_EVENTS_PATH), help="public qualifier events output path")
    parser.add_argument("--lineups-output", default=str(PUBLIC_LINEUPS_PATH), help="public qualifier lineups output path")
    parser.add_argument("--stats-output", default=str(PUBLIC_STATS_PATH), help="public qualifier match stats output path")
    parser.add_argument("--publish-report-output", default=str(PUBLISH_REPORT_PATH), help="qualifier publish report path")
    parser.add_argument("--detail-report-output", default=str(DETAIL_REPORT_PATH), help="qualifier detail extraction report path")
    args = parser.parse_args()

    matches = load_json(Path(args.input))
    if not isinstance(matches, list):
        raise TypeError("qualifier master source must contain a list")

    events, lineups, stats, detail_report = extract_details(matches)
    detail_report["source"] = str(Path(args.input))

    publish_report = {
        "generated_at": "2026-05-15T00:00:00Z",
        "source": str(Path(args.input)),
        "published_matches": len(matches),
        "published_events": len(events),
        "published_lineups": len(lineups),
        "published_stats": len(stats),
    }

    write_json(Path(args.matches_output), matches)
    write_json(Path(args.events_output), events)
    write_json(Path(args.lineups_output), lineups)
    write_json(Path(args.stats_output), stats)
    write_json(Path(args.publish_report_output), publish_report)
    write_json(Path(args.detail_report_output), detail_report)

    print(f"Published {len(matches)} qualifier matches to {args.matches_output}")
    print(f"Published {len(events)} qualifier events to {args.events_output}")
    print(f"Published {len(lineups)} qualifier lineups to {args.lineups_output}")
    print(f"Published {len(stats)} qualifier match stats to {args.stats_output}")
    print(f"Wrote qualifier publish report to {args.publish_report_output}")


if __name__ == "__main__":
    main()
