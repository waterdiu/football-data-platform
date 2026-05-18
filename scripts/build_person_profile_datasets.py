from __future__ import annotations

import argparse
import json
from pathlib import Path

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = ROOT / "data" / "normalized"
PUBLIC_DIR = ROOT / "data" / "public"
REPORTS_DIR = ROOT / "reports"

DATASETS = {
    "person_team_staff_master.json": "team-staff.json",
    "person_officials_master.json": "officials.json",
    "person_player_ratings_master.json": "player-ratings.json",
    "person_staff_ratings_master.json": "staff-ratings.json",
    "person_official_ratings_master.json": "official-ratings.json",
    "person_style_profiles_master.json": "person-style-profiles.json",
}


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_list(payload: object, label: str) -> list[dict]:
    if not isinstance(payload, list):
        raise TypeError(f"{label} must contain a list")
    return [item for item in payload if isinstance(item, dict)]


def compact_sources(row: dict) -> dict:
    source_urls = []
    if row.get("source_url"):
        source_urls.append(row["source_url"])
    source_refs = row.get("source_refs") if isinstance(row.get("source_refs"), dict) else {}
    for value in source_refs.values():
        if isinstance(value, str) and value.startswith("http") and value not in source_urls:
            source_urls.append(value)
    return {
        "source_status": row.get("source_status") or "unknown",
        "sources": row.get("sources") if isinstance(row.get("sources"), list) else [],
        "source_urls": source_urls,
        "source_refs": source_refs,
        "updated_at": row.get("updated_at"),
    }


def data_badge(tier: str, label: str, status: str = "available") -> dict:
    return {
        "data_tier": tier,
        "data_tier_label": label,
        "status": status,
    }


def build_coach_profile(staff: dict) -> dict:
    person_id = staff.get("staff_id")
    profile = {
        "person_id": person_id,
        "person_type": "coach",
        "competition_id": staff.get("competition_id") or "fifa_world_cup",
        "season_id": staff.get("season_id") or "2026",
        "display_name": staff.get("display_name") or staff.get("name"),
        "name": staff.get("name"),
        "name_zh": staff.get("name_zh"),
        "country_code": None,
        "country_name": staff.get("nationality"),
        "country_name_zh": None,
        "photo_url": None,
        "team_id": staff.get("team_id"),
        "team_name": staff.get("team_name"),
        "role": staff.get("role"),
        "role_zh": staff.get("role_zh"),
        "direct": {
            "staff_id": staff.get("staff_id"),
            "status": staff.get("status"),
            "nationality": staff.get("nationality"),
            "date_of_birth": staff.get("date_of_birth"),
            "age": staff.get("age"),
            "appointed_at": staff.get("appointed_at"),
            "contract_until": staff.get("contract_until"),
        },
        "derived": {
            "status": "pending_source",
            "sample_size_matches": 0,
            "window": None,
            "competition_scope": None,
            "metrics": {},
        },
        "distilled": {
            "distillation_status": "insufficient_sample",
            "sample_size_matches": 0,
            "style_tags": [],
            "summary": None,
        },
        "kpis": [
            {"key": "role", "label": "Role", "label_zh": "身份", "value": staff.get("role_zh") or staff.get("role"), "unit": None, **data_badge("direct", "direct")},
            {"key": "team", "label": "Team", "label_zh": "球队", "value": staff.get("team_name"), "unit": None, **data_badge("direct", "direct")},
            {"key": "derived_record", "label": "Derived record", "label_zh": "派生战绩", "value": None, "unit": None, **data_badge("derived", "derived", "pending_source")},
            {"key": "style_profile", "label": "Style profile", "label_zh": "风格画像", "value": "insufficient_sample", "unit": None, **data_badge("distilled", "distilled", "insufficient_sample")},
        ],
        "sections": [
            {"type": "identity", "data_tier": "direct", "status": "available", "fields": compact_sources(staff)},
            {"type": "career_summary", "data_tier": "derived", "status": "pending_source", "basis": {"sample_size_matches": 0}},
            {"type": "style_distillation", "data_tier": "distilled", "status": "insufficient_sample", "basis": {"sample_size_matches": 0, "minimum_required": 30}},
        ],
        "data_tiers": ["direct", "derived", "distilled"],
        **compact_sources(staff),
    }
    return profile


def build_player_profile(player: dict) -> dict:
    profile = {
        "person_id": player.get("player_id"),
        "person_type": "player",
        "competition_id": "fifa_world_cup",
        "season_id": "2026",
        "display_name": player.get("display_name") or player.get("name"),
        "name": player.get("name"),
        "name_zh": player.get("name_zh"),
        "country_code": None,
        "country_name": player.get("nationality"),
        "country_name_zh": None,
        "photo_url": None,
        "team_id": player.get("team_id"),
        "team_name": player.get("nationality"),
        "role": "player",
        "role_zh": "球员",
        "direct": {
            "player_id": player.get("player_id"),
            "position": player.get("position"),
            "shirt_number": player.get("shirt_number"),
            "club": player.get("club"),
            "date_of_birth": player.get("date_of_birth"),
            "age": player.get("age"),
            "status": player.get("status") or "selected",
        },
        "derived": {
            "status": "pending_source",
            "sample_size_matches": 0,
            "window": None,
            "competition_scope": None,
            "metrics": {},
        },
        "distilled": {
            "distillation_status": "insufficient_sample",
            "sample_size_matches": 0,
            "style_tags": [],
            "summary": None,
        },
        "kpis": [
            {"key": "position", "label": "Position", "label_zh": "位置", "value": player.get("position"), "unit": None, **data_badge("direct", "direct")},
            {"key": "club", "label": "Club", "label_zh": "俱乐部", "value": player.get("club"), "unit": None, **data_badge("direct", "direct")},
            {"key": "impact_score", "label": "Impact score", "label_zh": "影响力分", "value": None, "unit": None, **data_badge("derived", "derived", "pending_source")},
            {"key": "style_profile", "label": "Style profile", "label_zh": "风格画像", "value": "insufficient_sample", "unit": None, **data_badge("distilled", "distilled", "insufficient_sample")},
        ],
        "sections": [
            {"type": "identity", "data_tier": "direct", "status": "available", "fields": compact_sources(player)},
            {"type": "production_metrics", "data_tier": "derived", "status": "pending_source", "basis": {"sample_size_matches": 0}},
            {"type": "style_distillation", "data_tier": "distilled", "status": "insufficient_sample", "basis": {"sample_size_matches": 0, "minimum_required": 30}},
        ],
        "data_tiers": ["direct", "derived", "distilled"],
        **compact_sources(player),
    }
    return profile


def rating_by_entity_id(ratings: list[dict]) -> dict[str, dict]:
    return {
        str(row.get("entity_id") or ""): row
        for row in ratings
        if isinstance(row, dict) and row.get("entity_id")
    }


def build_referee_profile(official: dict, rating: dict | None = None) -> dict:
    rating = rating if isinstance(rating, dict) else {}
    sample_size = int(rating.get("sample_size") or 0)
    raw_metrics = rating.get("raw_metrics") if isinstance(rating.get("raw_metrics"), dict) else {}
    dimension_ratings = rating.get("dimension_ratings") if isinstance(rating.get("dimension_ratings"), dict) else {}
    style_tags = rating.get("style_tags") if isinstance(rating.get("style_tags"), list) else official.get("style_tags") or []
    derived_status = rating.get("status") or "pending_source"
    profile = {
        "person_id": official.get("official_id") or official.get("person_id"),
        "person_type": "referee",
        "competition_id": official.get("competition_id") or "fifa_world_cup",
        "season_id": official.get("season_id") or "2026",
        "display_name": official.get("display_name") or official.get("name"),
        "name": official.get("name"),
        "name_zh": official.get("name_zh"),
        "country_code": official.get("country_code"),
        "country_name": official.get("nationality"),
        "country_name_zh": None,
        "photo_url": None,
        "role": official.get("role") or "referee",
        "role_zh": official.get("role_zh") or "裁判",
        "direct": official,
        "derived": {
            "status": derived_status,
            "sample_size_matches": sample_size,
            "competition_scope": rating.get("competition_scope") or official.get("competition_scope"),
            "metrics": raw_metrics,
            "dimension_ratings": dimension_ratings,
            "overall_rating": rating.get("overall_rating"),
        },
        "distilled": {
            "distillation_status": "available" if style_tags else "insufficient_sample",
            "sample_size_matches": sample_size,
            "style_tags": style_tags,
            "summary": None if not style_tags else ", ".join(str(tag) for tag in style_tags),
        },
        "kpis": [
            {"key": "role", "label": "Role", "label_zh": "身份", "value": official.get("role") or "referee", "unit": None, **data_badge("direct", "direct")},
            {"key": "sample_size", "label": "Sample size", "label_zh": "样本数", "value": sample_size, "unit": "matches", **data_badge("derived", "derived", str(derived_status))},
            {"key": "yellow_cards_per_match", "label": "Yellow cards / match", "label_zh": "场均黄牌", "value": raw_metrics.get("yellow_cards_per_match"), "unit": None, **data_badge("derived", "derived", str(derived_status))},
            {"key": "style_profile", "label": "Style profile", "label_zh": "风格画像", "value": " / ".join(style_tags) if style_tags else "insufficient_sample", "unit": None, **data_badge("distilled", "distilled", "available" if style_tags else "insufficient_sample")},
        ],
        "sections": [
            {"type": "identity", "data_tier": "direct", "status": official.get("source_status") or "pending_source", "fields": compact_sources(official)},
            {"type": "officiating_metrics", "data_tier": "derived", "status": derived_status, "basis": {"sample_size_matches": sample_size, "minimum_required": 20}, "metrics": raw_metrics, "dimension_ratings": dimension_ratings},
            {"type": "style_distillation", "data_tier": "distilled", "status": "available" if style_tags else "insufficient_sample", "basis": {"sample_size_matches": sample_size, "minimum_required": 30}, "style_tags": style_tags},
        ],
        "data_tiers": ["direct", "derived", "distilled"],
        **compact_sources(official),
    }
    return profile


def index_row(profile: dict) -> dict:
    return {
        "person_id": profile.get("person_id"),
        "person_type": profile.get("person_type"),
        "display_name": profile.get("display_name"),
        "name": profile.get("name"),
        "name_zh": profile.get("name_zh"),
        "team_id": profile.get("team_id"),
        "team_name": profile.get("team_name"),
        "role": profile.get("role"),
        "role_zh": profile.get("role_zh"),
        "country_name": profile.get("country_name"),
        "source_status": profile.get("source_status"),
        "updated_at": profile.get("updated_at"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish person profile datasets from normalized masters.")
    parser.add_argument(
        "--report-output",
        default=str(REPORTS_DIR / "person_profile_publish_report.json"),
        help="publish report output path",
    )
    args = parser.parse_args()

    team_staff = ensure_list(load_json(NORMALIZED_DIR / "person_team_staff_master.json"), "person_team_staff_master.json")
    players = ensure_list(load_json(NORMALIZED_DIR / "world_cup_2026_players_master.json"), "world_cup_2026_players_master.json")
    officials = ensure_list(load_json(NORMALIZED_DIR / "person_officials_master.json"), "person_officials_master.json")
    official_ratings = ensure_list(load_json(NORMALIZED_DIR / "person_official_ratings_master.json"), "person_official_ratings_master.json")
    official_ratings_by_entity = rating_by_entity_id(official_ratings)

    coach_profiles = [build_coach_profile(row) for row in team_staff if row.get("role") == "head_coach"]
    player_profiles = [build_player_profile(row) for row in players]
    referee_profiles = [
        build_referee_profile(row, official_ratings_by_entity.get(str(row.get("official_id") or row.get("person_id") or "")))
        for row in officials
    ]
    people_index = [index_row(row) for row in [*coach_profiles, *player_profiles, *referee_profiles]]

    generated_datasets = {
        "people-index.json": people_index,
        "coach-profiles.json": coach_profiles,
        "player-profiles.json": player_profiles,
        "referee-profiles.json": referee_profiles,
    }

    counts: dict[str, int] = {}
    outputs: dict[str, str] = {}
    for public_filename, rows in generated_datasets.items():
        write_json(PUBLIC_DIR / public_filename, rows)
        counts[public_filename] = len(rows)
        outputs[public_filename] = str(PUBLIC_DIR / public_filename)

    for master_filename, public_filename in DATASETS.items():
        rows = ensure_list(load_json(NORMALIZED_DIR / master_filename), master_filename)
        write_json(PUBLIC_DIR / public_filename, rows)
        counts[public_filename] = len(rows)
        outputs[public_filename] = str(PUBLIC_DIR / public_filename)

    report = {
        "status": "published",
        "profile_contract": {
            "data_tiers": ["direct", "derived", "distilled"],
            "distillation_minimum_sample_matches": 30,
            "referee_metric_minimum_sample_matches": 20,
            "phase": "phase_1_direct_profiles",
        },
        "counts": counts,
        "outputs": outputs,
    }
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
