"""Rewrite the report's headline figures from the store.

The executive summary quotes six store totals and six per-year counts, and the
archive readme repeats two of them. Every ingest changes all of those, and they
were hand-maintained, so they drifted: the summary was 6,462 pairs behind the
store before this existed, which is the kind of error a reader cannot detect but
a reviewer recomputing the numbers can.

Nothing here interprets anything. It replaces marked numbers with what
`ark stats` reports, so the prose around them stays hand-written while the
figures cannot be stale.

Usage:
    uv run python scripts/refresh_report_figures.py           # dry run, prints the diff
    uv run python scripts/refresh_report_figures.py --write
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402

from ark.stats import collect_stats  # noqa: E402

REPORT = Path("docs/report.md")
ARCHIVE_README = Path("docs/delivery_readme.md")
STORE = Path("data/ark.duckdb")


def figures() -> dict:
    """Every number below comes from `collect_stats`, the same source `ark stats`
    prints, so the report cannot disagree with the command a reviewer runs."""
    conn = duckdb.connect(str(STORE), read_only=True)
    try:
        return collect_stats(conn)
    finally:
        conn.close()


def _row(label: str, value: int, bold: bool = False) -> str:
    shown = f"**{value:,}**" if bold else f"{value:,}"
    return f"| {label} | {shown} |"


def rewrite_report(text: str, s: dict) -> str:
    scoreboard = "\n".join(
        [
            "| Metric | Value |",
            "|---|--:|",
            _row("Net-new registered domains (absent from baseline)", s["netnew_domains"], True),
            _row("Net-new (domain, year) pairs", s["netnew_pairs_total"], True),
            _row("Baseline domains (read-only)", s["baseline_domains"]),
            _row("Total domains in store", s["total_domains"]),
            _row("Total (domain, year) pairs in store", s["total_pairs"]),
            _row("Evidence rows", s["evidence_rows"]),
            _row("Candidate pool (no year evidence yet)", s["candidate_pool"]),
        ]
    )
    text = re.sub(
        r"\| Metric \| Value \|\n\|---\|--:\|\n(?:\|.*\|\n)+",
        scoreboard + "\n",
        text,
        count=1,
    )
    years = sorted(s["netnew_pairs_by_year"])
    per_year = "\n".join(
        [
            "| " + " | ".join(str(y) for y in years) + " |",
            "|" + "--:|" * len(years),
            "| " + " | ".join(f"{s['netnew_pairs_by_year'][y]:,}" for y in years) + " |",
        ]
    )
    text = re.sub(
        r"\| 1996 \| 1997 \| 1998 \| 1999 \| 2000 \| 2001 \|\n\|(?:--:\|)+\n\|[^\n]+\|",
        per_year,
        text,
        count=1,
    )
    return text


HEADLINE = (
    r"\*\*Headline \(\d{4}-\d{2}-\d{2}\):\*\* [\d,]+ net-new registered "
    r"domains · [\d,]+ net-new"
)


def rewrite_archive_readme(text: str, s: dict, today: str = "2026-07-26") -> str:
    return re.sub(
        HEADLINE,
        f"**Headline ({today}):** {s['netnew_domains']:,} net-new registered domains · "
        f"{s['netnew_pairs_total']:,} net-new",
        text,
        count=1,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write the files.")
    args = parser.parse_args()

    f = figures()
    targets = [(REPORT, rewrite_report), (ARCHIVE_README, rewrite_archive_readme)]
    for path, rewrite in targets:
        before = path.read_text(encoding="utf-8")
        after = rewrite(before, f)
        if before == after:
            print(f"{path}: already current")
            continue
        if args.write:
            path.write_text(after, encoding="utf-8")
            print(f"{path}: updated")
        else:
            print(f"{path}: would change")
    print(
        f"net-new {f['netnew_domains']:,} domains / {f['netnew_pairs_total']:,} pairs, "
        f"{f['evidence_rows']:,} evidence rows, {f['candidate_pool']:,} candidates"
    )


if __name__ == "__main__":
    main()
