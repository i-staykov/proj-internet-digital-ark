"""Export the source-saturation ledger the reviewer's 0901 update requires.

His schema: "source version, coverage, overlap, quality limitations, effort, and the
reason to retain, deprioritize, or revisit a source family." This project has kept
exactly that, per family, in the register since phase 1, so the ledger is GENERATED
from the register at packaging time, never hand-maintained, and each row points back
at the register entry that carries the full measurement.

Read over both register pages, since `convert_register.py` gave every entry one row of
named columns and moved closed families to `docs/sources-closed.md`. Two consequences
worth stating: every entry reaches the ledger now, 470 rows against 202, not only those
that carried a bold heading, and an entry's `## Detail` block is read with its row,
because the reopen clause is prose and the row is only a projection of it.

Every cell is located by its header NAME, never by position, so a column added or moved
in the register cannot shift a cell here, and a required column that goes missing raises
with the headers it did find instead of exporting a wrong ledger.

Thirteen columns since 2026-09-03: the eight of phase 7, in their old order so a
consumer reading the first eight is unaffected, plus `coverage_period`,
`retrieval_method`, `baseline_overlap`, `effort` and `source_link`. The first four are
his own schema words (coverage, overlap, effort) that the register held and the CSV
dropped; the fifth is the source URL every entry carries under rule 8. `n/a` is kept
verbatim, because in the register it means the entry does not say, which is not the same
as a column the page does not have.

    uv run python scripts/round/saturation_ledger.py --out audit/source_saturation_ledger.csv
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

DAY_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
DATES_RE = re.compile(r"[Ww]hat dates one item[:\s]*([^.|]{0,160})")
EE_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*EE")
ANCHOR_RE = re.compile(r"\[detail\]\(#([^)]+)\)")
URL_RE = re.compile(r"https?://[^\s<>()\[\]]+")
# The register's own verdict words, in the priority the old parser used.
VERDICTS = ("BLOCKED", "REOPENED", "FIND", "CLOSED")

# Ledger field <- the register header names that carry it, best first. The open page
# spells eleven columns out; the closed page keeps five shorter names for the same
# things, so most fields accept two. The order here is the open page's, because the
# prose fallbacks read the cells joined and that is the order they were written in.
COLUMNS: dict[str, tuple[str, ...]] = {
    "source_family": ("source",),
    "version_or_date": ("version or date", "date"),
    "coverage_period": ("coverage period",),
    "retrieval_method": ("retrieval method",),
    "what_dates_one_item": ("what dates one item",),
    "baseline_overlap": ("baseline overlap",),
    "coverage_ee": ("net-new ee (date)", "measured"),
    "quality_limitations": ("quality issues", "reason"),
    "effort": ("effort",),
    "status": ("verdict",),
    "source_link": ("link",),
}
# Without these there is no ledger row worth writing, so their absence is an error and
# not an empty cell. Both pages carry all five. The rest are optional, and the closed
# page has none of them.
REQUIRED = (
    "source_family",
    "version_or_date",
    "coverage_ee",
    "quality_limitations",
    "source_link",
)
VOCABULARY = {name for names in COLUMNS.values() for name in names}
# The prose fallbacks scan the row's other cells. Joining them in this fixed order
# rather than the page's makes the output independent of how the register is ordered.
BODY_ORDER = tuple(field for field in COLUMNS if field != "source_family")

FIELDS = (
    "source_family",
    "version_or_date",
    "status",
    "coverage_ee",
    "what_dates_one_item",
    "quality_limitations",
    "decision",
    "reference",
    "coverage_period",
    "retrieval_method",
    "baseline_overlap",
    "effort",
    "source_link",
)


def _clean(text: str) -> str:
    text = re.sub(r"\*\*|`|<https?://[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _link(cell: str) -> str:
    """The link cell holds the source URL and often a detail anchor; keep the URL."""
    found = URL_RE.search(cell)
    return found.group(0) if found else _clean(cell)


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _cell(cells: list[str], index: dict[str, int], field: str) -> str:
    """One cell by ledger field name. Empty when the page has no such column."""
    position = index.get(field, -1)
    return cells[position] if 0 <= position < len(cells) else ""


def is_header(cells: list[str]) -> bool:
    """A register header row: names the source column and at least two more we know."""
    seen = {c.lower() for c in cells}
    return "source" in seen and len(seen & VOCABULARY) >= 3


def header_index(cells: list[str]) -> dict[str, int]:
    """Ledger field -> column position, by header name."""
    seen = [c.lower() for c in cells]
    index: dict[str, int] = {}
    for field, names in COLUMNS.items():
        for name in names:
            if name in seen:
                index[field] = seen.index(name)
                break
    return index


def require_columns(index: dict[str, int], cells: list[str], page: str) -> None:
    missing = [field for field in REQUIRED if field not in index]
    if not missing:
        return
    wanted = "; ".join(f"{field} (one of: {', '.join(COLUMNS[field])})" for field in missing)
    raise ValueError(
        f"{page}: register table has no column for {wanted}. Headers found: {', '.join(cells)}"
    )


def detail_blocks(text: str) -> dict[str, str]:
    """The `## Detail` appendix of one page, by anchor."""
    blocks: dict[str, list[str]] = {}
    anchor = ""
    for line in text.splitlines():
        if line.startswith("### "):
            anchor = line[4:].strip()
            blocks[anchor] = []
        elif line.startswith("## "):
            anchor = ""
        elif anchor:
            blocks[anchor].append(line)
    return {key: " ".join(value) for key, value in blocks.items()}


def rows_from_register(sources_md: str, page: str = "docs/sources.md") -> list[dict[str, str]]:
    """One ledger row per register row, whatever the page's column set is."""
    rows: list[dict[str, str]] = []
    details = detail_blocks(sources_md)
    index: dict[str, int] = {}
    for line in sources_md.splitlines():
        if not line.startswith("|"):
            if line.startswith("#"):
                index = {}
            continue
        if not set(line) - set("|-: "):
            continue
        cells = _cells(line)
        if is_header(cells):
            index = header_index(cells)
            require_columns(index, cells, page)
            continue
        if not index:
            continue
        cell = {field: _cell(cells, index, field) for field in COLUMNS}
        family = _clean(cell["source_family"])
        version = cell["version_or_date"]
        day = DAY_RE.search(version)
        # The row's other cells, plus any column the register has grown that we do
        # not name yet, so a new column still feeds the fallbacks below.
        extra = [cells[i] for i in range(len(cells)) if i not in set(index.values())]
        body = " ".join(value for value in [*(cell[f] for f in BODY_ORDER), *extra] if value)
        for anchor in ANCHOR_RE.findall(body):
            body = f"{body} {details.get(anchor, '')}"
        said = (cell["status"] or body[:120]).upper()
        verdict = next((token.lower() for token in VERDICTS if token in said), "closed")
        ee = EE_RE.search(cell["coverage_ee"] or body)
        quality = _clean(cell["quality_limitations"] or body)[:300]
        # The closed page's five columns have no dating column, so it is read out of
        # the row's prose and its detail block, which is where the clause still is.
        dates = cell["what_dates_one_item"]
        if dates in ("", "n/a"):
            clause = DATES_RE.search(body)
            dates = clause.group(1) if clause else ""
        reopen = ""
        lower = body.lower()
        for marker in ("reopen", "do not re-test", "revisit", "retire"):
            position = lower.find(marker)
            if position != -1:
                reopen = _clean(body[position : position + 220])
                break
        rows.append(
            {
                "source_family": family,
                "version_or_date": day.group(1) if day else _clean(version),
                "status": verdict,
                "coverage_ee": ee.group(1).replace(",", "") if ee else "",
                "what_dates_one_item": _clean(dates),
                "quality_limitations": quality,
                "decision": reopen or "closed on measurement; see register entry",
                "reference": f"{page} register row of {day.group(1) if day else 'no date'}",
                "coverage_period": _clean(cell["coverage_period"])[:120],
                "retrieval_method": _clean(cell["retrieval_method"])[:120],
                "baseline_overlap": _clean(cell["baseline_overlap"])[:120],
                "effort": _clean(cell["effort"])[:120],
                "source_link": _link(cell["source_link"]),
            }
        )
    return rows


def rows_from_contribution(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    rows = []
    with csv_path.open() as fh:
        for record in csv.DictReader(fh):
            pairs = record.get("netnew_pairs") or record.get("pairs") or ""
            rows.append(
                {
                    "source_family": record.get("source", ""),
                    "version_or_date": "active this round",
                    "status": "active",
                    "coverage_ee": "",
                    "what_dates_one_item": "see docs/sources.md section and evidence manifest",
                    "quality_limitations": f"net-new pairs this round: {pairs}",
                    "decision": "retain: still contributing",
                    "reference": "audit/source_contribution.csv",
                }
            )
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
            page = f"docs/{path.name}"
            rows += rows_from_register(path.read_text(encoding="utf-8"), page)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, restval="")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} ledger rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
