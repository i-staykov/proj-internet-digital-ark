"""How much is the reviewer's whole `deduplicated_urls` set worth, across all files?

One file was measured: 2003-2004 holds 349,775 domains the store has never seen,
179,038 EE upper bound, and a sampled **11.7% in-window hit rate**, so about
20,968 EE. The set has thirteen files and 70,061,582 lines.

This sizes the rest without re-querying the archive for each: it measures the
novel-domain count and its equivalent-English per file, then applies a per-era hit
rate. **The rate is the uncertain part and it is applied per era rather than
globally**, because a domain first crawled in 2013 is far less likely to have a
1999 capture than one first crawled in 2003, and using one rate for both is the
kind of averaging that produced this project's worst estimates.

Read-only against the store. Writes the merged novel-domain list, which is the
artifact worth having whatever the estimate says.

    uv run python scripts/dedup_pool_size.py --dir <merged260821 dir>
"""

import argparse
import sys
import time
from decimal import Decimal
from pathlib import Path

import duckdb

sys.path.insert(0, "src")
from ark.canonical import to_registrable  # noqa: E402
from ark.english_share import weight_of  # noqa: E402

# Measured on 2003-2004: 13 hits in 111 decided answers. The later eras are given
# progressively lower rates because a domain first seen in a 2013 crawl is much
# less likely to have existed in 1996-2001. These are ASSUMPTIONS for the later
# files, stated as such, and the only measured one is 2003-2004.
ERA_RATE = {
    "2001-2002": 0.30,
    "2002-2003": 0.20,
    "2003-2004": 0.117,
    "2004-2005": 0.09,
    "2005-2006": 0.07,
    "2006-2007": 0.06,
    "2007-2008": 0.05,
    "2008-2009": 0.04,
    "2009-2010": 0.035,
    "2010-2011": 0.03,
    "2011-2012": 0.025,
    "2012-2013": 0.02,
    "2013-2014": 0.02,
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", default="data/raw/dedup_pool/novel.txt")
    ap.add_argument("--read", type=int, default=0, help="lines per file, 0 = all")
    args = ap.parse_args()

    for _ in range(120):
        try:
            con = duckdb.connect("data/ark.duckdb", read_only=True)
            break
        except Exception:
            time.sleep(20)
    else:
        sys.exit("store stayed locked")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    seen_novel: set[str] = set()
    total_est = Decimal(0)

    print(f"{'file':<26}{'domains':>11}{'novel':>11}{'EE bound':>12}{'rate':>7}{'estimate':>11}")
    for era in ERA_RATE:
        path = Path(args.dir) / f"deduplicated_urls_{era}.txt"
        if not path.exists():
            continue
        domains: set[str] = set()
        with path.open(encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if args.read and i >= args.read:
                    break
                dom = to_registrable(line.strip())
                if dom:
                    domains.add(dom)
        if not domains:
            continue

        con.execute("drop table if exists probe")
        con.execute("create temp table probe(domain varchar)")
        con.executemany("insert into probe values (?)", [(d,) for d in sorted(domains)])
        novel = [
            r[0]
            for r in con.execute(
                """
                select p.domain from probe p
                where not exists (select 1 from domain d where d.domain = p.domain)
                """
            ).fetchall()
        ]
        ee = sum((weight_of(d) for d in novel), Decimal(0))
        rate = Decimal(str(ERA_RATE[era]))
        est = ee * rate
        total_est += est
        seen_novel.update(novel)
        print(
            f"{era:<26}{len(domains):>11,}{len(novel):>11,}{ee:>12,.0f}"
            f"{ERA_RATE[era]:>7.3f}{est:>11,.0f}"
        )

    out.write_text("\n".join(sorted(seen_novel)) + "\n", encoding="utf-8")
    print(f"\n  distinct novel domains across all files: {len(seen_novel):,}")
    print(f"  ESTIMATED equivalent-English: {total_est:,.0f}")
    print("  Only the 2003-2004 rate is measured (11.7%); the rest are assumptions,")
    print("  and the later files carry most of the count with the least confidence.")
    print(f"  wrote {out}")


if __name__ == "__main__":
    main()
