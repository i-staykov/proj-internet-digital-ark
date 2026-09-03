"""Export the source-saturation ledger the reviewer's 0901 update requires.

His schema: "source version, coverage, overlap, quality limitations, effort, and the
reason to retain, deprioritize, or revisit a source family." This project has kept
exactly that, per family, in `docs/sources.md` since phase 1: active sources in prose
sections, closed families as register rows whose second cell opens with the verdict
and figure and closes with what would reopen it. So the ledger is GENERATED from the
register at packaging time, never hand-maintained, and each row points back at the
register entry that carries the full measurement.

    uv run python scripts/round/saturation_ledger.py --out audit/source_saturation_ledger.csv
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

HEAD_RE = re.compile(r"\*\*(.+?)\s*\((\d{4}-\d{2}-\d{2})[^)]*\)\*\*")
VERDICT_RE = re.compile(
    r"\*\*\s*(CLOSED|FIND|BLOCKED|REOPENED|Worth|CLOSED,)?[^0-9]*?"
    r"([\d,]+(?:\.\d+)?)\s*(?:net-new\s+)?(?:post-split\s+)?EE",
    re.IGNORECASE,
)
DATES_RE = re.compile(r"[Ww]hat dates one item[:\s]*([^.|]{0,160})")


def _clean(text: str) -> str:
    text = re.sub(r"\*\*|`|<https?://[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def rows_from_register(sources_md: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in sources_md.splitlines():
        if not line.startswith("| **"):
            continue
        cells = [c.strip() for c in line.strip("|").split(" | ")]
        if len(cells) < 2:
            continue
        head = HEAD_RE.search(cells[0])
        if not head:
            continue
        family, day = head.group(1), head.group(2)
        body = " | ".join(cells[1:])
        verdict = "closed"
        for token in ("BLOCKED", "REOPENED", "FIND", "CLOSED"):
            if token in body[:120].upper():
                verdict = token.lower()
                break
        ee = VERDICT_RE.search(body)
        dates = DATES_RE.search(body)
        first_sentence = _clean(body.split(". ", 1)[0])[:300]
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
                "version_or_date": day,
                "status": verdict,
                "coverage_ee": ee.group(2).replace(",", "") if ee else "",
                "what_dates_one_item": _clean(dates.group(1)) if dates else "",
                "quality_limitations": first_sentence,
                "decision": reopen or "closed on measurement; see register entry",
                "reference": "docs/sources.md register row of " + day,
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
    parser.add_argument(
        "--contribution",
        type=Path,
        default=REPO / "output/internet-digital-ark-1996-2001/audit/source_contribution.csv",
    )
    args = parser.parse_args()

    rows = rows_from_contribution(args.contribution)
    rows += rows_from_register(args.sources.read_text(encoding="utf-8"))
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
