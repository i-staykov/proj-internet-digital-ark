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
README = Path("README.md")
SOURCES_DOC = Path("docs/sources.md")
CONTRIBUTION = Path("data/reports/source_contribution.csv")
STORE = Path("data/ark.duckdb")


def per_source() -> dict:
    """Per-source figures as of the last `ark export`, keyed by source name."""
    import csv

    with CONTRIBUTION.open(encoding="utf-8") as fh:
        return {r["source"]: r for r in csv.DictReader(fh)}


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


def rewrite_report_prose(text: str, s: dict, src: dict) -> str:
    """The figures scattered through the report's prose and tables.

    These are the ones that bit: hand-maintained numbers a reader cannot check
    and a reviewer recomputing the store can. Every one is anchored on wording
    that does not change, so only the number moves.
    """
    cdx = src.get("ia_cdx_bulk", {})
    rdap_snap = src.get("rdap_snapshot", {})

    def num(row: dict, key: str) -> str:
        return f"{int(row.get(key, 0)):,}" if row else "0"

    text = re.sub(
        r"(\| IA CDX verification engine \(`ia_cdx_bulk`\) \| `cdx_timestamp` \| [^|]*\| )"
        r"\+[\d,]+( \| )\+[\d,]+ and rising",
        lambda m: (
            f"{m.group(1)}+{num(cdx, 'netnew_domains')}{m.group(2)}"
            f"+{num(cdx, 'netnew_pairs')} and rising"
        ),
        text,
        count=1,
    )
    text = re.sub(
        r"(- \*\*Net-new domains vs net-new pairs\.\*\*[^\n]*?)[\d,]+( domains are entirely "
        r"absent from the baseline; )[\d,]+( pairs)",
        lambda m: (
            f"{m.group(1)}{s['netnew_domains']:,}{m.group(2)}"
            f"{s['netnew_pairs_total']:,}{m.group(3)}"
        ),
        text,
        count=1,
    )
    by_type = " · ".join(
        f"`{kind}` {count:,}" for kind, count in s["evidence_rows_by_type"].items()
    )
    text = re.sub(
        r"- \*\*Evidence rows by type:\*\* [^\n]+",
        f"- **Evidence rows by type:** {by_type}.",
        text,
        count=1,
    )
    text = re.sub(
        r"(the `rdap_snapshot` source carries \*\*)[\d,]+( evidence rows backing )[\d,]+"
        r"( pairs\*\* from )\w+( hashed journal files)",
        lambda m: (
            f"{m.group(1)}{num(rdap_snap, 'evidence_rows')}{m.group(2)}"
            f"{num(rdap_snap, 'netnew_pairs')}{m.group(3)}"
            f"{rdap_snap.get('files_ingested', '0')}{m.group(4)}"
        ),
        text,
        count=1,
    )
    return text


ARCHIVE_TOTAL = (
    r"(For the archive as delivered that total is \*\*)[\d,]+"
    r"( pairs over )[\d,]+( domains\*\*)"
)


def rewrite_readme(text: str, s: dict) -> str:
    def swap(m: re.Match) -> str:
        return (
            f"{m.group(1)}{s['netnew_pairs_total']:,}"
            f"{m.group(2)}{s['netnew_domains']:,}{m.group(3)}"
        )

    return re.sub(ARCHIVE_TOTAL, swap, text, count=1)


def rewrite_sources_doc(text: str, src: dict) -> str:
    cdx = src.get("ia_cdx_bulk", {})
    expansion = src.get("page_expansion", {})
    if cdx:
        text = re.sub(
            r"(\*\*Yield so far\.\*\* Still accumulating: \*\*)[\d,]+( evidence rows, )[\d,]+"
            r"( net-new pairs\*\* over ~)[\d,]+",
            lambda m: (
                f"{m.group(1)}{int(cdx['evidence_rows']):,}{m.group(2)}"
                f"{int(cdx['netnew_pairs']):,}{m.group(3)}{int(cdx['domains_touched']):,}"
            ),
            text,
            count=1,
        )
    if expansion:
        text = re.sub(
            r"attests\. [\d,]+ evidence rows and, by design",
            f"attests. {int(expansion['evidence_rows']):,} evidence rows and, by design",
            text,
            count=1,
        )
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write the files.")
    args = parser.parse_args()

    f = figures()
    src = per_source() if CONTRIBUTION.exists() else {}
    targets = [
        (REPORT, rewrite_report),
        (REPORT, lambda text, s: rewrite_report_prose(text, s, src)),
        (ARCHIVE_README, rewrite_archive_readme),
        (README, rewrite_readme),
        (SOURCES_DOC, lambda text, _s: rewrite_sources_doc(text, src)),
    ]
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
