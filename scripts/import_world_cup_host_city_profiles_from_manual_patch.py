from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH_PATH = ROOT / "data" / "patches" / "world_cup_2026_host_city_profiles.manual.json"
NORMALIZED_OUTPUT = ROOT / "data" / "normalized" / "world_cup_2026_host_city_profiles_master.json"
PUBLIC_OUTPUT = ROOT / "data" / "public" / "host-city-profiles.json"
REPORT_OUTPUT = ROOT / "reports" / "world_cup_host_city_profiles_import_report.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_entry(entry: dict, *, competition_id: str, season_id: str, updated_at: str, default_source_status: str) -> dict:
    source_urls = entry.get("source_urls")
    if not isinstance(source_urls, list):
        source_urls = []
    return {
        "competition_id": competition_id,
        "season_id": season_id,
        "city_id": str(entry.get("city_id") or ""),
        "site_city_key": str(entry.get("site_city_key") or ""),
        "city_name_en": str(entry.get("city_name_en") or ""),
        "city_name_zh": str(entry.get("city_name_zh") or ""),
        "country_en": str(entry.get("country_en") or ""),
        "country_zh": str(entry.get("country_zh") or ""),
        "region_en": entry.get("region_en"),
        "region_zh": entry.get("region_zh"),
        "timezone": str(entry.get("timezone") or ""),
        "population": entry.get("population"),
        "city_tags": [str(tag) for tag in entry.get("city_tags") or []],
        "climate_summary_zh": entry.get("climate_summary_zh"),
        "climate_summary_en": entry.get("climate_summary_en"),
        "football_culture_zh": entry.get("football_culture_zh"),
        "football_culture_en": entry.get("football_culture_en"),
        "transport_summary_zh": entry.get("transport_summary_zh"),
        "transport_summary_en": entry.get("transport_summary_en"),
        "local_feature_zh": entry.get("local_feature_zh"),
        "local_feature_en": entry.get("local_feature_en"),
        "primary_venue_id": str(entry.get("primary_venue_id") or ""),
        "source_status": str(entry.get("source_status") or default_source_status),
        "source_urls": [str(url) for url in source_urls],
        "updated_at": str(entry.get("updated_at") or updated_at),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import World Cup 2026 host city profiles from audited manual patch.")
    parser.add_argument("--patch", default=str(PATCH_PATH), help="manual patch input")
    parser.add_argument("--normalized-output", default=str(NORMALIZED_OUTPUT), help="normalized master output")
    parser.add_argument("--public-output", default=str(PUBLIC_OUTPUT), help="public dataset output")
    parser.add_argument("--report-output", default=str(REPORT_OUTPUT), help="import report output")
    args = parser.parse_args()

    patch = load_json(Path(args.patch))
    if not isinstance(patch, dict):
        raise TypeError("host city profile patch must contain an object")
    entries = patch.get("entries")
    if not isinstance(entries, list):
        raise TypeError("host city profile patch entries must contain a list")

    competition_id = str(patch.get("competition_id") or "fifa_world_cup")
    season_id = str(patch.get("season_id") or "2026")
    updated_at = str(patch.get("updated_at") or "2026-05-17T00:00:00Z")
    source_status = str(patch.get("source_status") or "manual_official_patch")
    rows = [
        normalize_entry(
            entry,
            competition_id=competition_id,
            season_id=season_id,
            updated_at=updated_at,
            default_source_status=source_status,
        )
        for entry in entries
        if isinstance(entry, dict)
    ]
    rows = sorted(rows, key=lambda row: str(row.get("city_id") or ""))

    city_ids = [str(row.get("city_id") or "") for row in rows]
    site_keys = [str(row.get("site_city_key") or "") for row in rows]
    if len(city_ids) != len(set(city_ids)):
        raise ValueError("duplicate city_id in host city profile patch")
    if len(site_keys) != len(set(site_keys)):
        raise ValueError("duplicate site_city_key in host city profile patch")
    missing_required = [
        row.get("city_id")
        for row in rows
        if not row.get("city_id")
        or not row.get("site_city_key")
        or not row.get("timezone")
        or not row.get("primary_venue_id")
        or not row.get("source_urls")
    ]
    if missing_required:
        raise ValueError(f"host city profiles missing required fields: {missing_required}")

    write_json(Path(args.normalized_output), rows)
    write_json(Path(args.public_output), rows)
    report = {
        "status": "published",
        "patch": str(args.patch),
        "normalized_output": str(args.normalized_output),
        "public_output": str(args.public_output),
        "rows": len(rows),
        "city_ids": city_ids,
        "site_city_keys": site_keys,
        "source_statuses": sorted({str(row.get("source_status") or "") for row in rows}),
    }
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
