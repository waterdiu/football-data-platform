from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "openfootball" / "worldcup-json"
YEARS = [
    1930,
    1934,
    1938,
    1950,
    1954,
    1958,
    1962,
    1966,
    1970,
    1974,
    1978,
    1982,
    1986,
    1990,
    1994,
    1998,
    2002,
    2006,
    2010,
    2014,
    2018,
    2022,
]


def fetch_year(year: int) -> str:
    return subprocess.check_output(
        [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github.raw",
            f"repos/openfootball/worldcup.json/contents/{year}/worldcup.json",
        ],
        text=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch openfootball World Cup JSON history files.")
    parser.add_argument("--from-year", type=int, default=1930)
    parser.add_argument("--to-year", type=int, default=2022)
    args = parser.parse_args()

    years = [year for year in YEARS if args.from_year <= year <= args.to_year]
    for year in years:
        payload = fetch_year(year)
        output = RAW_DIR / str(year) / "worldcup.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload if payload.endswith("\n") else payload + "\n", encoding="utf-8")
        print(f"fetched {year} -> {output}")


if __name__ == "__main__":
    main()
