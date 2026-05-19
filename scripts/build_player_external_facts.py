from __future__ import annotations

import argparse
import csv
import gzip
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = ROOT / "data" / "normalized"
REPORTS_DIR = ROOT / "reports"
ID_MAP_PATH = NORMALIZED_DIR / "person_id_map_master.json"
PLAYERS_PATH = NORMALIZED_DIR / "world_cup_2026_players_master.json"
TRANSFERMARKT_PLAYERS_PATH = (
    ROOT / "data" / "predictor-assets" / "files" / "raw" / "dcaribou_transfermarkt" / "players.csv.gz"
)
ACTIVITY_PATH = NORMALIZED_DIR / "person_player_dcaribou_activity_master.json"
OUTPUT_PATH = NORMALIZED_DIR / "person_player_external_facts_master.json"
REPORT_PATH = REPORTS_DIR / "player_external_facts_report.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_string(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def int_value(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def iso_date(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text.split(" ")[0]


def age_from_dob(dob: str | None, today: date) -> int | None:
    if not dob:
        return None
    try:
        parsed = date.fromisoformat(dob)
    except ValueError:
        return None
    return today.year - parsed.year - ((today.month, today.day) < (parsed.month, parsed.day))


def source_url(value: object) -> str | None:
    url = clean_string(value)
    if not url:
        return None
    return url.replace("https://www.transfermarkt.co.uk/", "https://www.transfermarkt.com/")


def impact_proxy_score(*, market_value: int | None, caps: int | None, goals: int | None) -> float | None:
    if market_value is None and caps is None and goals is None:
        return None
    market_component = min(60.0, ((market_value or 0) / 100_000_000) * 60.0)
    caps_component = min(25.0, ((caps or 0) / 100) * 25.0)
    goals_component = min(15.0, ((goals or 0) / 50) * 15.0)
    return round(market_component + caps_component + goals_component, 2)


def transfermarkt_index(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            player_id = clean_string(row.get("player_id"))
            if player_id:
                rows[player_id] = row
    return rows


def load_activity_transfermarkt_refs(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = load_json(path)
    if not isinstance(payload, list):
        return {}
    refs: dict[str, dict[str, Any]] = {}
    for row in payload:
        if not isinstance(row, dict):
            continue
        player_id = clean_string(row.get("player_id"))
        source_refs = row.get("source_refs") if isinstance(row.get("source_refs"), dict) else {}
        tm_id = clean_string(source_refs.get("transfermarkt_player_id"))
        if not player_id or not tm_id:
            continue
        refs[player_id] = {
            "key_transfermarkt": tm_id,
            "confidence": source_refs.get("id_map_confidence") or "medium",
            "resolution_method": source_refs.get("id_map_resolution_method") or "dcaribou_activity_transfermarkt_ref",
            "source_file": source_refs.get("source_file") or "person_player_dcaribou_activity_master.json",
        }
    return refs


def build_external_facts(
    *,
    players: list[dict[str, Any]],
    id_map: list[dict[str, Any]],
    activity_tm_refs: dict[str, dict[str, Any]],
    tm_rows_by_id: dict[str, dict[str, str]],
    generated_at: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    id_map_by_person_id = {
        str(row.get("platform_person_id")): row
        for row in id_map
        if row.get("platform_person_id")
    }
    today = datetime.now(timezone.utc).date()
    facts: list[dict[str, Any]] = []
    counts = {
        "players_considered": len(players),
        "id_map_rows": len(id_map),
        "activity_transfermarkt_refs": len(activity_tm_refs),
        "matched_transfermarkt_rows": 0,
        "matched_via_person_id_map": 0,
        "matched_via_activity_ref": 0,
        "club_available": 0,
        "date_of_birth_available": 0,
        "caps_available": 0,
        "goals_available": 0,
        "market_value_available": 0,
        "impact_proxy_available": 0,
    }

    for player in players:
        player_id = str(player.get("player_id") or "").strip()
        if not player_id:
            continue
        id_row = id_map_by_person_id.get(player_id)
        provider_refs = id_row.get("provider_refs") if isinstance(id_row, dict) else {}
        tm_id = clean_string(provider_refs.get("key_transfermarkt") if isinstance(provider_refs, dict) else None)
        id_source = "person_id_map"
        id_confidence = id_row.get("confidence") if isinstance(id_row, dict) else None
        id_resolution_method = id_row.get("resolution_method") if isinstance(id_row, dict) else None
        if not tm_id:
            activity_ref = activity_tm_refs.get(player_id, {})
            tm_id = clean_string(activity_ref.get("key_transfermarkt"))
            if tm_id:
                id_source = "dcaribou_activity_ref"
                id_confidence = activity_ref.get("confidence")
                id_resolution_method = activity_ref.get("resolution_method")
        tm_row = tm_rows_by_id.get(tm_id or "")
        if not tm_row:
            continue

        dob = iso_date(tm_row.get("date_of_birth"))
        caps = int_value(tm_row.get("international_caps"))
        goals = int_value(tm_row.get("international_goals"))
        market_value = int_value(tm_row.get("market_value_in_eur"))
        highest_market_value = int_value(tm_row.get("highest_market_value_in_eur"))
        proxy_score = impact_proxy_score(market_value=market_value, caps=caps, goals=goals)
        club = clean_string(tm_row.get("current_club_name"))
        fact = {
            "player_id": player_id,
            "team_id": player.get("team_id"),
            "name": player.get("name") or player.get("display_name"),
            "source_status": "third_party_transfermarkt_dataset",
            "source": "dcaribou/transfermarkt-datasets",
            "source_url": source_url(tm_row.get("url")),
            "source_refs": {
                "key_transfermarkt": tm_id,
                "reep_id": provider_refs.get("reep_id") if isinstance(provider_refs, dict) else None,
                "identity_ref_source": id_source,
                "person_id_map_confidence": id_confidence,
                "person_id_map_resolution_method": id_resolution_method,
                "source_file": "data/predictor-assets/files/raw/dcaribou_transfermarkt/players.csv.gz",
            },
            "confidence": "medium",
            "direct": {
                "club": club,
                "date_of_birth": dob,
                "age": age_from_dob(dob, today),
                "country_of_birth": clean_string(tm_row.get("country_of_birth")),
                "country_of_citizenship": clean_string(tm_row.get("country_of_citizenship")),
                "position_transfermarkt": clean_string(tm_row.get("position")),
                "sub_position": clean_string(tm_row.get("sub_position")),
                "foot": clean_string(tm_row.get("foot")),
                "height_cm": int_value(tm_row.get("height_in_cm")),
                "contract_expiration_date": iso_date(tm_row.get("contract_expiration_date")),
                "image_url": clean_string(tm_row.get("image_url")),
            },
            "derived": {
                "caps": caps,
                "goals": goals,
                "market_value_eur": market_value,
                "highest_market_value_eur": highest_market_value,
                "impact_proxy_score": proxy_score,
                "impact_proxy_method": "0-100 display proxy from Transfermarkt market value, international caps, and international goals; not an absence-impact percentage and not a model betting signal.",
            },
            "updated_at": generated_at,
        }
        facts.append(fact)
        counts["matched_transfermarkt_rows"] += 1
        counts["matched_via_person_id_map"] += int(id_source == "person_id_map")
        counts["matched_via_activity_ref"] += int(id_source == "dcaribou_activity_ref")
        counts["club_available"] += int(club is not None)
        counts["date_of_birth_available"] += int(dob is not None)
        counts["caps_available"] += int(caps is not None)
        counts["goals_available"] += int(goals is not None)
        counts["market_value_available"] += int(market_value is not None)
        counts["impact_proxy_available"] += int(proxy_score is not None)

    return facts, counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Build third-party player external facts for World Cup profiles.")
    parser.add_argument("--players", default=str(PLAYERS_PATH))
    parser.add_argument("--id-map", default=str(ID_MAP_PATH))
    parser.add_argument("--activity", default=str(ACTIVITY_PATH))
    parser.add_argument("--transfermarkt-players", default=str(TRANSFERMARKT_PLAYERS_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--report-output", default=str(REPORT_PATH))
    args = parser.parse_args()

    generated_at = now_utc()
    players = [row for row in load_json(Path(args.players)) if isinstance(row, dict)]
    id_map = [row for row in load_json(Path(args.id_map)) if isinstance(row, dict)]
    activity_tm_refs = load_activity_transfermarkt_refs(Path(args.activity))
    tm_rows = transfermarkt_index(Path(args.transfermarkt_players))
    facts, counts = build_external_facts(
        players=players,
        id_map=id_map,
        activity_tm_refs=activity_tm_refs,
        tm_rows_by_id=tm_rows,
        generated_at=generated_at,
    )
    write_json(Path(args.output), facts)
    report = {
        "generated_at": generated_at,
        "status": "published",
        "source": "dcaribou/transfermarkt-datasets",
        "source_file": "data/predictor-assets/files/raw/dcaribou_transfermarkt/players.csv.gz",
        "activity_ref_source": str(Path(args.activity)),
        "policy": "External facts supplement public profiles and do not overwrite official FIFA/FA roster masters.",
        "counts": counts,
        "outputs": {
            "normalized": str(Path(args.output)),
        },
    }
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
