from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHORITATIVE_FIXTURES_PATH = ROOT / "data" / "normalized" / "world_cup_2026_authoritative_fixtures.json"
LOCAL_FINALS_RESULTS_PATH = ROOT / "data" / "public" / "worldcup-site-finals-results.json"
NORMALIZED_RESULTS_PATH = ROOT / "data" / "normalized" / "world_cup_2026_results.json"
PUBLIC_RESULTS_PATH = ROOT / "data" / "public" / "results.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_status(value: str) -> str:
    status = str(value or "").strip().upper()
    mapping = {
        "SCHEDULED": "scheduled",
        "TIMED": "scheduled",
        "IN_PLAY": "in_play",
        "PAUSED": "in_play",
        "EXTRA_TIME": "extra_time",
        "PENALTIES": "penalties",
        "FINISHED": "finished",
        "POSTPONED": "postponed",
        "SUSPENDED": "suspended",
        "CANCELLED": "cancelled",
    }
    return mapping.get(status, status.casefold() or "unknown")


def local_status(value: str) -> str:
    mapping = {
        "scheduled": "scheduled",
        "completed": "finished",
    }
    return mapping.get(str(value or "").strip().casefold(), str(value or "").strip().casefold() or "unknown")


def infer_winner(home_score: object, away_score: object) -> str | None:
    if not isinstance(home_score, int) or not isinstance(away_score, int):
        return None
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "draw"


def build_results() -> list[dict[str, object]]:
    fixtures = load_json(AUTHORITATIVE_FIXTURES_PATH)
    if not isinstance(fixtures, list):
        raise TypeError("Authoritative fixtures must be a list.")
    local_results = load_json(LOCAL_FINALS_RESULTS_PATH)
    if not isinstance(local_results, list):
        raise TypeError("worldcup-site-finals-results.json must contain a list.")

    fixture_by_local_id = {}
    for fixture in fixtures:
        source_refs = fixture.get("source_refs") or {}
        local_id = source_refs.get("worldcup_2026_schedule_csv")
        if local_id:
            fixture_by_local_id[str(local_id)] = fixture

    results: list[dict[str, object]] = []
    for match in local_results:
        if not isinstance(match, dict):
            continue
        local_id = str(match.get("id", "")).strip()
        fixture = fixture_by_local_id.get(local_id)
        if not fixture:
            continue
        home_score = match.get("homeScore")
        away_score = match.get("awayScore")
        status = local_status(str(match.get("status") or ""))

        results.append(
            {
                "match_id": fixture["match_id"],
                "status": normalize_status(status),
                "score": {
                    "home": home_score if isinstance(home_score, int) else None,
                    "away": away_score if isinstance(away_score, int) else None,
                    "half_time_home": None,
                    "half_time_away": None,
                    "extra_time_home": match.get("homeScore") if bool(match.get("wentToExtraTime")) else None,
                    "extra_time_away": match.get("awayScore") if bool(match.get("wentToExtraTime")) else None,
                    "penalties_home": match.get("homePenaltyScore") if isinstance(match.get("homePenaltyScore"), int) else None,
                    "penalties_away": match.get("awayPenaltyScore") if isinstance(match.get("awayPenaltyScore"), int) else None,
                },
                "winner": infer_winner(home_score, away_score),
                "result_type": "penalties"
                if isinstance(match.get("homePenaltyScore"), int) or isinstance(match.get("awayPenaltyScore"), int)
                else "extra_time"
                if bool(match.get("wentToExtraTime"))
                else "regular",
                "provider": "worldcup_2026_local",
                "provider_match_id": local_id,
                "updated_at": str(match.get("updatedAt") or fixture.get("updated_at")),
            }
        )

    return sorted(results, key=lambda item: str(item["match_id"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build normalized World Cup results from local World Cup site data.")
    parser.add_argument("--normalized-output", default=str(NORMALIZED_RESULTS_PATH), help="normalized results output path")
    parser.add_argument("--public-output", default=str(PUBLIC_RESULTS_PATH), help="public results output path")
    args = parser.parse_args()

    results = build_results()
    write_json(Path(args.normalized_output), results)
    write_json(Path(args.public_output), results)
    print(f"Wrote {len(results)} results to {args.normalized_output}")
    print(f"Published {len(results)} results to {args.public_output}")


if __name__ == "__main__":
    main()
