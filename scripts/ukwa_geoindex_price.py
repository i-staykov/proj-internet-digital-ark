"""Price a geoindex slice: how many of its in-window (domain, year) pairs are net-new?

Read-only against the store, with a retry loop because `maintain.sh` holds the
single writer lock for minutes at a time and a measurement that dies on the lock
looks exactly like a measurement that found nothing.

A row is `<14-digit timestamp>/<url><TAB><postcode>`. The year is the timestamp's
first four digits, which is `cdx_timestamp` semantics: the capture evidences that
year and no other.
"""

import gzip
import sys
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

import duckdb

sys.path.insert(0, "src")
from ark.canonical import to_registrable  # noqa: E402
from ark.english_share import weight_of  # noqa: E402

paths = [Path(p) for p in sys.argv[1:]]
if not paths:
    sys.exit("usage: ukwa_geoindex_price.py <inwindow.tsv.gz> [...]")
pairs = set()
rows = bad = 0

for path in paths:
    before = len(pairs)
    with gzip.open(path, "rt", errors="replace") as fh:
        for line in fh:
            rows += 1
            stamp, _, rest = line.partition("/")
            if len(stamp) != 14 or not stamp.isdigit():
                bad += 1
                continue
            url = rest.split("\t", 1)[0]
            # `to_registrable` is the single funnel every hostname in this project
            # passes through, and it takes a URL or a host, so nothing is parsed by
            # hand here.
            dom = to_registrable(url)
            if not dom:
                bad += 1
                continue
            year = int(stamp[:4])
            if 1996 <= year <= 2001:
                pairs.add((dom, year))
    print(f"  {path.name}: +{len(pairs) - before:,} distinct pairs")

print(f"\n{len(paths)} file(s): {rows:,} rows, {bad:,} unusable")
print(f"  distinct in-window (domain, year) pairs: {len(pairs):,}")
print(f"  distinct domains:                       {len({d for d, _ in pairs}):,}")

for _ in range(60):
    try:
        con = duckdb.connect("data/ark.duckdb", read_only=True)
        break
    except Exception:
        time.sleep(20)
else:
    sys.exit("could not open the store read-only")

con.execute("create temp table probe(domain varchar, y integer)")
con.executemany("insert into probe values (?, ?)", sorted(pairs))

held = con.execute(
    """
    select count(*) from probe p
    where exists (
        select 1 from domain_year d
        where d.domain = p.domain and d.assigned_year = p.y
    )
    """
).fetchone()[0]
new_domains = con.execute(
    """
    select count(distinct p.domain) from probe p
    where not exists (select 1 from domain d where d.domain = p.domain)
    """
).fetchone()[0]

netnew = len(pairs) - held
share = 100 * netnew / max(len(pairs), 1)
print(f"  already held:                           {held:,}")
print(f"  NET-NEW pairs:                          {netnew:,}  ({share:.1f}%)")
print(f"  of which domains the store has never seen: {new_domains:,}")

newpairs = con.execute(
    """
    select p.domain, p.y from probe p
    where not exists (
        select 1 from domain_year d
        where d.domain = p.domain and d.assigned_year = p.y
    )
    """
).fetchall()
ee = sum((weight_of(d) for d, _ in newpairs), Decimal(0))
print(f"  NET-NEW equivalent-English:             {ee:,.1f}")
if netnew:
    print(f"  mean weight:                            {ee / netnew:.4f}")

tld = Counter(d.rsplit(".", 1)[-1] for d, _ in newpairs)
print(f"  top TLDs among net-new: {tld.most_common(6)}")
