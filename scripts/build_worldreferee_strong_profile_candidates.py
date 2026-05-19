from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
PROBE_REPORT_PATH = ROOT / "reports" / "worldreferee_referee_probe_report.json"
OUTPUT_PATH = ROOT / "reports" / "worldreferee_referee_strong_profile_candidates.json"

MIN_REPORT_SAMPLE = 20
MIN_STYLE_SAMPLE = 30
MIN_STRONG_SAMPLE = 50


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_list(payload: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise TypeError(f"{label} must contain a list")
    return [row for row in payload if isinstance(row, dict)]


def number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def classify_rate(value: float | None, *, low: float, high: float, label: str) -> str | None:
    if value is None:
        return None
    if value >= high:
        return f"{label}_high"
    if value <= low:
        return f"{label}_low"
    return f"{label}_medium"


def sample_gate(sample_size: int) -> dict[str, Any]:
    return {
        "sample_size": sample_size,
        "can_explain_report": sample_size >= MIN_REPORT_SAMPLE,
        "can_distill_style": sample_size >= MIN_STYLE_SAMPLE,
        "can_strong_model_signal": sample_size >= MIN_STRONG_SAMPLE,
        "thresholds": {
            "report_explanation": MIN_REPORT_SAMPLE,
            "style_distillation": MIN_STYLE_SAMPLE,
            "strong_model_signal": MIN_STRONG_SAMPLE,
        },
    }


def confidence_for(sample_size: int, metrics: dict[str, Any]) -> dict[str, Any]:
    required = [
        "yellow_cards_per_match",
        "red_cards_per_match",
        "penalties_per_match",
        "fouls",
    ]
    coverage = sum(1 for key in required if metrics.get(key) not in (None, "", [])) / len(required)
    sample_score = min(sample_size / MIN_STRONG_SAMPLE, 1.0)
    confidence = round((sample_score * 0.7) + (coverage * 0.3), 3)
    if confidence >= 0.8 and sample_size >= MIN_STRONG_SAMPLE:
        label = "high_candidate"
    elif confidence >= 0.55 and sample_size >= MIN_STYLE_SAMPLE:
        label = "medium_candidate"
    elif confidence >= 0.35 and sample_size >= MIN_REPORT_SAMPLE:
        label = "low_report_candidate"
    else:
        label = "insufficient_sample"
    return {
        "score": confidence,
        "label": label,
        "sample_score": round(sample_score, 3),
        "field_coverage": round(coverage, 3),
    }


def build_style_tags(metrics: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    yellow = number(metrics.get("yellow_cards_per_match"))
    red = number(metrics.get("red_cards_per_match"))
    penalties = number(metrics.get("penalties_per_match"))
    matches = int(number(metrics.get("matches")) or 0)

    for tag in [
        classify_rate(yellow, low=3.0, high=4.5, label="yellow_card"),
        classify_rate(red, low=0.08, high=0.22, label="red_card"),
        classify_rate(penalties, low=0.15, high=0.32, label="penalty"),
    ]:
        if tag:
            tags.append(tag)

    if matches >= 80:
        tags.append("high_experience")
    elif matches >= MIN_STRONG_SAMPLE:
        tags.append("experienced")
    elif matches >= MIN_STYLE_SAMPLE:
        tags.append("moderate_sample")
    return tags


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def scale_rate(value: float | None, *, low: float, high: float) -> float | None:
    if value is None:
        return None
    if high <= low:
        return None
    return round(clamp(((value - low) / (high - low)) * 100.0), 2)


def build_dimension_ratings(metrics: dict[str, Any], confidence: dict[str, Any]) -> dict[str, Any]:
    matches = int(number(metrics.get("matches")) or 0)
    yellow = number(metrics.get("yellow_cards_per_match"))
    red = number(metrics.get("red_cards_per_match"))
    penalties = number(metrics.get("penalties_per_match"))
    fouls_total = number(metrics.get("fouls"))
    fouls_per_match = round(fouls_total / matches, 4) if fouls_total is not None and matches > 0 else None

    card_strictness = scale_rate(yellow, low=2.0, high=5.5)
    red_card_risk = scale_rate(red, low=0.02, high=0.35)
    penalty_tendency = scale_rate(penalties, low=0.05, high=0.45)
    foul_involvement = scale_rate(fouls_per_match, low=1.0, high=8.0)
    experience = round(clamp((matches / 100.0) * 100.0), 2)
    field_coverage = round(float(confidence.get("field_coverage") or 0.0) * 100.0, 2)

    available = [
        value
        for value in [card_strictness, red_card_risk, penalty_tendency, foul_involvement, experience, field_coverage]
        if value is not None
    ]
    overall = round(sum(available) / len(available), 2) if available else None
    return {
        "overall_experimental_rating": overall,
        "card_strictness": card_strictness,
        "red_card_risk": red_card_risk,
        "penalty_tendency": penalty_tendency,
        "foul_involvement": foul_involvement,
        "experience": experience,
        "field_coverage": field_coverage,
        "raw_fouls_per_match": fouls_per_match,
        "rating_policy": "experimental_only_not_model_input",
    }


def build_risk_modifiers(metrics: dict[str, Any]) -> dict[str, Any]:
    yellow = number(metrics.get("yellow_cards_per_match"))
    red = number(metrics.get("red_cards_per_match"))
    penalties = number(metrics.get("penalties_per_match"))

    # These are bounded report candidates only. They must be re-estimated and
    # backtested before model use.
    card_risk = None if yellow is None else round(clamp((yellow - 3.2) / 2.0, -1.0, 1.0), 3)
    red_card_risk = None if red is None else round(clamp((red - 0.12) / 0.18, -1.0, 1.0), 3)
    penalty_risk = None if penalties is None else round(clamp((penalties - 0.20) / 0.20, -1.0, 1.0), 3)
    ou_modifier = None
    if red_card_risk is not None or penalty_risk is not None:
        red_component = red_card_risk or 0.0
        penalty_component = penalty_risk or 0.0
        ou_modifier = round(clamp((red_component * 0.03) + (penalty_component * 0.04), -0.08, 0.08), 3)
    return {
        "card_risk": card_risk,
        "red_card_risk": red_card_risk,
        "penalty_risk": penalty_risk,
        "ou_modifier_candidate": ou_modifier,
        "policy": "report_candidate_only; not consumed by predictor until source approval and backtest.",
    }


def build_candidate(row: dict[str, Any]) -> dict[str, Any]:
    parsed = row.get("parsed") if isinstance(row.get("parsed"), dict) else {}
    stats = parsed.get("stats") if isinstance(parsed.get("stats"), dict) else {}
    matches_sample = parsed.get("matches_sample") if isinstance(parsed.get("matches_sample"), list) else []
    sample_size = int(number(stats.get("matches")) or 0)
    metrics = {
        "matches": sample_size,
        "competitions": stats.get("competitions"),
        "yellow_cards": stats.get("yellow_cards"),
        "yellow_cards_per_match": stats.get("yellow_cards_per_match"),
        "red_cards": stats.get("red_cards"),
        "red_cards_per_match": stats.get("red_cards_per_match"),
        "penalties": stats.get("penalties"),
        "penalties_per_match": stats.get("penalties_per_match"),
        "fouls": stats.get("fouls"),
        "most_cards_1_game": stats.get("most_cards_1_game"),
        "active_years": stats.get("active_years"),
        "match_history_rows_sampled": len(matches_sample),
    }
    confidence = confidence_for(sample_size, metrics)
    gate = sample_gate(sample_size)
    dimension_ratings = build_dimension_ratings(metrics, confidence)
    risk_modifiers = build_risk_modifiers(metrics)
    return {
        "official_id": row.get("official_id"),
        "fifa_name": row.get("fifa_name"),
        "association_code": row.get("association_code"),
        "source": "WorldReferee",
        "source_url": row.get("url"),
        "canonical_url": parsed.get("canonical_url"),
        "raw_html_path": row.get("raw_html_path"),
        "source_status": "experimental_report_only",
        "metrics": metrics,
        "sample_gate": gate,
        "confidence": confidence,
        "dimension_ratings": dimension_ratings,
        "risk_modifiers": risk_modifiers,
        "style_tags": build_style_tags(metrics) if gate["can_distill_style"] else [],
        "distillation_status": "candidate" if gate["can_distill_style"] else "insufficient_sample",
        "model_signal_status": "candidate" if gate["can_strong_model_signal"] else "insufficient_sample",
        "sample_matches": matches_sample,
        "limitations": [
            "WorldReferee source policy and repeatability are not approved for production normalized/public data.",
            "The page-level stats mix competitions and historical windows; competition weighting is not audited.",
            "Fixture-level World Cup 2026 assignments are still pending FIFA match centre/report.",
        ],
    }


def build_report(probe_report: dict[str, Any]) -> dict[str, Any]:
    rows = ensure_list(probe_report.get("rows") or [], "worldreferee_referee_probe_report.rows")
    candidates = [build_candidate(row) for row in rows if row.get("probe_status") == "available"]
    with_stats = [row for row in candidates if int(row["metrics"].get("matches") or 0) > 0]
    report_ready = [row for row in candidates if row["sample_gate"]["can_explain_report"]]
    style_ready = [row for row in candidates if row["sample_gate"]["can_distill_style"]]
    strong_ready = [row for row in candidates if row["sample_gate"]["can_strong_model_signal"]]
    return {
        "generated_at": utc_now(),
        "status": "experimental_report_only",
        "source": "WorldReferee",
        "source_report": str(PROBE_REPORT_PATH.relative_to(ROOT)),
        "policy": {
            "production_write_allowed": False,
            "normalized_write_allowed": False,
            "public_api_write_allowed": False,
            "promotion_required_checks": [
                "terms_review",
                "stable_id_mapping",
                "repeatable_collection",
                "field_stability",
                "competition_scope_review",
            ],
        },
        "summary": {
            "candidate_count": len(candidates),
            "with_stats": len(with_stats),
            "report_explanation_candidates": len(report_ready),
            "style_distillation_candidates": len(style_ready),
            "strong_model_signal_candidates": len(strong_ready),
            "high_confidence_candidates": sum(1 for row in candidates if row["confidence"]["label"] == "high_candidate"),
            "medium_confidence_candidates": sum(1 for row in candidates if row["confidence"]["label"] == "medium_candidate"),
            "low_report_candidates": sum(1 for row in candidates if row["confidence"]["label"] == "low_report_candidate"),
            "insufficient_sample": sum(1 for row in candidates if row["confidence"]["label"] == "insufficient_sample"),
        },
        "thresholds": {
            "report_explanation": MIN_REPORT_SAMPLE,
            "style_distillation": MIN_STYLE_SAMPLE,
            "strong_model_signal": MIN_STRONG_SAMPLE,
        },
        "candidates": candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build experimental WorldReferee strong profile candidates.")
    parser.add_argument("--input", default=str(PROBE_REPORT_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args()

    report = build_report(load_json(Path(args.input)))
    write_json(Path(args.output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
