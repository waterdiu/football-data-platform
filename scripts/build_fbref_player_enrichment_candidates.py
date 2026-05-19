from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
COVERAGE_REPORT_PATH = ROOT / "reports" / "fbref_worldcup_player_coverage_report.json"
OUTPUT_PATH = ROOT / "reports" / "fbref_player_enrichment_candidates.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def has_model_usable_value(fbref: dict) -> bool:
    for key in ("nineties", "starts", "goals", "assists"):
        value = fbref.get(key)
        if isinstance(value, (int, float)) and value != 0:
            return True
    return False


def candidate_row(row: dict) -> dict:
    fbref = row.get("fbref") if isinstance(row.get("fbref"), dict) else {}
    refs = row.get("profile_refs") if isinstance(row.get("profile_refs"), dict) else {}
    return {
        "player_id": row.get("player_id"),
        "team_id": row.get("team_id"),
        "name": row.get("name"),
        "position": row.get("position"),
        "source": "fbref_premier_league_player_stats_local_asset",
        "source_status": "experimental_candidate",
        "candidate_confidence": "review_ready",
        "production_write_allowed": False,
        "normalized_write_allowed": False,
        "match_method": row.get("match_method"),
        "external_refs": {
            "key_transfermarkt": refs.get("key_transfermarkt"),
            "reep_id": refs.get("reep_id"),
            "person_id_map_confidence": refs.get("person_id_map_confidence"),
            "person_id_map_resolution_method": refs.get("person_id_map_resolution_method"),
        },
        "fbref": {
            "player": fbref.get("player"),
            "squad": fbref.get("squad"),
            "position": fbref.get("position"),
            "nineties": fbref.get("nineties"),
            "starts": fbref.get("starts"),
            "goals": fbref.get("goals"),
            "assists": fbref.get("assists"),
        },
        "excluded_fields": {
            "xg": "zero_only_in_current_asset",
            "xag": "zero_only_in_current_asset",
            "progressive_passes": "zero_only_in_current_asset",
            "tackles": "zero_only_in_current_asset",
            "interceptions": "zero_only_in_current_asset",
        },
    }


def build_candidates(report: dict) -> dict:
    candidates: list[dict] = []
    excluded: list[dict] = []
    for row in report.get("matched", []):
        refs = row.get("profile_refs") if isinstance(row.get("profile_refs"), dict) else {}
        fbref = row.get("fbref") if isinstance(row.get("fbref"), dict) else {}
        reasons: list[str] = []
        if refs.get("person_id_map_confidence") != "high":
            reasons.append("person_id_map_not_high_confidence")
        if not refs.get("key_transfermarkt") or not refs.get("reep_id"):
            reasons.append("missing_external_refs")
        if not has_model_usable_value(fbref):
            reasons.append("no_nonzero_model_usable_fields")
        if reasons:
            excluded.append(
                {
                    "player_id": row.get("player_id"),
                    "name": row.get("name"),
                    "team_id": row.get("team_id"),
                    "reasons": reasons,
                }
            )
        else:
            candidates.append(candidate_row(row))

    team_counts: dict[str, int] = {}
    for row in candidates:
        team_id = str(row.get("team_id") or "unknown")
        team_counts[team_id] = team_counts.get(team_id, 0) + 1

    return {
        "generated_at": utc_now(),
        "scope": "fbref_player_enrichment_candidates",
        "mode": "model_evaluation_candidates_only",
        "production_write_allowed": False,
        "normalized_write_allowed": False,
        "public_write_allowed": False,
        "source_report": str(COVERAGE_REPORT_PATH.relative_to(ROOT)),
        "candidate_count": len(candidates),
        "excluded_count": len(excluded),
        "team_counts": team_counts,
        "usable_fields": ["nineties", "starts", "goals", "assists"],
        "blocked_fields": ["xg", "xag", "progressive_passes", "tackles", "interceptions"],
        "promotion_gates": [
            "manual_review_or_rule_review_of_name_match",
            "confirm_source_policy_for_model_internal_use",
            "decide whether candidates remain report-only or become model-only asset",
            "do not publish to public API",
        ],
        "candidates": candidates,
        "excluded": excluded,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build report-only FBref player enrichment candidates for model evaluation.")
    parser.add_argument("--coverage-report", default=str(COVERAGE_REPORT_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args()

    payload = load_json(Path(args.coverage_report))
    if not isinstance(payload, dict):
        raise TypeError("coverage report must be an object")
    candidates = build_candidates(payload)
    write_json(Path(args.output), candidates)
    print(
        json.dumps(
            {
                "candidate_count": candidates["candidate_count"],
                "excluded_count": candidates["excluded_count"],
                "output": args.output,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
