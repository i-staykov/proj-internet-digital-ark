"""Rewrite the archive total in `README.md` from the store.

The readme quotes the net-new pair and domain totals, both of which change with
every ingest, and they were hand-maintained, so they drifted: the figure was
6,462 pairs behind the store before this existed, which is the kind of error a
reader cannot detect but a reviewer recomputing the numbers can.

Scope is deliberately one number in one file. This tool once carried rewriters
for the report, the archive readme and `sources.md` as well, all anchored on
wording those documents no longer use, so it matched nothing and printed
"already current" for each: a staleness guard that reported success precisely
because it had stopped looking. A rewriter that cannot find its anchor is worse
than no rewriter, so anything not demonstrably live is not kept here.

Needs the store, which is git-ignored, so this is a maintainer tool and not part
of any reviewer path.

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

README = Path("README.md")
STORE = Path("data/ark.duckdb")

ARCHIVE_TOTAL = (
    r"(For the archive as delivered that total is \*\*)[\d,]+"
    r"( pairs over )[\d,]+( domains\*\*)"
)


def figures() -> dict:
    """Every number below comes from `collect_stats`, the same source `ark stats`
    prints, so the readme cannot disagree with the command a reviewer runs."""
    conn = duckdb.connect(str(STORE), read_only=True)
    try:
        return collect_stats(conn)
    finally:
        conn.close()


def rewrite_readme(text: str, s: dict) -> str:
    def swap(m: re.Match) -> str:
        return (
            f"{m.group(1)}{s['netnew_pairs_total']:,}"
            f"{m.group(2)}{s['netnew_domains']:,}{m.group(3)}"
        )

    text, count = re.subn(ARCHIVE_TOTAL, swap, text, count=1)
    if not count:
        # The anchor is the whole tool. Failing loudly beats printing
        # "already current" over a document this no longer reaches.
        raise SystemExit(f"{README}: anchor not found, so nothing is being kept current")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write the file.")
    args = parser.parse_args()

    f = figures()
    before = README.read_text(encoding="utf-8")
    after = rewrite_readme(before, f)
    if before == after:
        print(f"{README}: already current")
    elif args.write:
        README.write_text(after, encoding="utf-8")
        print(f"{README}: updated")
    else:
        print(f"{README}: would change")
    print(
        f"net-new {f['netnew_domains']:,} domains / {f['netnew_pairs_total']:,} pairs, "
        f"{f['evidence_rows']:,} evidence rows, {f['candidate_pool']:,} candidates"
    )


if __name__ == "__main__":
    main()
