"""Build an RDAP target list from the reviewer's own out-of-window URL dumps.

**Why this is the fast route, and why it is different from finding more sources.**
The binding constraint is not candidates, it is *dating* them: the archive CDX
endpoint takes about 17,500 queries a day and the store already holds 2.35 million
undated candidates. RDAP is a different service entirely, measured here at 75 to
118 queries a second with no refusals, and it returns the registry's own creation
date, which is `whois_creation`: **master-eligible, self-dating, no corroboration
split**. So the same work that takes the archive a month takes RDAP a day.

**Where the targets come from.** Every task package ships thirteen
`deduplicated_urls_YYYY-YYYY.txt` files, 70,061,582 lines, and this project has
never opened one. They are out-of-window by name, which is presumably why. But a
domain crawled in 2003-2004 may well have been registered in 1999, and only the
registry can say. Measured: 26.5% of the 2003-2004 file and 60.9% of 2009-2010 are
domains the store has never seen.

**Ordered by era then by weight**, because an earlier crawl is far more likely to
carry an in-window creation date, and a `.uk` hit is worth 7x a `.de` one.

    uv run python scripts/dedup_rdap_targets.py --dir <merged dir> --out <file>
"""

import argparse
import sys
import time
from pathlib import Path

import duckdb

sys.path.insert(0, "src")
from ark.canonical import to_registrable  # noqa: E402
from ark.english_share import weight_of  # noqa: E402

# Earliest first: a domain first crawled in 2002 is far likelier to have been
# registered inside 1996-2001 than one first crawled in 2013. `2001-2002` is
# omitted because it was measured at 100% already held, so it has nothing to give.
ERAS = (
    "2002-2003",
    "2003-2004",
    "2004-2005",
    "2005-2006",
    "2006-2007",
    "2007-2008",
    "2008-2009",
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", default="data/raw/rdap/dedup_targets.txt")
    ap.add_argument("--max", type=int, default=4_000_000)
    args = ap.parse_args()

    for _ in range(120):
        try:
            con = duckdb.connect("data/ark.duckdb", read_only=True)
            break
        except Exception:
            time.sleep(20)
    else:
        sys.exit("store stayed locked")

    ordered: list[str] = []
    seen: set[str] = set()

    for era in ERAS:
        path = Path(args.dir) / f"deduplicated_urls_{era}.txt"
        if not path.exists() or len(ordered) >= args.max:
            continue
        domains: set[str] = set()
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                dom = to_registrable(line.strip())
                if dom and dom not in seen:
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
        # Weight descending inside the era, so an interrupted run has taken the
        # valuable half rather than an alphabetical slice.
        novel.sort(key=lambda d: (-weight_of(d), d))
        for d in novel:
            if d not in seen:
                seen.add(d)
                ordered.append(d)
        print(f"{era}: {len(domains):,} domains, {len(novel):,} novel, running {len(ordered):,}")
        if len(ordered) >= args.max:
            break

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(ordered[: args.max]) + "\n", encoding="utf-8")
    print(f"\nwrote {out}: {min(len(ordered), args.max):,} RDAP targets")


if __name__ == "__main__":
    main()
