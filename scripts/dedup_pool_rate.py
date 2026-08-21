"""What fraction of the reviewer's out-of-window pool has an IN-WINDOW capture?

`dedup_pool_probe.py` measured the pool's size: 26.5% of the 2003-2004 file and
60.9% of 2009-2010 are domains the store has never seen, worth 179,038 and 413,283
equivalent-English **if every one earned a year**. That "if" is the whole question,
and an upper bound quoted as a finding is exactly the error this project keeps
catching.

**The honest test is a hit rate**, so this asks the archive directly for a random
sample: does the domain have a capture in 1996-2001? A domain first seen in a
2009-2010 crawl usually did not exist in 1999, and only the archive can say.

The sample is drawn with a fixed seed so the measurement is reproducible, and the
rate it returns multiplies the upper bound into an estimate worth acting on.

    uv run python scripts/dedup_pool_rate.py <file> --sample 200
"""

import argparse
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from decimal import Decimal
from pathlib import Path

import duckdb

sys.path.insert(0, "src")
from ark.canonical import to_registrable  # noqa: E402
from ark.english_share import weight_of  # noqa: E402

UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
CDX = "https://web.archive.org/cdx/search/cdx"


def in_window(domain: str, timeout: float = 30.0) -> str:
    """'hit', 'miss', or an error token. One collapsed query covers all six years."""
    url = (
        f"{CDX}?url={urllib.parse.quote(domain)}&matchType=domain&from=1996&to=2001"
        "&fl=timestamp&collapse=timestamp:4&limit=8&filter=statuscode:200"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            body = fh.read().decode("utf-8", "replace").strip()
        return "hit" if body else "miss"
    except urllib.error.HTTPError as exc:
        return f"HTTP{exc.code}"
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{type(exc).__name__}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path")
    ap.add_argument("--sample", type=int, default=200)
    ap.add_argument("--read", type=int, default=1_500_000)
    ap.add_argument("--delay", type=float, default=1.2)
    args = ap.parse_args()

    domains: set[str] = set()
    with Path(args.path).open(encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if i >= args.read:
                break
            dom = to_registrable(line.strip())
            if dom:
                domains.add(dom)

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
    fresh = [
        r[0]
        for r in con.execute(
            """
            select p.domain from probe p
            where not exists (select 1 from domain d where d.domain = p.domain)
            """
        ).fetchall()
    ]
    print(f"{Path(args.path).name}: {len(fresh):,} domains the store has never seen")
    if not fresh:
        return

    rng = random.Random(20260821)
    sample = rng.sample(fresh, min(args.sample, len(fresh)))
    counts: Counter = Counter()
    hits: list[str] = []
    for i, dom in enumerate(sample, 1):
        r = in_window(dom)
        counts[r] += 1
        if r == "hit":
            hits.append(dom)
        time.sleep(args.delay)
        if i % 50 == 0:
            print(f"  {i}/{len(sample)}: {dict(counts)}", flush=True)

    decided = counts["hit"] + counts["miss"]
    errors = sum(v for k, v in counts.items() if k not in ("hit", "miss"))
    print(f"\n  decided {decided}, errors {errors}")
    if not decided:
        print("  NO DECIDED ANSWERS: the archive refused everything, so this measured nothing")
        return
    rate = counts["hit"] / decided
    print(f"  IN-WINDOW HIT RATE: {100 * rate:.1f}%  ({counts['hit']}/{decided})")

    ee_all = sum((weight_of(d) for d in fresh), Decimal(0))
    print(f"  pool upper bound   : {ee_all:,.0f} EE")
    print(f"  ESTIMATE at that rate: {ee_all * Decimal(rate):,.0f} EE")
    print("  (an estimate, not a measurement: it is the upper bound times a sampled rate)")
    if hits:
        print(f"  sample of hits: {hits[:8]}")


if __name__ == "__main__":
    main()
