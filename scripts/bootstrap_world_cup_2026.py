from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
WORLD_CUP_SITE_ROOT = ROOT.parent / "worldcup" / "2026"
PREDICTOR_ROOT = ROOT.parent / "world-cup-predictor"

CSV_PATH = WORLD_CUP_SITE_ROOT / "data" / "2026世界杯104场比赛赛程表.csv"
TEAM_TRANSLATIONS_PATH = PREDICTOR_ROOT / "frontend" / "src" / "lib" / "teams.ts"

PUBLIC_DIR = ROOT / "data" / "public"
CANONICAL_TEAMS_OUTPUT_PATH = PUBLIC_DIR / "canonical_teams.json"
TEAMS_OUTPUT_PATH = PUBLIC_DIR / "teams.json"
FIXTURES_OUTPUT_PATH = PUBLIC_DIR / "fixtures.json"

CN_TEAM_TO_EN = {
    "墨西哥": "Mexico",
    "南非": "South Africa",
    "韩国": "Korea Republic",
    "捷克共和国": "Czechia",
    "加拿大": "Canada",
    "波斯尼亚和黑塞哥维那": "Bosnia and Herzegovina",
    "卡塔尔": "Qatar",
    "瑞士": "Switzerland",
    "巴西": "Brazil",
    "摩洛哥": "Morocco",
    "海地": "Haiti",
    "苏格兰": "Scotland",
    "美国": "United States",
    "巴拉圭": "Paraguay",
    "澳大利亚": "Australia",
    "土耳其": "Turkiye",
    "德国": "Germany",
    "库拉索": "Curacao",
    "科特迪瓦": "Cote d'Ivoire",
    "厄瓜多尔": "Ecuador",
    "荷兰": "Netherlands",
    "日本": "Japan",
    "瑞典": "Sweden",
    "突尼斯": "Tunisia",
    "比利时": "Belgium",
    "埃及": "Egypt",
    "伊朗": "IR Iran",
    "新西兰": "New Zealand",
    "乌拉圭": "Uruguay",
    "沙特阿拉伯": "Saudi Arabia",
    "西班牙": "Spain",
    "佛得角": "Cabo Verde",
    "法国": "France",
    "塞内加尔": "Senegal",
    "伊拉克": "Iraq",
    "挪威": "Norway",
    "阿根廷": "Argentina",
    "阿尔及利亚": "Algeria",
    "奥地利": "Austria",
    "约旦": "Jordan",
    "葡萄牙": "Portugal",
    "刚果民主共和国": "Congo DR",
    "乌兹别克斯坦": "Uzbekistan",
    "哥伦比亚": "Colombia",
    "英格兰": "England",
    "克罗地亚": "Croatia",
    "加纳": "Ghana",
    "巴拿马": "Panama",
}

EN_TEAM_TO_CN = {english: chinese for chinese, english in CN_TEAM_TO_EN.items()}

CANONICAL_ALIASES = {
    "Cabo Verde": ["Cape Verde", "Cape Verde Islands", "佛得角"],
    "Czechia": ["Czech Republic", "捷克共和国", "捷克"],
    "IR Iran": ["Iran", "伊朗"],
    "Cote d'Ivoire": ["Ivory Coast", "科特迪瓦"],
    "Turkiye": ["Turkey", "土耳其"],
    "Congo DR": ["DR Congo", "Democratic Republic of the Congo", "刚果民主共和国"],
    "Bosnia and Herzegovina": ["Bosnia-Herzegovina", "波斯尼亚和黑塞哥维那"],
    "Curacao": ["Curaçao", "库拉索"],
    "United States": ["USA", "United States of America", "美国"],
    "Korea Republic": ["Korea", "South Korea", "韩国"],
}

TEAM_SHORT_NAMES = {
    "Algeria": "ALG",
    "Argentina": "ARG",
    "Australia": "AUS",
    "Austria": "AUT",
    "Belgium": "BEL",
    "Bosnia and Herzegovina": "BIH",
    "Brazil": "BRA",
    "Cabo Verde": "CPV",
    "Canada": "CAN",
    "Colombia": "COL",
    "Congo DR": "COD",
    "Costa Rica": "CRC",
    "Cote d'Ivoire": "CIV",
    "Croatia": "CRO",
    "Curacao": "CUW",
    "Czechia": "CZE",
    "Ecuador": "ECU",
    "Egypt": "EGY",
    "England": "ENG",
    "France": "FRA",
    "Germany": "GER",
    "Ghana": "GHA",
    "Haiti": "HAI",
    "IR Iran": "IRN",
    "Iraq": "IRQ",
    "Japan": "JPN",
    "Jordan": "JOR",
    "Korea Republic": "KOR",
    "Mexico": "MEX",
    "Morocco": "MAR",
    "Netherlands": "NED",
    "New Zealand": "NZL",
    "Norway": "NOR",
    "Panama": "PAN",
    "Paraguay": "PAR",
    "Portugal": "POR",
    "Qatar": "QAT",
    "Saudi Arabia": "KSA",
    "Scotland": "SCO",
    "Senegal": "SEN",
    "South Africa": "RSA",
    "Spain": "ESP",
    "Sweden": "SWE",
    "Switzerland": "SUI",
    "Tunisia": "TUN",
    "Turkiye": "TUR",
    "United States": "USA",
    "Uruguay": "URU",
    "Uzbekistan": "UZB",
}

GROUP_IDS = [chr(code) for code in range(ord("A"), ord("L") + 1)]
MATCH_STAGE_MAP = {
    range(1, 73): ("group", "Group Stage"),
    range(73, 89): ("round_of_32", "Round of 32"),
    range(89, 97): ("round_of_16", "Round of 16"),
    range(97, 101): ("quarterfinal", "Quarterfinal"),
    range(101, 103): ("semifinal", "Semifinal"),
    range(103, 104): ("third_place", "Third Place Playoff"),
    range(104, 105): ("final", "Final"),
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


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    lowered = lowered.replace("&", " and ")
    lowered = lowered.replace("'", "")
    lowered = lowered.replace(".", " ")
    lowered = lowered.replace("/", " ")
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered).strip("-")
    return lowered


def normalize_venue_id(venue_name: str) -> str:
    venue_name = str(venue_name or "").strip()
    return VENUE_ID_BY_VENUE_NAME.get(venue_name) or slugify(venue_name)


def parse_team_translations() -> dict[str, dict[str, object]]:
    source = TEAM_TRANSLATIONS_PATH.read_text(encoding="utf-8")
    pattern = re.compile(
        r'"(?P<name>[^"]+)": \{ zh: "(?P<zh>[^"]+)"(?:, flag: "(?P<flag>[^"]+)")?(?:, fifaRank: (?P<rank>\d+))? \}'
    )
    translations: dict[str, dict[str, object]] = {}
    for match in pattern.finditer(source):
        name = match.group("name")
        entry: dict[str, object] = {"zh": match.group("zh")}
        if match.group("flag"):
            entry["flag"] = match.group("flag")
        if match.group("rank"):
            entry["fifa_rank"] = int(match.group("rank"))
        translations[name] = entry
    return translations


def parse_beijing_time(value: str) -> str:
    parsed = datetime.strptime(value.replace("（北京时间）", "").strip(), "%Y年%m月%d日 %H:%M")
    local_dt = parsed.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    return local_dt.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z")


def detect_stage(match_number: int) -> tuple[str, str]:
    for number_range, stage_info in MATCH_STAGE_MAP.items():
        if match_number in number_range:
            return stage_info
    raise ValueError(f"Unknown stage for match {match_number}")


def build_placeholder_from_label(label: str) -> dict[str, object] | None:
    group_match = re.fullmatch(r"([A-L])组(第一|第二)", label)
    if group_match:
        group_id, placement = group_match.groups()
        suffix = "winner" if placement == "第一" else "runner_up"
        english_label = f"Group {group_id} {'Winner' if placement == '第一' else 'Runner-up'}"
        return {
            "team_id": f"slot-group-{group_id.lower()}-{suffix}",
            "name": english_label,
            "short_name": f"{group_id}{'1' if placement == '第一' else '2'}",
            "localized_name": {"zh-CN": label},
            "aliases": [label, english_label],
            "sources": ["manual"],
            "updated_at": "2026-05-15T00:00:00Z",
            "is_placeholder": True,
        }

    best_third_match = re.fullmatch(r"([A-L/]+)组第三名", label)
    if best_third_match:
        groups = best_third_match.group(1)
        english_label = f"Best Third-Place Team from {groups}"
        return {
            "team_id": f"slot-best-third-{groups.lower().replace('/', '-')}",
            "name": english_label,
            "short_name": "3RD",
            "localized_name": {"zh-CN": label},
            "aliases": [label, english_label],
            "sources": ["manual"],
            "updated_at": "2026-05-15T00:00:00Z",
            "is_placeholder": True,
        }

    winner_match = re.fullmatch(r"第(\d+)场胜者", label)
    if winner_match:
        match_no = winner_match.group(1)
        english_label = f"Winner of Match {match_no}"
        return {
            "team_id": f"slot-winner-match-{match_no}",
            "name": english_label,
            "short_name": f"W{match_no}",
            "localized_name": {"zh-CN": label},
            "aliases": [label, english_label],
            "sources": ["manual"],
            "updated_at": "2026-05-15T00:00:00Z",
            "is_placeholder": True,
        }

    loser_match = re.fullmatch(r"第(\d+)场负者", label)
    if loser_match:
        match_no = loser_match.group(1)
        english_label = f"Loser of Match {match_no}"
        return {
            "team_id": f"slot-loser-match-{match_no}",
            "name": english_label,
            "short_name": f"L{match_no}",
            "localized_name": {"zh-CN": label},
            "aliases": [label, english_label],
            "sources": ["manual"],
            "updated_at": "2026-05-15T00:00:00Z",
            "is_placeholder": True,
        }

    return None


def team_record_from_english_name(name: str, translations: dict[str, dict[str, object]]) -> dict[str, object]:
    translation = translations.get(name, {})
    aliases = [name]
    aliases.extend(CANONICAL_ALIASES.get(name, []))
    zh_name = translation.get("zh") or EN_TEAM_TO_CN.get(name)
    if isinstance(zh_name, str):
        aliases.append(zh_name)

    team: dict[str, object] = {
        "team_id": slugify(name),
        "name": name,
        "aliases": sorted(set(filter(None, aliases))),
        "sources": ["worldcup_2026_csv", "world_cup_predictor"],
        "updated_at": "2026-05-15T00:00:00Z",
    }
    if zh_name:
        team["localized_name"] = {"zh-CN": zh_name}
    if "flag" in translation:
        team["flag_emoji"] = translation["flag"]
    if "fifa_rank" in translation:
        team["fifa_rank"] = translation["fifa_rank"]
    short_name = TEAM_SHORT_NAMES.get(name) or re.sub(r"[^A-Z]", "", name.upper())[:3]
    if short_name:
        team["short_name"] = short_name
    return team


def canonical_team_from_cn(label: str, translations: dict[str, dict[str, object]]) -> dict[str, object]:
    english_name = CN_TEAM_TO_EN.get(label)
    if english_name:
        return team_record_from_english_name(english_name, translations)

    placeholder = build_placeholder_from_label(label)
    if placeholder:
        return placeholder

    raise KeyError(f"Unsupported team label in CSV: {label}")


def build_group_assignment(match_number: int) -> str | None:
    if 1 <= match_number <= 72:
        return GROUP_IDS[(match_number - 1) // 6]
    return None


def build_fixture(row: dict[str, str], translations: dict[str, dict[str, object]]) -> tuple[dict[str, object], list[dict[str, object]]]:
    match_number = int(row["序号"])
    stage, round_label = detect_stage(match_number)
    group_id = build_group_assignment(match_number)

    home_team = canonical_team_from_cn(row["主队"], translations)
    away_team = canonical_team_from_cn(row["客队"], translations)

    fixture = {
        "match_id": f"fifa_world_cup:2026:schedule_csv:{match_number:03d}",
        "competition_id": "fifa_world_cup",
        "season_id": "2026",
        "stage": stage,
        "round": round_label,
        "group": group_id,
        "date_utc": parse_beijing_time(row["比赛时间"]),
        "status": "scheduled",
        "home_team_id": home_team["team_id"],
        "away_team_id": away_team["team_id"],
        "venue_id": normalize_venue_id(row["比赛场馆"]),
        "venue_name": row["比赛场馆"],
        "host_city": row["比赛城市"],
        "host_city_id": HOST_CITY_ID_BY_CITY_NAME.get(row["比赛城市"]) or slugify(row["比赛城市"]),
        "match_theme": row["比赛主题"],
        "source_refs": {
            "worldcup_2026_schedule_csv": row["序号"],
        },
        "updated_at": "2026-05-15T00:00:00Z",
    }

    return fixture, [home_team, away_team]


def load_csv_rows() -> list[dict[str, str]]:
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    translations = parse_team_translations()
    rows = load_csv_rows()

    teams_by_id: dict[str, dict[str, object]] = {}
    fixtures: list[dict[str, object]] = []

    for row in rows:
        fixture, teams = build_fixture(row, translations)
        fixtures.append(fixture)
        for team in teams:
            team_id = str(team["team_id"])
            if team_id not in teams_by_id:
                teams_by_id[team_id] = team

    teams = sorted(teams_by_id.values(), key=lambda item: str(item["team_id"]))
    fixtures = sorted(fixtures, key=lambda item: str(item["match_id"]))

    write_json(CANONICAL_TEAMS_OUTPUT_PATH, teams)
    write_json(TEAMS_OUTPUT_PATH, teams)
    write_json(FIXTURES_OUTPUT_PATH, fixtures)

    print(f"Wrote {len(teams)} teams to {CANONICAL_TEAMS_OUTPUT_PATH}")
    print(f"Wrote {len(teams)} teams to {TEAMS_OUTPUT_PATH}")
    print(f"Wrote {len(fixtures)} fixtures to {FIXTURES_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
