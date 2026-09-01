"""Apply the corroboration split to the URLMerchant for-sale inventory, before any ingest.

**What the artifact is.** URLMerchant was a domain broker whose whole inventory was
printed as static A-Z listing pages, `domains/domain_<letter>[_<n>].html`, 100 names to a
page, and Wayback captured them. `statistics.html` states the population, "Total Domain
Names Listed: 156,122", and each letter head page states its own share, "1 to 100 of 8599
Matching Domain Names".

**What dates one page, and it is a stamp the generator wrote.** Every page carries
`<META NAME="UPDATED" CONTENT="Tuesday, Jul 17 2001 1:19:41 AM">`, written by the program
that printed the table out of URLMerchant's own listings database, and the Wayback capture
fixes when the archive saw that table. The broker is asserting the name is registered and
for sale at that instant; `statistics.html` says they "routinely remove names that have
been deleted by the registrar and are freely available". So the page's own stamp dates the
page, not the capture, which is why this reads the stamp per page rather than trusting the
capture year: four pages in the snapshot were served from 2002 captures and four carry 2002
stamps, and both sets are dropped here.

**The split applies, because the names are a person's.** An owner submitted each name to
the broker by hand, so the DATE is a machine's and the NAME is a human's typing. Under the
project's rule a name another source already dates carries the page's stamp year as
`artifact_listing`; a name appearing only here parks in the candidate pool as `link_target`
and earns no year. The measured typo upper bound on the novel half is 44.8%, which is why
that half cannot be admitted on the broker's word alone.

**Rule 6: one page evidences its own year and no other.** Every in-window stamp in the
snapshot is 2001, so every dated row is 2001. The site's "Copyright (c) 1998-2001" implies
1999 and 2000 captures of the same namespace exist; those are separate artifacts with
their own stamps and are not this ingest.

`--tag` exists because the bulk ledger keys on (source name, file name) and refuses a file
whose hash changed. The page collector outlives the session, so a later pass over more
pages splits into its own tagged journals and the two ingests stay separately attributable.

Read-only against the store.

    uv run python scripts/sources/directories/split_urlmerchant.py                      # report
      only
    uv run python scripts/sources/directories/split_urlmerchant.py --tag b1 --write
"""

import argparse
import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ark.canonical import to_registrable  # noqa: E402
from ark.db import DEFAULT_DB_PATH, connect_read_only_patiently  # noqa: E402
from ark.english_share import weight_of  # noqa: E402
from ark.ingest import YEARS  # noqa: E402
from ark.journal import journal_writer, write_journal_line  # noqa: E402

SRC = ROOT / "data/raw/urlmerchant/pages"
OUT = ROOT / "data/raw/urlmerchant"

# The generator's own stamp, and the only thing that dates a page.
_STAMP = re.compile(r'<META NAME="UPDATED" CONTENT="([^"]+)"', re.IGNORECASE)
# Each listed name is the argument of the page's own popup call, `p2('example.com')`.
_LISTED = re.compile(r"p2\('([^']+)'\)")
_YEAR_IN_STAMP = re.compile(r"\b(19\d\d|20\d\d)\b")


def read_pages(paths: list[Path], stats: Counter) -> dict[str, set[str]]:
    """Canonical registrable domains per stamp year, over every listing page."""
    by_year: dict[str, set[str]] = {}
    for path in paths:
        body = path.read_text(encoding="utf-8", errors="replace")
        stamp = _STAMP.search(body)
        if stamp is None:
            stats["page_without_a_stamp"] += 1
            continue
        found = _YEAR_IN_STAMP.search(stamp.group(1))
        if found is None:
            stats["stamp_without_a_year"] += 1
            continue
        year = int(found.group(1))
        if year not in YEARS:
            stats["page_stamped_out_of_window"] += 1
            continue
        names = {name.lower() for name in _LISTED.findall(body)}
        if not names:
            stats["page_listing_nothing"] += 1
            continue
        stats["pages_read"] += 1
        stats["name_slots"] += len(names)
        bucket = by_year.setdefault(f"{year}-{stamp.group(1)}", set())
        for raw in names:
            domain = to_registrable(raw)
            if domain is None:
                stats["uncanonical_name"] += 1
                continue
            bucket.add(domain)
    return by_year


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the two lanes")
    parser.add_argument(
        "--tag",
        default="",
        help="suffix for the output names, so a later batch of pages does not overwrite "
        "a journal already in the ingest ledger",
    )
    args = parser.parse_args()

    paths = sorted(SRC.glob("_domains_*.html"))
    if not paths:
        return exit_with(f"no listing pages under {SRC}")
    stats: Counter = Counter()
    by_stamp = read_pages(paths, stats)
    print(f"{len(paths):,} listing pages on disk, {stats['pages_read']:,} in-window and stamped")
    for key, value in sorted(stats.items()):
        print(f"  {key:<28}{value:>10,}")

    # One (domain, year) per name per stamp year. Pages within a letter are disjoint,
    # so the union across pages is where the distinct count comes from.
    pairs: dict[tuple[str, int], str] = {}
    for key, names in sorted(by_stamp.items()):
        year = int(key.split("-", 1)[0])
        stamp_text = key.split("-", 1)[1]
        for domain in names:
            pairs.setdefault((domain, year), stamp_text)
    domains = {domain for domain, _ in pairs}
    print(f"\n{len(domains):,} distinct registrable domains, {len(pairs):,} (domain, year) rows")

    conn = connect_read_only_patiently(DEFAULT_DB_PATH)
    try:
        attested = {
            row[0] for row in conn.execute("SELECT DISTINCT domain FROM domain_year").fetchall()
        }
        held = {
            (row[0], row[1])
            for row in conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall()
        }
    finally:
        conn.close()

    dated, candidates = [], []
    netnew_ee = Decimal(0)
    netnew_pairs = 0
    for (domain, year), stamp_text in sorted(pairs.items()):
        row = {
            "domain": domain,
            "year": year,
            "message_id": f"urlmerchant updated {stamp_text}",
            "group": "urlmerchant",
            "url": "https://web.archive.org/web/20010901000000id_/"
            "http://www.urlmerchant.com:80/domains/",
        }
        if domain in attested:
            dated.append(row)
            if (domain, year) not in held:
                netnew_pairs += 1
                netnew_ee += weight_of(domain)
        else:
            candidates.append(row)

    corroborated = len({d for d, _ in pairs if d in attested})
    print(f"  corroborated, so datable : {corroborated:,}  ({corroborated / len(domains):.1%})")
    print(f"  novel, so candidate only : {len(domains) - corroborated:,}")
    print(f"\ndated lane rows      : {len(dated):,}")
    print(f"candidate lane rows  : {len(candidates):,}")
    print(f"net-new post-split   : {netnew_pairs:,} pairs, {netnew_ee:,.1f} EE")
    print("\nEE here is the split's own estimate; the ingest and `ark stats` decide.")

    if not args.write:
        print("\nreport only. Pass --write to emit the two lanes.")
        return 0

    suffix = f"_{args.tag}" if args.tag else ""
    OUT.mkdir(parents=True, exist_ok=True)
    for name, batch in (("urlmerchant_dated", dated), ("urlmerchant_candidates", candidates)):
        path = OUT / f"{name}{suffix}.jsonl.gz"
        with journal_writer(path) as handle:
            for row in batch:
                write_journal_line(handle, row)
        print(f"wrote {path} ({len(batch):,} rows)")
    print("\nnext:")
    for key in ("urlmerchant_dated", "urlmerchant_candidates"):
        print(f"  uv run ark ingest {key} data/raw/urlmerchant/{key}{suffix}.jsonl.gz")
    return 0


def exit_with(message: str) -> int:
    print(message)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
