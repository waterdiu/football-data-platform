from __future__ import annotations

import re
import ssl
import json
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

try:
    import certifi
except ImportError:  # pragma: no cover - fallback for minimal Python runtimes.
    certifi = None

DEFAULT_WORLD_CUP_NEWS_SOURCE_URLS: tuple[tuple[str, str], ...] = (
    ("fifa_news", "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles"),
    ("fifa_world_cup_news", "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/news"),
    ("bbc_world_cup", "https://www.bbc.com/sport/football/world-cup"),
    ("sky_world_cup", "https://www.skysports.com/world-cup-news"),
    ("espn_soccer", "https://www.espn.com/soccer/"),
)

WORLD_CUP_TEAM_NEWS_URLS: dict[str, tuple[tuple[str, str], ...]] = {
    "Argentina": (("argentina_fa", "https://www.afa.com.ar/en/"),),
    "Brazil": (("brazil_cbf", "https://www.cbf.com.br/selecao-brasileira/noticias"),),
    "Canada": (("canada_soccer", "https://canadasoccer.com/news/"),),
    "England": (("england_fa", "https://www.englandfootball.com/articles"),),
    "France": (("france_fff", "https://www.fff.fr/selection/2-equipe-de-france/index.html"),),
    "Germany": (("germany_dfb", "https://www.dfb.de/en/news/"),),
    "Mexico": (("mexico_fmf", "https://miseleccion.mx/noticias/"),),
    "Netherlands": (("netherlands_knvb", "https://www.onsoranje.nl/nieuws"),),
    "Portugal": (("portugal_fpf", "https://www.fpf.pt/News"),),
    "Spain": (("spain_rfef", "https://rfef.es/es/noticias"),),
    "United States": (("usa_soccer", "https://www.ussoccer.com/stories"),),
}

INJURY_KEYWORDS = (
    "injured",
    "injury",
    "doubtful",
    "ruled out",
    "out injured",
    "fitness",
    "hamstring",
    "ankle",
    "knee",
    "unavailable",
    "will miss",
)
SUSPENSION_KEYWORDS = ("suspended", "suspension", "red card", "ban", "banned")
MOTIVATION_KEYWORDS = (
    "must win",
    "qualification",
    "qualify",
    "knockout",
    "group stage",
    "top the group",
    "elimination",
)
ROTATION_KEYWORDS = (
    "rotate",
    "rotation",
    "rested",
    "rest",
    "bench",
    "line-up",
    "lineup",
    "starting xi",
    "squad",
    "available",
)
SCHEDULE_PRESSURE_KEYWORDS = (
    "three days",
    "short turnaround",
    "fixture congestion",
    "congested",
    "fatigue",
    "tired",
    "extra time",
    "penalties",
)
ARTICLE_HINT_KEYWORDS = (
    "team news",
    "injury",
    "injured",
    "fitness",
    "preview",
    "press conference",
    "suspended",
    "suspension",
    "line-up",
    "lineup",
    "squad",
    "available",
    "ruled out",
    "fatigue",
    "rotation",
)
NON_ARTICLE_PATH_PATTERNS = (
    r"^/?$",
    r"/teams/",
    r"/women",
    r"/u21",
    r"/u18",
    r"/tickets?/?",
    r"/shop/?",
    r"/assets/",
    r"/static/",
)
ENTITY_STOPWORDS = {"BBC", "FIFA", "Sky Sports", "Team News", "World Cup"}

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "configs" / "prematch_news" / "world_cup_2026.json"


def _plain_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?。！？])\s+", text) if sentence.strip()]


def _fetch_text(url: str, *, timeout_seconds: int = 20) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 football-data-platform/0.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    context = ssl.create_default_context(cafile=certifi.where() if certifi else None)
    with urlopen(request, timeout=timeout_seconds, context=context) as response:  # noqa: S310 - configured trusted news URLs.
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _is_non_article_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path or "/"
    if re.search(r"\.(png|jpg|jpeg|gif|svg|webp|ico|css|js|pdf)(\?|$)", path, flags=re.IGNORECASE):
        return True
    return any(re.search(pattern, path, flags=re.IGNORECASE) for pattern in NON_ARTICLE_PATH_PATTERNS)


def _discover_article_links(html: str, *, base_url: str, team_aliases: set[str], max_links: int) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    base_host = urlparse(base_url).netloc
    for match in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html, flags=re.I | re.S):
        href = unescape(match.group(1).strip())
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute_url = urljoin(base_url, href).split("#", 1)[0]
        parsed = urlparse(absolute_url)
        if parsed.scheme not in {"http", "https"} or (base_host and parsed.netloc != base_host):
            continue
        if _is_non_article_url(absolute_url):
            continue
        haystack = f"{_plain_text(match.group(2))} {absolute_url}".casefold()
        if not any(alias.casefold() in haystack for alias in team_aliases):
            continue
        if not any(keyword in haystack for keyword in ARTICLE_HINT_KEYWORDS):
            continue
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        links.append(absolute_url)
        if len(links) >= max_links:
            break
    return links


def _team_lookup(teams: list[dict]) -> dict[str, dict]:
    return {str(team.get("team_id") or ""): team for team in teams if isinstance(team, dict)}


def _team_name(team_id: str, teams_by_id: dict[str, dict]) -> str:
    team = teams_by_id.get(team_id) or {}
    return str(team.get("name") or team_id)


def _team_aliases(team_id: str, teams_by_id: dict[str, dict]) -> set[str]:
    team = teams_by_id.get(team_id) or {}
    aliases = {str(team.get("name") or ""), str(team.get("short_name") or ""), team_id.replace("-", " ")}
    aliases.update(str(alias) for alias in team.get("aliases") or [])
    localized = team.get("localized_name") or {}
    if isinstance(localized, dict):
        aliases.update(str(value) for value in localized.values())
    return {alias for alias in aliases if alias}


def _fixture_team_aliases(fixtures: list[dict], teams_by_id: dict[str, dict]) -> set[str]:
    aliases: set[str] = set()
    for fixture in fixtures:
        aliases.update(_team_aliases(str(fixture.get("home_team_id") or ""), teams_by_id))
        aliases.update(_team_aliases(str(fixture.get("away_team_id") or ""), teams_by_id))
    return aliases


def _enabled_sources(rows: object) -> list[tuple[str, str]]:
    if not isinstance(rows, list):
        return []
    sources: list[tuple[str, str]] = []
    for item in rows:
        if not isinstance(item, dict) or item.get("enabled") is False:
            continue
        source_name = str(item.get("source") or "").strip()
        url = str(item.get("url") or "").strip()
        if source_name and url:
            sources.append((source_name, url))
    return sources


def _load_source_config(config_path: str | Path | None = None) -> dict:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        return {
            "max_article_links_per_source": 3,
            "global_sources": [
                {"source": source_name, "url": url, "enabled": True}
                for source_name, url in DEFAULT_WORLD_CUP_NEWS_SOURCE_URLS
            ],
            "team_sources": {
                team_name: [
                    {"source": source_name, "url": url, "enabled": True}
                    for source_name, url in rows
                ]
                for team_name, rows in WORLD_CUP_TEAM_NEWS_URLS.items()
            },
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _source_urls(fixtures: list[dict], teams_by_id: dict[str, dict], source_config: dict | None = None) -> list[tuple[str, str]]:
    seen: set[str] = set()
    sources: list[tuple[str, str]] = []
    config = source_config or _load_source_config()

    def append(source_name: str, url: str) -> None:
        if url and url not in seen:
            seen.add(url)
            sources.append((source_name, url))

    for source_name, url in _enabled_sources(config.get("global_sources")):
        append(source_name, url)
    needed = {
        _team_name(str(fixture.get(key) or ""), teams_by_id)
        for fixture in fixtures
        for key in ("home_team_id", "away_team_id")
    }
    team_sources = config.get("team_sources") if isinstance(config.get("team_sources"), dict) else {}
    for team_name in sorted(needed):
        for source_name, url in _enabled_sources(team_sources.get(team_name)):
            append(source_name, url)
    return sources


def _matching_keywords(sentence: str, keywords: tuple[str, ...]) -> list[str]:
    lowered = sentence.casefold()
    return [keyword for keyword in keywords if keyword in lowered]


def _extract_entities(sentence: str, team_aliases: set[str]) -> list[str]:
    blocked = {alias.casefold() for alias in team_aliases}
    entities: list[str] = []
    seen: set[str] = set()
    for candidate in re.findall(r"\b[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){0,2}\b", sentence):
        cleaned = re.sub(r"\s+", " ", candidate).strip(" .,;:()[]")
        if not cleaned or cleaned.casefold() in blocked or cleaned in ENTITY_STOPWORDS:
            continue
        if len(cleaned.split()) == 1 and cleaned.casefold() in {"the", "but", "and", "after", "before"}:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        entities.append(cleaned)
    return entities[:4]


def _signal_certainty(signal_type: str, sentence: str, keyword: str) -> str:
    lowered = sentence.casefold()
    if signal_type == "suspension":
        return "confirmed"
    if keyword in {"ruled out", "out injured", "unavailable", "will miss"}:
        return "confirmed_absence"
    if keyword in {"doubtful", "fitness"} or "could miss" in lowered or "faces a late test" in lowered:
        return "uncertain"
    if signal_type in {"rotation", "schedule_pressure"} and any(token in lowered for token in ("may", "could", "expected", "likely")):
        return "probable"
    return "reported"


def _empty_context(team_name: str) -> dict:
    return {
        "team_name": team_name,
        "injury_mentions_count": 0,
        "suspension_mentions_count": 0,
        "motivation_mentions_count": 0,
        "rotation_mentions_count": 0,
        "schedule_pressure_mentions_count": 0,
        "total_signal_count": 0,
        "confidence_score": 0.0,
        "injury_mentions": [],
        "suspension_mentions": [],
        "motivation_mentions": [],
        "rotation_mentions": [],
        "schedule_pressure_mentions": [],
    }


def _append_signal(bucket: dict, key: str, sentence: str, source_name: str, url: str, keyword: str, aliases: set[str]) -> None:
    field = f"{key}_mentions"
    item = {
        "text": sentence[:280],
        "keyword": keyword,
        "source": source_name,
        "url": url,
        "certainty": _signal_certainty(key, sentence, keyword),
        "entities": _extract_entities(sentence, aliases),
    }
    if item not in bucket[field]:
        bucket[field].append(item)
        bucket[f"{key}_mentions_count"] = len(bucket[field])


def _summarize_team_context(side: str, context: dict) -> list[str]:
    team_name = context.get("team_name") or side
    pieces: list[str] = []
    for key, label in (
        ("injury", "injury"),
        ("suspension", "suspension"),
        ("motivation", "motivation"),
        ("rotation", "rotation"),
        ("schedule_pressure", "schedule pressure"),
    ):
        count = int(context.get(f"{key}_mentions_count") or 0)
        if count:
            pieces.append(f"{team_name}: {count} {label} signal(s)")
    return pieces


def _merge_context_row(existing: dict, update: dict, fetched_at: str) -> dict:
    row = dict(existing)
    source_statuses = dict(row.get("source_statuses") or {})
    source_statuses["pre_match_news"] = "available"
    row["source_statuses"] = source_statuses
    row["prematch_news_summary"] = update
    row["source_freshness"] = update.get("source_freshness", [])
    row["latest_snapshots_count"] = max(int(row.get("latest_snapshots_count") or 0), 1)
    row["updated_at"] = fetched_at
    return row


def collect_prematch_context(
    *,
    fixtures: list[dict],
    teams: list[dict],
    existing_context_rows: list[dict],
    fetched_at: str,
    max_article_links_per_source: int = 3,
    source_config_path: str | Path | None = None,
) -> tuple[list[dict], dict]:
    teams_by_id = _team_lookup(teams)
    source_config = _load_source_config(source_config_path)
    max_article_links_per_source = int(source_config.get("max_article_links_per_source") or max_article_links_per_source)
    sources = _source_urls(fixtures, teams_by_id, source_config)
    pages: list[dict] = []
    failed_sources: list[str] = []
    errors: list[str] = []
    source_freshness: list[dict[str, object]] = []
    fixture_aliases = _fixture_team_aliases(fixtures, teams_by_id)

    for source_name, url in sources:
        page_count = 0
        try:
            html = _fetch_text(url)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            failed_sources.append(source_name)
            errors.append(f"{source_name}: {exc}")
            source_freshness.append(
                {
                    "source": source_name,
                    "url": url,
                    "status": "provider_error",
                    "last_checked_at": fetched_at,
                    "pages_collected": 0,
                    "error": str(exc),
                }
            )
            continue
        pages.append({"source_name": source_name, "url": url, "text": _plain_text(html)})
        page_count += 1
        for article_url in _discover_article_links(html, base_url=url, team_aliases=fixture_aliases, max_links=max_article_links_per_source):
            try:
                article_html = _fetch_text(article_url)
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                failed_sources.append(f"{source_name}:article")
                errors.append(f"{article_url}: {exc}")
                continue
            pages.append({"source_name": f"{source_name}:article", "url": article_url, "text": _plain_text(article_html)})
            page_count += 1
        source_freshness.append(
            {
                "source": source_name,
                "url": url,
                "status": "available",
                "last_checked_at": fetched_at,
                "pages_collected": page_count,
            }
        )

    if not pages:
        return [], {
            "status": "provider_error" if errors else "no_rows",
            "attempted_sources": len(sources),
            "successful_pages": 0,
            "failed_sources": failed_sources,
            "errors": errors[:20],
            "source_freshness": source_freshness,
        }

    existing_by_match = {str(item.get("match_id") or ""): item for item in existing_context_rows if isinstance(item, dict)}
    updates: list[dict] = []
    for fixture in fixtures:
        match_id = str(fixture.get("match_id") or "")
        home_id = str(fixture.get("home_team_id") or "")
        away_id = str(fixture.get("away_team_id") or "")
        home_aliases = _team_aliases(home_id, teams_by_id)
        away_aliases = _team_aliases(away_id, teams_by_id)
        contexts = {
            "home": _empty_context(_team_name(home_id, teams_by_id)),
            "away": _empty_context(_team_name(away_id, teams_by_id)),
        }
        for page in pages:
            for sentence in _sentences(str(page.get("text") or "")):
                lowered = sentence.casefold()
                sides = []
                if any(alias.casefold() in lowered for alias in home_aliases):
                    sides.append(("home", home_aliases))
                if any(alias.casefold() in lowered for alias in away_aliases):
                    sides.append(("away", away_aliases))
                for side, aliases in sides:
                    for signal_type, keywords in (
                        ("injury", INJURY_KEYWORDS),
                        ("suspension", SUSPENSION_KEYWORDS),
                        ("motivation", MOTIVATION_KEYWORDS),
                        ("rotation", ROTATION_KEYWORDS),
                        ("schedule_pressure", SCHEDULE_PRESSURE_KEYWORDS),
                    ):
                        for keyword in _matching_keywords(sentence, keywords)[:2]:
                            _append_signal(
                                contexts[side],
                                signal_type,
                                sentence,
                                str(page.get("source_name") or "unknown"),
                                str(page.get("url") or ""),
                                keyword,
                                aliases,
                            )
        signal_count = 0
        for side in ("home", "away"):
            side_count = sum(
                int(contexts[side].get(f"{key}_mentions_count") or 0)
                for key in ("injury", "suspension", "motivation", "rotation", "schedule_pressure")
            )
            signal_count += side_count
            source_count = len(
                {
                    item.get("source")
                    for key in ("injury", "suspension", "motivation", "rotation", "schedule_pressure")
                    for item in contexts[side].get(f"{key}_mentions", [])
                    if isinstance(item, dict) and item.get("source")
                }
            )
            contexts[side]["total_signal_count"] = side_count
            contexts[side]["confidence_score"] = round(min(1.0, side_count * 0.12 + source_count * 0.08), 3)
        if not signal_count:
            continue
        summary = {
            "provider": "platform_prematch_news",
            "status": "available",
            "fetched_at": fetched_at,
            "signals_count": signal_count,
            "sources_checked": [{"source": page["source_name"], "url": page["url"]} for page in pages],
            "source_freshness": source_freshness,
            "home": contexts["home"],
            "away": contexts["away"],
            "summary": "; ".join(_summarize_team_context("home", contexts["home"]) + _summarize_team_context("away", contexts["away"])),
        }
        updates.append(_merge_context_row(existing_by_match.get(match_id, {"match_id": match_id}), summary, fetched_at))

    return updates, {
        "status": "collected" if updates else "no_rows",
        "attempted_sources": len(sources),
        "successful_pages": len(pages),
        "failed_sources": failed_sources,
        "errors": errors[:20],
        "rows_collected": len(updates),
        "source_freshness": source_freshness,
    }
