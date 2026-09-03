"""Export the source-saturation ledger the reviewer's 0901 update requires.

His schema: "source version, coverage, overlap, quality limitations, effort, and the
reason to retain, deprioritize, or revisit a source family." Since the 2026-09-03
row conversion the register carries exactly those as columns, one row per source,
open rows in `docs/sources.md` and closed ones in `docs/sources-closed.md`. So this
reads both BY COLUMN HEADER rather than by regex over prose, and the ledger stays
GENERATED at packaging time, never hand-maintained.

    uv run python scripts/round/saturation_ledger.py --out audit/source_saturation_ledger.csv
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

FIELDS = [
    "source_family",
    "version_or_date",
    "status",
    "coverage_period",
    "retrieval_method",
    "baseline_overlap",
    "coverage_ee",
    "what_dates_one_item",
    "quality_limitations",
    "effort",
    "decision",
    "reference",
]

# The register's column headings, as the two tables spell them, to the field they
# fill. A heading this does not know is carried into `quality_limitations`.
HEADERS = {
    "source": "source_family",
    "version or date": "version_or_date",
    "date": "version_or_date",
    "coverage period": "coverage_period",
    "retrieval method": "retrieval_method",
    "what dates one item": "what_dates_one_item",
    "baseline overlap": "baseline_overlap",
    "net-new ee (date)": "coverage_ee",
    "measured": "coverage_ee",
    "quality issues": "quality_limitations",
    "reason": "quality_limitations",
    "effort": "effort",
    "verdict": "status",
    "link": "reference",
}

EE_RE = re.compile(r"([\d,]+(?:\.\d+)?)")
DATES_RE = re.compile(r"[Ww]hat dates one item[:\s]*([^.|]{0,160})")
REOPEN_MARKERS = ("reopen", "do not re-test", "revisit", "retire")


def _clean(text: str) -> str:
    text = re.sub(r"\*\*|`|<https?://[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_separator(cells: list[str]) -> bool:
    # `|---|---|` splits to one cell that still holds its own pipes
    return set("".join(cells)) <= {"-", " ", ":", "|"}


def rows_from_register(text: str, reference: str) -> list[dict[str, str]]:
    """One ledger row per table row, under whatever headings the table declares."""
    rows: list[dict[str, str]] = []
    columns: list[str] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            if not line.strip():
                columns = []
            continue
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        if cells and cells[0].lower() == "source":
            columns = [HEADERS.get(c.lower(), "quality_limitations") for c in cells]
            continue
        if not columns or _is_separator(cells):
            continue
        row = {field: "" for field in FIELDS}
        for field, value in zip(columns, cells, strict=False):
            row[field] = f"{row[field]} {_clean(value)}".strip() if row[field] else _clean(value)
        if not row["source_family"] or row["source_family"] == "n/a":
            continue
        ee = EE_RE.search(row["coverage_ee"])
        row["coverage_ee"] = ee.group(1).replace(",", "") if ee else ""
        row["status"] = row["status"] or "closed"
        if not row["what_dates_one_item"] or row["what_dates_one_item"] == "n/a":
            dates = DATES_RE.search(row["quality_limitations"])
            row["what_dates_one_item"] = _clean(dates.group(1)) if dates else ""
        row["decision"] = _decision(row)
        row["reference"] = reference
        rows.append(row)
    return rows


def _decision(row: dict[str, str]) -> str:
    """Retain, revisit or leave closed, in the entry's own words where it says."""
    blob = row["quality_limitations"]
    lowered = blob.lower()
    for marker in REOPEN_MARKERS:
        position = lowered.find(marker)
        if position != -1:
            return _clean(blob[position : position + 220])
    if row["status"] == "active":
        return "retain: still contributing"
    if row["status"] == "parked":
        return "revisit: priced, not banked"
    return "closed on measurement; see register entry"


def rows_from_contribution(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    rows = []
    with csv_path.open() as fh:
        for record in csv.DictReader(fh):
            pairs = record.get("netnew_pairs") or record.get("pairs") or ""
            row = {field: "" for field in FIELDS}
            row.update(
                {
                    "source_family": record.get("source", ""),
                    "version_or_date": "active this round",
                    "status": "active",
                    "what_dates_one_item": "see docs/sources.md section and evidence manifest",
                    "quality_limitations": f"net-new pairs this round: {pairs}",
                    "decision": "retain: still contributing",
                    "reference": "audit/source_contribution.csv",
                }
            )
            rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sources", type=Path, default=REPO / "docs/sources.md")
    parser.add_argument("--closed", type=Path, default=REPO / "docs/sources-closed.md")
    parser.add_argument(
        "--contribution",
        type=Path,
        default=REPO / "output/internet-digital-ark-1996-2001/audit/source_contribution.csv",
    )
    args = parser.parse_args()

    rows = rows_from_contribution(args.contribution)
    for path in (args.sources, args.closed):
        if path.is_file():
            rows += rows_from_register(path.read_text(encoding="utf-8"), f"docs/{path.name}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} ledger rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
