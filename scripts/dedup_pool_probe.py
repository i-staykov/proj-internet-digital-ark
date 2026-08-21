"""What is in the reviewer's own `deduplicated_urls_YYYY-YYYY.txt` files?

**Why this is worth asking.** Every task package he has ever sent ships thirteen of
these, 70,061,582 lines in total, and this project has never opened one. They are
out-of-window by name, 2001-2002 through 2013-2014, which is presumably why they
were skipped. But a domain that was live in 2001-2002 very plausibly existed in
2001, and the earliest file alone is 1,097,867 lines.

**What they can and cannot be.** They are NOT evidence: the file name is a range,
not a per-item date, and this project's whole discipline is that a per-entity date
is not a per-field date. So nothing here can date a year. What they CAN be is a
**candidate pool**: names to ask the archive about, which then earn their own year
from a capture. That is the same route `usenet_mention` takes, and it needs no new
approval because `link_target` is candidate-only by construction.

**The question this answers before any of that matters**: how many of these names
does the store already hold? If the answer is most of them, the pool is worthless.

Read-only against the store.

    uv run python scripts/dedup_pool_probe.py <file> [--limit N]
"""

import argparse
import sys
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

import duckdb

sys.path.insert(0, "src")
from ark.canonical import to_registrable  # noqa: E402
from ark.english_share import weight_of  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path")
    ap.add_argument("--limit", type=int, default=0, help="read only the first N lines")
    args = ap.parse_args()

    path = Path(args.path)
    domains: set[str] = set()
    lines = bad = 0
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            lines += 1
            if args.limit and lines > args.limit:
                break
            dom = to_registrable(line.strip())
            if dom:
                domains.add(dom)
            else:
                bad += 1

    print(f"{path.name}: {lines:,} lines, {bad:,} unusable, {len(domains):,} distinct domains")
    if not domains:
        return

    for _ in range(120):
        try:
            con = duckdb.connect("data/ark.duckdb", read_only=True)
            break
        except Exception:
            time.sleep(20)
    else:
        sys.exit("store stayed locked")

    con.execute("create temp table probe(domain varchar)")
    con.executemany("insert into probe values (?)", [(d,) for d in sorted(domains)])

    known = con.execute(
        """
        select count(*) from probe p
        where exists (select 1 from domain d where d.domain = p.domain)
        """
    ).fetchone()[0]
    dated = con.execute(
        """
        select count(*) from probe p
        where exists (select 1 from domain_year y where y.domain = p.domain)
        """
    ).fetchone()[0]
    fresh = con.execute(
        """
        select p.domain from probe p
        where not exists (select 1 from domain d where d.domain = p.domain)
        """
    ).fetchall()

    print(f"  the store has seen  : {known:,} ({100 * known / len(domains):.1f}%)")
    print(f"  already dated       : {dated:,} ({100 * dated / len(domains):.1f}%)")
    print(f"  COMPLETELY NEW      : {len(fresh):,} ({100 * len(fresh) / len(domains):.1f}%)")

    ee = sum((weight_of(d) for (d,) in fresh), Decimal(0))
    print(f"  their EE if every one earned a year, an UPPER BOUND: {ee:,.0f}")
    tld = Counter(d.rsplit(".", 1)[-1] for (d,) in fresh)
    print(f"  top TLDs among the new: {tld.most_common(10)}")


if __name__ == "__main__":
    main()
