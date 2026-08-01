"""Measure how often pairs with no known capture actually have one.

The language engine orders its work list by whether the store already holds
`cdx_timestamp` evidence for the exact (domain, year). That ordering is a
priority decision and nothing more: a pair without such evidence has never been
asked, so its absence says only that we have not looked.

The question this settles is a budget question. 1996 and 1997 hold 25,647 of the
96,522 additions and 21 capture-backed pairs between them, so under a strict
capture-backed ordering they will stay at zero English verdicts no matter how
long the engine runs. Those are also the two years closest to the completeness
threshold, so writing them off without measuring would be the expensive kind of
guess.

There is reason to think the population changed. An earlier 74-pair sample of
1996 returned zero captures, but those domains were known only from registry
creation dates. The Usenet-discovered ones were announced on a public forum in
that year, which is evidence that a live website existed to be crawled.

One unfiltered index request per pair, which is the cheapest question the CDX
API answers, and no page fetches at all.

    uv run python scripts/measure_capture_rate.py --years 1996 1997 -n 200
"""

import argparse
import random
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ark.cdx import RateGovernor, http_fetch  # noqa: E402
from ark.language import any_capture_url  # noqa: E402

DB = Path("data/ark.duckdb")

SAMPLE_SQL = """
    SELECT dy.domain, dy.assigned_year
    FROM domain_year dy
    WHERE dy.assigned_year IN ({years})
      AND NOT EXISTS (
        SELECT 1 FROM evidence p
        WHERE p.domain = dy.domain AND p.evidence_year = dy.assigned_year
          AND p.evidence_type = 'prior_reused'
      )
      AND NOT EXISTS (
        SELECT 1 FROM evidence c
        WHERE c.domain = dy.domain AND c.evidence_year = dy.assigned_year
          AND c.evidence_type = 'cdx_timestamp'
      )
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=int, nargs="+", default=[1996, 1997])
    parser.add_argument("-n", type=int, default=200, help="pairs to sample per year")
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=20260801, help="fixed, so this is repeatable")
    args = parser.parse_args()

    conn = duckdb.connect(str(DB), read_only=True)
    years = ", ".join(str(y) for y in args.years)
    rows = conn.execute(SAMPLE_SQL.format(years=years)).fetchall()
    # Closed before the network work starts. A read connection held open for the
    # duration blocks the writer, and this run takes tens of minutes while the
    # maintenance loop needs the store every fifteen.
    conn.close()
    print(f"population: {len(rows)} pairs with no known capture in {args.years}", flush=True)

    rng = random.Random(args.seed)
    by_year: dict[int, list[str]] = {}
    for domain, year in rows:
        by_year.setdefault(year, []).append(domain)

    governor = RateGovernor(delay=args.delay, min_delay=args.delay)
    fetch = http_fetch(45.0)
    overall_hits = overall_asked = 0
    for year in sorted(by_year):
        pool = by_year[year]
        sample = rng.sample(pool, min(args.n, len(pool)))
        hits = asked = failed = 0
        for domain in sample:
            governor.wait()
            status, body = fetch(any_capture_url(domain, year))
            if status != 200:
                failed += 1
                governor.on_throttle()
                continue
            governor.on_success()
            asked += 1
            if body.strip():
                hits += 1
        rate = 100.0 * hits / asked if asked else 0.0
        print(
            f"{year}: sampled {len(sample)} of {len(pool)}, "
            f"answered {asked}, failed {failed}, with a capture {hits} ({rate:.1f}%)",
            flush=True,
        )
        overall_hits += hits
        overall_asked += asked

    if overall_asked:
        share = 100.0 * overall_hits / overall_asked
        print(f"TOTAL: {overall_hits}/{overall_asked} = {share:.1f}%")


if __name__ == "__main__":
    main()
