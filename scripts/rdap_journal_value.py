"""What is an RDAP journal actually worth, net of what the store already holds?

RDAP returns the registry's own creation date, which is `whois_creation`:
master-eligible, self-dating, no corroboration split. So a domain created in 1999
becomes a 1999 pair the moment it is banked, with no archive query at all.

**Why this script exists rather than a one-liner.** Two figures differ by 7x and
quoting the wrong one is the error this project keeps catching. The GROSS figure is
how many answers carry an in-window creation date; the NET figure is how many of
those the store does not already hold. Measured on the first sample: 31.65% gross
and 14.0% of those net, so 196.8 EE per thousand queries gross against 28.1 net.

Read-only against the store, with the usual retry around the single writer.

    uv run python scripts/rdap_journal_value.py data/raw/rdap/rdap_*.jsonl.gz
"""

import gzip
import json
import sys
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

import duckdb

sys.path.insert(0, "src")
from ark.english_share import weight_of  # noqa: E402


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]]
    if not paths:
        sys.exit("usage: rdap_journal_value.py <journal> [...]")

    queried = 0
    answered = 0
    pairs: set[tuple[str, int]] = set()
    for path in paths:
        try:
            with gzip.open(path, "rt") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    queried += 1
                    if rec.get("status") != 200:
                        continue
                    answered += 1
                    year = rec.get("creation_year")
                    dom = rec.get("domain")
                    if year and dom and 1996 <= int(year) <= 2001:
                        pairs.add((dom, int(year)))
        except EOFError:
            # A live `.part` has no end-of-stream marker; everything read is valid.
            pass

    print(f"{len(paths)} journal(s): {queried:,} queried, {answered:,} answered 200")
    share = 100 * len(pairs) / max(queried, 1)
    print(f"  in-window creation pairs: {len(pairs):,}  ({share:.2f}%)")
    if not pairs:
        return

    for _ in range(120):
        try:
            con = duckdb.connect("data/ark.duckdb", read_only=True)
            break
        except Exception:
            time.sleep(20)
    else:
        sys.exit("store stayed locked")

    con.execute("create temp table probe(domain varchar, y integer)")
    con.executemany("insert into probe values (?, ?)", sorted(pairs))
    new = con.execute(
        """
        select p.domain, p.y from probe p
        where not exists (
            select 1 from domain_year d where d.domain = p.domain and d.assigned_year = p.y
        )
        """
    ).fetchall()

    ee = sum((weight_of(d) for d, _ in new), Decimal(0))
    print(f"  NET-NEW pairs : {len(new):,}  ({100 * len(new) / len(pairs):.1f}% of in-window)")
    print(f"  NET-NEW EE    : {ee:,.1f}")
    if queried:
        print(f"  net EE per 1,000 queries: {ee / Decimal(queried) * 1000:,.1f}")
    print(f"  TLDs: {Counter(d.rsplit('.', 1)[-1] for d, _ in new).most_common(6)}")
    print(f"  years: {sorted(Counter(y for _, y in new).items())}")


if __name__ == "__main__":
    main()
