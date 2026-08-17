"""Read the attrition.org web defacement mirror indexes into journals.

**Why a defacement mirror is dated evidence of existence.** attrition.org ran a
mirror from January 1999 to 21 May 2001, with pre-1999 entries copied in from
earlier mirrors. Each index row is a date, an operating system, the defacer, the
organisation name and the host that was defaced. A defaced host is a host that
was **serving on that day**, and the mirror operators saved a copy of the page at
that host on that date, so the record is contemporaneous and the hostname was
verified by the act of mirroring rather than typed from memory.

That is why this carries `artifact_listing` and takes **no corroboration split**.
It is the same claim a dated survey file or a registry dump makes: a dated
artifact enumerating hosts that were live. A name that did not resolve could not
have been mirrored, so the fabrication risk the split exists to catch is absent
here in a way it is not for a hostname typed into a Usenet post.

**The date is carried twice and the two are cross-checked.** Every row starts
`[99.11.30]`, a two-digit year, and most also link a mirror path
`1999/11/30/www.example.com/` carrying a four-digit one. 98.9% of rows carry both
and agree.

The cross-check is scoped to the claim actually being made, which is a **year**.
Fourteen rows disagree: twelve by a single day, which cannot move a record between
annual files and are kept, and **two by a whole year, which is exactly the error
that would file a domain wrongly, so those are dropped**. Dropping all fourteen
would be tidier and would throw away twelve real observations to guard against a
risk they do not carry.

**The one honest weakness, measured rather than argued.** The date is when the
mirror *recorded* the defacement, at most a day or two after the host was seen
live. That sits inside a year boundary except at New Year, where a row dated
1 or 2 January could belong to the previous December. The count of such rows is
reported at the end, which bounds the exposure instead of pretending it away.

    uv run python scripts/collect_attrition.py            # measure, write nothing
    uv run python scripts/collect_attrition.py --write    # write the journal and seeds

Input is the 33 index pages already on disk. It sends no network request.
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ark.canonical import to_registrable  # noqa: E402
from ark.ingest import YEARS  # noqa: E402
from ark.journal import journal_writer, write_journal_line  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
IN_DIR = ROOT / "data/raw/source_probe_260806/attrition"
OUT_DIR = ROOT / "data/raw/attrition"

# Only the monthly and yearly index pages. The mirror also publishes 265 per-TLD
# and per-defacer breakout pages (`com.html`, `uk.html`, ...) which re-slice the
# same rows; taking those as well would count every defacement twice.
INDEX = re.compile(r"^(19|20)\d\d(-\d\d)?\.html$")

# `[YY.MM.DD]` at the start of a data row. The mirror ran 1995-2001, so a
# two-digit year maps unambiguously into the 1900s.
ROW_DATE = re.compile(r"^\[(\d\d)\.(\d\d)\.(\d\d)\]")

# The archived copy's own path, which carries a four-digit year: the second
# witness. Anchored on four digits so a stray relative link cannot match.
MIRROR_PATH = re.compile(r'href="((?:19|20)\d\d)/(\d\d)/(\d\d)/([^"/]+)/?"')

# The defaced host, in parentheses at the end of the row, usually wrapped in a
# link. Both forms appear across the eleven years of markup.
HOST = re.compile(
    r"\(\s*<a[^>]*>\s*([A-Za-z0-9][A-Za-z0-9.\-]*\.[A-Za-z]{2,})\s*</a>\s*\)"
    r"|\(\s*([A-Za-z0-9][A-Za-z0-9.\-]*\.[A-Za-z]{2,})\s*\)"
)

MIRROR_BASE = "https://github.com/attrition-org/web-hack-mirror/blob/main/mirror"


def rows_in(path: Path, stats: Counter) -> list[tuple[str, int, int, int, str | None]]:
    """Yield (host, year, month, day, mirror_path) for every dated row in one index."""
    out = []
    for line in path.read_text(errors="replace").split("\n"):
        m = ROW_DATE.match(line)
        if not m:
            continue
        stats["rows"] += 1
        yy, mm, dd = (int(v) for v in m.groups())
        year = 1900 + yy if yy >= 90 else 2000 + yy

        host_m = HOST.search(line)
        if not host_m:
            stats["row_without_host"] += 1
            continue
        host = host_m.group(1) or host_m.group(2)

        # The second witness, preferred for the evidence URL because it names the
        # archived copy itself. Checked on the YEAR, which is the claim being
        # made: a day-level disagreement cannot move a record between annual
        # files, and a year-level one is precisely the error that would.
        path_m = MIRROR_PATH.search(line)
        mirror = None
        if path_m:
            p_year, p_mm, p_dd, p_host = path_m.groups()
            if int(p_year) != year:
                stats["dropped_year_disagreement"] += 1
                continue
            if (int(p_mm), int(p_dd)) != (mm, dd):
                stats["kept_day_disagreement"] += 1
            else:
                stats["date_confirmed_twice"] += 1
            mirror = f"{p_year}/{p_mm}/{p_dd}/{p_host}"
        else:
            stats["date_single_witness"] += 1

        if (mm, dd) in ((1, 1), (1, 2)):
            stats["dated_1_or_2_january"] += 1
        out.append((host, year, mm, dd, mirror))
    return out


def collect(in_dir: Path, out_dir: Path, write: bool) -> Counter:
    stats: Counter = Counter()
    pages = sorted(p for p in in_dir.iterdir() if INDEX.match(p.name))
    if not pages:
        raise SystemExit(f"no index pages in {in_dir}")
    stats["pages"] = len(pages)

    dated: list[dict] = []
    candidates: list[str] = []
    for page in pages:
        for host, year, mm, dd, mirror in rows_in(page, stats):
            domain = to_registrable(host)
            if not domain:
                stats["unparseable_host"] += 1
                continue
            url = f"{MIRROR_BASE}/{mirror}/" if mirror else f"{MIRROR_BASE}/{page.name}"
            record = {
                "domain": domain,
                "year": year,
                "url": url,
                "group": "attrition",
                "value": f"attrition defacement {year:04d}-{mm:02d}-{dd:02d} {host}",
            }
            if year in YEARS:
                stats["in_window"] += 1
                dated.append(record)
            else:
                # Real hosts the mirror saw serving outside 1996-2001. They earn no
                # annual row, but a name seen serving is worth dating, so they go to
                # a seed file for `ark seed` to put in the candidate pool.
                #
                # NOT a journal, and that distinction cost a wrong turn worth
                # recording: journals go through the shared parser, which requires
                # `year in YEARS` by design, so a journal of out-of-window rows is
                # rejected wholesale as malformed. The pool is entered by seed file.
                stats["out_of_window"] += 1
                candidates.append(domain)

    stats["distinct_domains_in_window"] = len({r["domain"] for r in dated})
    stats["distinct_domains_out_of_window"] = len(set(candidates))
    # Rows are observations, not pairs: one host defaced three times in a year is
    # three records and one (domain, year). Both are worth printing, because the
    # row count is what the journal holds and the pair count is what can ever
    # reach an annual file.
    stats["distinct_pairs_in_window"] = len({(r["domain"], r["year"]) for r in dated})

    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        journal = out_dir / "attrition_dated.jsonl.gz"
        with journal_writer(journal) as fh:
            for record in dated:
                write_journal_line(fh, record)
        print(f"wrote {journal} ({len(dated):,} records)")

        seeds = out_dir / "attrition_out_of_window_hosts.txt"
        seeds.write_text("".join(f"{d}\n" for d in sorted(set(candidates))))
        print(f"wrote {seeds} ({len(set(candidates)):,} domains, feed with `ark seed`)")
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in-dir", type=Path, default=IN_DIR)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--write", action="store_true", help="write the journals")
    args = ap.parse_args()

    stats = collect(args.in_dir, args.out_dir, args.write)
    for key in sorted(stats):
        print(f"  {key:<32}{stats[key]:>10,}")
    if not args.write:
        print("\nnothing written, pass --write")


if __name__ == "__main__":
    main()
