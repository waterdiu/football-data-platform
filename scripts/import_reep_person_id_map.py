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
DEFAULT_PATCH_PATH = ROOT / "data" / "patches" / "person_id_map.manual.json"

TEAM_NATIONALITY_ALIASES = {
    "belgium": {"belgium"},
    "bosnia-and-herzegovina": {"bosnia and herzegovina"},
    "cote-divoire": {"ivory coast", "cote d ivoire", "côte d ivoire"},
    "france": {"france"},
    "haiti": {"haiti"},
    "japan": {"japan"},
    "sweden": {"sweden"},
    "tunisia": {"tunisia"},
}

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


def team_nationality_aliases(team_id: str | None) -> set[str]:
    if not team_id:
        return set()
    return TEAM_NATIONALITY_ALIASES.get(team_id, {team_id.replace("-", " ")})


def add_index_candidate(
    index: dict[str, list[dict[str, Any]]],
    match_key: str,
    candidate: dict[str, Any],
) -> None:
    if not match_key:
        return
    existing_ids = {item.get("reep_id") for item in index[match_key]}
    if candidate.get("reep_id") in existing_ids:
        return
    index[match_key].append(candidate)


def load_reep_index(
    people_path: Path,
    names_path: Path | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], int, int]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    candidates_by_id: dict[str, dict[str, Any]] = {}
    row_count = 0
    alias_row_count = 0
    with people_path.open("r", encoding="utf-8", newline="") as f:
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
                "match_source": "canonical_name",
            }
            candidates_by_id[candidate["reep_id"]] = candidate
            add_index_candidate(index, norm_name(name), candidate)

    if names_path and names_path.exists():
        with names_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                alias_row_count += 1
                reep_id = str(row.get("reep_id") or "").strip()
                base_candidate = candidates_by_id.get(reep_id)
                if not base_candidate:
                    continue
                for field in ("name", "alias"):
                    alias = str(row.get(field) or "").strip()
                    if not alias:
                        continue
                    alias_candidate = dict(base_candidate)
                    alias_candidate["matched_alias"] = alias
                    alias_candidate["match_source"] = "alias"
                    add_index_candidate(index, norm_name(alias), alias_candidate)
    return dict(index), row_count, alias_row_count


def build_id_map(
    *,
    players: list[dict[str, Any]],
    reep_index: dict[str, list[dict[str, Any]]],
    generated_at: str,
    source_version: str,
    manual_overrides: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    counts = {"exact_unique": 0, "ambiguous": 0, "missing": 0}
    unresolved: list[dict[str, Any]] = []

    for player in players:
        platform_person_id = str(player.get("player_id") or "").strip()
        name = str(player.get("name") or player.get("display_name") or "").strip()
        if not platform_person_id or not name:
            continue

        match_key = norm_name(name)
        candidates = reep_index.get(match_key, [])
        resolution_method = None
        if len(candidates) == 1:
            candidate = candidates[0]
            match_status = "exact_unique"
            team_aliases = team_nationality_aliases(str(player.get("team_id") or ""))
            nationality_matches_team = (
                norm_name(str(candidate.get("nationality") or "")) in team_aliases
            )
            is_alias_match = candidate.get("match_source") == "alias"
            confidence = "high" if not is_alias_match or nationality_matches_team else "medium"
            provider_refs = candidate["provider_refs"]
            candidate_payload: list[dict[str, Any]] = []
            resolution_method = "alias_unique" if is_alias_match else "name_unique"
        elif len(candidates) > 1:
            team_aliases = team_nationality_aliases(str(player.get("team_id") or ""))
            nationality_matches = [
                candidate
                for candidate in candidates
                if norm_name(str(candidate.get("nationality") or "")) in team_aliases
            ]
            if len(nationality_matches) == 1:
                candidate = nationality_matches[0]
                match_status = "exact_unique"
                confidence = "medium"
                provider_refs = candidate["provider_refs"]
                candidate_payload = []
                resolution_method = "name_plus_unique_team_nationality"
            else:
                match_status = "ambiguous"
                confidence = "low"
                provider_refs = {}
                candidate_payload = candidates
                resolution_method = "needs_manual_review"
        else:
            match_status = "missing"
            confidence = "none"
            provider_refs = {}
            candidate_payload = []
            resolution_method = "not_found"

        manual_override = manual_overrides.get(platform_person_id)
        if manual_override:
            match_status = "exact_unique"
            confidence = str(manual_override.get("confidence") or "high")
            provider_refs = dict(manual_override.get("provider_refs") or {})
            candidate_payload = []
            resolution_method = "manual_review"

        counts[match_status] += 1
        row = (
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
                "resolution_method": resolution_method,
                "source": "reep",
                "source_license": "CC0-1.0",
                "source_version": source_version,
                "provider_refs": provider_refs,
                "candidates": candidate_payload,
                "manual_review": manual_override or None,
                "updated_at": generated_at,
            }
        )
        rows.append(row)
        if match_status != "exact_unique":
            unresolved.append(row)
    return rows, counts, unresolved


def load_manual_overrides(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise TypeError("manual patch must be an object")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise TypeError("manual patch must contain an entries list")

    overrides: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        platform_person_id = str(entry.get("platform_person_id") or "").strip()
        provider_refs = entry.get("provider_refs")
        if not platform_person_id or not isinstance(provider_refs, dict):
            continue
        if not str(provider_refs.get("reep_id") or "").strip():
            continue
        overrides[platform_person_id] = entry
    return overrides


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Reep person ID mappings for World Cup players.")
    parser.add_argument("--reep-people-csv", required=True, help="Path to Reep data/people.csv")
    parser.add_argument("--reep-names-csv", help="Optional path to Reep data/names.csv aliases")
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
    parser.add_argument(
        "--unresolved-output",
        default=str(REPORTS_DIR / "person_id_map_unresolved_report.json"),
        help="unresolved ambiguous/missing mappings report output",
    )
    parser.add_argument(
        "--manual-patch",
        default=str(DEFAULT_PATCH_PATH),
        help="manual person ID map review patch file",
    )
    args = parser.parse_args()

    generated_at = now_utc()
    players_payload = load_json(Path(args.players_json))
    if not isinstance(players_payload, list):
        raise TypeError("players JSON must be a list")
    players = [item for item in players_payload if isinstance(item, dict)]

    reep_index, reep_rows, reep_alias_rows = load_reep_index(
        Path(args.reep_people_csv),
        Path(args.reep_names_csv) if args.reep_names_csv else None,
    )
    manual_overrides = load_manual_overrides(Path(args.manual_patch))
    id_map, counts, unresolved = build_id_map(
        players=players,
        reep_index=reep_index,
        generated_at=generated_at,
        source_version=args.source_version,
        manual_overrides=manual_overrides,
    )

    write_json(Path(args.output), id_map)
    write_json(Path(args.unresolved_output), unresolved)
    report = {
        "generated_at": generated_at,
        "status": "imported",
        "source": "reep",
        "source_license": "CC0-1.0",
        "source_version": args.source_version,
        "source_people_csv": str(Path(args.reep_people_csv)),
        "source_names_csv": str(Path(args.reep_names_csv)) if args.reep_names_csv else None,
        "source_rows": reep_rows,
        "source_alias_rows": reep_alias_rows,
        "manual_patch": str(Path(args.manual_patch)),
        "manual_overrides_applied": len(manual_overrides),
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
            "unresolved_report": str(Path(args.unresolved_output)),
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
