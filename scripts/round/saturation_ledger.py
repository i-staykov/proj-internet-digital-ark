"""Export the source-saturation ledger the reviewer's 0901 update requires.

His schema: "source version, coverage, overlap, quality limitations, effort, and the
reason to retain, deprioritize, or revisit a source family." This project has kept
exactly that, per family, in the register since phase 1, so the ledger is GENERATED
from the register at packaging time, never hand-maintained, and each row points back
at the register entry that carries the full measurement.

Read by COLUMN HEADER, over both register pages, since `convert_register.py` gave
every entry one row of named columns and moved closed families to
`docs/sources-closed.md`. Two consequences worth stating: every entry reaches the
ledger now, 470 rows against 202, not only those that carried a bold heading, and an entry's
`## Detail` block is read with its row, because the reopen clause is prose and the
row is only a projection of it.

The eight columns are unchanged. E4.3 owns adding `retrieval_method`.

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
# The register's own verdict words, in the priority the old parser used.
VERDICTS = ("BLOCKED", "REOPENED", "FIND", "CLOSED")


def _clean(text: str) -> str:
    text = re.sub(r"\*\*|`|<https?://[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


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
    header: list[str] = []
    for line in sources_md.splitlines():
        if not line.startswith("|"):
            if line.startswith("#"):
                header = []
            continue
        cells = _cells(line)
        if cells[0].lower() == "source":
            header = [c.lower() for c in cells]
            continue
        if not header or not (set(cells[0]) - set("-: ")):
            continue
        row = dict(zip(header, cells, strict=False))
        family = _clean(cells[0])
        version = row.get("version or date") or row.get("date") or ""
        day = DAY_RE.search(version)
        body = " ".join(cells[1:])
        for anchor in ANCHOR_RE.findall(line):
            body = f"{body} {details.get(anchor, '')}"
        said = row.get("verdict", body[:120]).upper()
        verdict = next((token.lower() for token in VERDICTS if token in said), "closed")
        ee = EE_RE.search(row.get("net-new ee (date)") or row.get("measured") or body)
        quality = _clean(row.get("quality issues") or row.get("reason") or body)[:300]
        # The closed page's five columns have no dating column, so it is read out of
        # the row's prose and its detail block, which is where the clause still is.
        dates = row.get("what dates one item", "")
        if dates in ("", "n/a"):
            clause = DATES_RE.search(body)
            dates = clause.group(1) if clause else ""
        reopen = ""
        lower = body.lower()
        for marker in ("reopen", "do not re-test", "revisit", "retire"):
            pos = lower.find(marker)
            if pos != -1:
                reopen = _clean(body[pos : pos + 220])
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
    fields = [
        "source_family",
        "version_or_date",
        "status",
        "coverage_ee",
        "what_dates_one_item",
        "quality_limitations",
        "decision",
        "reference",
    ]
    with args.out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} ledger rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
