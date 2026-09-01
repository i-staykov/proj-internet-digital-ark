"""Rank the candidate pool by CORROBORATION rather than by a modelled hit rate.

**Why this exists: the modelled ranking put fabricated names first and cost an 80x
collapse.** On 2026-08-27 a rebuild of `queue_pool_local.txt` took the local CDX engine
from 1.15-1.66 years per query to 0.014. Failures FELL from 58% to 9% over the same
period and 312 of 342 requests were answered, so the archive was replying and the names
simply had no in-window capture: a property of the population, not of the rate. The
queue head explained it. 18,184 of the first 20,000 lines were `.ca`, and they were
strings like `afakeaddress.ca`, `lgffu.ca` and `doodoo.cg`. That is the same failure
`build_query_queue.py` records for `.mil` on 11 August, recurring under a different TLD
once `.ca` had enough dated rows for `pool_plausibility` to rank it while its pool
stayed fabricated.

So this does not re-tune the model. It applies a filter the model cannot express:
**how many INDEPENDENT sources name this string at all.** A fabricated name arrives
from one generator and is named once; a real name that several unrelated corpora
mention is very unlikely to be invented. Measured over the whole pool on 2026-08-27:

    named by 1 source   2,050,909   86.32%
    named by 2          307,145     12.93%
    named by 3           17,770      0.75%
    named by 4              209      0.01%
    named by 5+               3      0.00%

Keeping the multi-source slice leaves 325,127 names worth 209,036 equivalent-English if
every one gained a single year, led by `.au` at 0.9904, `.gov` at 0.9825 and `.uk` at
0.9813 rather than by a fabricated `.ca` block.

**Not a replacement for `build_query_queue.py` and not yet measured against it.** The
gap population cannot contain a fabricated name at all, since a gap target is a name
already held, so gap work needs no filter of this kind. This is for the discovery half,
and the honest status on the day it was written is: built, ranked, unmeasured, and NOT
switched into a running engine, because the engine it would have replaced was measuring
1.67 years per query at the time and a working engine is not a test bed.

    uv run python scripts/engines/build_multisrc_queue.py
    uv run python scripts/engines/build_multisrc_queue.py --min-sources 3 --out other.txt

Read-only against the store, so it is safe to run while the collectors are working.
"""

import argparse
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402

from ark.english_share import english_weights  # noqa: E402

STORE = ROOT / "data/ark.duckdb"
DEFAULT_OUT = ROOT / "data/raw/cdx/queue_pool_multisrc.txt"

POOL = """
WITH pool AS (
  SELECT e.domain, count(DISTINCT e.source_id) AS srcs
  FROM evidence e
  WHERE NOT EXISTS (SELECT 1 FROM domain_year dy WHERE dy.domain = e.domain)
  GROUP BY e.domain
)
SELECT domain, srcs FROM pool WHERE srcs >= ?
"""


def open_store(attempts: int = 40, pause: float = 8.0) -> duckdb.DuckDBPyConnection:
    """Read-only, retrying: the collectors hold the single writer for seconds at a time."""
    for _ in range(attempts):
        try:
            return duckdb.connect(str(STORE), read_only=True)
        except Exception:  # noqa: BLE001 (a lock is the expected failure, not an error)
            time.sleep(pause)
    raise SystemExit(f"{STORE} stayed locked")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--min-sources",
        type=int,
        default=2,
        help="keep pool names that at least this many distinct sources mention (default 2)",
    )
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--dry-run", action="store_true", help="report without writing")
    args = ap.parse_args()

    weights = english_weights()
    con = open_store()
    rows = con.execute(POOL, [args.min_sources]).fetchall()
    print(f"{len(rows):,} pool names named by >= {args.min_sources} sources")
    if not rows:
        return

    def weight_of(domain: str) -> Decimal:
        return weights.get(domain.rsplit(".", 1)[-1], Decimal(0))

    # weight x corroboration count, then the name itself so the order is stable across runs
    ranked = sorted(rows, key=lambda r: (-(weight_of(r[0]) * r[1]), r[0]))
    ceiling = sum(weight_of(d) for d, _ in ranked)
    print(f"{ceiling:,.0f} equivalent-English if every name gained one year")
    print(f"head: {[d for d, _ in ranked[:8]]}")
    if args.dry_run:
        print("dry run, nothing written")
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(f"{d}\n" for d, _ in ranked), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
