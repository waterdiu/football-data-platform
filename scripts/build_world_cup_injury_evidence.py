from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = ROOT / "data" / "normalized"
PUBLIC_DIR = ROOT / "data" / "public"
REPORTS_DIR = ROOT / "reports"

INJURIES_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_model_injuries_master.json"
PREMATCH_CONTEXT_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_model_prematch_context_master.json"
PLAYERS_MASTER_PATH = NORMALIZED_DIR / "world_cup_2026_players_master.json"
TEAMS_PATH = PUBLIC_DIR / "teams.json"
REPORT_PATH = REPORTS_DIR / "world_cup_injury_evidence_report.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_name(value: object) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def player_name_index(players: list[dict]) -> dict[str, dict[str, set[str]]]:
    names_by_team: dict[str, dict[str, set[str]]] = {}
    for player in players:
        if not isinstance(player, dict):
            continue
        team_id = str(player.get("team_id") or "")
        if not team_id:
            continue
        names = [player.get("name"), player.get("display_name"), player.get("name_zh")]
        normalized_names = {normalize_name(name) for name in names if normalize_name(name)}
        last_names = {
            normalize_name(str(name).split()[-1])
            for name in names
            if isinstance(name, str) and len(str(name).split()) > 1 and len(str(name).split()[-1]) >= 4
        }
        team_index = names_by_team.setdefault(team_id, {"full": set(), "last": set()})
        team_index["full"].update(normalized_names)
        team_index["last"].update(last_names)
    return names_by_team


def team_name_index(teams: list[dict]) -> dict[str, str]:
    index: dict[str, str] = {}
    for team in teams:
        if not isinstance(team, dict):
            continue
        team_id = str(team.get("team_id") or "")
        if not team_id:
            continue
        names = [team.get("name"), team.get("short_name"), *(team.get("aliases") or [])]
        for name in names:
            key = normalize_name(name)
            if key:
                index[key] = team_id
    return index


def entity_near_keyword(text: object, entity: object, keyword: object, *, max_distance: int = 40) -> bool:
    value = str(text or "").casefold()
    entity_value = str(entity or "").strip().casefold()
    token = str(keyword or "").strip().casefold()
    if not value or not entity_value or not token:
        return False
    entity_positions = [match.start() for match in re.finditer(re.escape(entity_value), value)]
    keyword_positions = [match.start() for match in re.finditer(rf"(?<![a-z]){re.escape(token)}(?![a-z])", value)]
    return any(abs(entity_position - keyword_position) <= max_distance for entity_position in entity_positions for keyword_position in keyword_positions)


def match_player_entities(
    entities: list[object],
    *,
    team_id: str,
    names_by_team: dict[str, dict[str, set[str]]],
    text: object,
    keyword: object,
) -> list[str]:
    team_index = names_by_team.get(team_id)
    if not team_index:
        return []
    matched: list[str] = []
    for entity in entities:
        entity_name = str(entity or "").strip()
        normalized = normalize_name(entity_name)
        if not normalized:
            continue
        if normalized in team_index["full"] or normalized in team_index["last"]:
            if entity_near_keyword(text, entity_name, keyword):
                matched.append(entity_name)
    return matched


def has_keyword_boundary(text: object, keyword: object) -> bool:
    value = str(text or "")
    token = str(keyword or "").strip()
    if not token:
        return False
    return re.search(rf"(?<![A-Za-z]){re.escape(token)}(?![A-Za-z])", value, flags=re.IGNORECASE) is not None


def evidence_items(context: dict, *, side: str, team_id: str, names_by_team: dict[str, dict[str, set[str]]]) -> list[dict]:
    items: list[dict] = []
    for signal_type in ("injury", "suspension"):
        for mention in context.get(f"{signal_type}_mentions", []):
            if not isinstance(mention, dict):
                continue
            if not has_keyword_boundary(mention.get("text"), mention.get("keyword")):
                continue
            entities = mention.get("entities") if isinstance(mention.get("entities"), list) else []
            players = match_player_entities(
                entities,
                team_id=team_id,
                names_by_team=names_by_team,
                text=mention.get("text"),
                keyword=mention.get("keyword"),
            )
            if not players:
                continue
            items.append(
                {
                    "side": side,
                    "team_name": context.get("team_name"),
                    "signal_type": signal_type,
                    "status": "suspended" if signal_type == "suspension" else "injury_reported",
                    "certainty": mention.get("certainty") or "reported",
                    "keyword": mention.get("keyword"),
                    "players": players,
                    "source": mention.get("source"),
                    "source_url": mention.get("url"),
                    "evidence_text": mention.get("text"),
                }
            )
    return items


def summarize_prematch_absences(
    row: dict,
    *,
    generated_at: str,
    names_by_team: dict[str, dict[str, set[str]]],
    team_ids_by_name: dict[str, str],
) -> dict:
    summary = row.get("prematch_news_summary") if isinstance(row.get("prematch_news_summary"), dict) else {}
    evidence: list[dict] = []
    for side in ("home", "away"):
        context = summary.get(side) if isinstance(summary.get(side), dict) else {}
        team_id = team_ids_by_name.get(normalize_name(context.get("team_name")))
        evidence.extend(evidence_items(context, side=side, team_id=team_id, names_by_team=names_by_team))
    source_urls = sorted({str(item.get("source_url") or "") for item in evidence if item.get("source_url")})
    sources = sorted({str(item.get("source") or "") for item in evidence if item.get("source")})
    return {
        "status": "available" if evidence else "no_news_absence_evidence",
        "source": "platform_prematch_news",
        "generated_at": generated_at,
        "evidence_count": len(evidence),
        "sources": sources,
        "source_urls": source_urls,
        "evidence": evidence,
        "note": (
            "News evidence is not a final injury list. It is used for model/report downgrades "
            "until official injury, suspension, or lineup sources are available."
        ),
    }


def merge_source_status(existing_status: str, absence_summary: dict, *, existing_reason: str) -> str:
    if absence_summary.get("status") == "available":
        if existing_status in {"available", "partial"}:
            return existing_status
        return "partial"
    if existing_status in {"available", "partial"}:
        return existing_status
    if existing_reason == "prematch_news_absence_evidence" and not existing_status:
        return "unavailable"
    return existing_status or "unavailable"


def status_without_absence_evidence(row: dict) -> str:
    api_status = str(((row.get("injury_summary") or {}).get("api_football_status")) or "")
    if api_status in {"available", "partial", "unavailable", "missing_auth", "plan_restricted", "provider_error"}:
        return api_status
    source_status = str(row.get("source_status") or "")
    return "" if source_status == "partial" and row.get("status_reason") == "prematch_news_absence_evidence" else source_status


def main() -> None:
    parser = argparse.ArgumentParser(description="Build World Cup injury evidence from prematch news context.")
    parser.add_argument("--injuries-master", default=str(INJURIES_MASTER_PATH))
    parser.add_argument("--prematch-context-master", default=str(PREMATCH_CONTEXT_MASTER_PATH))
    parser.add_argument("--players-master", default=str(PLAYERS_MASTER_PATH))
    parser.add_argument("--teams", default=str(TEAMS_PATH))
    parser.add_argument("--report-output", default=str(REPORT_PATH))
    args = parser.parse_args()

    injuries = load_json(Path(args.injuries_master))
    prematch_context = load_json(Path(args.prematch_context_master))
    players = load_json(Path(args.players_master))
    teams = load_json(Path(args.teams))
    if not isinstance(injuries, list):
        raise TypeError("injuries master must contain a list")
    if not isinstance(prematch_context, list):
        raise TypeError("prematch context master must contain a list")
    if not isinstance(players, list):
        raise TypeError("players master must contain a list")
    if not isinstance(teams, list):
        raise TypeError("teams must contain a list")

    generated_at = datetime.now(timezone.utc).isoformat()
    names_by_team = player_name_index(players)
    team_ids_by_name = team_name_index(teams)
    context_by_match = {
        str(row.get("match_id") or ""): row
        for row in prematch_context
        if isinstance(row, dict) and row.get("match_id")
    }

    updated_rows: list[dict] = []
    evidence_match_count = 0
    evidence_count = 0
    for injury_row in injuries:
        if not isinstance(injury_row, dict):
            continue
        match_id = str(injury_row.get("match_id") or "")
        context_row = context_by_match.get(match_id, {})
        absence_summary = summarize_prematch_absences(
            context_row,
            generated_at=generated_at,
            names_by_team=names_by_team,
            team_ids_by_name=team_ids_by_name,
        )
        row = dict(injury_row)
        row["absence_evidence_summary"] = absence_summary
        base_status = status_without_absence_evidence(row)
        row["source_status"] = merge_source_status(
            base_status,
            absence_summary,
            existing_reason=str(row.get("status_reason") or ""),
        )
        if absence_summary["status"] == "available":
            row["status_reason"] = "prematch_news_absence_evidence"
            evidence_match_count += 1
            evidence_count += int(absence_summary.get("evidence_count") or 0)
        elif row.get("status_reason") == "prematch_news_absence_evidence":
            row["status_reason"] = row["source_status"]
        updated_rows.append(row)

    write_json(Path(args.injuries_master), updated_rows)
    report = {
        "generated_at": generated_at,
        "injuries_rows": len(updated_rows),
        "prematch_context_rows": len(prematch_context),
        "matches_with_absence_evidence": evidence_match_count,
        "absence_evidence_count": evidence_count,
        "player_teams_indexed": len(names_by_team),
        "team_names_indexed": len(team_ids_by_name),
        "output": str(Path(args.injuries_master).relative_to(ROOT)),
    }
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
