"""Re-rank the generated sibling RDAP queue by how long its BASE label lived.

**Measured on the engine's own answers, not assumed.** On 2026-08-27, 47,164 queries
into an unranked run, the in-window hit rate split 7.3-fold by how many of the six
years the store holds the sibling's base label:

    base label held   queried    hits   hit rate
        1 year         25,449     276      1.08%
        2 years        10,613     197      1.86%
        3 years         5,303     114      2.15%
        4 years         2,985      87      2.91%
        5 years         1,730      71      4.10%
        6 years         1,084      85      7.84%

and 54% of the queries were being spent in the worst bucket. The mechanism is
ordinary: a label the archive can see across all six years belonged to a going
concern, and a going concern of that era defensively registered the other two
gTLDs, in that era. A label seen in one year only is as likely to be a typo, a
parked name or a one-page site that never had a sibling at all.

Ties break on TLD weight, `.org` 0.7101 before `.com` 0.6321 before `.net` 0.4530,
because within a bucket the answer is worth what its suffix is worth.

The queue is replaced atomically, so the running engine reads a complete file at
its next round rather than a half-written one.

    uv run python scripts/rank_sibling_queue.py --write
"""

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ark.db import DEFAULT_DB_PATH, connect_read_only_patiently  # noqa: E402
from ark.english_share import weight_of  # noqa: E402

QUEUE = Path("data/raw/rdap/queue_siblings.txt")


def base_longevity(conn) -> dict[str, int]:
    """Label -> the most years any gTLD under it is held in window."""
    best: dict[str, int] = defaultdict(int)
    rows = conn.execute("""
        SELECT domain, count(DISTINCT assigned_year) FROM domain_year
        WHERE assigned_year BETWEEN 1996 AND 2001
          AND (domain LIKE '%.com' OR domain LIKE '%.net' OR domain LIKE '%.org')
        GROUP BY domain
    """).fetchall()
    for domain, years in rows:
        label = domain.rsplit(".", 1)[0]
        if years > best[label]:
            best[label] = years
    return best


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--queue", type=Path, default=QUEUE)
    ap.add_argument("--write", action="store_true", help="replace the queue in place")
    args = ap.parse_args()

    if not args.queue.is_file():
        print(f"no queue at {args.queue}")
        return 1
    conn = connect_read_only_patiently(DEFAULT_DB_PATH)
    try:
        best = base_longevity(conn)
    finally:
        conn.close()
    print(f"{len(best):,} base labels carry an in-window year")

    names = [n.strip() for n in args.queue.read_text().splitlines() if n.strip()]
    print(f"{len(names):,} names queued")

    def key(name: str) -> tuple[int, float]:
        label, _, tld = name.rpartition(".")
        return (-best.get(label, 0), -float(weight_of(tld)))

    names.sort(key=key)
    spread: dict[int, int] = defaultdict(int)
    for name in names:
        spread[best.get(name.rpartition(".")[0], 0)] += 1
    print("\n  base held  queued")
    for years in sorted(spread, reverse=True):
        print(f"  {years:>9}  {spread[years]:>10,}")

    if not args.write:
        print("\nreport only. Pass --write to replace the queue.")
        return 0
    tmp = args.queue.with_suffix(".txt.ranked")
    tmp.write_text("\n".join(names) + "\n")
    os.replace(tmp, args.queue)
    print(f"\nwrote {args.queue} in ranked order, atomically")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
