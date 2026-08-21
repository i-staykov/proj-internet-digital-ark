"""Which domains should RDAP actually query? Measured, because I got it backwards.

**The mistake worth recording.** The obvious optimisation was to point RDAP only at
domains the store has never seen, on the reasoning that a domain we already hold
cannot produce a net-new pair. Measured over 48,237 queries, that list returns
**100% net-new but only 1.02% in-window**, worth 6.3 equivalent-English per
thousand queries. The raw unfiltered list returns 36.4% in-window and 11.4% of
those net-new, worth **25.7 per thousand**. So the filter is **4x worse**, and the
reason is obvious in hindsight: a domain the store has never seen is precisely a
domain that did not exist in 1996-2001.

**What that implies about the right population.** The value is in domains the store
already knows are real and era-relevant, but whose *creation year* it does not
hold. A domain can be in the store with a 1999 capture and a 1997 creation date,
and that creation date is a pair we do not have. So the target list is store
domains that have never been RDAP-queried, weighted, not the novel ones.

This measures the size of that population before anything is queried.

    uv run python scripts/rdap_population.py
"""

import gzip
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

import duckdb

sys.path.insert(0, "src")
from ark.english_share import english_weights  # noqa: E402


def main() -> None:
    queried: set[str] = set()
    for path in sorted(Path("data/raw/rdap").glob("rdap*.jsonl.gz*")):
        try:
            with gzip.open(path, "rt") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    dom = rec.get("domain")
                    if dom:
                        queried.add(dom)
        except EOFError:
            pass
        except Exception:
            continue
    print(f"already RDAP-queried, from journals on disk: {len(queried):,}")

    for _ in range(120):
        try:
            con = duckdb.connect("data/ark.duckdb", read_only=True)
            break
        except Exception:
            time.sleep(20)
    else:
        sys.exit("store stayed locked")

    con.execute("create temp table done(domain varchar)")
    if queried:
        con.executemany("insert into done values (?)", [(d,) for d in queried])

    total = con.execute("select count(*) from domain").fetchone()[0]
    unqueried = con.execute(
        """
        select count(*) from domain d
        where not exists (select 1 from done q where q.domain = d.domain)
        """
    ).fetchone()[0]
    print(f"domains in store: {total:,}")
    print(f"never RDAP-queried: {unqueried:,}")

    weights = english_weights()
    print("\nunqueried by TLD, top 15 by equivalent-English if every one were dated:")
    rows = con.execute(
        """
        select regexp_extract(d.domain, '([^.]+)$') as tld, count(*) n
        from domain d
        where not exists (select 1 from done q where q.domain = d.domain)
        group by 1 order by 2 desc limit 40
        """
    ).fetchall()
    ranked = sorted(rows, key=lambda r: -(weights.get(r[0], Decimal(0)) * r[1]))
    for tld, n in ranked[:15]:
        w = weights.get(tld, Decimal(0))
        print(f"  {tld:>10}  {n:>10,}  w={w:.4f}  ceiling {w * n:>12,.0f} EE")
    ceiling = sum(weights.get(t, Decimal(0)) * n for t, n in rows)
    print(f"\n  ceiling over the top 40 TLDs: {ceiling:,.0f} EE if every one dated in window")
    print("  the realised figure is far lower: only some carry an in-window creation date.")


if __name__ == "__main__":
    main()
