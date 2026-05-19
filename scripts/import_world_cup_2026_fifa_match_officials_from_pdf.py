from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from json_io import write_json

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PDF_PATH = ROOT / "downloaded_files" / "fifa_world_cup_2026_match_officials.pdf"
OUTPUT_PATH = ROOT / "data" / "normalized" / "world_cup_2026_match_officials_master.json"
REPORT_PATH = ROOT / "reports" / "world_cup_2026_match_officials_import_report.json"

SOURCE_URL = "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/match-officials-appointed-referees"
SOURCE_PDF_URL = "https://digitalhub.fifa.com/"

COLUMN_RANGES = [
    (0, 180, 180, 240),
    (240, 390, 390, 430),
    (430, 580, 580, 620),
    (620, 760, 760, 820),
]
ROLE_BY_COLUMN = {
    0: "referee",
    1: "assistant_referee",
    2: "assistant_referee",
    3: "video_match_official",
}
ROLE_ZH = {
    "referee": "主裁判",
    "assistant_referee": "助理裁判",
    "video_match_official": "视频比赛官员",
}
EXPECTED_COUNTS = {
    "referee": 52,
    "assistant_referee": 88,
    "video_match_official": 30,
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "unknown"


def words_in_range(words: list[tuple], x_start: int, x_end: int) -> str:
    selected = [word for word in words if x_start <= word[0] < x_end]
    return " ".join(word[4] for word in sorted(selected, key=lambda item: item[0])).strip()


def extract_rows(pdf_path: Path) -> list[dict]:
    try:
        import fitz
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyMuPDF is required to parse the FIFA officials PDF.") from exc

    doc = fitz.open(pdf_path)
    line_words: dict[float, list[tuple]] = defaultdict(list)
    for page in doc:
        for word in page.get_text("words"):
            if word[1] > 185:
                line_words[round(word[1], 1)].append(word)

    rows: list[dict] = []
    for y_value, words in sorted(line_words.items()):
        for column_index, (name_start, name_end, assoc_start, assoc_end) in enumerate(COLUMN_RANGES):
            name = words_in_range(words, name_start, name_end)
            association_code = words_in_range(words, assoc_start, assoc_end)
            if not name or not association_code:
                continue
            if not re.fullmatch(r"[A-Z]{3}", association_code):
                raise ValueError(f"Unexpected association code at y={y_value}: {name} / {association_code}")
            role = ROLE_BY_COLUMN[column_index]
            rows.append(
                {
                    "name": name,
                    "association_code": association_code,
                    "role": role,
                    "pdf_y": y_value,
                    "pdf_column": column_index,
                }
            )
    return rows


def normalize_rows(rows: list[dict], *, updated_at: str) -> list[dict]:
    normalized: list[dict] = []
    seen_ids: set[str] = set()
    for row in rows:
        role = str(row["role"])
        name = str(row["name"])
        association_code = str(row["association_code"])
        official_id = f"official:fifa-world-cup:2026:{role}:{slugify(name)}"
        if official_id in seen_ids:
            raise ValueError(f"Duplicate official_id: {official_id}")
        seen_ids.add(official_id)
        normalized.append(
            {
                "official_id": official_id,
                "person_id": official_id,
                "name": name,
                "display_name": name,
                "name_zh": None,
                "country": association_code,
                "country_code": association_code,
                "nationality": association_code,
                "association_code": association_code,
                "confederation": None,
                "roles": [role],
                "role": role,
                "role_zh": ROLE_ZH[role],
                "assigned_matches": [],
                "assignment_status": "pending_match_assignment",
                "fifa_listed_since": "2026",
                "competition_id": "fifa_world_cup",
                "season_id": "2026",
                "competition_scope": "fifa_world_cup_2026",
                "source_status": "official_fifa_match_official_list",
                "sources": ["fifa_official_match_officials_pdf"],
                "source_refs": {
                    "source_url": SOURCE_URL,
                    "source_pdf_url": SOURCE_PDF_URL,
                    "source_pdf_path": str(SOURCE_PDF_PATH.relative_to(ROOT)),
                    "pdf_column": row["pdf_column"],
                    "pdf_y": row["pdf_y"],
                },
                "source_url": SOURCE_URL,
                "updated_at": updated_at,
                "metrics": {},
                "sample_status": "pending_match_assignment",
                "style_tags": [],
                "distillation_status": "insufficient_sample",
            }
        )
    return sorted(normalized, key=lambda item: (str(item["role"]), str(item["association_code"]), str(item["name"])))


def count_by_role(rows: list[dict]) -> dict[str, int]:
    counts = {role: 0 for role in EXPECTED_COUNTS}
    for row in rows:
        role = str(row.get("role") or "")
        counts[role] = counts.get(role, 0) + 1
    return counts


def load_existing_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError(f"Existing officials output is not a list: {path}")
    return [row for row in payload if isinstance(row, dict)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Import FIFA World Cup 2026 match officials from the official FIFA PDF.")
    parser.add_argument("--source-pdf", default=str(SOURCE_PDF_PATH), help="official FIFA PDF path")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="normalized officials output")
    parser.add_argument("--report-output", default=str(REPORT_PATH), help="import report output")
    args = parser.parse_args()

    source_pdf = Path(args.source_pdf)
    if not source_pdf.exists():
        raise FileNotFoundError(f"Missing FIFA match officials PDF: {source_pdf}")

    updated_at = datetime.now(timezone.utc).isoformat()
    try:
        extracted_rows = extract_rows(source_pdf)
        normalized_rows = normalize_rows(extracted_rows, updated_at=updated_at)
        import_status = "published"
    except RuntimeError:
        normalized_rows = load_existing_rows(Path(args.output))
        if not normalized_rows:
            raise
        import_status = "reused_existing_output_missing_pdf_parser"
    counts = count_by_role(normalized_rows)
    if counts != EXPECTED_COUNTS:
        raise ValueError(f"Unexpected FIFA officials counts: {counts}; expected {EXPECTED_COUNTS}")

    write_json(Path(args.output), normalized_rows)
    report = {
        "status": import_status,
        "source_pdf": str(source_pdf.relative_to(ROOT) if source_pdf.is_relative_to(ROOT) else source_pdf),
        "source_url": SOURCE_URL,
        "output": str(Path(args.output).relative_to(ROOT) if Path(args.output).is_relative_to(ROOT) else args.output),
        "counts": counts,
        "total": len(normalized_rows),
        "expected_counts": EXPECTED_COUNTS,
        "generated_at": updated_at,
    }
    write_json(Path(args.report_output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
