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

TEAM_RECENT_MATCHES_PATH = PUBLIC_DIR / "team-recent-matches.json"


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


def percentage(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return round((numerator / denominator) * 100.0, 2)


def per_match(value: float, matches: int) -> float | None:
    if matches <= 0:
        return None
    return round(value / matches, 3)


def clamp_rating(value: float | None) -> float | None:
    if value is None:
        return None
    return round(max(0.0, min(100.0, value)), 2)


def build_recent_team_basis(team_recent: dict | None) -> dict:
    match_count = int(team_recent.get("match_count") or 0) if isinstance(team_recent, dict) else 0
    return {
        "sample_size_matches": match_count,
        "window": "last_10" if match_count else None,
        "competition_scope": "international_team_recent_matches" if match_count else None,
        "source": "data/public/team-recent-matches.json" if match_count else None,
        "method": "Team recent-form proxy for page display; not a full coach career record." if match_count else None,
    }


def build_coach_recent_metrics(team_recent: dict | None) -> tuple[dict, dict, list[dict]]:
    if not isinstance(team_recent, dict) or int(team_recent.get("match_count") or 0) <= 0:
        return (
            {
                "status": "pending_source",
                "sample_size_matches": 0,
                "window": None,
                "competition_scope": None,
                "basis": build_recent_team_basis(None),
                "metrics": {},
            },
            {},
            [],
        )

    summary = team_recent.get("form_summary") if isinstance(team_recent.get("form_summary"), dict) else {}
    matches = team_recent.get("matches") if isinstance(team_recent.get("matches"), list) else []
    sample_size = int(team_recent.get("match_count") or len(matches))
    won = int(summary.get("won") or 0)
    drawn = int(summary.get("drawn") or 0)
    lost = int(summary.get("lost") or 0)
    goals_for = int(summary.get("goals_for") or 0)
    goals_against = int(summary.get("goals_against") or 0)
    clean_sheets = sum(1 for row in matches if isinstance(row, dict) and row.get("score_against") == 0)
    recent_form = {
        "played": sample_size,
        "won": won,
        "drawn": drawn,
        "lost": lost,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "goal_difference": int(summary.get("goal_difference") or goals_for - goals_against),
    }
    metrics = {
        "matches_managed_total": sample_size,
        "w_total": won,
        "d_total": drawn,
        "l_total": lost,
        "win_rate_pct": percentage(won, sample_size),
        "goals_for_per_match": per_match(goals_for, sample_size),
        "goals_against_per_match": per_match(goals_against, sample_size),
        "clean_sheet_rate_pct": percentage(clean_sheets, sample_size),
        "recent_10_form": recent_form,
    }
    basis = build_recent_team_basis(team_recent)
    derived = {
        "status": "available",
        "sample_size_matches": sample_size,
        "window": "last_10",
        "competition_scope": "international_team_recent_matches",
        "basis": basis,
        "metrics": metrics,
    }
    ability_bars = [
        {
            "key": "recent_win_rate",
            "label": "Recent win rate",
            "label_zh": "近期胜率",
            "value": metrics["win_rate_pct"],
            "unit": "%",
            **data_badge("derived", "derived", "available"),
        },
        {
            "key": "attacking_output",
            "label": "Attacking output",
            "label_zh": "进攻产出",
            "value": clamp_rating((metrics["goals_for_per_match"] or 0.0) / 3.0 * 100.0),
            "unit": "rating",
            **data_badge("derived", "derived", "available"),
        },
        {
            "key": "defensive_solidity",
            "label": "Defensive solidity",
            "label_zh": "防守稳固度",
            "value": metrics["clean_sheet_rate_pct"],
            "unit": "rating",
            **data_badge("derived", "derived", "available"),
        },
        {
            "key": "sample_confidence",
            "label": "Sample confidence",
            "label_zh": "样本置信度",
            "value": clamp_rating(sample_size / 30.0 * 100.0),
            "unit": "rating",
            **data_badge("derived", "derived", "low_sample"),
        },
    ]
    return derived, metrics, ability_bars


def field_status(value: object) -> str:
    return "available" if value not in (None, "", []) else "pending_source"


def build_direct_field_coverage(fields: dict) -> dict:
    return {key: field_status(value) for key, value in fields.items()}


def build_coach_profile(staff: dict, team_recent: dict | None = None) -> dict:
    person_id = staff.get("staff_id")
    derived, coach_metrics, ability_bars = build_coach_recent_metrics(team_recent)
    record = coach_metrics.get("recent_10_form") if isinstance(coach_metrics.get("recent_10_form"), dict) else {}
    record_value = None
    if record:
        record_value = f"{record.get('won', 0)}-{record.get('drawn', 0)}-{record.get('lost', 0)}"
    direct_fields = {
        "staff_id": staff.get("staff_id"),
        "status": staff.get("status"),
        "nationality": staff.get("nationality"),
        "date_of_birth": staff.get("date_of_birth"),
        "age": staff.get("age"),
        "appointed_at": staff.get("appointed_at"),
        "contract_until": staff.get("contract_until"),
        "current_team_display": staff.get("team_name"),
    }
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
            **direct_fields,
            "field_coverage": build_direct_field_coverage(direct_fields),
        },
        "derived": derived,
        "distilled": {
            "distillation_status": "insufficient_sample",
            "sample_size_matches": int(derived.get("sample_size_matches") or 0),
            "style_tags": [],
            "summary": None,
        },
        "kpis": [
            {"key": "role", "label": "Role", "label_zh": "身份", "value": staff.get("role_zh") or staff.get("role"), "unit": None, **data_badge("direct", "direct")},
            {"key": "team", "label": "Team", "label_zh": "球队", "value": staff.get("team_name"), "unit": None, **data_badge("direct", "direct")},
            {"key": "recent_record", "label": "Recent record", "label_zh": "近10场战绩", "value": record_value, "unit": "W-D-L" if record_value else None, **data_badge("derived", "derived", str(derived.get("status") or "pending_source"))},
            {"key": "win_rate_pct", "label": "Win rate", "label_zh": "胜率", "value": coach_metrics.get("win_rate_pct"), "unit": "%", **data_badge("derived", "derived", str(derived.get("status") or "pending_source"))},
            {"key": "style_profile", "label": "Style profile", "label_zh": "风格画像", "value": "insufficient_sample", "unit": None, **data_badge("distilled", "distilled", "insufficient_sample")},
        ],
        "sections": [
            {"type": "identity", "data_tier": "direct", "status": "available", "fields": {**direct_fields, **compact_sources(staff)}},
            {"type": "kpi_strip", "data_tier": "derived", "status": derived.get("status"), "metrics": coach_metrics, "basis": derived.get("basis")},
            {"type": "data_grid", "data_tier": "direct", "status": "available", "fields": direct_fields, "field_coverage": build_direct_field_coverage(direct_fields)},
            {"type": "ability_bars", "data_tier": "derived", "status": derived.get("status"), "items": ability_bars, "basis": derived.get("basis")},
            {"type": "career_summary", "data_tier": "derived", "status": derived.get("status"), "basis": derived.get("basis"), "metrics": coach_metrics},
            {"type": "style_distillation", "data_tier": "distilled", "status": "insufficient_sample", "basis": {"sample_size_matches": int(derived.get("sample_size_matches") or 0), "minimum_required": 30}},
        ],
        "data_tiers": ["direct", "derived", "distilled"],
        **compact_sources(staff),
    }
    return profile


def build_player_profile(player: dict) -> dict:
    direct_fields = {
        "player_id": player.get("player_id"),
        "position": player.get("position"),
        "shirt_number": player.get("shirt_number"),
        "club": player.get("club"),
        "date_of_birth": player.get("date_of_birth"),
        "age": player.get("age"),
        "status": player.get("status") or "selected",
    }
    direct_coverage = build_direct_field_coverage(direct_fields)
    derived_basis = {
        "sample_size_matches": 0,
        "window": None,
        "competition_scope": None,
        "source": None,
        "method": "Pending reliable caps/goals/minutes/club source. Missing values are explicit nulls, not zero.",
    }
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
            **direct_fields,
            "field_coverage": direct_coverage,
        },
        "derived": {
            "status": "pending_source",
            "sample_size_matches": 0,
            "window": None,
            "competition_scope": None,
            "metrics": {},
            "basis": derived_basis,
            "impact_box": {
                "status": "pending_source",
                "absence_impact_pct": None,
                "absence_impact_explain_zh": None,
                "absence_impact_explain_en": None,
                "basis": derived_basis,
            },
        },
        "distilled": {
            "distillation_status": "insufficient_sample",
            "sample_size_matches": 0,
            "style_tags": [],
            "summary": None,
        },
        "kpis": [
            {"key": "position", "label": "Position", "label_zh": "位置", "value": player.get("position"), "unit": None, **data_badge("direct", "direct")},
            {"key": "club", "label": "Club", "label_zh": "俱乐部", "value": player.get("club"), "unit": None, **data_badge("direct", "direct", direct_coverage.get("club", "pending_source"))},
            {"key": "shirt_number", "label": "Shirt number", "label_zh": "号码", "value": player.get("shirt_number"), "unit": None, **data_badge("direct", "direct", direct_coverage.get("shirt_number", "pending_source"))},
            {"key": "impact_score", "label": "Impact score", "label_zh": "影响力分", "value": None, "unit": None, **data_badge("derived", "derived", "pending_source")},
            {"key": "style_profile", "label": "Style profile", "label_zh": "风格画像", "value": "insufficient_sample", "unit": None, **data_badge("distilled", "distilled", "insufficient_sample")},
        ],
        "sections": [
            {"type": "identity", "data_tier": "direct", "status": "available", "fields": {**direct_fields, **compact_sources(player)}},
            {"type": "data_grid", "data_tier": "direct", "status": "partial", "fields": direct_fields, "field_coverage": direct_coverage},
            {"type": "kpi_strip", "data_tier": "derived", "status": "pending_source", "metrics": {}, "basis": derived_basis},
            {"type": "ability_bars", "data_tier": "derived", "status": "pending_source", "items": [], "basis": derived_basis},
            {"type": "impact_box", "data_tier": "derived", "status": "pending_source", "absence_impact_pct": None, "basis": derived_basis},
            {"type": "production_metrics", "data_tier": "derived", "status": "pending_source", "basis": derived_basis, "metrics": {}},
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
    assigned_matches = official.get("assigned_matches") if isinstance(official.get("assigned_matches"), list) else []
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
        "direct": {
            **official,
            "assigned_matches": assigned_matches,
            "assignment_status": official.get("assignment_status") or "missing_referee_assignment",
        },
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
            {"type": "identity", "data_tier": "direct", "status": official.get("source_status") or "pending_source", "fields": {**compact_sources(official), "assigned_matches": assigned_matches, "assignment_status": official.get("assignment_status") or "missing_referee_assignment"}},
            {"type": "officiating_metrics", "data_tier": "derived", "status": derived_status, "basis": {"sample_size_matches": sample_size, "minimum_required": 20}, "metrics": raw_metrics, "dimension_ratings": dimension_ratings},
            {"type": "style_distillation", "data_tier": "distilled", "status": "available" if style_tags else "insufficient_sample", "basis": {"sample_size_matches": sample_size, "minimum_required": 30}, "style_tags": style_tags},
        ],
        "data_tiers": ["direct", "derived", "distilled"],
        **compact_sources(official),
    }
    return profile


def load_team_recent_matches() -> dict[str, dict]:
    if not TEAM_RECENT_MATCHES_PATH.exists():
        return {}
    rows = ensure_list(load_json(TEAM_RECENT_MATCHES_PATH), "team-recent-matches.json")
    return {
        str(row.get("team_id")): row
        for row in rows
        if row.get("team_id")
    }


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
    team_recent_by_id = load_team_recent_matches()

    coach_profiles = [
        build_coach_profile(row, team_recent_by_id.get(str(row.get("team_id") or "")))
        for row in team_staff
        if row.get("role") == "head_coach"
    ]
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
            "phase": "phase_1_5_renderable_profiles",
            "coach_derived_basis": "team recent-match proxy from data/public/team-recent-matches.json",
            "player_missing_field_policy": "explicit null plus pending_source; never fill with zero or inferred facts",
        },
        "counts": counts,
        "outputs": outputs,
    }
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
