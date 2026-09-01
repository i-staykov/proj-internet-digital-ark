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

**WHETHER RANKING PAYS IS UNRESOLVED, AND THE FIRST ANSWER HERE WAS WRONG.**
An earlier version of this docstring claimed ranking loses sixtyfold on throughput.
That claim was confounded and is withdrawn. What the per-minute series in the
journals actually shows, all times UTC on 2026-08-27:

    unranked     23:24-23:40   27 69 71 69 64 65 61 65 67 67 64 67 66 67 65 62 60 q/s
    ranked       23:44-23:50    0 13  0  0  0  0  0
    interleaved  23:53-23:59    0  0  1  0  1  0  0
    shuffled     00:02-00:09   15  9  0  0  0  1  0  0

The unranked run held about 65 queries a second FLAT for seventeen minutes, with no
decay, and then every later run collapsed whatever order it used. The shuffled run
is the same population as the unranked one and collapsed too, which is what rules
the ordering explanation out: **Verisign served 64,568 queries at 65 q/s and then
clamped to near zero for at least the next twenty-five minutes, across three
restarts.** That is a quota, and the three ordering experiments all ran inside it.

What IS established, because it is a property of the population rather than of the
limiter: ranking by base-label longevity raises the share of queries answering 200
from 18.7% to 74.4%, and the in-window creation rate from 1.80% to 4.02%. Whether
that costs throughput is untested and needs a rested registry to settle.

**Ties do NOT break on TLD weight either, and that mistake is worth recording.** The first
version sorted `.org` 0.7101 before `.com` 0.6321 before `.net` 0.4530, on the
reasoning that within a bucket an answer is worth what its suffix is worth. That
made the head of the queue 100% `.org`, every one of which goes to PIR, and PIR
throttles far harder than Verisign: throughput fell from about 50 queries a second
to **0.2**, so the better per-query yield arrived as 21 equivalent-English an hour
against 1,476 before. This project's own register already says it for Nominet,
"throughput is the constraint, not density", and sorting on weight walked into it.

So within a longevity bucket the three suffixes are INTERLEAVED, `.com`, `.net`,
`.org` in rotation, which keeps Verisign work in front of every worker while `.org`
trickles at whatever PIR will serve.

The queue is replaced atomically, so the running engine reads a complete file at
its next round rather than a half-written one.

    uv run python scripts/engines/rank_sibling_queue.py --write
"""

import argparse
import hashlib
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from ark.db import DEFAULT_DB_PATH, connect_read_only_patiently  # noqa: E402

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
    ap.add_argument(
        "--shuffle",
        action="store_true",
        help="deterministic shuffle instead of ranking, which is what pays: see the docstring",
    )
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

    if args.shuffle:
        # **The measured default.** Ranking works and costs more than it earns; the
        # docstring has the numbers. A deterministic shuffle restores the 404-heavy mix
        # the registries serve fast, and is reproducible unlike an unordered file.
        names.sort(key=lambda n: hashlib.blake2b(n.encode(), digest_size=8).digest())
        spread: dict[int, int] = defaultdict(int)
        for name in names[:200_000]:
            spread[best.get(name.rpartition(".")[0], 0)] += 1
        print("\n  shuffled. base-longevity mix over the first 200,000:")
        for years in sorted(spread, reverse=True):
            print(f"  {years:>9}  {spread[years]:>10,}")
        if not args.write:
            print("\nreport only. Pass --write to replace the queue.")
            return 0
        tmp = args.queue.with_suffix(".txt.ranked")
        tmp.write_text("\n".join(names) + "\n")
        os.replace(tmp, args.queue)
        print(f"\nwrote {args.queue} shuffled, atomically")
        return 0

    # Bucket by longevity, then interleave the suffixes inside each bucket so no
    # stretch of the queue is served by a single registry.
    buckets: dict[int, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for name in names:
        label, _, tld = name.rpartition(".")
        buckets[best.get(label, 0)][tld].append(name)

    names = []
    for years in sorted(buckets, reverse=True):
        lanes = [buckets[years][t] for t in ("com", "net", "org") if buckets[years].get(t)]
        lanes += [v for k, v in buckets[years].items() if k not in ("com", "net", "org")]
        position = 0
        while any(position < len(lane) for lane in lanes):
            for lane in lanes:
                if position < len(lane):
                    names.append(lane[position])
            position += 1
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
