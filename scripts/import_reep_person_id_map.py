#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLAYERS_PATH = ROOT / "data" / "public" / "players.json"
NORMALIZED_DIR = ROOT / "data" / "normalized"
REPORTS_DIR = ROOT / "reports"

PROVIDER_FIELDS = [
    "reep_id",
    "key_wikidata",
    "key_transfermarkt",
    "key_transfermarkt_manager",
    "key_fbref",
    "key_soccerway",
    "key_sofascore",
    "key_flashscore",
    "key_opta",
    "key_premier_league",
    "key_11v11",
    "key_espn",
    "key_national_football_teams",
    "key_worldfootball",
    "key_soccerbase",
    "key_kicker",
    "key_uefa",
    "key_lequipe",
    "key_fff_fr",
    "key_serie_a",
    "key_besoccer",
    "key_footballdatabase_eu",
    "key_eu_football_info",
    "key_hugman",
    "key_german_fa",
    "key_statmuse_pl",
    "key_sofifa",
    "key_soccerdonna",
    "key_dongqiudi",
    "key_understat",
    "key_whoscored",
    "key_fbref_verified",
    "key_sportmonks",
    "key_api_football",
    "key_fotmob",
    "key_opta_numeric",
    "key_thesportsdb",
    "key_skillcorner",
    "key_wyscout",
    "key_impect",
    "key_heimspiel",
    "key_capology",
]

RE_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
RE_SPACES = re.compile(r"\s+")


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def strip_accents(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch)
    )


def norm_name(value: str) -> str:
    lowered = strip_accents(value).lower().strip()
    normalized = RE_NON_ALNUM.sub(" ", lowered)
    return RE_SPACES.sub(" ", normalized).strip()


def compact_provider_refs(row: dict[str, str]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for field in PROVIDER_FIELDS:
        value = str(row.get(field) or "").strip()
        if value:
            refs[field] = value
    return refs


def load_reep_index(path: Path) -> tuple[dict[str, list[dict[str, Any]]], int]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    row_count = 0
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_count += 1
            name = str(row.get("name") or row.get("full_name") or "").strip()
            if not name:
                continue
            if str(row.get("type") or "").strip() != "player":
                continue
            candidate = {
                "reep_id": str(row.get("reep_id") or "").strip(),
                "name": name,
                "full_name": str(row.get("full_name") or "").strip() or None,
                "date_of_birth": str(row.get("date_of_birth") or "").strip() or None,
                "nationality": str(row.get("nationality") or "").strip() or None,
                "position": str(row.get("position") or "").strip() or None,
                "provider_refs": compact_provider_refs(row),
            }
            index[norm_name(name)].append(candidate)
    return dict(index), row_count


def build_id_map(
    *,
    players: list[dict[str, Any]],
    reep_index: dict[str, list[dict[str, Any]]],
    generated_at: str,
    source_version: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    counts = {"exact_unique": 0, "ambiguous": 0, "missing": 0}

    for player in players:
        platform_person_id = str(player.get("player_id") or "").strip()
        name = str(player.get("name") or player.get("display_name") or "").strip()
        if not platform_person_id or not name:
            continue

        match_key = norm_name(name)
        candidates = reep_index.get(match_key, [])
        if len(candidates) == 1:
            candidate = candidates[0]
            match_status = "exact_unique"
            confidence = "high"
            provider_refs = candidate["provider_refs"]
            candidate_payload: list[dict[str, Any]] = []
        elif len(candidates) > 1:
            match_status = "ambiguous"
            confidence = "low"
            provider_refs = {}
            candidate_payload = candidates
        else:
            match_status = "missing"
            confidence = "none"
            provider_refs = {}
            candidate_payload = []

        counts[match_status] += 1
        rows.append(
            {
                "platform_person_id": platform_person_id,
                "person_type": "player",
                "competition_id": "fifa_world_cup",
                "season_id": "2026",
                "team_id": player.get("team_id"),
                "name": name,
                "match_key": match_key,
                "match_status": match_status,
                "confidence": confidence,
                "source": "reep",
                "source_license": "CC0-1.0",
                "source_version": source_version,
                "provider_refs": provider_refs,
                "candidates": candidate_payload,
                "updated_at": generated_at,
            }
        )
    return rows, counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Reep person ID mappings for World Cup players.")
    parser.add_argument("--reep-people-csv", required=True, help="Path to Reep data/people.csv")
    parser.add_argument("--players-json", default=str(PLAYERS_PATH), help="Platform players JSON")
    parser.add_argument(
        "--source-version",
        default="2026.17",
        help="Reep data_version from data/meta.json",
    )
    parser.add_argument(
        "--output",
        default=str(NORMALIZED_DIR / "person_id_map_master.json"),
        help="normalized person ID map output",
    )
    parser.add_argument(
        "--report-output",
        default=str(REPORTS_DIR / "person_id_map_import_report.json"),
        help="import report output",
    )
    args = parser.parse_args()

    generated_at = now_utc()
    players_payload = load_json(Path(args.players_json))
    if not isinstance(players_payload, list):
        raise TypeError("players JSON must be a list")
    players = [item for item in players_payload if isinstance(item, dict)]

    reep_index, reep_rows = load_reep_index(Path(args.reep_people_csv))
    id_map, counts = build_id_map(
        players=players,
        reep_index=reep_index,
        generated_at=generated_at,
        source_version=args.source_version,
    )

    write_json(Path(args.output), id_map)
    report = {
        "generated_at": generated_at,
        "status": "imported",
        "source": "reep",
        "source_license": "CC0-1.0",
        "source_version": args.source_version,
        "source_people_csv": str(Path(args.reep_people_csv)),
        "source_rows": reep_rows,
        "players_considered": len(players),
        "rows_written": len(id_map),
        "counts": counts,
        "coverage": {
            "matched_count": counts["exact_unique"] + counts["ambiguous"],
            "unambiguous_count": counts["exact_unique"],
            "ambiguous_count": counts["ambiguous"],
            "missing_count": counts["missing"],
            "hit_rate": round((counts["exact_unique"] + counts["ambiguous"]) / len(players), 6) if players else 0,
            "unambiguous_rate": round(counts["exact_unique"] / len(players), 6) if players else 0,
        },
        "outputs": {
            "normalized": str(Path(args.output)),
        },
        "notes": [
            "This import writes an ID map only; it does not overwrite FIFA/FA roster facts.",
            "Ambiguous rows require DOB, club, provider ID, or manual review before use as high-confidence mappings.",
        ],
    }
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

