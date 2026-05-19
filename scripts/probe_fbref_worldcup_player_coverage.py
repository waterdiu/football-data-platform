from __future__ import annotations

import argparse
import csv
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
PLAYERS_PATH = ROOT / "data" / "public" / "api" / "worldcup" / "2026" / "core" / "players.json"
FBREF_PLAYER_STATS_PATH = ROOT / "data" / "predictor-assets" / "files" / "raw" / "fbref_premier_league_player_stats.csv"
PLAYER_PROFILES_PATH = ROOT / "data" / "public" / "api" / "worldcup" / "2026" / "core" / "player-profiles.json"
REPORT_PATH = ROOT / "reports" / "fbref_worldcup_player_coverage_report.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    keep = [ch.lower() if ch.isalnum() else " " for ch in ascii_only]
    return " ".join("".join(keep).split())


def safe_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def safe_int(value: str | None) -> int | None:
    number = safe_float(value)
    return int(number) if number is not None else None


def fbref_stat_row(row: dict[str, str]) -> dict[str, object]:
    return {
        "player": row.get("Player"),
        "squad": row.get("Squad"),
        "position": row.get("Pos"),
        "nineties": safe_float(row.get("90s")),
        "starts": safe_int(row.get("Starts")),
        "goals": safe_int(row.get("Gls")),
        "assists": safe_int(row.get("Ast")),
        "xg": safe_float(row.get("xG")),
        "xag": safe_float(row.get("xAG")),
        "progressive_passes": safe_float(row.get("PrgP")),
        "tackles": safe_float(row.get("Tkl")),
        "interceptions": safe_float(row.get("Int")),
    }


def profile_refs(profile: dict | None) -> dict[str, object]:
    if not isinstance(profile, dict):
        return {}
    direct = profile.get("direct") if isinstance(profile.get("direct"), dict) else {}
    external_fact = direct.get("external_fact") if isinstance(direct.get("external_fact"), dict) else {}
    refs = external_fact.get("source_refs") if isinstance(external_fact.get("source_refs"), dict) else {}
    return {
        "key_transfermarkt": refs.get("key_transfermarkt"),
        "reep_id": refs.get("reep_id"),
        "person_id_map_confidence": refs.get("person_id_map_confidence"),
        "person_id_map_resolution_method": refs.get("person_id_map_resolution_method"),
        "external_fact_confidence": external_fact.get("confidence"),
        "external_fact_source": external_fact.get("source"),
    }


def build_report(players: list[dict], fbref_rows: list[dict[str, str]], profiles: list[dict]) -> dict:
    fbref_by_name: dict[str, list[dict[str, str]]] = {}
    for row in fbref_rows:
        key = normalize_name(row.get("Player"))
        if key:
            fbref_by_name.setdefault(key, []).append(row)

    matched: list[dict[str, object]] = []
    unmatched: list[dict[str, object]] = []
    ambiguous: list[dict[str, object]] = []
    team_counts: dict[str, dict[str, int]] = {}
    profiles_by_id = {profile.get("person_id"): profile for profile in profiles if isinstance(profile, dict)}

    for player in players:
        name = player.get("display_name") or player.get("name")
        key = normalize_name(str(name or ""))
        team_id = str(player.get("team_id") or "unknown")
        team_counts.setdefault(team_id, {"players": 0, "matched": 0, "ambiguous": 0, "unmatched": 0})
        team_counts[team_id]["players"] += 1
        rows = fbref_by_name.get(key, [])
        base = {
            "player_id": player.get("player_id"),
            "name": name,
            "team_id": team_id,
            "position": player.get("position"),
            "profile_refs": profile_refs(profiles_by_id.get(player.get("player_id"))),
        }
        if len(rows) == 1:
            team_counts[team_id]["matched"] += 1
            matched.append({**base, "fbref": fbref_stat_row(rows[0]), "match_method": "normalized_exact_name"})
        elif len(rows) > 1:
            team_counts[team_id]["ambiguous"] += 1
            ambiguous.append(
                {
                    **base,
                    "candidate_count": len(rows),
                    "candidates": [fbref_stat_row(row) for row in rows],
                    "match_method": "normalized_exact_name_multiple_rows",
                }
            )
        else:
            team_counts[team_id]["unmatched"] += 1
            unmatched.append(base)

    numeric_columns = ["90s", "Starts", "Gls", "Ast", "xG", "xAG", "PrgP", "Tkl", "Int"]
    field_coverage = {}
    for column in numeric_columns:
        present = 0
        nonzero = 0
        for row in fbref_rows:
            value = safe_float(row.get(column))
            if value is not None:
                present += 1
                if value != 0:
                    nonzero += 1
        field_coverage[column] = {
            "present_rows": present,
            "nonzero_rows": nonzero,
            "all_zero_or_missing": nonzero == 0,
        }

    usable_fields = [
        column
        for column in numeric_columns
        if not field_coverage[column]["all_zero_or_missing"]
    ]
    zero_only_fields = [
        column
        for column in numeric_columns
        if field_coverage[column]["all_zero_or_missing"]
    ]
    matched_with_high_confidence_external_id = sum(
        1
        for row in matched
        if (row.get("profile_refs") or {}).get("person_id_map_confidence") == "high"
        and (row.get("profile_refs") or {}).get("key_transfermarkt")
    )

    return {
        "generated_at": utc_now(),
        "scope": "fbref_worldcup_player_coverage_probe",
        "mode": "report_only",
        "production_write_allowed": False,
        "normalized_write_allowed": False,
        "inputs": {
            "worldcup_players": str(PLAYERS_PATH.relative_to(ROOT)),
            "fbref_player_stats": str(FBREF_PLAYER_STATS_PATH.relative_to(ROOT)),
        },
        "worldcup_player_count": len(players),
        "fbref_row_count": len(fbref_rows),
        "matched_count": len(matched),
        "matched_with_high_confidence_external_id": matched_with_high_confidence_external_id,
        "ambiguous_count": len(ambiguous),
        "unmatched_count": len(unmatched),
        "matched_rate": round(len(matched) / len(players), 4) if players else 0,
        "team_counts": team_counts,
        "matched": matched,
        "ambiguous": ambiguous,
        "unmatched": unmatched,
        "field_coverage": field_coverage,
        "usable_fields": usable_fields,
        "zero_only_fields": zero_only_fields,
        "conclusion": (
            "fbref_epl_player_stats_can_enrich_world_cup_players_with_current_or_recent_epl_activity"
            if matched
            else "no_current_world_cup_players_matched_fbref_epl_stats"
        ),
        "limits": [
            "name-only matching is not enough for production writes",
            "high-confidence external ids in this report are Transfermarkt/Reep refs, not FBref ids",
            "this report uses local predictor-assets FBref CSV, not live FBref scraping",
            "coverage is limited to Premier League players present in the FBref asset",
            "columns reported as zero_only_fields must not be treated as real zero performance",
            "do not write to normalized/public until player_id mapping and license/source policy are approved",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe whether local FBref EPL player stats can enrich World Cup roster players.")
    parser.add_argument("--players", default=str(PLAYERS_PATH))
    parser.add_argument("--fbref", default=str(FBREF_PLAYER_STATS_PATH))
    parser.add_argument("--profiles", default=str(PLAYER_PROFILES_PATH))
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args()

    players_payload = load_json(Path(args.players))
    if not isinstance(players_payload, list):
        raise TypeError("players payload must be a list")
    fbref_rows = load_csv(Path(args.fbref))
    profiles_payload = load_json(Path(args.profiles))
    if not isinstance(profiles_payload, list):
        raise TypeError("profiles payload must be a list")
    report = build_report(players_payload, fbref_rows, profiles_payload)
    write_json(Path(args.output), report)
    print(
        json.dumps(
            {
                "worldcup_player_count": report["worldcup_player_count"],
                "fbref_row_count": report["fbref_row_count"],
                "matched_count": report["matched_count"],
                "ambiguous_count": report["ambiguous_count"],
                "unmatched_count": report["unmatched_count"],
                "matched_rate": report["matched_rate"],
                "output": args.output,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
