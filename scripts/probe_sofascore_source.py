from __future__ import annotations

import argparse
import json
import ssl
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from json_io import write_json

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "providers" / "sofascore_probe.json"
REPORT_PATH = ROOT / "reports" / "sofascore_source_probe.json"
RAW_DIR = ROOT / "data" / "raw" / "experimental" / "sofascore"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def fetch_json(url: str, *, timeout: int = 20) -> tuple[int | None, object | None, str | None]:
    context = ssl.create_default_context(cafile=certifi.where() if certifi else None)
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "football-data-platform-sofascore-probe/0.1",
        },
    )
    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            status = int(response.status)
            raw = response.read().decode("utf-8")
    except HTTPError as error:
        return int(error.code), None, str(error)
    except (URLError, TimeoutError, OSError) as error:
        return None, None, str(error)
    try:
        return status, json.loads(raw), None
    except json.JSONDecodeError:
        return status, None, "response was not JSON"


def payload_size(payload: object) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("events", "statistics", "lineups", "incidents", "shotmap", "data"):
            if isinstance(payload.get(key), list):
                return len(payload[key])
        return len(payload)
    return 0


def collect_keys(payload: object, *, max_depth: int = 4) -> list[str]:
    keys: set[str] = set()

    def walk(value: object, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                keys.add(path)
                walk(child, path, depth + 1)
        elif isinstance(value, list):
            for child in value[:5]:
                walk(child, prefix, depth + 1)

    walk(payload, "", 0)
    return sorted(keys)[:200]


def infer_field_coverage(keys: list[str], field_targets: dict[str, list[str]]) -> dict[str, object]:
    lowered = [key.casefold() for key in keys]

    def has_any(tokens: list[str]) -> bool:
        return any(any(token.casefold() in key for key in lowered) for token in tokens)

    return {
        "possession": has_any(["possession"]),
        "shots": has_any(["shot", "shots"]),
        "shots_on_target": has_any(["onTarget", "shotsOnTarget", "target"]),
        "passes": has_any(["pass", "passes"]),
        "pass_accuracy": has_any(["accuratePass", "passAccuracy", "accurate passes"]),
        "lineups": has_any(["lineup", "formation", "player.position", "substitute"]),
        "player_ratings": has_any(["rating", "sofaScoreRating"]),
        "xg_or_shot_quality": has_any(["xg", "expected", "expectedGoals"]),
        "ppda_direct": has_any(["ppda"]),
        "ppda_inputs_possible": has_any(["pass"]) and has_any(["tackle", "interception", "duel", "defensive"]),
        "target_groups": list(field_targets),
    }


def endpoint_url(api_base: str, template: str, **values: object) -> str:
    path = template.format(**values).lstrip("/")
    return urljoin(api_base.rstrip("/") + "/", path)


def summarize_endpoint(
    *,
    name: str,
    url: str,
    payload: object | None,
    status: int | None,
    error: str | None,
    field_targets: dict[str, list[str]],
) -> dict[str, object]:
    keys = collect_keys(payload) if payload is not None else []
    return {
        "endpoint": name,
        "url": url,
        "http_status": status,
        "error": error,
        "row_count_or_key_count": payload_size(payload) if payload is not None else 0,
        "top_level_type": type(payload).__name__ if payload is not None else None,
        "keys_sample": keys[:80],
        "field_coverage_inferred": infer_field_coverage(keys, field_targets),
    }


def write_raw_payload(*, endpoint: str, identifier: str, payload: object | None) -> str | None:
    if payload is None:
        return None
    output = RAW_DIR / endpoint / f"{identifier}.json"
    write_json(output, payload)
    return rel(output)


def probe_event(
    *,
    event_id: str,
    config: dict,
    live: bool,
    write_raw: bool,
) -> dict[str, object]:
    provider = config["provider"]
    api_base = str(provider["api_base"])
    templates = config["endpoint_templates"]
    field_targets = config["field_targets"]
    endpoints = {
        "event_statistics": templates["event_statistics"],
        "event_lineups": templates["event_lineups"],
        "event_incidents": templates["event_incidents"],
        "event_shotmap": templates["event_shotmap"],
        "event_graph": templates["event_graph"],
    }
    rows: list[dict[str, object]] = []
    for name, template in endpoints.items():
        url = endpoint_url(api_base, template, event_id=event_id)
        if not live:
            rows.append(
                {
                    "endpoint": name,
                    "url": url,
                    "probe_status": "metadata_only",
                    "field_coverage_inferred": {},
                }
            )
            continue
        status, payload, error = fetch_json(url)
        row = summarize_endpoint(
            name=name,
            url=url,
            payload=payload,
            status=status,
            error=error,
            field_targets=field_targets,
        )
        if write_raw:
            row["raw_output"] = write_raw_payload(endpoint=name, identifier=event_id, payload=payload)
        rows.append(row)
    return {
        "event_id": event_id,
        "endpoints": rows,
    }


def probe_team_events(*, team_id: str, config: dict, live: bool, write_raw: bool) -> dict[str, object]:
    provider = config["provider"]
    api_base = str(provider["api_base"])
    template = str(config["endpoint_templates"]["team_events_last"])
    url = endpoint_url(api_base, template, team_id=team_id)
    if not live:
        return {
            "team_id": team_id,
            "endpoint": "team_events_last",
            "url": url,
            "probe_status": "metadata_only",
        }
    status, payload, error = fetch_json(url)
    row = summarize_endpoint(
        name="team_events_last",
        url=url,
        payload=payload,
        status=status,
        error=error,
        field_targets=config["field_targets"],
    )
    if write_raw:
        row["raw_output"] = write_raw_payload(endpoint="team_events_last", identifier=team_id, payload=payload)
    event_ids: list[str] = []
    if isinstance(payload, dict) and isinstance(payload.get("events"), list):
        for event in payload["events"][:5]:
            if isinstance(event, dict) and event.get("id") is not None:
                event_ids.append(str(event["id"]))
    return {
        "team_id": team_id,
        **row,
        "event_ids_sample": event_ids,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Sofascore experimental field coverage.")
    parser.add_argument("--live", action="store_true", help="attempt live non-official Sofascore endpoint probes")
    parser.add_argument("--write-raw", action="store_true", help="write live payloads to data/raw/experimental/sofascore")
    parser.add_argument("--event-id", action="append", default=[], help="Sofascore event id to probe")
    parser.add_argument("--team-id", action="append", default=[], help="Sofascore team id to probe for recent events")
    parser.add_argument("--output", default=str(REPORT_PATH), help="probe report output path")
    args = parser.parse_args()

    config = load_json(CONFIG_PATH)
    if not isinstance(config, dict):
        raise TypeError("Sofascore probe config must be an object")
    provider = config.get("provider") if isinstance(config.get("provider"), dict) else {}
    policy = config.get("policy") if isinstance(config.get("policy"), dict) else {}
    probe_inputs = config.get("probe_inputs") if isinstance(config.get("probe_inputs"), dict) else {}
    event_ids = [str(value) for value in (args.event_id or probe_inputs.get("event_ids") or []) if str(value)]
    team_ids = [str(value) for value in (args.team_id or probe_inputs.get("team_ids") or []) if str(value)]

    team_probes = [
        probe_team_events(team_id=team_id, config=config, live=args.live, write_raw=args.write_raw)
        for team_id in team_ids
    ]
    discovered_event_ids: list[str] = []
    for row in team_probes:
        for event_id in row.get("event_ids_sample") or []:
            if isinstance(event_id, str) and event_id not in discovered_event_ids:
                discovered_event_ids.append(event_id)
    all_event_ids = event_ids + [event_id for event_id in discovered_event_ids if event_id not in event_ids]
    event_probes = [
        probe_event(event_id=event_id, config=config, live=args.live, write_raw=args.write_raw)
        for event_id in all_event_ids
    ]

    endpoint_rows = [
        endpoint
        for event in event_probes
        for endpoint in event.get("endpoints", [])
        if isinstance(endpoint, dict)
    ]
    observed_coverage = {
        key: sum(1 for row in endpoint_rows if (row.get("field_coverage_inferred") or {}).get(key))
        for key in (
            "possession",
            "shots",
            "shots_on_target",
            "passes",
            "pass_accuracy",
            "lineups",
            "player_ratings",
            "xg_or_shot_quality",
            "ppda_direct",
            "ppda_inputs_possible",
        )
    }

    report = {
        "generated_at": utc_now(),
        "scope": "sofascore_experimental_probe",
        "provider": provider,
        "policy": policy,
        "live": args.live,
        "write_raw": args.write_raw,
        "summary": {
            "classification": "experimental_only",
            "production_write_allowed": False,
            "normalized_write_allowed": False,
            "public_api_write_allowed": False,
            "team_probe_count": len(team_probes),
            "event_probe_count": len(event_probes),
            "endpoint_probe_count": len(endpoint_rows),
            "observed_field_endpoint_counts": observed_coverage,
        },
        "team_probes": team_probes,
        "event_probes": event_probes,
        "github_projects_to_review": config.get("github_projects_to_review") or [],
        "recommended_next_steps": [
            "Use known Sofascore team/event ids only for live probes; do not crawl schedules broadly.",
            "Keep all live payloads under data/raw/experimental/sofascore.",
            "Do not promote Sofascore rows to normalized/model/public API without authorization and field stability review.",
            "If shotmap includes xG, it can support post-match validation only after legal review.",
            "Treat PPDA as missing unless direct PPDA or event-level pass/defensive-action inputs are verified.",
        ],
    }
    write_json(Path(args.output), report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
