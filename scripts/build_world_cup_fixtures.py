from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "data" / "public"
NORMALIZED_DIR = ROOT / "data" / "normalized"

LOCAL_FULL_SCHEDULE_PATH = PUBLIC_DIR / "worldcup-site-full-schedule.json"
TEAMS_PATH = PUBLIC_DIR / "teams.json"
CURRENT_FIXTURES_PATH = PUBLIC_DIR / "fixtures.json"
NORMALIZED_OUTPUT_PATH = NORMALIZED_DIR / "world_cup_2026_authoritative_fixtures.json"
PUBLIC_OUTPUT_PATH = PUBLIC_DIR / "fixtures.json"

UPDATED_AT = "2026-05-15T00:00:00Z"

GROUP_STAGE_RE = re.compile(r"^Group ([A-L])$")
SOURCE_STAGE_MAP = {
    "Round of 32": ("round_of_32", "Round of 32"),
    "Round of 16": ("round_of_16", "Round of 16"),
    "Quarter-finals": ("quarterfinal", "Quarter-finals"),
    "Semi-finals": ("semifinal", "Semi-finals"),
    "Match for Third Place": ("third_place", "Match for Third Place"),
    "Final": ("final", "Final"),
}
VENUE_ID_BY_VENUE_NAME = {
    "BC Place 温哥华球场": "bc-place-vancouver",
    "BC Place Vancouver": "bc-place-vancouver",
}
HOST_CITY_ID_BY_CITY_NAME = {
    "亚特兰大": "atlanta",
    "波士顿": "boston",
    "达拉斯": "dallas",
    "瓜达拉哈拉": "guadalajara",
    "休斯敦": "houston",
    "堪萨斯城": "kansas-city",
    "洛杉矶": "los-angeles",
    "墨西哥城": "mexico-city",
    "迈阿密": "miami",
    "蒙特雷": "monterrey",
    "纽约/新泽西": "new-york-new-jersey",
    "费城": "philadelphia",
    "旧金山湾区": "san-francisco-bay-area",
    "西雅图": "seattle",
    "多伦多": "toronto",
    "温哥华": "vancouver",
}


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    lowered = lowered.replace("&", " and ")
    lowered = lowered.replace("'", "")
    lowered = lowered.replace(".", " ")
    lowered = lowered.replace("/", " ")
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered).strip("-")
    return lowered


def build_team_lookup(teams: object) -> dict[str, str]:
    if not isinstance(teams, list):
        raise TypeError("teams.json must contain a list")

    lookup: dict[str, str] = {}
    for item in teams:
        if not isinstance(item, dict):
            continue
        team_id = str(item.get("team_id") or "").strip()
        if not team_id:
            continue

        names = [str(item.get("name") or "").strip()]
        localized = item.get("localized_name")
        if isinstance(localized, dict):
            names.extend(str(value).strip() for value in localized.values() if str(value).strip())
        aliases = item.get("aliases")
        if isinstance(aliases, list):
            names.extend(str(value).strip() for value in aliases if str(value).strip())

        for name in names:
            if name:
                lookup[name] = team_id
    return lookup


def build_existing_fixture_lookup(fixtures: object) -> dict[str, dict[str, object]]:
    if not isinstance(fixtures, list):
        raise TypeError("fixtures.json must contain a list")

    lookup: dict[str, dict[str, object]] = {}
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        source_refs = fixture.get("source_refs")
        if not isinstance(source_refs, dict):
            continue
        local_id = source_refs.get("worldcup_2026_schedule_csv")
        if local_id is not None:
            lookup[str(local_id)] = fixture
    return lookup


def parse_date_utc(value: str) -> str:
    parsed = datetime.fromisoformat(str(value).strip())
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_stage(stage_label: str, group_id: str | None) -> tuple[str, str, str | None]:
    stage_label = str(stage_label or "").strip()
    group_match = GROUP_STAGE_RE.fullmatch(stage_label)
    if group_match:
        return ("group", "Group Stage", group_match.group(1))
    if group_id:
        normalized_group_id = str(group_id).strip()
        if normalized_group_id:
            return ("group", "Group Stage", normalized_group_id)
    if stage_label in SOURCE_STAGE_MAP:
        stage, round_label = SOURCE_STAGE_MAP[stage_label]
        return (stage, round_label, None)
    raise ValueError(f"Unsupported stage label: {stage_label}")


def resolve_team_id(label: str, lookup: dict[str, str]) -> str:
    team_id = lookup.get(str(label).strip())
    if team_id:
        return team_id
    raise KeyError(f"Unknown team label in local full schedule: {label}")


def normalize_venue_id(venue_name: str, existing: dict[str, object] | None) -> str:
    venue_name = str(venue_name or "").strip()
    if venue_name in VENUE_ID_BY_VENUE_NAME:
        return VENUE_ID_BY_VENUE_NAME[venue_name]
    if existing and str(existing.get("venue_name") or "").strip() in VENUE_ID_BY_VENUE_NAME:
        return VENUE_ID_BY_VENUE_NAME[str(existing.get("venue_name") or "").strip()]
    return str((existing or {}).get("venue_id") or slugify(venue_name))


def build_fixtures() -> list[dict[str, object]]:
    local_full_schedule = load_json(LOCAL_FULL_SCHEDULE_PATH)
    teams = load_json(TEAMS_PATH)
    current_fixtures = load_json(CURRENT_FIXTURES_PATH)

    if not isinstance(local_full_schedule, list):
        raise TypeError("worldcup-site-full-schedule.json must contain a list")

    team_lookup = build_team_lookup(teams)
    existing_lookup = build_existing_fixture_lookup(current_fixtures)
    rebuilt: list[dict[str, object]] = []

    for match in local_full_schedule:
        if not isinstance(match, dict):
            continue
        local_id = str(match.get("id") or "").strip()
        if not local_id:
            continue

        existing = existing_lookup.get(local_id)
        if existing is None:
            raise KeyError(f"Missing existing fixture mapping for local schedule id {local_id}")

        stage, round_label, group = parse_stage(str(match.get("stageLabel") or ""), match.get("groupId"))
        source_refs = dict(existing.get("source_refs") or {})
        source_refs["worldcup_2026_schedule_csv"] = local_id

        host_city = str(match.get("city") or existing.get("host_city") or "").strip()
        venue_name = str(match.get("venue") or existing.get("venue_name") or "").strip()
        fixture = {
            "match_id": existing.get("match_id") or f"fifa_world_cup:2026:site:{local_id}",
            "competition_id": "fifa_world_cup",
            "season_id": "2026",
            "stage": stage,
            "round": round_label,
            "date_utc": parse_date_utc(str(match.get("dateLabel") or "")),
            "status": str(match.get("predictionStatus") or "scheduled").strip().casefold() or "scheduled",
            "home_team_id": resolve_team_id(str(match.get("homeTeam") or ""), team_lookup),
            "away_team_id": resolve_team_id(str(match.get("awayTeam") or ""), team_lookup),
            "venue_id": normalize_venue_id(venue_name, existing),
            "venue_name": venue_name,
            "host_city": host_city,
            "host_city_id": HOST_CITY_ID_BY_CITY_NAME.get(host_city) or slugify(host_city),
            "match_theme": str(match.get("title") or existing.get("match_theme") or "").strip(),
            "source_refs": source_refs,
            "updated_at": UPDATED_AT,
        }
        if group:
            fixture["group"] = group

        rebuilt.append(fixture)

    return sorted(rebuilt, key=lambda item: int(str(item["source_refs"]["worldcup_2026_schedule_csv"])))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build World Cup fixtures from local World Cup site full schedule.")
    parser.add_argument("--normalized-output", default=str(NORMALIZED_OUTPUT_PATH), help="normalized fixtures output path")
    parser.add_argument("--public-output", default=str(PUBLIC_OUTPUT_PATH), help="public fixtures output path")
    args = parser.parse_args()

    fixtures = build_fixtures()
    write_json(Path(args.normalized_output), fixtures)
    write_json(Path(args.public_output), fixtures)
    print(f"Wrote {len(fixtures)} fixtures to {args.normalized_output}")
    print(f"Published {len(fixtures)} fixtures to {args.public_output}")


if __name__ == "__main__":
    main()
