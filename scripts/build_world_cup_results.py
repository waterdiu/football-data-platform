from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_MATCHES_PATH = ROOT / "data" / "raw" / "football-data-org" / "world_cup_2026_matches.json"
AUTHORITATIVE_FIXTURES_PATH = ROOT / "data" / "normalized" / "world_cup_2026_authoritative_fixtures.json"
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


def normalize_winner(value: str | None) -> str | None:
    mapping = {
        "HOME_TEAM": "home",
        "AWAY_TEAM": "away",
        "DRAW": "draw",
    }
    if value is None:
        return None
    return mapping.get(str(value).strip().upper())


def build_results() -> list[dict[str, object]]:
    fixtures = load_json(AUTHORITATIVE_FIXTURES_PATH)
    payload = load_json(RAW_MATCHES_PATH)
    if not isinstance(fixtures, list):
        raise TypeError("Authoritative fixtures must be a list.")
    if not isinstance(payload, dict):
        raise TypeError("football-data.org raw payload must be an object.")

    fixture_by_fdorg_id = {}
    for fixture in fixtures:
        source_refs = fixture.get("source_refs") or {}
        football_data_id = source_refs.get("football_data_org")
        if football_data_id:
            fixture_by_fdorg_id[str(football_data_id)] = fixture

    results: list[dict[str, object]] = []
    for match in payload.get("matches", []):
        football_data_id = str(match.get("id", "")).strip()
        fixture = fixture_by_fdorg_id.get(football_data_id)
        if not fixture:
            continue

        score = match.get("score") or {}
        full_time = score.get("fullTime") or {}
        half_time = score.get("halfTime") or {}
        extra_time = score.get("extraTime") or {}
        penalties = score.get("penalties") or {}

        results.append(
            {
                "match_id": fixture["match_id"],
                "status": normalize_status(match.get("status")),
                "score": {
                    "home": full_time.get("home"),
                    "away": full_time.get("away"),
                    "half_time_home": half_time.get("home"),
                    "half_time_away": half_time.get("away"),
                    "extra_time_home": extra_time.get("home"),
                    "extra_time_away": extra_time.get("away"),
                    "penalties_home": penalties.get("home"),
                    "penalties_away": penalties.get("away"),
                },
                "winner": normalize_winner(score.get("winner")),
                "result_type": str(score.get("duration") or "REGULAR").casefold(),
                "provider": "football_data_org",
                "provider_match_id": football_data_id,
                "updated_at": str(match.get("lastUpdated") or fixture.get("updated_at")),
            }
        )

    return sorted(results, key=lambda item: str(item["match_id"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build normalized World Cup results from football-data.org raw payload.")
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
