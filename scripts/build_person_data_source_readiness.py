from __future__ import annotations

import argparse
import csv
import glob
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "person_data_source_readiness.json"

LOCAL_SOURCES = {
    "dcaribou_players": ROOT
    / "data"
    / "predictor-assets"
    / "files"
    / "raw"
    / "dcaribou_transfermarkt"
    / "players.csv.gz",
    "dcaribou_clubs": ROOT
    / "data"
    / "predictor-assets"
    / "files"
    / "raw"
    / "dcaribou_transfermarkt"
    / "clubs.csv.gz",
    "player_ability": ROOT
    / "data"
    / "predictor-assets"
    / "files"
    / "processed"
    / "player_ability.csv",
    "fbref_player_stats": ROOT
    / "data"
    / "predictor-assets"
    / "files"
    / "raw"
    / "fbref_premier_league_player_stats.csv",
    "transfermarkt_player_values": ROOT
    / "data"
    / "predictor-assets"
    / "files"
    / "raw"
    / "transfermarkt_player_values.csv",
    "premier_league_availability": ROOT
    / "data"
    / "predictor-assets"
    / "files"
    / "raw"
    / "premier_league_historical_player_availability.csv",
    "statsbomb_matches": ROOT
    / "data"
    / "predictor-assets"
    / "files"
    / "raw"
    / "statsbomb_matches.json",
}

DCARIBOU_EXPECTED_TABLES = [
    "competitions.csv",
    "games.csv",
    "clubs.csv",
    "players.csv",
    "player_valuations.csv",
    "appearances.csv",
    "game_events.csv",
    "game_lineups.csv",
    "club_games.csv",
    "transfers.csv",
    "countries.csv",
    "national_teams.csv",
]

DCARIBOU_PUBLIC_BASE_URL = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data"

DCARIBOU_PUBLIC_TARGETS = {
    "duckdb": f"{DCARIBOU_PUBLIC_BASE_URL}/transfermarkt-datasets.duckdb",
    "zip": f"{DCARIBOU_PUBLIC_BASE_URL}/transfermarkt-datasets.zip",
    "competitions": f"{DCARIBOU_PUBLIC_BASE_URL}/competitions.csv.gz",
    "games": f"{DCARIBOU_PUBLIC_BASE_URL}/games.csv.gz",
    "clubs": f"{DCARIBOU_PUBLIC_BASE_URL}/clubs.csv.gz",
    "players": f"{DCARIBOU_PUBLIC_BASE_URL}/players.csv.gz",
    "player_valuations": f"{DCARIBOU_PUBLIC_BASE_URL}/player_valuations.csv.gz",
    "appearances": f"{DCARIBOU_PUBLIC_BASE_URL}/appearances.csv.gz",
    "game_events": f"{DCARIBOU_PUBLIC_BASE_URL}/game_events.csv.gz",
    "game_lineups": f"{DCARIBOU_PUBLIC_BASE_URL}/game_lineups.csv.gz",
    "club_games": f"{DCARIBOU_PUBLIC_BASE_URL}/club_games.csv.gz",
    "transfers": f"{DCARIBOU_PUBLIC_BASE_URL}/transfers.csv.gz",
    "countries": f"{DCARIBOU_PUBLIC_BASE_URL}/countries.csv.gz",
    "national_teams": f"{DCARIBOU_PUBLIC_BASE_URL}/national_teams.csv.gz",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def csv_summary(path: Path, *, gzipped: bool = False) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "exists": path.exists(),
        "path": str(path.relative_to(ROOT)) if path.exists() else str(path),
    }
    if not path.exists():
        return summary

    opener = gzip.open if gzipped else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:  # type: ignore[arg-type]
        reader = csv.reader(handle)
        header = next(reader, [])
        rows = sum(1 for _ in reader)
    summary.update(
        {
            "size_bytes": path.stat().st_size,
            "row_count": rows,
            "columns": header,
        }
    )
    return summary


def json_summary(path: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "exists": path.exists(),
        "path": str(path.relative_to(ROOT)) if path.exists() else str(path),
    }
    if not path.exists():
        return summary
    payload = json.loads(path.read_text(encoding="utf-8"))
    sample = payload[0] if isinstance(payload, list) and payload else payload
    summary.update(
        {
            "size_bytes": path.stat().st_size,
            "record_count": len(payload) if hasattr(payload, "__len__") else None,
            "sample_keys": list(sample.keys()) if isinstance(sample, dict) else None,
        }
    )
    return summary


def statsbomb_event_summary(root: Path) -> dict[str, Any]:
    files = sorted(glob.glob(str(root / "data" / "predictor-assets" / "files" / "raw" / "statsbomb_events" / "*.json")))
    event_types: set[str] = set()
    player_names: set[str] = set()
    files_read = 0
    events_read = 0

    for file_name in files:
        try:
            payload = json.loads(Path(file_name).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, list):
            continue
        files_read += 1
        events_read += len(payload)
        for event in payload:
            if not isinstance(event, dict):
                continue
            event_type = event.get("type")
            if isinstance(event_type, dict) and event_type.get("name"):
                event_types.add(str(event_type["name"]))
            player = event.get("player")
            if isinstance(player, dict) and player.get("name"):
                player_names.add(str(player["name"]))

    return {
        "exists": bool(files),
        "event_file_count": len(files),
        "files_read": files_read,
        "events_read": events_read,
        "unique_player_names": len(player_names),
        "event_types": sorted(event_types),
        "production_scope": "style-rule sample only; not a full FIFA World Cup 2026 player coverage source",
    }


def build_report() -> dict[str, Any]:
    dcaribou_local = {
        "players.csv": csv_summary(LOCAL_SOURCES["dcaribou_players"], gzipped=True),
        "clubs.csv": csv_summary(LOCAL_SOURCES["dcaribou_clubs"], gzipped=True),
    }
    present_dcaribou_tables = {"players.csv", "clubs.csv"}
    missing_dcaribou_tables = [name for name in DCARIBOU_EXPECTED_TABLES if name not in present_dcaribou_tables]

    return {
        "generated_at": now_utc(),
        "status": "requires_source_expansion",
        "purpose": "Read-only readiness report for coach/player/referee profile data sources.",
        "rules": {
            "no_public_publish": True,
            "license_gate": "Sources without explicit usable license remain probe-only and must not write normalized/public datasets.",
            "distillation_gate": "Style labels require evidence and sufficient sample; otherwise keep distillation_status=insufficient_sample.",
        },
        "local_sources": {
            "dcaribou_transfermarkt": {
                "license": "CC0-1.0",
                "local_tables": dcaribou_local,
                "expected_tables_from_metadata": DCARIBOU_EXPECTED_TABLES,
                "missing_local_tables": missing_dcaribou_tables,
                "readiness": "partial",
                "can_fill_now": ["player club", "date_of_birth", "age", "caps", "goals", "market value"],
                "blocked_fields": [
                    "shirt_number",
                    "recent minutes",
                    "appearances",
                    "lineup number",
                    "event-backed player style",
                    "coach tenure",
                ],
                "next_action": "Fetch or import the remaining dcaribou CC0 tables before computing true player impact/style.",
            },
            "player_ability": csv_summary(LOCAL_SOURCES["player_ability"]),
            "fbref_player_stats": {
                **csv_summary(LOCAL_SOURCES["fbref_player_stats"]),
                "production_scope": "Premier League player-stat sample; not national-team roster truth.",
            },
            "transfermarkt_player_values": csv_summary(LOCAL_SOURCES["transfermarkt_player_values"]),
            "premier_league_availability": {
                **csv_summary(LOCAL_SOURCES["premier_league_availability"]),
                "production_scope": "historical EPL availability sample; not FIFA World Cup 2026 injury truth.",
            },
            "statsbomb_matches": json_summary(LOCAL_SOURCES["statsbomb_matches"]),
            "statsbomb_events": statsbomb_event_summary(ROOT),
        },
        "github_source_decisions": {
            "dcaribou_transfermarkt_datasets": {
                "repo": "https://github.com/dcaribou/transfermarkt-datasets",
                "license": "CC0-1.0",
                "decision": "production_candidate",
                "public_download_targets": DCARIBOU_PUBLIC_TARGETS,
                "download_probe_status": "public URLs discovered in README; current environment R2 HEAD probes did not complete before timeout on 2026-05-18",
                "note": "Git metadata describes tables such as games, appearances, game_events, game_lineups and club_games, and README exposes R2 download URLs. Current local platform asset only has players/clubs.",
            },
            "salimt_football_datasets": {
                "repo": "https://github.com/salimt/football-datasets",
                "license": "missing_in_github_metadata",
                "decision": "probe_only",
                "license_evidence": {
                    "github_repo_license_metadata": None,
                    "license_file_present": False,
                    "license_file_probe": "GET /repos/salimt/football-datasets/contents/LICENSE returned 404 on 2026-05-18.",
                    "recursive_tree_license_paths": [],
                    "readme_license_badge": "README contains a GitHub License badge pointing to /blob/main/LICENSE, but that target file is absent.",
                },
                "useful_files": [
                    "datalake/transfermarkt/player_profiles/player_profiles.csv",
                    "datalake/transfermarkt/player_national_performances/player_national_performances.csv",
                    "datalake/transfermarkt/player_injuries/player_injuries.csv",
                ],
            },
            "statsbomb_open_data": {
                "repo": "https://github.com/statsbomb/open-data",
                "license": "non-standard / requires review",
                "decision": "research_style_sample",
            },
        },
        "field_readiness": {
            "coach_appointed_at": {
                "status": "blocked",
                "reason": "No reliable structured local source. Requires audited FA/FIFA/Wikidata evidence or manual patch.",
            },
            "coach_contract_until": {
                "status": "blocked",
                "reason": "No reliable structured local source. Requires official contract evidence.",
            },
            "player_shirt_number": {
                "status": "blocked",
                "reason": "Current local roster patches and dcaribou players table do not contain squad shirt numbers.",
            },
            "true_absence_impact_pct": {
                "status": "blocked",
                "reason": "Requires minutes, appearances, availability, and team performance sample; current impact_proxy_score is display-only.",
            },
            "player_style_distillation": {
                "status": "research_ready_not_production_ready",
                "reason": "StatsBomb and FBref samples can validate rules, but 2026 roster coverage is incomplete.",
            },
            "referee_worldcup_assignments": {
                "status": "pending_official_source",
                "reason": "Historical EPL referee samples exist, but FIFA World Cup 2026 assignments are not available in platform data.",
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a readiness report for person profile data sources.")
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args()
    report = build_report()
    write_json(Path(args.output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
