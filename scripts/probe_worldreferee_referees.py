from __future__ import annotations

import argparse
import json
import re
import ssl
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from json_io import write_json

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None

ROOT = Path(__file__).resolve().parents[1]
OFFICIALS_PATH = ROOT / "data" / "normalized" / "world_cup_2026_match_officials_master.json"
REPORT_PATH = ROOT / "reports" / "worldreferee_referee_probe_report.json"
RAW_DIR = ROOT / "data" / "raw" / "experimental" / "referee_sources" / "worldreferee"

DEFAULT_LIMIT = 6
BASE_URL = "https://worldreferee.com/referee"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_list(payload: object, label: str) -> list[dict]:
    if not isinstance(payload, list):
        raise TypeError(f"{label} must contain a list")
    return [item for item in payload if isinstance(item, dict)]


def slug_from_fifa_name(name: str) -> str:
    tokens = [token for token in name.split() if token]
    surname_tokens: list[str] = []
    given_tokens: list[str] = []
    for token in tokens:
        if not given_tokens and token.upper() == token:
            surname_tokens.append(token)
        else:
            given_tokens.append(token)
    if not surname_tokens and tokens:
        surname_tokens = [tokens[-1]]
        given_tokens = tokens[:-1]
    if not given_tokens and len(surname_tokens) > 1:
        surname_tokens, given_tokens = surname_tokens[-1:], surname_tokens[:-1]
    parts = [*given_tokens, *surname_tokens]
    slug = "_".join(re.sub(r"[^a-z0-9]+", "", part.casefold()) for part in parts)
    return "_".join(part for part in slug.split("_") if part)


def fetch_html(url: str, *, timeout: int = 20) -> tuple[int | None, str | None, str | None]:
    context = ssl.create_default_context(cafile=certifi.where() if certifi else None)
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "football-data-platform-worldreferee-probe/0.1",
        },
    )
    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            return int(response.status), response.read().decode("utf-8", errors="replace"), None
    except HTTPError as error:
        return int(error.code), None, str(error)
    except (URLError, TimeoutError, OSError) as error:
        return None, None, str(error)


def parse_stat_value(text: str, *, numeric: bool = True) -> float | int | str:
    cleaned = text.strip().replace(",", "")
    if not numeric:
        return text.strip()
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    if not match:
        return text.strip()
    value = match.group(0)
    return float(value) if "." in value else int(value)


def parse_stats(soup: BeautifulSoup) -> dict[str, object]:
    stats: dict[str, object] = {}
    for stat in soup.select(".wr-ref-stat"):
        num = stat.select_one(".wr-ref-stat-num")
        label = stat.select_one(".wr-ref-stat-label")
        avg = stat.select_one(".wr-ref-stat-avg")
        if not num or not label:
            continue
        key = re.sub(r"[^a-z0-9]+", "_", label.get_text(" ", strip=True).casefold()).strip("_")
        stats[key] = parse_stat_value(num.get_text(" ", strip=True), numeric=key != "active_years")
        if avg:
            avg_text = avg.get_text(" ", strip=True)
            match = re.search(r"([0-9.]+)", avg_text)
            if match:
                stats[f"{key}_per_match"] = float(match.group(1))
    return stats


def parse_matches(soup: BeautifulSoup, *, limit: int = 25) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    current_competition: str | None = None
    for table_row in soup.select("table.wr-match-table tr"):
        group = table_row.select_one(".wr-match-group-row td")
        if group:
            current_competition = group.get_text(" ", strip=True)
            continue
        stage = table_row.select_one(".wr-match-stage")
        home = table_row.select_one(".wr-match-home")
        away = table_row.select_one(".wr-match-away")
        result = table_row.select_one(".wr-match-result")
        date = table_row.select_one(".wr-match-date")
        cards = table_row.select_one(".wr-match-cards")
        if not (stage and home and away and result and date):
            continue
        row = {
            "competition": current_competition,
            "stage": stage.get_text(" ", strip=True),
            "home": home.get_text(" ", strip=True),
            "away": away.get_text(" ", strip=True),
            "result": result.get_text(" ", strip=True),
            "date": date.get_text(" ", strip=True),
            "cards_text": cards.get_text(" ", strip=True) if cards else "",
            "yellow_cards_visible": len(cards.select(".wr-ci-y")) if cards else 0,
            "red_cards_visible": len(cards.select(".wr-ci-r")) if cards else 0,
        }
        rows.append(row)
        if len(rows) >= limit:
            break
    return rows


def parse_page(html: str) -> dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one("h1.wr-page-hero-title")
    badges = [badge.get_text(" ", strip=True) for badge in soup.select(".wr-info-badge")]
    description = soup.select_one('meta[name="description"]')
    canonical = soup.select_one('link[rel="canonical"]')
    stats = parse_stats(soup)
    matches = parse_matches(soup)
    return {
        "page_title": unescape(title.get_text(" ", strip=True)) if title else None,
        "badges": badges,
        "description": description.get("content") if description else None,
        "canonical_url": canonical.get("href") if canonical else None,
        "stats": stats,
        "matches_sample": matches,
        "field_coverage": {
            "matches": "matches" in stats,
            "competitions": "competitions" in stats,
            "yellow_cards": "yellow_cards" in stats,
            "red_cards": "red_cards" in stats,
            "penalties": "penalties" in stats,
            "fouls": "fouls" in stats,
            "active_years": "active_years" in stats,
            "match_history_rows": len(matches),
        },
    }


def source_rows(limit: int | None) -> list[dict]:
    officials = ensure_list(load_json(OFFICIALS_PATH), "world_cup_2026_match_officials_master.json")
    referees = [row for row in officials if row.get("role") == "referee"]
    return referees if limit is None else referees[:limit]


def probe_referee(referee: dict, *, write_raw: bool) -> dict:
    slug = slug_from_fifa_name(str(referee.get("name") or ""))
    url = f"{BASE_URL}/{slug}"
    status, html, error = fetch_html(url)
    row = {
        "official_id": referee.get("official_id"),
        "fifa_name": referee.get("name"),
        "association_code": referee.get("association_code"),
        "candidate_slug": slug,
        "url": url,
        "http_status": status,
        "probe_status": "error" if error else "available" if status == 200 and html else "unavailable",
        "error": error,
        "parsed": {},
        "raw_html_path": None,
    }
    if not html:
        return row
    parsed = parse_page(html)
    row["parsed"] = parsed
    if write_raw:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        raw_path = RAW_DIR / f"{slug}.html"
        raw_path.write_text(html, encoding="utf-8")
        row["raw_html_path"] = str(raw_path.relative_to(ROOT))
    return row


def build_report(*, limit: int | None, sleep_seconds: float, write_raw: bool) -> dict:
    generated_at = utc_now()
    rows = []
    for index, referee in enumerate(source_rows(limit)):
        if index and sleep_seconds > 0:
            time.sleep(sleep_seconds)
        rows.append(probe_referee(referee, write_raw=write_raw))
    available_rows = [row for row in rows if row.get("probe_status") == "available"]
    coverage_keys = ("matches", "competitions", "yellow_cards", "red_cards", "penalties", "fouls", "active_years")
    return {
        "generated_at": generated_at,
        "status": "probe_only",
        "source": "WorldReferee",
        "source_url": "https://worldreferee.com/",
        "policy": {
            "production_write_allowed": False,
            "allowed_outputs": ["reports", "data/raw/experimental/referee_sources/worldreferee"],
            "promotion_required_checks": ["terms_review", "stable_id_mapping", "field_stability", "sample_thresholds"],
        },
        "scope": {
            "requested_referees": len(rows),
            "limit": limit,
            "write_raw": write_raw,
        },
        "summary": {
            "available": len(available_rows),
            "unavailable": len(rows) - len(available_rows),
            "field_coverage": {
                key: sum(1 for row in available_rows if (row.get("parsed") or {}).get("field_coverage", {}).get(key))
                for key in coverage_keys
            },
            "match_history_rows_total": sum(
                int((row.get("parsed") or {}).get("field_coverage", {}).get("match_history_rows") or 0)
                for row in available_rows
            ),
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe WorldReferee coverage for FIFA World Cup 2026 referees.")
    parser.add_argument("--all", action="store_true", help="probe all 52 appointed FIFA referees")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="number of referees to probe unless --all is set")
    parser.add_argument("--sleep", type=float, default=0.5, help="seconds to sleep between requests")
    parser.add_argument("--write-raw", action="store_true", help="write raw HTML to data/raw/experimental")
    parser.add_argument("--output", default=str(REPORT_PATH), help="report output path")
    args = parser.parse_args()

    limit = None if args.all else args.limit
    report = build_report(limit=limit, sleep_seconds=args.sleep, write_raw=args.write_raw)
    write_json(Path(args.output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
