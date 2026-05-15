from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "data" / "public"
NORMALIZED_DIR = ROOT / "data" / "normalized"
MOCK_DIR = ROOT / "data" / "mock"

FIXTURES_PATH = PUBLIC_DIR / "fixtures.json"
CANONICAL_TEAMS_PATH = PUBLIC_DIR / "canonical_teams.json"
DEFAULT_FOOTBALL_DATA_PAYLOAD = MOCK_DIR / "football_data_world_cup_matches.sample.json"
RAW_FOOTBALL_DATA_PAYLOAD = ROOT / "data" / "raw" / "football-data-org" / "world_cup_2026_matches.json"
OUTPUT_MAPPING_PATH = NORMALIZED_DIR / "world_cup_2026_authoritative_match_map.json"
OUTPUT_RECONCILED_FIXTURES_PATH = NORMALIZED_DIR / "world_cup_2026_authoritative_fixtures.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def alias_to_team_id_map(canonical_teams: list[dict]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for team in canonical_teams:
        team_id = str(team["team_id"])
        aliases = set(team.get("aliases", []))
        aliases.add(str(team.get("name", "")))
        localized_name = ((team.get("localized_name") or {}).get("zh-CN")) if isinstance(team.get("localized_name"), dict) else None
        if localized_name:
            aliases.add(str(localized_name))
        for alias in aliases:
            normalized = alias.strip().casefold()
            if normalized:
                mapping[normalized] = team_id
    return mapping


def team_id_from_provider_name(name: str, alias_map: dict[str, str]) -> str | None:
    return alias_map.get(str(name or "").strip().casefold())


def fixture_match_key(date_utc: str, home_team_id: str, away_team_id: str) -> tuple[str, str, str]:
    return (date_utc, home_team_id, away_team_id)


def date_part(value: str) -> str:
    return value[:10]


def normalize_stage(value: str) -> str:
    text = str(value or "").strip().casefold()
    mapping = {
        "group": "group",
        "group_stage": "group",
        "last_32": "round_of_32",
        "round_of_32": "round_of_32",
        "last_16": "round_of_16",
        "round_of_16": "round_of_16",
        "quarter_finals": "quarterfinal",
        "quarterfinal": "quarterfinal",
        "semi_finals": "semifinal",
        "semifinal": "semifinal",
        "third_place": "third_place",
        "final": "final",
    }
    return mapping.get(text, text)


def build_existing_fixture_indexes(fixtures: list[dict]) -> tuple[
    dict[tuple[str, str, str], dict],
    dict[tuple[str, str, str], list[dict]],
    dict[tuple[str, str], list[dict]],
]:
    exact_index: dict[tuple[str, str, str], dict] = {}
    date_pair_index: dict[tuple[str, str, str], list[dict]] = {}
    stage_datetime_index: dict[tuple[str, str], list[dict]] = {}
    for fixture in fixtures:
        exact_key = fixture_match_key(
            str(fixture["date_utc"]),
            str(fixture["home_team_id"]),
            str(fixture["away_team_id"]),
        )
        exact_index[exact_key] = fixture

        date_key = (
            date_part(str(fixture["date_utc"])),
            str(fixture["home_team_id"]),
            str(fixture["away_team_id"]),
        )
        date_pair_index.setdefault(date_key, []).append(fixture)

        stage_key = (
            normalize_stage(str(fixture.get("stage") or "")),
            str(fixture["date_utc"]),
        )
        stage_datetime_index.setdefault(stage_key, []).append(fixture)
    return exact_index, date_pair_index, stage_datetime_index


def build_authoritative_match_id(football_data_id: str) -> str:
    return f"fifa_world_cup:2026:fdorg:{football_data_id}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Map bootstrap World Cup fixtures to authoritative football-data.org match IDs.")
    parser.add_argument(
        "--football-data-payload",
        default=str(RAW_FOOTBALL_DATA_PAYLOAD if RAW_FOOTBALL_DATA_PAYLOAD.exists() else DEFAULT_FOOTBALL_DATA_PAYLOAD),
        help="Path to football-data.org matches payload JSON.",
    )
    args = parser.parse_args()

    fixtures = load_json(FIXTURES_PATH)
    canonical_teams = load_json(CANONICAL_TEAMS_PATH)
    football_data_payload = load_json(Path(args.football_data_payload))

    if not isinstance(fixtures, list):
        raise TypeError("fixtures.json must contain a list")
    if not isinstance(canonical_teams, list):
        raise TypeError("canonical_teams.json must contain a list")

    alias_map = alias_to_team_id_map(canonical_teams)
    exact_index, date_pair_index, stage_datetime_index = build_existing_fixture_indexes(fixtures)
    matches = football_data_payload.get("matches", []) if isinstance(football_data_payload, dict) else []

    mappings: list[dict[str, object]] = []
    reconciled_fixtures: list[dict[str, object]] = []
    unmatched_provider_matches: list[dict[str, object]] = []

    for match in matches:
        provider_id = str(match.get("id", "")).strip()
        date_utc = str(match.get("utcDate", "")).strip()
        home_name = str((match.get("homeTeam") or {}).get("name") or "").strip()
        away_name = str((match.get("awayTeam") or {}).get("name") or "").strip()

        home_team_id = team_id_from_provider_name(home_name, alias_map)
        away_team_id = team_id_from_provider_name(away_name, alias_map)

        existing = None
        reason = ""

        if provider_id and date_utc and home_team_id and away_team_id:
            exact_key = fixture_match_key(date_utc, home_team_id, away_team_id)
            existing = exact_index.get(exact_key)
            if not existing:
                date_key = (date_part(date_utc), home_team_id, away_team_id)
                candidates = date_pair_index.get(date_key, [])
                if len(candidates) == 1:
                    existing = candidates[0]
                elif len(candidates) > 1:
                    reason = "multiple bootstrap fixtures matched by date/home/away"

        if not existing and provider_id and date_utc and not home_name and not away_name:
            stage_key = (normalize_stage(str(match.get("stage") or "")), date_utc)
            candidates = stage_datetime_index.get(stage_key, [])
            if len(candidates) == 1:
                existing = candidates[0]
            elif len(candidates) > 1:
                reason = "multiple bootstrap fixtures matched by stage/date"

        if not existing:
            unmatched_provider_matches.append(
                {
                    "provider_id": provider_id,
                    "utcDate": date_utc,
                    "homeTeam": home_name,
                    "awayTeam": away_name,
                    "reason": reason or "missing canonical mapping or no bootstrap fixture match",
                }
            )
            continue

        authoritative_match_id = build_authoritative_match_id(provider_id)
        source_refs = dict(existing.get("source_refs") or {})
        source_refs["football_data_org"] = provider_id

        reconciled = {
            **existing,
            "match_id": authoritative_match_id,
            "source_refs": source_refs,
        }
        reconciled_fixtures.append(reconciled)
        mappings.append(
            {
                "temporary_match_id": existing["match_id"],
                "authoritative_match_id": authoritative_match_id,
                "source_refs": source_refs,
                "match_key": {
                    "date_utc": date_utc,
                    "home_team_id": home_team_id,
                    "away_team_id": away_team_id,
                },
            }
        )

    unmatched_bootstrap_fixtures = [
        fixture
        for fixture in fixtures
        if not any(mapping["temporary_match_id"] == fixture["match_id"] for mapping in mappings)
    ]

    mappings = sorted(mappings, key=lambda item: str(item["temporary_match_id"]))
    reconciled_fixtures = sorted(reconciled_fixtures, key=lambda item: str(item["match_id"]))

    result = {
        "generated_at": "2026-05-15T00:00:00Z",
        "provider": "football_data_org",
        "mapped_matches": len(mappings),
        "unmatched_provider_matches": unmatched_provider_matches,
        "unmatched_bootstrap_fixtures": [
            {
                "match_id": fixture["match_id"],
                "date_utc": fixture["date_utc"],
                "home_team_id": fixture["home_team_id"],
                "away_team_id": fixture["away_team_id"],
            }
            for fixture in unmatched_bootstrap_fixtures
        ],
        "mappings": mappings,
    }

    write_json(OUTPUT_MAPPING_PATH, result)
    write_json(OUTPUT_RECONCILED_FIXTURES_PATH, reconciled_fixtures)

    print(f"Wrote mapping file to {OUTPUT_MAPPING_PATH}")
    print(f"Wrote reconciled fixtures to {OUTPUT_RECONCILED_FIXTURES_PATH}")
    print(f"Mapped {len(mappings)} matches")
    print(f"Unmatched provider matches: {len(unmatched_provider_matches)}")
    print(f"Unmatched bootstrap fixtures: {len(unmatched_bootstrap_fixtures)}")


if __name__ == "__main__":
    main()
