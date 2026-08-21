"""Price a suffix-sweep journal: how many of its pairs are net-new?

Read-only with the usual retry, because the store takes one writer and
`maintain.sh` holds it for minutes.
"""

import glob
import gzip
import json
import sys
import time
from collections import Counter
from decimal import Decimal

import duckdb

sys.path.insert(0, "src")
from ark.canonical import to_registrable  # noqa: E402
from ark.english_share import weight_of  # noqa: E402

paths = sys.argv[1:] or sorted(glob.glob("data/raw/cdx_suffix/*.jsonl.gz"))
pairs: set[tuple[str, int]] = set()
rows = 0
for path in paths:
    # **A journal being written has no end-of-stream marker**, so gzip raises
    # EOFError on the last partial member. That is the normal state of the file
    # this pricer exists to read: the sweep runs for days and the question is
    # always "what has it found so far". Everything before the truncation point
    # is valid, so it is kept and the exception is where the read stops.
    try:
        with gzip.open(path, "rt", errors="replace") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                rows += 1
                stamp = d.get("timestamp") or ""
                if len(stamp) != 14 or not stamp.isdigit():
                    continue
                year = int(stamp[:4])
                if not (1996 <= year <= 2001):
                    continue
                dom = to_registrable(d.get("url") or "")
                if dom:
                    pairs.add((dom, year))
    except EOFError:
        pass

print(f"{len(paths)} journal(s): {rows:,} rows, {len(pairs):,} distinct in-window pairs")
print(f"  distinct domains: {len({d for d, _ in pairs}):,}")
if not pairs:
    sys.exit()

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
    where not exists (select 1 from domain_year d
                      where d.domain = p.domain and d.assigned_year = p.y)
    """
).fetchall()
newdom = con.execute(
    """
    select count(distinct p.domain) from probe p
    where not exists (select 1 from domain d where d.domain = p.domain)
    """
).fetchone()[0]
ee = sum((weight_of(d) for d, _ in new), Decimal(0))

print(f"  already held : {len(pairs) - len(new):,}")
print(f"  NET-NEW pairs: {len(new):,}  ({100 * len(new) / len(pairs):.1f}%)")
print(f"  of which domains never seen: {newdom:,}")
print(f"  NET-NEW EE   : {ee:,.1f}")
print(f"  top TLDs     : {Counter(d.rsplit('.', 1)[-1] for d, _ in new).most_common(5)}")
