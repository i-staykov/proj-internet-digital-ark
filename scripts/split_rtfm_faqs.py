"""Read the rtfm.mit.edu Usenet FAQ mirror and split it by corroboration.

A FAQ carries its own revision date and lists dozens of sites, which is the
property that made Usenet work: the date is intrinsic to the artifact rather than
recovered from a crawl. Unlike the UUCP maps in `ark.uucp`, though, the URLs here
are prose typed by a human, so this takes the ordinary corroboration split rather
than being treated as registry evidence.

**The date basis is the whole difficulty, and the obvious choice is wrong.** rtfm
keeps exactly one copy of each FAQ, the last one the auto-reposter sent, so the
`Date:` header is the date of a repost and not of the content. Measured over the
mirror: of 12,318 documents carrying both a `Date:` and a revision header, 6,610
disagree, and the disagreement is one-directional, 3,296 cases where the repost is
later against 4 where it is earlier. The SSL-Talk FAQ is the clean example,
`Date: 17 Apr 2004` against `Last-modified: Nov 16 1998`. Using `Date:` would have
stamped 1998 content as 2004.

So the year comes from `Last-modified:`, `X-Last-Updated:` or `Version:`, and
`Date:` is used only where no revision header exists. That fallback errs late
rather than early, which is the safe direction for an existence claim.

    uv run python scripts/split_rtfm_faqs.py --write
"""

import argparse
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import duckdb  # noqa: E402
from probe_texts_corpus import domains_in  # noqa: E402

from ark.journal import journal_writer, write_journal_line  # noqa: E402

STORE = ROOT / "data/ark.duckdb"
DEFAULT_ROOT = ROOT / "data/raw/rtfm/rtfm.mit.edu/pub/usenet-by-group"
OUT_DIR = ROOT / "data/raw/rtfm"
YEARS = range(1996, 2002)

_REVISION = re.compile(
    r"^(?:Last-modified|Last-Modified|X-Last-Updated|Last Modified|Version)\s*:\s*(.+)$",
    re.M,
)
_DATE = re.compile(r"^Date\s*:\s*(.+)$", re.M)
_YEAR = re.compile(r"\b(19[89]\d|20[0-2]\d)\b")


def year_in(value: str) -> int | None:
    match = _YEAR.search(value)
    return int(match.group(1)) if match else None


def content_year(text: str) -> tuple[int | None, bool]:
    """(year, whether it came from a revision header rather than the repost date)."""
    head = text[:6000]
    for value in _REVISION.findall(head):
        year = year_in(value)
        if year:
            return year, True
    for value in _DATE.findall(head):
        year = year_in(value)
        if year:
            return year, False
    return None, False


def open_store(attempts: int = 60, pause: float = 15.0) -> duckdb.DuckDBPyConnection:
    for attempt in range(attempts):
        try:
            return duckdb.connect(str(STORE), read_only=True)
        except duckdb.IOException:
            if attempt == attempts - 1:
                raise
            time.sleep(pause)
    raise AssertionError("unreachable")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    if not args.root.is_dir():
        raise SystemExit(f"corpus not found at {args.root}")

    stats: Counter = Counter()
    seen: dict[tuple[str, int], str] = {}
    for path in sorted(p for p in args.root.rglob("*") if p.is_file()):
        try:
            text = path.read_text(errors="replace")
        except OSError:
            stats["unreadable"] += 1
            continue
        stats["documents"] += 1
        year, from_revision = content_year(text)
        if year is None:
            stats["undated"] += 1
            continue
        stats["revision_header" if from_revision else "repost_date_fallback"] += 1
        if year not in YEARS:
            stats["out_of_window"] += 1
            continue
        stats["in_window"] += 1
        for domain in domains_in(text):
            seen.setdefault((domain, year), str(path.relative_to(args.root)))

    conn = open_store()
    try:
        attested = {
            r[0] for r in conn.execute("SELECT DISTINCT domain FROM domain_year").fetchall()
        }
        held = {
            (r[0], r[1])
            for r in conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall()
        }
    finally:
        conn.close()

    dated, candidates = [], []
    fresh = 0
    for (domain, year), origin in sorted(seen.items()):
        record = {
            "domain": domain,
            "year": year,
            "message_id": origin,
            "group": "rtfm-faq",
            "url": "https://archive.org/details/ftp_rtfm.mit.edu_2014.07",
        }
        if domain in attested:
            dated.append(record)
            fresh += (domain, year) not in held
        else:
            candidates.append(record)

    print("documents:", dict(stats))
    print(f"in-window (domain, year) rows: {len(seen):,}")
    print(f"  corroborated elsewhere -> dated_directory : {len(dated):,}")
    print(f"    of those, not yet held                  : {fresh:,}")
    print(f"  seen only here -> candidate pool          : {len(candidates):,}")
    if not args.write:
        print("\ndry run; pass --write to create both journals")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, batch in (("rtfm_dated", dated), ("rtfm_candidates", candidates)):
        path = OUT_DIR / f"{name}.jsonl.gz"
        with journal_writer(path) as fh:
            for record in batch:
                write_journal_line(fh, record)
        print(f"wrote {path} ({len(batch):,} records)")


if __name__ == "__main__":
    main()
