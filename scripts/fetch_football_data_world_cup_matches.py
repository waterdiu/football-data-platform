from __future__ import annotations

import argparse
import json
import os
import ssl
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
WORLD_CUP_SITE_ROOT = ROOT.parent / "worldcup" / "2026"
PREDICTOR_ROOT = ROOT.parent / "world-cup-predictor"

RAW_DIR = ROOT / "data" / "raw" / "football-data-org"
DEFAULT_OUTPUT_PATH = RAW_DIR / "world_cup_2026_matches.json"
DEFAULT_URL = "https://api.football-data.org/v4/competitions/WC/matches?season=2026"


def load_env_value(name: str) -> str | None:
    direct = os.environ.get(name, "").strip()
    if direct:
        return direct

    env_paths = [
        ROOT / ".env.local",
        WORLD_CUP_SITE_ROOT / ".env.local",
        PREDICTOR_ROOT / ".env.local",
    ]
    for env_path in env_paths:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == name and value.strip():
                return value.strip()
    return None


def fetch_json(url: str, api_key: str, *, insecure: bool = False) -> dict:
    request = Request(
        url,
        headers={
            "X-Auth-Token": api_key,
            "Accept": "application/json",
            "User-Agent": "football-data-platform/0.1",
        },
        method="GET",
    )
    context = ssl._create_unverified_context() if insecure else None
    with urlopen(request, timeout=30, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch World Cup 2026 match payload from football-data.org")
    parser.add_argument("--url", default=DEFAULT_URL, help="football-data.org endpoint")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="output JSON path")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification for local recovery when the Python trust store is broken.",
    )
    args = parser.parse_args()

    api_key = load_env_value("FOOTBALL_DATA_API_KEY")
    if not api_key:
        raise RuntimeError("FOOTBALL_DATA_API_KEY was not found in environment or known .env.local files.")

    try:
        payload = fetch_json(args.url, api_key, insecure=args.insecure)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"football-data.org request failed with HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"football-data.org request failed: {error.reason}") from error

    output_path = Path(args.output)
    write_json(output_path, payload)
    match_count = len(payload.get("matches", [])) if isinstance(payload, dict) else 0
    print(f"Wrote football-data.org payload to {output_path}")
    print(f"Match count: {match_count}")


if __name__ == "__main__":
    main()
