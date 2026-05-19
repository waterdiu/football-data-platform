from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_API_DIR = ROOT / "data" / "public" / "api" / "worldcup" / "2026"
PUBLIC_DIR = ROOT / "data" / "public"
MODEL_DIR = ROOT / "data" / "model"
REPORTS_DIR = ROOT / "reports"
OUTPUT_PATH = REPORTS_DIR / "world_cup_pre_tournament_readiness.json"

GENERATED_AT = "2026-05-19T00:00:00Z"
EXPECTED_FIXTURES = 104
EXPECTED_TEAMS = 48
EXPECTED_HOST_CITIES = 16


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def rows(payload: Any, *keys: str) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
        for key in ("data", "rows", "fixtures", "matches", "teams", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def row_count(payload: Any, *keys: str) -> int:
    return len(rows(payload, *keys))


def status_counts(items: list[Any], field: str = "source_status") -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        value = str(item.get(field) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def nested(payload: Any, *path: str) -> Any:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def report_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    phase: str,
    status: str,
    severity: str,
    title: str,
    detail: str,
    evidence: dict[str, Any] | None = None,
    next_action: str,
) -> None:
    checks.append(
        {
            "id": check_id,
            "phase": phase,
            "status": status,
            "severity": severity,
            "title": title,
            "detail": detail,
            "evidence": evidence or {},
            "next_action": next_action,
        }
    )


def main() -> None:
    fixtures = load_json(PUBLIC_DIR / "fixtures.json")
    teams = load_json(PUBLIC_API_DIR / "core" / "teams.json")
    host_cities = load_json(PUBLIC_API_DIR / "core" / "host-city-profiles.json")
    venues = load_json(PUBLIC_API_DIR / "core" / "venues.json")
    team_history = load_json(PUBLIC_API_DIR / "core" / "team-world-cup-history.json")
    team_recent_matches = load_json(PUBLIC_API_DIR / "core" / "team-recent-matches.json")
    player_profiles = load_json(PUBLIC_API_DIR / "core" / "player-profiles.json")
    coach_profiles = load_json(PUBLIC_API_DIR / "core" / "coach-profiles.json")
    referee_profiles = load_json(PUBLIC_API_DIR / "core" / "referee-profiles.json")
    predictions = load_json(PUBLIC_API_DIR / "predictor" / "predictions-source.json")
    runtime_summary = load_json(PUBLIC_API_DIR / "predictor" / "runtime-summary.json")

    lineups = load_json(MODEL_DIR / "lineups.json")
    injuries = load_json(MODEL_DIR / "injuries.json")
    weather = load_json(MODEL_DIR / "weather.json")
    odds = load_json(MODEL_DIR / "odds_snapshots.json")

    data_quality = load_json(REPORTS_DIR / "data-quality.json")
    source_health = load_json(REPORTS_DIR / "source-health.json")
    roster_checklist = load_json(REPORTS_DIR / "world_cup_roster_source_checklist.json")
    api_football_probe = load_json(REPORTS_DIR / "api_football_worldcup_runtime_probe.json")
    odds_api_scan = load_json(REPORTS_DIR / "odds_api_io_event_scan_report.json")
    odds_api_sampling = load_json(REPORTS_DIR / "odds_api_io_sampling_report.json")
    person_readiness = load_json(REPORTS_DIR / "person_data_source_readiness.json")

    checks: list[dict[str, Any]] = []

    fixture_count = row_count(fixtures)
    missing_kickoff = 0
    for fixture in rows(fixtures):
        if isinstance(fixture, dict) and not (fixture.get("kickoff_at") or fixture.get("date_utc")):
            missing_kickoff += 1
    report_check(
        checks,
        check_id="core_fixtures_kickoff",
        phase="P0_core",
        status="pass" if fixture_count == EXPECTED_FIXTURES and missing_kickoff == 0 else "blocked",
        severity="P0",
        title="104 场赛程与 kickoff_at",
        detail=f"fixtures={fixture_count}, missing_kickoff={missing_kickoff}",
        evidence={"fixture_count": fixture_count, "missing_kickoff": missing_kickoff},
        next_action="若失败，先停止所有消费项目发布，重建 canonical fixtures。",
    )

    report_check(
        checks,
        check_id="core_teams",
        phase="P0_core",
        status="pass" if row_count(teams) >= EXPECTED_TEAMS else "attention",
        severity="P0",
        title="世界杯球队基础信息",
        detail=f"teams={row_count(teams)}",
        evidence={"minimum_expected": EXPECTED_TEAMS, "actual": row_count(teams)},
        next_action="少于 48 队时先修 canonical teams；多于 48 队时确认是否包含历史/候选队伍并保持 source_status。",
    )

    report_check(
        checks,
        check_id="core_host_city_venues",
        phase="P0_core",
        status="pass" if row_count(host_cities) == EXPECTED_HOST_CITIES and row_count(venues) >= EXPECTED_HOST_CITIES else "attention",
        severity="P1",
        title="主办城市与球场",
        detail=f"host_cities={row_count(host_cities)}, venues={row_count(venues)}",
        evidence={"host_cities": row_count(host_cities), "venues": row_count(venues)},
        next_action="复核 venue_id/host_city_id/lat/lon/roof/surface/altitude/source_urls。",
    )

    history_rows = rows(team_history)
    history_counts = status_counts(history_rows)
    report_check(
        checks,
        check_id="team_world_cup_history",
        phase="P0_site",
        status="pass" if len(history_rows) == EXPECTED_TEAMS else "attention",
        severity="P1",
        title="球队历届世界杯战绩",
        detail=f"team_history_rows={len(history_rows)}",
        evidence={"rows": len(history_rows), "source_status_counts": history_counts},
        next_action="如果仍有 pending_source，确认是无参赛史还是缺数据源，并补 source_status。",
    )

    report_check(
        checks,
        check_id="team_recent_matches",
        phase="P0_site",
        status="pass" if row_count(team_recent_matches) == EXPECTED_TEAMS else "attention",
        severity="P1",
        title="48 队最近比赛基础数据",
        detail=f"team_recent_match_rows={row_count(team_recent_matches)}",
        evidence={"expected": EXPECTED_TEAMS, "actual": row_count(team_recent_matches)},
        next_action="继续用 API-FOOTBALL Pro 或历史数据补过程字段，基础比分必须保持稳定。",
    )

    roster_summary = roster_checklist.get("summary") if isinstance(roster_checklist, dict) else {}
    imported_teams = int(roster_summary.get("imported_teams") or roster_summary.get("imported_team_count") or roster_summary.get("imported") or 0)
    pending_teams = int(roster_summary.get("pending_teams") or roster_summary.get("pending_team_count") or roster_summary.get("pending") or max(EXPECTED_TEAMS - imported_teams, 0))
    report_check(
        checks,
        check_id="official_roster_import",
        phase="P0_people",
        status="pass" if imported_teams == EXPECTED_TEAMS else "pending_window",
        severity="P0",
        title="官方 26 人名单",
        detail=f"imported_teams={imported_teams}, pending_teams={pending_teams}",
        evidence={"summary": roster_summary, "player_profile_rows": row_count(player_profiles)},
        next_action="继续监控 FIFA/足协最终名单；第三方数据只补事实字段，不冒充官方名单。",
    )

    report_check(
        checks,
        check_id="coach_profiles",
        phase="P1_people",
        status="pass" if row_count(coach_profiles) == EXPECTED_TEAMS else "attention",
        severity="P1",
        title="48 队主教练基础档案",
        detail=f"coach_profiles={row_count(coach_profiles)}",
        evidence={"expected": EXPECTED_TEAMS, "actual": row_count(coach_profiles)},
        next_action="appointed_at/contract_until 仍需足协公告、FIFA profile、Wikidata 或 Transfermarkt manager profile 交叉校验。",
    )

    referee_count = row_count(referee_profiles)
    report_check(
        checks,
        check_id="world_cup_referee_profiles",
        phase="P1_people",
        status="pending_window" if referee_count == 0 else "pass",
        severity="P1",
        title="世界杯裁判名单与画像",
        detail=f"referee_profiles={referee_count}",
        evidence={"referee_profiles": referee_count},
        next_action="等待 FIFA 正式裁判名单/单场指派；样本不足时只展示，不入强模型结论。",
    )

    if isinstance(api_football_probe, dict):
        api_status = str(nested(api_football_probe, "summary", "overall_status") or api_football_probe.get("overall_status") or "unknown")
    else:
        api_status = "missing_report"
    api_plan_restricted = "plan_restricted" in json.dumps(api_football_probe, ensure_ascii=False) if api_football_probe is not None else False
    report_check(
        checks,
        check_id="api_football_pro_coverage",
        phase="P0_runtime",
        status="pending_plan" if api_plan_restricted or api_football_probe is None else "pass",
        severity="P0",
        title="API-FOOTBALL Pro 覆盖复验",
        detail=f"probe_status={api_status}, plan_restricted={api_plan_restricted}",
        evidence={
            "probe_report_exists": api_football_probe is not None,
            "overall_status": api_status,
            "plan_restricted_observed": api_plan_restricted,
        },
        next_action="Pro 开通后立即重跑 scripts/probe_api_football_worldcup_runtime.py。",
    )

    injury_counts = status_counts(rows(injuries))
    report_check(
        checks,
        check_id="runtime_injuries",
        phase="P0_runtime",
        status="pending_plan" if injury_counts.get("missing_auth") or injury_counts.get("plan_restricted") else "pass" if injury_counts.get("available") else "attention",
        severity="P0",
        title="伤停/停赛运行期数据",
        detail=f"injury_status_counts={injury_counts}",
        evidence={"rows": row_count(injuries), "source_status_counts": injury_counts},
        next_action="Pro 后验证 injuries；官方/新闻 evidence 继续作为低置信补源。",
    )

    lineup_counts = status_counts(rows(lineups))
    report_check(
        checks,
        check_id="runtime_lineups",
        phase="P0_runtime",
        status="pending_window" if lineup_counts.get("unavailable") else "pass" if lineup_counts.get("available") else "attention",
        severity="P0",
        title="确认首发",
        detail=f"lineup_status_counts={lineup_counts}",
        evidence={"rows": row_count(lineups), "source_status_counts": lineup_counts},
        next_action="只能在 T-90/T-60/T-30/T-15 窗口采集；confirmed 后只新增快照不覆盖。",
    )

    odds_rows = row_count(odds)
    world_cup_candidates = int(nested(odds_api_scan, "summary", "world_cup_candidate_count") or 0)
    mapped_rows = int(
        nested(odds_api_sampling, "summary", "mapped_row_count")
        or nested(odds_api_sampling, "summary", "standard_rows")
        or (odds_api_sampling.get("normalized_row_count") if isinstance(odds_api_sampling, dict) else 0)
        or 0
    )
    report_check(
        checks,
        check_id="runtime_odds",
        phase="P0_runtime",
        status="attention" if odds_rows == 0 else "pass",
        severity="P0",
        title="赔率 1X2/AH/OU",
        detail=f"runtime_odds_rows={odds_rows}, odds_api_io_world_cup_candidates={world_cup_candidates}",
        evidence={
            "runtime_rows": odds_rows,
            "odds_api_io_world_cup_candidate_count": world_cup_candidates,
            "odds_api_io_mapped_rows": mapped_rows,
        },
        next_action="首场前 5 天重跑 Odds-API.io event scan；API-FOOTBALL Pro odds 只先验证，不直接作为强 Kelly/CLV。",
    )

    weather_counts = status_counts(rows(weather))
    report_check(
        checks,
        check_id="runtime_weather",
        phase="P1_runtime",
        status="pending_window" if weather_counts.get("unavailable") else "pass" if weather_counts.get("available") else "attention",
        severity="P1",
        title="天气预报",
        detail=f"weather_status_counts={weather_counts}",
        evidence={"rows": row_count(weather), "source_status_counts": weather_counts},
        next_action="进入 Open-Meteo 16 天预报窗口后刷新 T-72/T-24/T-6/T-1 天气。",
    )

    runtime_rows = row_count(runtime_summary)
    report_check(
        checks,
        check_id="predictor_runtime_summary",
        phase="P0_model",
        status="pass" if runtime_rows == EXPECTED_FIXTURES else "attention",
        severity="P0",
        title="模型 runtime summary",
        detail=f"runtime_summary_rows={runtime_rows}",
        evidence={"expected": EXPECTED_FIXTURES, "actual": runtime_rows},
        next_action="保持 104 场稳定行；缺失运行期数据必须标 source_status，不得填 0。",
    )

    prediction_rows = row_count(predictions, "fixtures")
    missing_prediction_kickoff = 0
    for item in rows(predictions, "fixtures"):
        if isinstance(item, dict) and not (item.get("kickoff_at") or item.get("date_utc")):
            missing_prediction_kickoff += 1
    report_check(
        checks,
        check_id="predictor_predictions_source",
        phase="P0_model",
        status="pass" if prediction_rows == EXPECTED_FIXTURES and missing_prediction_kickoff == 0 else "attention",
        severity="P0",
        title="模型预测源与 kickoff",
        detail=f"prediction_rows={prediction_rows}, missing_kickoff={missing_prediction_kickoff}",
        evidence={"prediction_rows": prediction_rows, "missing_kickoff": missing_prediction_kickoff},
        next_action="模型重新写回后必须通过 publish 层保留 kickoff/date_utc/venue/stage 字段。",
    )

    person_field_readiness = person_readiness.get("field_readiness") if isinstance(person_readiness, dict) else {}
    report_check(
        checks,
        check_id="person_profile_snapshot_inputs",
        phase="P1_model",
        status="attention",
        severity="P1",
        title="人物画像快照输入",
        detail="人物档案基础数据存在，但真实能力评分、真实缺阵影响、裁判画像和风格蒸馏仍缺强样本。",
        evidence={"field_readiness": person_field_readiness},
        next_action="先输出 confidence/sample_size/source/evidence；样本不足时只做报告和 Kelly 降权。",
    )

    quality_counts = nested(data_quality, "summary", "status_counts") or {}
    health_runtime = nested(source_health, "runtime_collection") or nested(source_health, "sources", "runtime_collection")
    report_check(
        checks,
        check_id="health_reports_available",
        phase="P1_ops",
        status="pass" if data_quality is not None and source_health is not None else "attention",
        severity="P1",
        title="健康报告与质量报告",
        detail="source-health 和 data-quality 是排障入口。",
        evidence={
            "data_quality_exists": data_quality is not None,
            "data_quality_status_counts": quality_counts,
            "source_health_exists": source_health is not None,
            "runtime_collection_summary": health_runtime,
        },
        next_action="每次全量发布后重建 source-health、data-quality 和本 readiness 报告。",
    )

    status_counts_summary: dict[str, int] = {}
    severity_counts_summary: dict[str, int] = {}
    phase_counts_summary: dict[str, int] = {}
    for check in checks:
        status_counts_summary[check["status"]] = status_counts_summary.get(check["status"], 0) + 1
        severity_counts_summary[check["severity"]] = severity_counts_summary.get(check["severity"], 0) + 1
        phase_counts_summary[check["phase"]] = phase_counts_summary.get(check["phase"], 0) + 1

    payload = {
        "generated_at": GENERATED_AT,
        "scope": "worldcup_2026_pre_tournament",
        "summary": {
            "checks": len(checks),
            "status_counts": dict(sorted(status_counts_summary.items())),
            "severity_counts": dict(sorted(severity_counts_summary.items())),
            "phase_counts": dict(sorted(phase_counts_summary.items())),
            "blocking_count": status_counts_summary.get("blocked", 0),
            "attention_count": status_counts_summary.get("attention", 0),
            "pending_window_count": status_counts_summary.get("pending_window", 0),
            "pending_plan_count": status_counts_summary.get("pending_plan", 0),
        },
        "checks": checks,
        "recommended_next_steps": [
            "API-FOOTBALL Pro 开通后立即重跑 scripts/probe_api_football_worldcup_runtime.py。",
            "首场比赛前 5 天重跑 Odds-API.io event scan，确认 World Cup event 可见性。",
            "继续监控 FIFA/足协官方 26 人名单，禁止第三方名单冒充官方名单。",
            "进入 T-window 后刷新 lineups、injuries、weather、odds，并重建 runtime_summary。",
            "每次全量发布后重建 source-health、data-quality 和本 readiness 报告。",
        ],
    }
    write_json(OUTPUT_PATH, payload)
    print(f"Wrote pre-tournament readiness report to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
