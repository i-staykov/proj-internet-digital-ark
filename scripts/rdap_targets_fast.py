"""Build the novel-domain RDAP target list, in DuckDB rather than in Python.

**Why this replaces the Python version.** The first attempt canonicalised 70 million
lines one at a time and had produced nothing after an hour. DuckDB reads the files,
filters and anti-joins against the store's 13 million known domains in one pass, and
that is the difference between an hour and a minute.

**Why novel-only matters so much.** Measured on a raw sample of 3,000 `.com`
queries: 36.4% carried an in-window creation date, but only 11.4% of those were new
to the store, so 25.7 net equivalent-English per thousand queries. A domain the
store has never seen cannot already hold the pair, so restricting the target list to
novel domains removes almost all of that waste.

**Why `.com` and `.net` first.** Throughput is the whole game, and it is a property
of the registry rather than of the query: a mixed-TLD list ran at 0.55 queries a
second because slow and dead registries block the queue, while the same code against
Verisign alone ran 3,000 queries in 46 seconds, **65 q/s**. `.com` is also the
largest share of the pool and carries weight 0.6321.

**This list is the FOLLOW-ON, not the first choice.** Measured, it returns 100%
net-new but only 1.02% in-window, worth **6.3 equivalent-English per thousand
queries**, against **20.2** for `rdap_store_targets.py`. A domain the store has
never seen is precisely a domain that did not exist in 1996-2001. So the store
population is worked first and this one exists to stop the channel idling when
that is exhausted: 11.4 million store domains is about twenty hours at the
measured combined rate, and this adds roughly twenty million more.

Read-only against the store.

    uv run python scripts/rdap_targets_fast.py --dir <merged dir> --out <file>
"""

import argparse
import sys
import time
from pathlib import Path

import duckdb

# Earliest crawls first: a domain first seen in 2002 is far likelier to have been
# registered inside 1996-2001 than one first seen in 2013. `2001-2002` is omitted,
# measured at 100% already held.
ERAS = (
    "2002-2003",
    "2003-2004",
    "2004-2005",
    "2005-2006",
    "2006-2007",
    "2007-2008",
    "2008-2009",
    "2009-2010",
    "2010-2011",
    "2011-2012",
    "2012-2013",
    "2013-2014",
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", default="data/raw/rdap/novel_com.txt")
    ap.add_argument("--max", type=int, default=8_000_000)
    args = ap.parse_args()

    files = [str(Path(args.dir) / f"deduplicated_urls_{e}.txt") for e in ERAS]
    files = [f for f in files if Path(f).exists()]
    if not files:
        sys.exit(f"no deduplicated_urls files under {args.dir}")

    for _ in range(120):
        try:
            con = duckdb.connect("data/ark.duckdb", read_only=True)
            break
        except Exception:
            time.sleep(20)
    else:
        sys.exit("store stayed locked")

    # `lower(trim(...))` only; no public-suffix work, because the filter below already
    # restricts to a bare `label.com` shape where the registrable domain IS the line.
    # Anything more clever here would be re-implementing `to_registrable` in SQL, and
    # a second canonical funnel is exactly what `canonical.py` exists to prevent.
    #
    # The file list is interpolated rather than bound, because DuckDB cannot prepare
    # a `create view` statement and returns "Unexpected prepared parameter". The paths
    # come from a fixed directory argument and a hardcoded era list, so there is no
    # untrusted input here; the quotes are escaped anyway.
    filelist = ", ".join("'" + f.replace("'", "''") + "'" for f in files)
    con.execute(
        f"""
        create or replace temp view raw as
        select distinct lower(trim(column0)) as d
        from read_csv([{filelist}], header=false, columns={{'column0':'VARCHAR'}},
                      quote='', escape='', ignore_errors=true)
        """
    )
    con.execute(
        """
        create or replace temp view candidates as
        select d from raw
        where regexp_matches(d, '^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]\\.(com|net)$')
        """
    )
    rows = con.execute(
        """
        select c.d from candidates c
        where not exists (select 1 from domain m where m.domain = c.d)
        limit ?
        """,
        [args.max],
    ).fetchall()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(r[0] for r in rows) + "\n", encoding="utf-8")
    print(f"{len(files)} file(s) read")
    print(f"wrote {out}: {len(rows):,} novel .com/.net domains the store has never seen")


if __name__ == "__main__":
    main()
