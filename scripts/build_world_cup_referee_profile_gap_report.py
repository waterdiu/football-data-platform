from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = ROOT / "data" / "normalized"
REPORTS_DIR = ROOT / "reports"
FIFA_OFFICIALS_PATH = NORMALIZED_DIR / "world_cup_2026_match_officials_master.json"
OFFICIAL_RATINGS_PATH = NORMALIZED_DIR / "person_official_ratings_master.json"
OUTPUT_PATH = REPORTS_DIR / "world_cup_referee_profile_gap_report.json"

MIN_EXPLANATION_SAMPLE = 20
MIN_DISTILLATION_SAMPLE = 30
MIN_STRONG_MODEL_SAMPLE = 50

UEFA_ASSOCIATIONS = {
    "ALB",
    "AND",
    "ARM",
    "AUT",
    "AZE",
    "BEL",
    "BIH",
    "BLR",
    "BUL",
    "CRO",
    "CYP",
    "CZE",
    "DEN",
    "ENG",
    "ESP",
    "EST",
    "FIN",
    "FRA",
    "GEO",
    "GER",
    "GRE",
    "HUN",
    "IRL",
    "ISL",
    "ISR",
    "ITA",
    "KAZ",
    "KOS",
    "LIE",
    "LTU",
    "LUX",
    "LVA",
    "MDA",
    "MKD",
    "MLT",
    "MNE",
    "NED",
    "NIR",
    "NOR",
    "POL",
    "POR",
    "ROU",
    "RUS",
    "SCO",
    "SMR",
    "SRB",
    "SUI",
    "SVK",
    "SVN",
    "SWE",
    "TUR",
    "UKR",
    "WAL",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_list(payload: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise TypeError(f"{label} must contain a list")
    return [item for item in payload if isinstance(item, dict)]


def normalize_token(value: str) -> str:
    return re.sub(r"[^a-z]", "", value.casefold())


def parse_fifa_name(name: str) -> dict[str, str | None]:
    tokens = [token for token in name.split() if token]
    if not tokens:
        return {"surname": None, "given_initial": None, "display_order_name": name}

    surname_tokens: list[str] = []
    given_tokens: list[str] = []
    for token in tokens:
        if not given_tokens and token.upper() == token:
            surname_tokens.append(token)
        else:
            given_tokens.append(token)

    if not surname_tokens:
        surname_tokens = [tokens[-1]]
        given_tokens = tokens[:-1]

    if not given_tokens and len(surname_tokens) >= 2:
        surname_tokens, given_tokens = surname_tokens[-1:], surname_tokens[:-1]

    surname = " ".join(surname_tokens).title()
    given = " ".join(token.title() for token in given_tokens) if given_tokens else None
    given_initial = normalize_token(given_tokens[0])[:1] if given_tokens else None
    display_order_name = f"{given} {surname}".strip() if given else surname
    return {
        "surname": surname,
        "given_initial": given_initial,
        "display_order_name": display_order_name,
    }


def parse_historical_referee_name(name: str) -> dict[str, str | None]:
    tokens = [token for token in name.split() if token]
    if len(tokens) < 2:
        return {"surname": normalize_token(tokens[-1]) if tokens else None, "given_initial": None}
    initial = normalize_token(tokens[0])[:1]
    surname = normalize_token(tokens[-1])
    return {"surname": surname, "given_initial": initial}


def build_rating_index(ratings: list[dict[str, Any]]) -> dict[tuple[str | None, str | None], dict[str, Any]]:
    index: dict[tuple[str | None, str | None], dict[str, Any]] = {}
    for rating in ratings:
        entity_id = str(rating.get("entity_id") or "")
        name = entity_id.rsplit(":", 1)[-1].replace("-", " ")
        parsed = parse_historical_referee_name(name)
        key = (parsed["surname"], parsed["given_initial"])
        if key[0]:
            existing = index.get(key)
            if not existing or int(rating.get("sample_size") or 0) > int(existing.get("sample_size") or 0):
                index[key] = rating
    return index


def source_candidates(association_code: str, has_local_sample: bool) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if has_local_sample:
        candidates.append(
            {
                "source": "football-data.co.uk_premier_league_sample",
                "status": "available_local",
                "fills": ["yellow_cards", "red_cards", "home_win_rate", "draw_rate", "avg_goals"],
                "limitations": ["club-league sample only", "not World Cup assignment", "limited foul/penalty/VAR fields"],
            }
        )
    if association_code in UEFA_ASSOCIATIONS:
        candidates.append(
            {
                "source": "football-data.co.uk_european_leagues",
                "status": "candidate_backfill",
                "fills": ["yellow_cards", "red_cards", "home_away_outcomes", "match_goals"],
                "limitations": ["coverage depends on referee appearing in supported European league CSVs"],
            }
        )
    candidates.extend(
        [
            {
                "source": "worldfootball.net_referee_pages",
                "status": "probe_required",
                "fills": ["match_history", "cards", "competition_scope"],
                "limitations": ["terms/stability/id-mapping must be reviewed before normalized/public use"],
            },
            {
                "source": "WorldReferee",
                "status": "probe_required",
                "fills": ["international_match_history", "cards", "tournament_experience"],
                "limitations": ["terms/stability/id-mapping must be reviewed before normalized/public use"],
            },
            {
                "source": "API-FOOTBALL Pro",
                "status": "pending_plan_upgrade_probe",
                "fills": ["fixture_referee", "events_cards", "fixture_statistics_if_available"],
                "limitations": ["may require fixture-level aggregation; referee search/stat endpoints are not assumed"],
            },
        ]
    )
    return candidates


def sample_gate(sample_size: int) -> dict[str, Any]:
    return {
        "sample_size": sample_size,
        "can_explain_report": sample_size >= MIN_EXPLANATION_SAMPLE,
        "can_distill_style": sample_size >= MIN_DISTILLATION_SAMPLE,
        "can_strong_model_signal": sample_size >= MIN_STRONG_MODEL_SAMPLE,
        "thresholds": {
            "report_explanation": MIN_EXPLANATION_SAMPLE,
            "style_distillation": MIN_DISTILLATION_SAMPLE,
            "strong_model_signal": MIN_STRONG_MODEL_SAMPLE,
        },
    }


def build_report() -> dict[str, Any]:
    officials = ensure_list(load_json(FIFA_OFFICIALS_PATH), "world_cup_2026_match_officials_master.json")
    ratings = ensure_list(load_json(OFFICIAL_RATINGS_PATH), "person_official_ratings_master.json")
    rating_index = build_rating_index(ratings)

    referee_rows = [row for row in officials if row.get("role") == "referee"]
    rows: list[dict[str, Any]] = []
    matched_rows = 0
    explain_ready_rows = 0
    distill_ready_rows = 0
    strong_model_rows = 0

    for referee in referee_rows:
        parsed = parse_fifa_name(str(referee.get("name") or ""))
        key = (normalize_token(str(parsed["surname"] or "")), parsed["given_initial"])
        rating = rating_index.get(key)
        sample_size = int(rating.get("sample_size") or 0) if rating else 0
        has_local_sample = rating is not None
        matched_rows += 1 if has_local_sample else 0
        explain_ready_rows += 1 if sample_size >= MIN_EXPLANATION_SAMPLE else 0
        distill_ready_rows += 1 if sample_size >= MIN_DISTILLATION_SAMPLE else 0
        strong_model_rows += 1 if sample_size >= MIN_STRONG_MODEL_SAMPLE else 0
        rows.append(
            {
                "official_id": referee.get("official_id"),
                "name": referee.get("name"),
                "display_order_name": parsed["display_order_name"],
                "association_code": referee.get("association_code"),
                "role": referee.get("role"),
                "source_status": referee.get("source_status"),
                "local_historical_sample": {
                    "status": "available" if has_local_sample else "missing",
                    "rating_entity_id": rating.get("entity_id") if rating else None,
                    "sample_size": sample_size,
                    "metrics": rating.get("raw_metrics") if rating else {},
                    "dimension_ratings": rating.get("dimension_ratings") if rating else {},
                    "style_tags": rating.get("style_tags") if rating else [],
                    "source_scope": rating.get("competition_scope") if rating else None,
                },
                "sample_gate": sample_gate(sample_size),
                "missing_fields_for_strong_profile": [
                    field
                    for field, value in {
                        "international_match_history": None,
                        "fouls_per_match": (rating.get("raw_metrics") or {}).get("fouls_per_match") if rating else None,
                        "penalties_per_match": (rating.get("raw_metrics") or {}).get("penalties_per_match") if rating else None,
                        "var_intervention_profile": None,
                        "world_cup_match_assignments": None,
                    }.items()
                    if value in (None, "", [])
                ],
                "recommended_sources": source_candidates(str(referee.get("association_code") or ""), has_local_sample),
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "requires_source_expansion",
        "scope": "FIFA World Cup 2026 appointed referees only; assistant referees and video match officials are listed but not profiled here.",
        "summary": {
            "fifa_referees": len(referee_rows),
            "local_historical_sample_matches": matched_rows,
            "report_explanation_ready": explain_ready_rows,
            "style_distillation_ready": distill_ready_rows,
            "strong_model_signal_ready": strong_model_rows,
            "needs_external_profile_source": len(referee_rows) - matched_rows,
        },
        "source_policy": {
            "production_now": ["FIFA official match officials list", "football-data.co.uk local historical samples"],
            "probe_before_public": ["worldfootball.net referee pages", "WorldReferee", "API-FOOTBALL Pro referee/fixture aggregation"],
            "not_allowed": ["unreviewed reverse-engineered pages into normalized/public"],
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build World Cup referee profile gap report.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="report output path")
    args = parser.parse_args()
    report = build_report()
    write_json(Path(args.output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
