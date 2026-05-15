from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_FIXTURES_PATH = ROOT / "data" / "normalized" / "world_cup_2026_authoritative_fixtures.json"
PUBLIC_FIXTURES_PATH = ROOT / "data" / "public" / "fixtures.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish normalized football data artifacts to public outputs.")
    parser.add_argument(
        "--authoritative-fixtures",
        default=str(NORMALIZED_FIXTURES_PATH),
        help="Path to authoritative normalized fixtures JSON.",
    )
    parser.add_argument(
        "--public-fixtures",
        default=str(PUBLIC_FIXTURES_PATH),
        help="Path to public fixtures JSON output.",
    )
    args = parser.parse_args()

    authoritative_fixtures_path = Path(args.authoritative_fixtures)
    fixtures = load_json(authoritative_fixtures_path)
    if not isinstance(fixtures, list):
        raise TypeError("Authoritative fixtures payload must be a list.")

    write_json(Path(args.public_fixtures), fixtures)
    print(f"Published {len(fixtures)} fixtures to {args.public_fixtures}")


if __name__ == "__main__":
    main()
