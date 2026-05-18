from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = ROOT / "data" / "normalized"
REPORTS_DIR = ROOT / "reports"

DEFAULT_DUCKDB_PATHS = [
    ROOT / "data" / "raw" / "vendor" / "dcaribou_transfermarkt" / "transfermarkt-datasets.duckdb",
    Path("/Users/chamcham/Downloads/transfermarkt-datasets.duckdb"),
]

PLAYERS_PATH = NORMALIZED_DIR / "world_cup_2026_players_master.json"
ID_MAP_PATH = NORMALIZED_DIR / "person_id_map_master.json"
OUTPUT_PATH = NORMALIZED_DIR / "person_player_dcaribou_activity_master.json"
REPORT_PATH = REPORTS_DIR / "dcaribou_person_activity_import_report.json"

TEAM_CITIZENSHIP_ALIASES = {
    "korea-republic": {"korea, south", "south korea", "korea republic", "republic of korea"},
}

RE_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def json_default(value: object) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_duckdb_path(value: str | None) -> Path:
    if value:
        path = Path(value).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"DuckDB file not found: {path}")
        return path
    for path in DEFAULT_DUCKDB_PATHS:
        if path.exists():
            return path
    expected = ", ".join(str(path) for path in DEFAULT_DUCKDB_PATHS)
    raise FileNotFoundError(f"DuckDB file not found. Expected one of: {expected}")


def clean_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def strip_accents(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch)
    )


def compact_name(value: str) -> str:
    return RE_NON_ALNUM.sub("", strip_accents(value).lower())


def reverse_compact_name(value: str) -> str:
    parts = [part for part in re.split(r"\s+", strip_accents(value).strip()) if part]
    return compact_name(" ".join(reversed(parts)))


def row_dict(description: list[tuple], row: tuple) -> dict[str, Any]:
    return {description[index][0]: value for index, value in enumerate(row)}


def fetch_dicts(con: Any, query: str) -> list[dict[str, Any]]:
    cursor = con.execute(query)
    description = cursor.description or []
    return [row_dict(description, row) for row in cursor.fetchall()]


def build_target_players(players: list[dict[str, Any]], id_map: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    player_by_id = {str(row.get("player_id")): row for row in players if row.get("player_id")}
    id_map_by_person_id = {
        str(row.get("platform_person_id")): row
        for row in id_map
        if row.get("platform_person_id")
    }
    targets: list[dict[str, Any]] = []
    counts = {
        "platform_players": len(player_by_id),
        "id_map_rows": len(id_map),
        "with_transfermarkt_id": 0,
        "without_transfermarkt_id": 0,
    }

    for platform_player_id, player in sorted(player_by_id.items()):
        id_row = id_map_by_person_id.get(platform_player_id)
        provider_refs = id_row.get("provider_refs") if isinstance(id_row, dict) else {}
        tm_id = clean_int(provider_refs.get("key_transfermarkt") if isinstance(provider_refs, dict) else None)
        if tm_id is None:
            counts["without_transfermarkt_id"] += 1
            continue
        counts["with_transfermarkt_id"] += 1
        targets.append(
            {
                "platform_player_id": platform_player_id,
                "team_id": player.get("team_id"),
                "name": player.get("name") or player.get("display_name"),
                "transfermarkt_player_id": tm_id,
                "id_map_confidence": id_row.get("confidence") if isinstance(id_row, dict) else None,
                "id_map_resolution_method": id_row.get("resolution_method") if isinstance(id_row, dict) else None,
            }
        )
    return targets, counts


def build_dcaribou_name_fallback_targets(
    con: Any,
    players: list[dict[str, Any]],
    id_map: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Use local dcaribou identity rows only when Reep has no TM id and the match is unique.

    This is intentionally conservative. It handles deterministic spelling-order mismatches such
    as Korean roster names ("Son Heungmin") vs Transfermarkt names ("Heung-min Son"), but it does
    not resolve ambiguous same-name rows or fuzzy romanization differences.
    """
    player_by_id = {str(row.get("player_id")): row for row in players if row.get("player_id")}
    id_map_by_person_id = {
        str(row.get("platform_person_id")): row
        for row in id_map
        if row.get("platform_person_id")
    }

    citizenship_rows = fetch_dicts(
        con,
        """
        select
          player_id,
          name,
          country_of_citizenship,
          date_of_birth,
          current_club_name,
          position,
          sub_position,
          international_caps,
          international_goals
        from players
        where country_of_citizenship is not null
        """,
    )
    candidates_by_country: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in citizenship_rows:
        citizenship = str(row.get("country_of_citizenship") or "").lower()
        key = compact_name(str(row.get("name") or ""))
        if key:
            candidates_by_country[citizenship][key].append(row)

    fallback_targets: list[dict[str, Any]] = []
    counts = {
        "dcaribou_name_fallback_considered": 0,
        "dcaribou_name_fallback_unique": 0,
        "dcaribou_name_fallback_ambiguous": 0,
        "dcaribou_name_fallback_missing": 0,
    }

    for platform_player_id, player in sorted(player_by_id.items()):
        id_row = id_map_by_person_id.get(platform_player_id)
        provider_refs = id_row.get("provider_refs") if isinstance(id_row, dict) else {}
        tm_id = clean_int(provider_refs.get("key_transfermarkt") if isinstance(provider_refs, dict) else None)
        if tm_id is not None:
            continue

        team_id = str(player.get("team_id") or "")
        citizenship_aliases = TEAM_CITIZENSHIP_ALIASES.get(team_id)
        if not citizenship_aliases:
            continue

        counts["dcaribou_name_fallback_considered"] += 1
        name = str(player.get("name") or player.get("display_name") or "").strip()
        match_keys = {compact_name(name), reverse_compact_name(name)}
        matches: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        for citizenship in citizenship_aliases:
            country_index = candidates_by_country.get(citizenship, {})
            for match_key in match_keys:
                for candidate in country_index.get(match_key, []):
                    candidate_id = clean_int(candidate.get("player_id"))
                    if candidate_id is None or candidate_id in seen_ids:
                        continue
                    seen_ids.add(candidate_id)
                    matches.append(candidate)

        if len(matches) == 1:
            counts["dcaribou_name_fallback_unique"] += 1
            match = matches[0]
            fallback_targets.append(
                {
                    "platform_player_id": platform_player_id,
                    "team_id": player.get("team_id"),
                    "name": player.get("name") or player.get("display_name"),
                    "transfermarkt_player_id": int(match["player_id"]),
                    "id_map_confidence": "medium",
                    "id_map_resolution_method": "dcaribou_country_reverse_name_unique",
                }
            )
        elif len(matches) > 1:
            counts["dcaribou_name_fallback_ambiguous"] += 1
        else:
            counts["dcaribou_name_fallback_missing"] += 1

    return fallback_targets, counts


def register_targets(con: Any, targets: list[dict[str, Any]]) -> None:
    con.execute("create temp table target_players(player_id integer)")
    con.executemany(
        "insert into target_players values (?)",
        [(row["transfermarkt_player_id"],) for row in targets],
    )


def index_by_player(rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        player_id = clean_int(row.get("player_id"))
        if player_id is not None:
            grouped[player_id].append(row)
    return grouped


def single_by_player(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    output: dict[int, dict[str, Any]] = {}
    for row in rows:
        player_id = clean_int(row.get("player_id"))
        if player_id is not None:
            output[player_id] = row
    return output


def build_activity_rows(con: Any, targets: list[dict[str, Any]], generated_at: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    register_targets(con, targets)

    appearance_summary = single_by_player(
        fetch_dicts(
            con,
            """
            select
              a.player_id,
              count(*) as appearances_total,
              coalesce(sum(a.minutes_played), 0) as minutes_total,
              coalesce(sum(a.goals), 0) as goals_total,
              coalesce(sum(a.assists), 0) as assists_total,
              coalesce(sum(a.yellow_cards), 0) as yellow_cards_total,
              coalesce(sum(a.red_cards), 0) as red_cards_total,
              max(a.date) as latest_appearance_date
            from appearances a
            join target_players t on a.player_id = t.player_id
            group by a.player_id
            """,
        )
    )
    recent_appearances = index_by_player(
        fetch_dicts(
            con,
            """
            select * exclude rn
            from (
              select
                a.player_id,
                a.game_id,
                a.date,
                a.competition_id,
                a.player_club_id,
                a.player_name,
                a.minutes_played,
                a.goals,
                a.assists,
                a.yellow_cards,
                a.red_cards,
                g.home_club_name,
                g.away_club_name,
                g.home_club_goals,
                g.away_club_goals,
                g.round,
                row_number() over (partition by a.player_id order by a.date desc, a.game_id desc) as rn
              from appearances a
              left join games g on cast(a.game_id as varchar) = g.game_id
              join target_players t on a.player_id = t.player_id
            )
            where rn <= 10
            order by player_id, date desc, game_id desc
            """,
        )
    )
    lineup_summary_rows = fetch_dicts(
        con,
        """
        select
          gl.player_id,
          count(*) as lineup_rows,
          sum(case when gl.type = 'starting_lineup' then 1 else 0 end) as starts,
          sum(case when gl.type = 'substitutes' then 1 else 0 end) as bench_rows,
          max(gl.date) as latest_lineup_date
        from game_lineups gl
        join target_players t on gl.player_id = t.player_id
        group by gl.player_id
        """,
    )
    lineup_summary = single_by_player(lineup_summary_rows)
    lineup_numbers = index_by_player(
        fetch_dicts(
            con,
            """
            select * exclude rn
            from (
              select
                gl.player_id,
                gl.number,
                count(*) as sample_size,
                max(gl.date) as latest_seen_date,
                row_number() over (
                  partition by gl.player_id
                  order by count(*) desc, max(gl.date) desc, gl.number
                ) as rn
              from game_lineups gl
              join target_players t on gl.player_id = t.player_id
              where gl.number is not null and gl.number <> ''
              group by gl.player_id, gl.number
            )
            where rn <= 5
            order by player_id, sample_size desc, latest_seen_date desc
            """,
        )
    )
    latest_lineups = index_by_player(
        fetch_dicts(
            con,
            """
            select * exclude rn
            from (
              select
                gl.player_id,
                gl.game_id,
                gl.date,
                gl.type,
                gl.position,
                gl.number,
                gl.team_captain,
                row_number() over (partition by gl.player_id order by gl.date desc, gl.game_id desc) as rn
              from game_lineups gl
              join target_players t on gl.player_id = t.player_id
            )
            where rn <= 10
            order by player_id, date desc, game_id desc
            """,
        )
    )
    event_summary = single_by_player(
        fetch_dicts(
            con,
            """
            select
              ge.player_id,
              count(*) as events_total,
              sum(case when ge.type = 'Goals' then 1 else 0 end) as goal_events,
              sum(case when ge.type = 'Cards' then 1 else 0 end) as card_events,
              sum(case when ge.type = 'Substitutions' then 1 else 0 end) as substitution_events,
              max(ge.date) as latest_event_date
            from game_events ge
            join target_players t on ge.player_id = t.player_id
            group by ge.player_id
            """,
        )
    )
    valuation_history = index_by_player(
        fetch_dicts(
            con,
            """
            select * exclude rn
            from (
              select
                pv.player_id,
                pv.date,
                pv.market_value_in_eur,
                pv.current_club_name,
                pv.current_club_id,
                row_number() over (partition by pv.player_id order by pv.date desc) as rn
              from player_valuations pv
              join target_players t on pv.player_id = t.player_id
            )
            where rn <= 5
            order by player_id, date desc
            """,
        )
    )

    output: list[dict[str, Any]] = []
    counts = {
        "target_players": len(targets),
        "with_appearance_summary": 0,
        "with_lineup_summary": 0,
        "with_lineup_number_candidates": 0,
        "with_event_summary": 0,
        "with_valuation_history": 0,
    }

    for target in targets:
        tm_id = int(target["transfermarkt_player_id"])
        appearances = appearance_summary.get(tm_id, {})
        lineups = lineup_summary.get(tm_id, {})
        events = event_summary.get(tm_id, {})
        numbers = lineup_numbers.get(tm_id, [])
        valuations = valuation_history.get(tm_id, [])
        counts["with_appearance_summary"] += int(bool(appearances))
        counts["with_lineup_summary"] += int(bool(lineups))
        counts["with_lineup_number_candidates"] += int(bool(numbers))
        counts["with_event_summary"] += int(bool(events))
        counts["with_valuation_history"] += int(bool(valuations))

        output.append(
            {
                "player_id": target["platform_player_id"],
                "team_id": target["team_id"],
                "name": target["name"],
                "source_status": "third_party_transfermarkt_dataset",
                "source": "dcaribou/transfermarkt-datasets",
                "confidence": "medium",
                "source_refs": {
                    "transfermarkt_player_id": tm_id,
                    "source_file": "transfermarkt-datasets.duckdb",
                    "source_tables": [
                        "appearances",
                        "game_lineups",
                        "game_events",
                        "player_valuations",
                        "games",
                    ],
                    "id_map_confidence": target["id_map_confidence"],
                    "id_map_resolution_method": target["id_map_resolution_method"],
                },
                "lineup_number_candidates": [
                    {
                        "number": row.get("number"),
                        "sample_size": row.get("sample_size"),
                        "latest_seen_date": json_default(row.get("latest_seen_date")),
                    }
                    for row in numbers
                ],
                "activity": {
                    "appearances_total": appearances.get("appearances_total"),
                    "minutes_total": appearances.get("minutes_total"),
                    "goals_total": appearances.get("goals_total"),
                    "assists_total": appearances.get("assists_total"),
                    "yellow_cards_total": appearances.get("yellow_cards_total"),
                    "red_cards_total": appearances.get("red_cards_total"),
                    "latest_appearance_date": json_default(appearances.get("latest_appearance_date"))
                    if appearances.get("latest_appearance_date")
                    else None,
                },
                "lineups": {
                    "lineup_rows": lineups.get("lineup_rows"),
                    "starts": lineups.get("starts"),
                    "bench_rows": lineups.get("bench_rows"),
                    "latest_lineup_date": json_default(lineups.get("latest_lineup_date"))
                    if lineups.get("latest_lineup_date")
                    else None,
                    "latest_rows": [
                        {
                            "game_id": row.get("game_id"),
                            "date": json_default(row.get("date")),
                            "type": row.get("type"),
                            "position": row.get("position"),
                            "number": row.get("number"),
                            "team_captain": bool(row.get("team_captain")) if row.get("team_captain") is not None else None,
                        }
                        for row in latest_lineups.get(tm_id, [])
                    ],
                },
                "events": {
                    "events_total": events.get("events_total"),
                    "goal_events": events.get("goal_events"),
                    "card_events": events.get("card_events"),
                    "substitution_events": events.get("substitution_events"),
                    "latest_event_date": json_default(events.get("latest_event_date"))
                    if events.get("latest_event_date")
                    else None,
                },
                "recent_appearances": [
                    {
                        "game_id": row.get("game_id"),
                        "date": json_default(row.get("date")),
                        "competition_id": row.get("competition_id"),
                        "home_team": row.get("home_club_name"),
                        "away_team": row.get("away_club_name"),
                        "score": {
                            "home": row.get("home_club_goals"),
                            "away": row.get("away_club_goals"),
                        },
                        "minutes_played": row.get("minutes_played"),
                        "goals": row.get("goals"),
                        "assists": row.get("assists"),
                        "yellow_cards": row.get("yellow_cards"),
                        "red_cards": row.get("red_cards"),
                        "round": row.get("round"),
                    }
                    for row in recent_appearances.get(tm_id, [])
                ],
                "valuation_history": [
                    {
                        "date": json_default(row.get("date")),
                        "market_value_eur": row.get("market_value_in_eur"),
                        "club": row.get("current_club_name"),
                        "club_id": row.get("current_club_id"),
                    }
                    for row in valuations
                ],
                "usage_policy": {
                    "production_use": "supplemental_profile_fact",
                    "not_official_roster_source": True,
                    "not_absence_impact_pct": True,
                    "not_world_cup_lineup_confirmation": True,
                },
                "updated_at": generated_at,
            }
        )

    return output, counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Import narrow dcaribou person activity facts from a local DuckDB file.")
    parser.add_argument("--duckdb", default=None, help="Path to transfermarkt-datasets.duckdb")
    parser.add_argument("--players", default=str(PLAYERS_PATH))
    parser.add_argument("--id-map", default=str(ID_MAP_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--report-output", default=str(REPORT_PATH))
    args = parser.parse_args()

    try:
        import duckdb
    except ModuleNotFoundError as exc:
        raise SystemExit("Missing optional dependency: install with `python3 -m pip install duckdb`.") from exc

    duckdb_path = resolve_duckdb_path(args.duckdb)
    generated_at = now_utc()
    players = [row for row in load_json(Path(args.players)) if isinstance(row, dict)]
    id_map = [row for row in load_json(Path(args.id_map)) if isinstance(row, dict)]
    targets, target_counts = build_target_players(players, id_map)

    con = duckdb.connect(str(duckdb_path), read_only=True)
    fallback_targets, fallback_counts = build_dcaribou_name_fallback_targets(con, players, id_map)
    existing_platform_ids = {row["platform_player_id"] for row in targets}
    merged_targets = targets + [
        row for row in fallback_targets if row["platform_player_id"] not in existing_platform_ids
    ]
    records, activity_counts = build_activity_rows(con, merged_targets, generated_at)
    write_json(Path(args.output), records)
    report = {
        "generated_at": generated_at,
        "status": "published",
        "source": "dcaribou/transfermarkt-datasets",
        "source_license": "CC0-1.0",
        "source_file": duckdb_path.name,
        "source_file_location_policy": "Local raw/vendor or Downloads input; the DuckDB file is not committed to git.",
        "policy": "Narrow supplemental profile facts only; does not overwrite FIFA roster masters and does not publish public API by itself.",
        "counts": {
            **target_counts,
            **fallback_counts,
            "target_players_after_fallback": len(merged_targets),
            **activity_counts,
        },
        "outputs": {
            "normalized": str(Path(args.output)),
        },
    }
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
