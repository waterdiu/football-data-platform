from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
VENUE_CONFIG_PATH = ROOT / "configs" / "venues" / "world_cup_2026.json"
HOST_CITY_PATH = ROOT / "data" / "public" / "host-city-profiles.json"
FIXTURES_PATH = ROOT / "data" / "public" / "fixtures.json"
NORMALIZED_OUTPUT = ROOT / "data" / "normalized" / "world_cup_2026_venues_master.json"
PUBLIC_OUTPUT = ROOT / "data" / "public" / "venues.json"
REPORT_OUTPUT = ROOT / "reports" / "world_cup_venues_report.json"
UPDATED_AT = "2026-05-18T00:00:00Z"
EXPECTED_VENUE_COUNT = 16
EXPECTED_FIXTURE_COUNT = 104

REQUIRED_VENUE_FIELDS = [
    "venue_id",
    "host_city_id",
    "site_city_key",
    "venue_name_en",
    "display_name",
    "city_name_en",
    "country_en",
    "timezone",
    "address",
    "latitude",
    "longitude",
    "altitude_m",
    "capacity_fifa_2026",
    "roof_type",
    "surface_type_current",
    "surface_type_world_cup_expected",
    "fifa_venue_name",
    "source_urls",
]

CITY_ID_ALIASES = {
    "Kansas City": "kansas-city",
    "Dallas": "dallas",
    "Vancouver": "vancouver",
    "Toronto": "toronto",
    "Guadalajara": "guadalajara",
    "Mexico City": "mexico-city",
    "Monterrey": "monterrey",
    "Boston": "boston",
    "Miami": "miami",
    "San Francisco Bay Area": "san-francisco-bay-area",
    "Philadelphia": "philadelphia",
    "Seattle": "seattle",
    "Atlanta": "atlanta",
    "New York/New Jersey": "new-york-new-jersey",
    "New York New Jersey": "new-york-new-jersey",
    "Houston": "houston",
    "Los Angeles": "los-angeles",
}

COUNTRY_BY_CITY_ID = {
    "guadalajara": ("Mexico", "墨西哥"),
    "mexico-city": ("Mexico", "墨西哥"),
    "monterrey": ("Mexico", "墨西哥"),
    "toronto": ("Canada", "加拿大"),
    "vancouver": ("Canada", "加拿大"),
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_city_id(city: object) -> str:
    text = str(city or "").strip()
    return CITY_ID_ALIASES.get(text, "-".join(part for part in text.lower().replace("/", " ").split() if part))


def build_venue_rows(
    *,
    venue_config: dict[str, dict[str, Any]],
    host_cities: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    host_by_venue = {
        str(row.get("primary_venue_id")): row
        for row in host_cities
        if row.get("primary_venue_id")
    }
    fixture_counts: dict[str, int] = {}
    fixture_stage_counts: dict[str, dict[str, int]] = {}
    venue_names_by_id: dict[str, set[str]] = {}
    for fixture in fixtures:
        venue_id = str(fixture.get("venue_id") or "")
        if not venue_id:
            continue
        fixture_counts[venue_id] = fixture_counts.get(venue_id, 0) + 1
        stage = str(fixture.get("stage") or "unknown")
        fixture_stage_counts.setdefault(venue_id, {})
        fixture_stage_counts[venue_id][stage] = fixture_stage_counts[venue_id].get(stage, 0) + 1
        venue_name = str(fixture.get("venue_name") or "").strip()
        if venue_name:
            venue_names_by_id.setdefault(venue_id, set()).add(venue_name)

    rows: list[dict[str, Any]] = []
    for venue_id, venue in sorted(venue_config.items()):
        city_id = normalize_city_id(venue.get("city"))
        host = host_by_venue.get(venue_id) or {}
        country_en, country_zh = COUNTRY_BY_CITY_ID.get(city_id, ("United States", "美国"))
        rows.append(
            {
                "competition_id": "fifa_world_cup",
                "season_id": "2026",
                "venue_id": str(venue.get("venue_id") or venue_id),
                "venue_name_en": str(venue.get("name") or ""),
                "venue_name_zh": None,
                "display_name": str(venue.get("name") or ""),
                "host_city_id": str(host.get("city_id") or city_id),
                "site_city_key": host.get("site_city_key"),
                "city_name_en": host.get("city_name_en") or venue.get("city"),
                "city_name_zh": host.get("city_name_zh"),
                "country_en": host.get("country_en") or country_en,
                "country_zh": host.get("country_zh") or country_zh,
                "timezone": host.get("timezone"),
                "address": venue.get("address"),
                "latitude": venue.get("latitude"),
                "longitude": venue.get("longitude"),
                "altitude_m": venue.get("altitude_m"),
                "capacity_fifa_2026": venue.get("capacity_fifa_2026"),
                "roof_type": venue.get("roof_type"),
                "surface_type_current": venue.get("surface_type_current"),
                "surface_type_world_cup_expected": venue.get("surface_type_world_cup_expected"),
                "fifa_venue_name": venue.get("fifa_venue_name"),
                "fixture_count": fixture_counts.get(venue_id, 0),
                "fixture_stage_counts": fixture_stage_counts.get(venue_id, {}),
                "fixture_venue_names": sorted(venue_names_by_id.get(venue_id, set())),
                "aliases": sorted({str(venue.get("name") or ""), *venue_names_by_id.get(venue_id, set())}),
                "source_status": "platform_config_plus_fifa_host_city_patch",
                "source_urls": sorted(
                    {
                        *([str(url) for url in venue.get("source_urls", []) if url] if isinstance(venue.get("source_urls"), list) else []),
                        *([str(url) for url in host.get("source_urls", []) if url] if isinstance(host.get("source_urls"), list) else []),
                    }
                ),
                "updated_at": UPDATED_AT,
            }
        )
    return rows


def build_quality_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fixture_count_total = sum(int(row.get("fixture_count") or 0) for row in rows)
    missing_required_fields: dict[str, list[str]] = {}
    for row in rows:
        missing = [
            field
            for field in REQUIRED_VENUE_FIELDS
            if row.get(field) in (None, "", [])
        ]
        if missing:
            missing_required_fields[str(row.get("venue_id"))] = missing

    alias_to_ids: dict[str, set[str]] = {}
    for row in rows:
        venue_id = str(row.get("venue_id") or "")
        for alias in row.get("aliases") or []:
            if not alias:
                continue
            alias_to_ids.setdefault(str(alias), set()).add(venue_id)

    alias_collisions = {
        alias: sorted(ids)
        for alias, ids in sorted(alias_to_ids.items())
        if len(ids) > 1
    }
    multi_alias_venues = {
        str(row.get("venue_id")): sorted(row.get("aliases") or [])
        for row in rows
        if len(row.get("aliases") or []) > 1
    }
    zero_fixture_venues = [
        str(row.get("venue_id"))
        for row in rows
        if int(row.get("fixture_count") or 0) == 0
    ]

    checks = {
        "venue_count": len(rows) == EXPECTED_VENUE_COUNT,
        "fixture_count_total": fixture_count_total == EXPECTED_FIXTURE_COUNT,
        "unique_venue_id": len({row.get("venue_id") for row in rows}) == len(rows),
        "required_fields_complete": not missing_required_fields,
        "no_alias_collisions": not alias_collisions,
        "all_venues_have_fixtures": not zero_fixture_venues,
    }
    return {
        "checks": checks,
        "status": "pass" if all(checks.values()) else "attention",
        "expected": {
            "venues": EXPECTED_VENUE_COUNT,
            "fixtures": EXPECTED_FIXTURE_COUNT,
        },
        "missing_required_fields": missing_required_fields,
        "alias_collisions": alias_collisions,
        "multi_alias_venues": multi_alias_venues,
        "zero_fixture_venues": zero_fixture_venues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build World Cup 2026 venue profiles.")
    parser.add_argument("--venue-config", default=str(VENUE_CONFIG_PATH))
    parser.add_argument("--host-cities", default=str(HOST_CITY_PATH))
    parser.add_argument("--fixtures", default=str(FIXTURES_PATH))
    parser.add_argument("--normalized-output", default=str(NORMALIZED_OUTPUT))
    parser.add_argument("--public-output", default=str(PUBLIC_OUTPUT))
    parser.add_argument("--report-output", default=str(REPORT_OUTPUT))
    args = parser.parse_args()

    venue_config = load_json(Path(args.venue_config))
    if not isinstance(venue_config, dict):
        raise TypeError("venue config must be an object")
    host_cities = [row for row in load_json(Path(args.host_cities)) if isinstance(row, dict)]
    fixtures = [row for row in load_json(Path(args.fixtures)) if isinstance(row, dict)]
    rows = build_venue_rows(venue_config=venue_config, host_cities=host_cities, fixtures=fixtures)
    if len(rows) != EXPECTED_VENUE_COUNT:
        raise ValueError(f"expected 16 venue rows, got {len(rows)}")
    if len({row["venue_id"] for row in rows}) != len(rows):
        raise ValueError("duplicate venue_id in venue rows")
    write_json(Path(args.normalized_output), rows)
    write_json(Path(args.public_output), rows)
    quality = build_quality_report(rows)
    report = {
        "status": "published",
        "rows": len(rows),
        "fixture_count_total": sum(int(row.get("fixture_count") or 0) for row in rows),
        "capacity_rows": sum(1 for row in rows if row.get("capacity_fifa_2026") is not None),
        "surface_rows": sum(1 for row in rows if row.get("surface_type_current")),
        "roof_rows": sum(1 for row in rows if row.get("roof_type")),
        "altitude_rows": sum(1 for row in rows if row.get("altitude_m") is not None),
        "venue_ids": [row["venue_id"] for row in rows],
        "quality": quality,
        "outputs": {
            "normalized": str(Path(args.normalized_output)),
            "public": str(Path(args.public_output)),
        },
    }
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
