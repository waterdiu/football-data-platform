#!/usr/bin/env python3
"""
Validate how well Reep `people.csv` can map to our World Cup roster players.

Why this exists:
- We want to use Reep as an identity mapping layer only if it actually covers
  World Cup player names at an acceptable rate.
- This script produces a machine-readable coverage report for review.

Inputs:
- `data/public/players.json` (platform published players dataset)
- Reep `people.csv` (path provided via --reep-people-csv)

Output:
- `reports/reep_worldcup_coverage.json` by default

Notes:
- This is name-based matching only (our current roster imports often lack DOB).
- Matching is intentionally conservative and explainable.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


RE_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
RE_SPACES = re.compile(r"\s+")


def _strip_accents(s: str) -> str:
    # Turn "Onaná" into "Onana" etc.
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch)
    )


def norm_name(name: str) -> str:
    s = _strip_accents(name).lower().strip()
    s = RE_NON_ALNUM.sub(" ", s)
    s = RE_SPACES.sub(" ", s).strip()
    return s


def load_players(players_json: Path) -> List[dict]:
    with players_json.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {players_json}, got {type(data).__name__}")
    return data


@dataclass(frozen=True)
class ReepPersonIndex:
    by_norm_name: Dict[str, Set[str]]
    row_count: int


def load_reep_people_index(people_csv: Path, *, max_rows: Optional[int]) -> ReepPersonIndex:
    by_norm_name: Dict[str, Set[str]] = {}
    row_count = 0
    with people_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_count += 1
            if max_rows is not None and row_count > max_rows:
                break
            # Try common columns; we keep it resilient because Reep schemas can evolve.
            raw_name = (row.get("name") or row.get("full_name") or row.get("display_name") or "").strip()
            if not raw_name:
                continue
            pid = (row.get("reep_id") or row.get("id") or row.get("person_id") or "").strip() or f"row:{row_count}"
            key = norm_name(raw_name)
            by_norm_name.setdefault(key, set()).add(pid)
    return ReepPersonIndex(by_norm_name=by_norm_name, row_count=row_count if max_rows is None else min(row_count, max_rows))


def iter_worldcup_player_records(players: List[dict]) -> Iterable[Tuple[str, str, Optional[str]]]:
    """
    Yields (player_id, name, team_id)
    """
    for p in players:
        if not isinstance(p, dict):
            continue
        player_id = str(p.get("player_id") or "").strip()
        name = str(p.get("name") or p.get("display_name") or "").strip()
        team_id = p.get("team_id")
        team_id = str(team_id).strip() if team_id is not None else None
        if not player_id or not name:
            continue
        yield player_id, name, team_id


def build_report(
    *,
    players: List[dict],
    reep_index: ReepPersonIndex,
    reep_people_csv: Path,
    expected_people_count: Optional[int],
    expected_min_fraction: float,
    max_examples: int,
) -> dict:
    total = 0
    matched = 0
    ambiguous = 0
    misses: List[dict] = []
    ambiguous_examples: List[dict] = []

    for player_id, name, team_id in iter_worldcup_player_records(players):
        total += 1
        key = norm_name(name)
        hits = reep_index.by_norm_name.get(key)
        if not hits:
            if len(misses) < max_examples:
                misses.append(
                    {
                        "player_id": player_id,
                        "name": name,
                        "team_id": team_id,
                        "match_key": key,
                    }
                )
            continue

        matched += 1
        if len(hits) > 1:
            ambiguous += 1
            if len(ambiguous_examples) < max_examples:
                ambiguous_examples.append(
                    {
                        "player_id": player_id,
                        "name": name,
                        "team_id": team_id,
                        "match_key": key,
                        "reep_candidate_count": len(hits),
                        "reep_candidate_ids_sample": sorted(list(hits))[:10],
                    }
                )

    hit_rate = (matched / total) if total else 0.0
    ambiguous_rate = (ambiguous / matched) if matched else 0.0
    warnings: List[str] = []
    file_size_bytes = reep_people_csv.stat().st_size if reep_people_csv.exists() else None
    if expected_people_count is not None and expected_people_count > 0:
        fraction = reep_index.row_count / expected_people_count
        if fraction < expected_min_fraction:
            warnings.append(
                f"Reep people.csv appears incomplete: indexed_rows={reep_index.row_count} "
                f"expected_people_count={expected_people_count} fraction={fraction:.3f} (< {expected_min_fraction:.2f})."
            )
    recommended_min_hit_rate = 0.70
    coverage_passed = hit_rate >= recommended_min_hit_rate and not warnings
    decision_status = "passed_coverage_gate" if coverage_passed else "blocked"
    status = "coverage_validated" if coverage_passed else "coverage_not_validated"
    reason = (
        f"Complete Reep people.csv is available and name-only matching covers {matched} of {total} current World Cup roster players."
        if coverage_passed
        else "Reep people.csv coverage validation did not pass; see warnings and summary."
    )

    return {
        "generated_at_utc": None,  # set by caller
        "status": status,
        "input": {
            "players_dataset": "data/public/players.json",
            "reep_people_csv_path": str(reep_people_csv),
            "reep_people_csv_size_bytes": file_size_bytes,
            "reep_people_csv_rows_indexed": reep_index.row_count,
            "expected_people_count": expected_people_count,
            "expected_min_fraction": expected_min_fraction,
        },
        "summary": {
            "worldcup_player_count": total,
            "matched_count": matched,
            "hit_rate": round(hit_rate, 6),
            "ambiguous_matched_count": ambiguous,
            "ambiguous_rate_within_matched": round(ambiguous_rate, 6),
        },
        "validation_gate": {
            "recommended_min_hit_rate": recommended_min_hit_rate,
            "decision_status": decision_status,
            "license_review_required": True,
            "reason": reason,
        },
        "examples": {
            "misses": misses,
            "ambiguous_matches": ambiguous_examples,
        },
        "warnings": warnings,
        "interpretation": {
            "recommended_min_hit_rate": recommended_min_hit_rate,
            "notes": [
                "This is name-only matching; false negatives are expected when a player uses diacritics, alternate spellings, or different tokenization.",
                "Ambiguous matches indicate that name-only matching is insufficient; we should prefer provider IDs, DOB, or club to disambiguate where possible.",
                "Do not treat this report as a green light for production ingestion without a license review.",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--players-json",
        default="data/public/players.json",
        help="Platform players dataset (default: data/public/players.json)",
    )
    parser.add_argument(
        "--reep-people-csv",
        required=True,
        help="Path to Reep people.csv",
    )
    parser.add_argument(
        "--out",
        default="reports/reep_worldcup_coverage.json",
        help="Output report path (default: reports/reep_worldcup_coverage.json)",
    )
    parser.add_argument(
        "--max-reep-rows",
        type=int,
        default=None,
        help="Limit Reep rows for quick trials (default: no limit)",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=50,
        help="Max examples to include in report for misses/ambiguous (default: 50)",
    )
    parser.add_argument(
        "--expected-people-count",
        type=int,
        default=None,
        help="Optional expected number of rows in people.csv (used to detect incomplete downloads)",
    )
    parser.add_argument(
        "--expected-min-fraction",
        type=float,
        default=0.90,
        help="Minimum fraction of expected rows before warning (default: 0.90)",
    )
    args = parser.parse_args()

    players_json = Path(args.players_json)
    reep_people_csv = Path(args.reep_people_csv)
    out_path = Path(args.out)

    players = load_players(players_json)
    reep_index = load_reep_people_index(reep_people_csv, max_rows=args.max_reep_rows)
    report = build_report(
        players=players,
        reep_index=reep_index,
        reep_people_csv=reep_people_csv,
        expected_people_count=args.expected_people_count,
        expected_min_fraction=args.expected_min_fraction,
        max_examples=args.max_examples,
    )

    report["generated_at_utc"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out == "-":
        print(payload, end="")
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
