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
    "person_player_external_facts_master.json": "player-external-facts.json",
    "person_player_dcaribou_activity_master.json": "player-dcaribou-activity.json",
    "person_staff_external_facts_master.json": "staff-external-facts.json",
    "person_player_ratings_master.json": "player-ratings.json",
    "person_staff_ratings_master.json": "staff-ratings.json",
    "person_official_ratings_master.json": "official-ratings.json",
    "person_style_profiles_master.json": "person-style-profiles.json",
}

TEAM_RECENT_MATCHES_PATH = PUBLIC_DIR / "team-recent-matches.json"
PLAYER_EXTERNAL_FACTS_PATH = NORMALIZED_DIR / "person_player_external_facts_master.json"
PLAYER_ACTIVITY_FACTS_PATH = NORMALIZED_DIR / "person_player_dcaribou_activity_master.json"
STAFF_EXTERNAL_FACTS_PATH = NORMALIZED_DIR / "person_staff_external_facts_master.json"
WORLD_CUP_OFFICIALS_PATH = NORMALIZED_DIR / "world_cup_2026_match_officials_master.json"


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


def available_count(rows: list[dict], key: str) -> int:
    count = 0
    for row in rows:
        value = row.get(key)
        if value in (None, "", []) and isinstance(row.get("direct"), dict):
            value = row["direct"].get(key)
        if value not in (None, "", []):
            count += 1
    return count


def profile_identity_coverage(rows: list[dict], fields: list[str]) -> dict:
    total = len(rows)
    return {
        "total": total,
        "fields": {
            field: {
                "available": available_count(rows, field),
                "missing": total - available_count(rows, field),
            }
            for field in fields
        },
    }


def source_compact_from_external_fact(fact: dict | None) -> dict:
    if not isinstance(fact, dict):
        return {}
    source_url = fact.get("source_url")
    return {
        "source_status": fact.get("source_status"),
        "source": fact.get("source"),
        "source_url": source_url,
        "source_refs": fact.get("source_refs") if isinstance(fact.get("source_refs"), dict) else {},
        "confidence": fact.get("confidence"),
        "updated_at": fact.get("updated_at"),
    }


def build_coach_profile(staff: dict, team_recent: dict | None = None, external_fact: dict | None = None) -> dict:
    person_id = staff.get("staff_id")
    derived, coach_metrics, ability_bars = build_coach_recent_metrics(team_recent)
    record = coach_metrics.get("recent_10_form") if isinstance(coach_metrics.get("recent_10_form"), dict) else {}
    record_value = None
    if record:
        record_value = f"{record.get('won', 0)}-{record.get('drawn', 0)}-{record.get('lost', 0)}"
    external_direct = external_fact.get("direct") if isinstance(external_fact, dict) and isinstance(external_fact.get("direct"), dict) else {}
    nationality = staff.get("nationality") or external_direct.get("nationality")
    date_of_birth = staff.get("date_of_birth") or external_direct.get("date_of_birth")
    age = staff.get("age") or external_direct.get("age")
    direct_fields = {
        "staff_id": staff.get("staff_id"),
        "status": staff.get("status"),
        "nationality": nationality,
        "date_of_birth": date_of_birth,
        "age": age,
        "appointed_at": staff.get("appointed_at"),
        "contract_until": staff.get("contract_until"),
        "current_team_display": staff.get("team_name"),
    }
    direct_coverage = build_direct_field_coverage(direct_fields)
    field_sources = {
        "staff_id": "official_fifa",
        "status": "official_fifa",
        "current_team_display": "official_fifa",
        "appointed_at": "pending_source",
        "contract_until": "pending_source",
    }
    for key in ("nationality", "date_of_birth", "age"):
        if direct_coverage.get(key) == "available":
            field_sources[key] = external_fact.get("source_status") if isinstance(external_fact, dict) else "unknown"
    profile = {
        "person_id": person_id,
        "person_type": "coach",
        "competition_id": staff.get("competition_id") or "fifa_world_cup",
        "season_id": staff.get("season_id") or "2026",
        "display_name": staff.get("display_name") or staff.get("name"),
        "name": staff.get("name"),
        "name_zh": staff.get("name_zh"),
        "country_code": None,
        "country_name": nationality,
        "country_name_zh": None,
        "date_of_birth": date_of_birth,
        "age": age,
        "photo_url": None,
        "team_id": staff.get("team_id"),
        "team_name": staff.get("team_name"),
        "role": staff.get("role"),
        "role_zh": staff.get("role_zh"),
        "direct": {
            **direct_fields,
            "field_coverage": direct_coverage,
            "field_sources": field_sources,
            "external_fact": source_compact_from_external_fact(external_fact),
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
            {"type": "identity", "data_tier": "direct", "status": "available", "fields": {**direct_fields, **compact_sources(staff), "external_fact": source_compact_from_external_fact(external_fact)}},
            {"type": "kpi_strip", "data_tier": "derived", "status": derived.get("status"), "metrics": coach_metrics, "basis": derived.get("basis")},
            {"type": "data_grid", "data_tier": "direct", "status": "partial", "fields": direct_fields, "field_coverage": direct_coverage, "field_sources": field_sources},
            {"type": "ability_bars", "data_tier": "derived", "status": derived.get("status"), "items": ability_bars, "basis": derived.get("basis")},
            {"type": "career_summary", "data_tier": "derived", "status": derived.get("status"), "basis": derived.get("basis"), "metrics": coach_metrics},
            {"type": "style_distillation", "data_tier": "distilled", "status": "insufficient_sample", "basis": {"sample_size_matches": int(derived.get("sample_size_matches") or 0), "minimum_required": 30}},
        ],
        "data_tiers": ["direct", "derived", "distilled"],
        **compact_sources(staff),
    }
    return profile


def build_player_profile(player: dict, external_fact: dict | None = None, activity_fact: dict | None = None) -> dict:
    external_direct = external_fact.get("direct") if isinstance(external_fact, dict) and isinstance(external_fact.get("direct"), dict) else {}
    external_derived = external_fact.get("derived") if isinstance(external_fact, dict) and isinstance(external_fact.get("derived"), dict) else {}
    activity = activity_fact.get("activity") if isinstance(activity_fact, dict) and isinstance(activity_fact.get("activity"), dict) else {}
    lineups = activity_fact.get("lineups") if isinstance(activity_fact, dict) and isinstance(activity_fact.get("lineups"), dict) else {}
    events = activity_fact.get("events") if isinstance(activity_fact, dict) and isinstance(activity_fact.get("events"), dict) else {}
    lineup_number_candidates = activity_fact.get("lineup_number_candidates") if isinstance(activity_fact, dict) and isinstance(activity_fact.get("lineup_number_candidates"), list) else []
    recent_appearances = activity_fact.get("recent_appearances") if isinstance(activity_fact, dict) and isinstance(activity_fact.get("recent_appearances"), list) else []
    valuation_history = activity_fact.get("valuation_history") if isinstance(activity_fact, dict) and isinstance(activity_fact.get("valuation_history"), list) else []
    club = player.get("club") or external_direct.get("club")
    date_of_birth = player.get("date_of_birth") or external_direct.get("date_of_birth")
    age = player.get("age") or external_direct.get("age")
    direct_fields = {
        "player_id": player.get("player_id"),
        "position": player.get("position"),
        "shirt_number": player.get("shirt_number"),
        "club": club,
        "date_of_birth": date_of_birth,
        "age": age,
        "status": player.get("status") or "selected",
        "country_of_citizenship": external_direct.get("country_of_citizenship"),
        "height_cm": external_direct.get("height_cm"),
        "foot": external_direct.get("foot"),
        "sub_position": external_direct.get("sub_position"),
        "image_url": external_direct.get("image_url"),
    }
    direct_coverage = build_direct_field_coverage(direct_fields)
    field_sources = {
        "player_id": "official_fifa",
        "position": "official_fifa",
        "status": "official_fifa",
    }
    for key in ("club", "date_of_birth", "age", "country_of_citizenship", "height_cm", "foot", "sub_position", "image_url"):
        if direct_coverage.get(key) == "available":
            field_sources[key] = external_fact.get("source_status") if isinstance(external_fact, dict) else "unknown"
    for key in ("shirt_number",):
        field_sources[key] = "pending_source"
    metrics = {
        key: value
        for key, value in {
            "caps": external_derived.get("caps"),
            "goals": external_derived.get("goals"),
            "market_value_eur": external_derived.get("market_value_eur"),
            "highest_market_value_eur": external_derived.get("highest_market_value_eur"),
            "impact_proxy_score": external_derived.get("impact_proxy_score"),
            "appearances_total": activity.get("appearances_total"),
            "minutes_total": activity.get("minutes_total"),
            "assists_total": activity.get("assists_total"),
            "starts_total": lineups.get("starts"),
            "bench_rows_total": lineups.get("bench_rows"),
            "event_rows_total": events.get("events_total"),
        }.items()
        if value is not None
    }
    derived_status = "available" if metrics else "pending_source"
    sample_size = int(metrics.get("caps") or 0)
    derived_basis = {
        "sample_size_matches": sample_size,
        "window": "career" if metrics else None,
        "competition_scope": "international_caps_transfermarkt" if metrics else None,
        "source": "data/normalized/person_player_external_facts_master.json" if metrics else None,
        "method": "Third-party Transfermarkt dataset facts and a simple display impact proxy; missing values are explicit nulls, not zero." if metrics else "Pending reliable caps/goals/minutes/club source. Missing values are explicit nulls, not zero.",
        "external_fact": source_compact_from_external_fact(external_fact),
        "activity_fact": source_compact_from_external_fact(activity_fact),
    }
    impact_box = {
        "status": "available" if metrics.get("impact_proxy_score") is not None else "pending_source",
        "impact_proxy_score": metrics.get("impact_proxy_score"),
        "absence_impact_pct": None,
        "absence_impact_explain_zh": "当前仅有基于身价、国家队出场和国家队进球的展示型影响力代理分；不是缺阵百分比。"
        if metrics.get("impact_proxy_score") is not None
        else None,
        "absence_impact_explain_en": "Current value is a display-only impact proxy from market value, international caps, and goals; it is not an absence-impact percentage."
        if metrics.get("impact_proxy_score") is not None
        else None,
        "basis": derived_basis,
    }
    ability_items = []
    if metrics.get("caps") is not None:
        ability_items.append({"key": "international_experience", "label": "International experience", "label_zh": "国家队经验", "value": clamp_rating((metrics["caps"] / 100) * 100), "unit": "rating", **data_badge("derived", "derived", "available")})
    if metrics.get("goals") is not None:
        ability_items.append({"key": "international_goals", "label": "International goals", "label_zh": "国家队进球", "value": clamp_rating((metrics["goals"] / 50) * 100), "unit": "rating", **data_badge("derived", "derived", "available")})
    if metrics.get("market_value_eur") is not None:
        ability_items.append({"key": "market_value_proxy", "label": "Market value proxy", "label_zh": "身价代理", "value": clamp_rating((metrics["market_value_eur"] / 100_000_000) * 100), "unit": "rating", **data_badge("derived", "derived", "available")})
    if metrics.get("impact_proxy_score") is not None:
        ability_items.append({"key": "impact_proxy_score", "label": "Impact proxy", "label_zh": "影响力代理", "value": metrics["impact_proxy_score"], "unit": "rating", **data_badge("derived", "derived", "available")})
    if metrics.get("minutes_total") is not None:
        ability_items.append({"key": "historical_minutes", "label": "Historical minutes", "label_zh": "历史出场分钟", "value": clamp_rating((metrics["minutes_total"] / 30000) * 100), "unit": "rating", **data_badge("derived", "derived", "available")})
    top_number_candidate = lineup_number_candidates[0] if lineup_number_candidates else {}
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
        "date_of_birth": date_of_birth,
        "age": age,
        "photo_url": None,
        "team_id": player.get("team_id"),
        "team_name": player.get("nationality"),
        "role": "player",
        "role_zh": "球员",
        "direct": {
            **direct_fields,
            "field_coverage": direct_coverage,
            "field_sources": field_sources,
            "external_fact": source_compact_from_external_fact(external_fact),
        },
        "derived": {
            "status": derived_status,
            "sample_size_matches": sample_size,
            "window": "career" if metrics else None,
            "competition_scope": "international_caps_transfermarkt" if metrics else None,
            "metrics": metrics,
            "basis": derived_basis,
            "impact_box": impact_box,
            "lineup_number_candidates": lineup_number_candidates,
            "activity_ref": "player-dcaribou-activity.json" if activity_fact else None,
        },
        "distilled": {
            "distillation_status": "insufficient_sample",
            "sample_size_matches": 0,
            "style_tags": [],
            "summary": None,
        },
        "kpis": [
            {"key": "position", "label": "Position", "label_zh": "位置", "value": player.get("position"), "unit": None, **data_badge("direct", "direct")},
            {"key": "club", "label": "Club", "label_zh": "俱乐部", "value": club, "unit": None, **data_badge("direct", "direct", direct_coverage.get("club", "pending_source"))},
            {"key": "shirt_number", "label": "Shirt number", "label_zh": "号码", "value": player.get("shirt_number"), "unit": None, **data_badge("direct", "direct", direct_coverage.get("shirt_number", "pending_source"))},
            {"key": "historical_number_candidate", "label": "Historical number", "label_zh": "历史常用号码", "value": top_number_candidate.get("number"), "unit": "candidate" if top_number_candidate else None, **data_badge("derived", "derived", "available" if top_number_candidate else "pending_source")},
            {"key": "caps", "label": "Caps", "label_zh": "国家队出场", "value": metrics.get("caps"), "unit": None, **data_badge("derived", "derived", derived_status)},
            {"key": "goals", "label": "Goals", "label_zh": "国家队进球", "value": metrics.get("goals"), "unit": None, **data_badge("derived", "derived", derived_status)},
            {"key": "minutes_total", "label": "Historical minutes", "label_zh": "历史分钟", "value": metrics.get("minutes_total"), "unit": "min", **data_badge("derived", "derived", "available" if metrics.get("minutes_total") is not None else "pending_source")},
            {"key": "impact_score", "label": "Impact score", "label_zh": "影响力分", "value": metrics.get("impact_proxy_score"), "unit": "proxy", **data_badge("derived", "derived", impact_box["status"])},
            {"key": "style_profile", "label": "Style profile", "label_zh": "风格画像", "value": "insufficient_sample", "unit": None, **data_badge("distilled", "distilled", "insufficient_sample")},
        ],
        "sections": [
            {"type": "identity", "data_tier": "direct", "status": "available", "fields": {**direct_fields, **compact_sources(player)}},
            {"type": "data_grid", "data_tier": "direct", "status": "partial", "fields": direct_fields, "field_coverage": direct_coverage},
            {"type": "kpi_strip", "data_tier": "derived", "status": derived_status, "metrics": metrics, "basis": derived_basis},
            {"type": "ability_bars", "data_tier": "derived", "status": derived_status, "items": ability_items, "basis": derived_basis},
            {"type": "impact_box", "data_tier": "derived", **impact_box},
            {"type": "production_metrics", "data_tier": "derived", "status": derived_status, "basis": derived_basis, "metrics": metrics},
            {
                "type": "historical_activity",
                "data_tier": "derived",
                "status": "available" if activity_fact else "pending_source",
                "basis": {
                    "source": "data/normalized/person_player_dcaribou_activity_master.json" if activity_fact else None,
                    "public_dataset": "player-dcaribou-activity.json" if activity_fact else None,
                    "usage": "Historical supplemental Transfermarkt activity; not FIFA World Cup 2026 official shirt number or confirmed lineup.",
                    "minimum_required": 1,
                },
                "lineup_number_candidates": lineup_number_candidates,
                "activity": activity,
                "lineups": lineups,
                "events": events,
                "detail_ref": {
                    "dataset": "player-dcaribou-activity.json",
                    "key": player.get("player_id"),
                } if activity_fact else None,
            },
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
    date_of_birth = official.get("date_of_birth")
    age = official.get("age")
    direct_fields = {
        "official_id": official.get("official_id") or official.get("person_id"),
        "person_id": official.get("person_id") or official.get("official_id"),
        "name": official.get("name"),
        "display_name": official.get("display_name") or official.get("name"),
        "name_zh": official.get("name_zh"),
        "country": official.get("country"),
        "country_code": official.get("country_code"),
        "nationality": official.get("nationality"),
        "association_code": official.get("association_code"),
        "confederation": official.get("confederation"),
        "date_of_birth": date_of_birth,
        "age": age,
        "roles": official.get("roles") if isinstance(official.get("roles"), list) else [],
        "role": official.get("role") or "referee",
        "role_zh": official.get("role_zh") or "裁判",
        "assigned_matches": assigned_matches,
        "assignment_status": official.get("assignment_status") or "missing_referee_assignment",
        "fifa_listed_since": official.get("fifa_listed_since"),
        "competition_id": official.get("competition_id") or "fifa_world_cup",
        "season_id": official.get("season_id") or "2026",
        "competition_scope": official.get("competition_scope"),
        "source_status": official.get("source_status"),
        "sources": official.get("sources") if isinstance(official.get("sources"), list) else [],
        "source_refs": official.get("source_refs") if isinstance(official.get("source_refs"), dict) else {},
        "source_url": official.get("source_url"),
        "updated_at": official.get("updated_at"),
    }
    direct_coverage = build_direct_field_coverage(direct_fields)
    source_status = official.get("source_status") or "unknown"
    field_sources = {
        key: source_status if direct_coverage.get(key) == "available" else "pending_source"
        for key in direct_fields
    }
    for key in ("date_of_birth", "age", "fifa_listed_since"):
        if direct_coverage.get(key) != "available":
            field_sources[key] = "pending_identity_source"
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
        "date_of_birth": date_of_birth,
        "age": age,
        "photo_url": None,
        "role": official.get("role") or "referee",
        "role_zh": official.get("role_zh") or "裁判",
        "direct": {
            **direct_fields,
            "field_coverage": direct_coverage,
            "field_sources": field_sources,
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
            {"type": "identity", "data_tier": "direct", "status": official.get("source_status") or "pending_source", "fields": {**direct_fields, **compact_sources(official)}, "field_coverage": direct_coverage, "field_sources": field_sources},
            {"type": "data_grid", "data_tier": "direct", "status": "partial", "fields": direct_fields, "field_coverage": direct_coverage, "field_sources": field_sources},
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


def load_player_external_facts() -> dict[str, dict]:
    if not PLAYER_EXTERNAL_FACTS_PATH.exists():
        return {}
    rows = ensure_list(load_json(PLAYER_EXTERNAL_FACTS_PATH), "person_player_external_facts_master.json")
    return {
        str(row.get("player_id")): row
        for row in rows
        if row.get("player_id")
    }


def load_player_activity_facts() -> dict[str, dict]:
    if not PLAYER_ACTIVITY_FACTS_PATH.exists():
        return {}
    rows = ensure_list(load_json(PLAYER_ACTIVITY_FACTS_PATH), "person_player_dcaribou_activity_master.json")
    return {
        str(row.get("player_id")): row
        for row in rows
        if row.get("player_id")
    }


def load_staff_external_facts() -> dict[str, dict]:
    if not STAFF_EXTERNAL_FACTS_PATH.exists():
        return {}
    rows = ensure_list(load_json(STAFF_EXTERNAL_FACTS_PATH), "person_staff_external_facts_master.json")
    return {
        str(row.get("staff_id")): row
        for row in rows
        if row.get("staff_id")
    }


def load_world_cup_officials() -> list[dict]:
    if not WORLD_CUP_OFFICIALS_PATH.exists():
        return []
    return ensure_list(load_json(WORLD_CUP_OFFICIALS_PATH), "world_cup_2026_match_officials_master.json")


def merge_officials(*official_groups: list[dict]) -> list[dict]:
    merged_by_id: dict[str, dict] = {}
    for group in official_groups:
        for row in group:
            official_id = str(row.get("official_id") or row.get("person_id") or "")
            if not official_id:
                continue
            normalized = dict(row)
            normalized.setdefault("date_of_birth", None)
            normalized.setdefault("age", None)
            normalized.setdefault("identity_field_coverage", {})
            if isinstance(normalized["identity_field_coverage"], dict):
                normalized["identity_field_coverage"].update(
                    {
                        "date_of_birth": field_status(normalized.get("date_of_birth")),
                        "age": field_status(normalized.get("age")),
                    }
                )
            normalized.setdefault("identity_field_sources", {})
            if isinstance(normalized["identity_field_sources"], dict):
                normalized["identity_field_sources"].update(
                    {
                        "date_of_birth": "pending_identity_source"
                        if normalized.get("date_of_birth") in (None, "")
                        else normalized.get("source_status") or "unknown",
                        "age": "pending_identity_source"
                        if normalized.get("age") in (None, "")
                        else normalized.get("source_status") or "unknown",
                    }
                )
            merged_by_id[official_id] = normalized
    return sorted(
        merged_by_id.values(),
        key=lambda row: (
            str(row.get("competition_id") or ""),
            str(row.get("role") or ""),
            str(row.get("country_code") or row.get("country") or ""),
            str(row.get("name") or ""),
        ),
    )


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
        "date_of_birth": profile.get("date_of_birth"),
        "age": profile.get("age"),
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
    historical_officials = ensure_list(load_json(NORMALIZED_DIR / "person_officials_master.json"), "person_officials_master.json")
    world_cup_officials = load_world_cup_officials()
    officials = merge_officials(historical_officials, world_cup_officials)
    official_ratings = ensure_list(load_json(NORMALIZED_DIR / "person_official_ratings_master.json"), "person_official_ratings_master.json")
    official_ratings_by_entity = rating_by_entity_id(official_ratings)
    team_recent_by_id = load_team_recent_matches()
    player_external_facts_by_id = load_player_external_facts()
    player_activity_facts_by_id = load_player_activity_facts()
    staff_external_facts_by_id = load_staff_external_facts()

    coach_profiles = [
        build_coach_profile(
            row,
            team_recent_by_id.get(str(row.get("team_id") or "")),
            staff_external_facts_by_id.get(str(row.get("staff_id") or "")),
        )
        for row in team_staff
        if row.get("role") == "head_coach"
    ]
    player_profiles = [
        build_player_profile(
            row,
            player_external_facts_by_id.get(str(row.get("player_id") or "")),
            player_activity_facts_by_id.get(str(row.get("player_id") or "")),
        )
        for row in players
    ]
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
        "officials.json": officials,
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

    identity_coverage = {
        "coach_profiles": profile_identity_coverage(
            coach_profiles,
            ["date_of_birth", "age", "nationality", "country_name"],
        ),
        "player_profiles": profile_identity_coverage(
            player_profiles,
            ["date_of_birth", "age", "club", "position", "shirt_number"],
        ),
        "referee_profiles": profile_identity_coverage(
            referee_profiles,
            ["date_of_birth", "age", "country_code", "country_name", "role", "source_status"],
        ),
        "officials": {
            "total": len(officials),
            "fields": {
                "date_of_birth": {
                    "available": available_count(officials, "date_of_birth"),
                    "missing": len(officials) - available_count(officials, "date_of_birth"),
                    "source": "pending_identity_source",
                },
                "age": {
                    "available": available_count(officials, "age"),
                    "missing": len(officials) - available_count(officials, "age"),
                    "source": "pending_identity_source",
                },
            },
        },
    }

    report = {
        "status": "published",
        "profile_contract": {
            "data_tiers": ["direct", "derived", "distilled"],
            "distillation_minimum_sample_matches": 30,
            "referee_metric_minimum_sample_matches": 20,
            "phase": "phase_1_5_renderable_profiles",
            "coach_derived_basis": "team recent-match proxy from data/public/team-recent-matches.json",
            "coach_external_fact_source": "withqwerty/reep coach rows for nationality/date_of_birth/age",
            "player_external_fact_source": "dcaribou/transfermarkt-datasets via Reep key_transfermarkt mapping",
            "player_missing_field_policy": "explicit null plus pending_source; never fill with zero or inferred facts",
            "official_sources": {
                "world_cup_2026": "FIFA official match officials list; roster only, not per-match assignments.",
                "premier_league_historical": "football-data.co.uk referee sample metrics for historical style profiles.",
            },
        },
        "counts": counts,
        "identity_coverage": identity_coverage,
        "outputs": outputs,
    }
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
