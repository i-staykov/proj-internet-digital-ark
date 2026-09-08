"""Rank subdomain platforms by hostname density in the reviewer's own benchmark.

The reviewer's 0901 workflow: "identify high-density subdomain platforms from the
current benchmark, generate platform-query hypotheses, then run domain-wide archive
queries separately for every target year." This is that first step, measured rather
than guessed: a parent that already carries many distinct hostnames in his files is
a proven platform, and `matchType=domain` on it enumerates what the benchmark holds
only a slice of (cjb.net measured ~336,000 hostnames at 2001 in CDX against ~5,000
in the files).

Output: one parent per line, ranked by distinct sub-hostnames x TLD English weight,
ready as the sweep queue for `cdx_suffix_sweep.py` (which takes any domain, not only
a public suffix).

    uv run python scripts/engines/rank_platform_parents.py --top 60
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from ark.baseline import CURRENT_BASELINE_DIR  # noqa: E402
from ark.canonical import to_registrable  # noqa: E402
from ark.english_share import english_weights  # noqa: E402

# floats are enough for a ranking; the exact Decimal table stays in english_share
WEIGHTS = {tld: float(share) for tld, share in english_weights().items()}

# 1996-2001, the six annual files, so six is the most years one host can be worth
YEARS = 6


def weight_of(parent: str) -> float:
    return WEIGHTS.get(parent.rsplit(".", 1)[-1], 0.0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=60)
    parser.add_argument("--out", type=Path, default=REPO / "data/raw/cdx/platform_parents.txt")
    parser.add_argument(
        "--net-new",
        action="store_true",
        help="rank by the host-YEARS we do not already hold; adds parents known only to the store",
    )
    args = parser.parse_args()

    subhosts: Counter[str] = Counter()
    # **What HE already holds, per year, not just which hosts he knows.** A record is one
    # (host, year), so his six files hold host-YEARS, and a parent whose host-years he has
    # in full returns nothing net-new however many hosts it carries. Measured 2026-09-08:
    # of 44,738 hostname-year rows a sweep banked, 36,811 were already in his files and only
    # 7,927 reached the shipped additions, so ranking that subtracted our side alone was
    # optimising the wrong difference.
    reviewer_years: Counter[str] = Counter()
    seen: set[str] = set()
    parent_of: dict[str, str] = {}
    for year_file in sorted(CURRENT_BASELINE_DIR.glob("[12]*.txt")):
        with year_file.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                host = line.strip().lower()
                # a hostname record has at least three labels; two-label lines are
                # their own registrable almost always and the PSL call is the cost
                if host.count(".") < 2:
                    continue
                parent = parent_of.get(host)
                if parent is None:
                    parent = to_registrable(host) or ""
                    parent_of[host] = parent
                if not parent or parent == host:
                    continue
                reviewer_years[parent] += 1
                if host not in seen:
                    seen.add(host)
                    subhosts[parent] += 1

    # **Divide the hosts we lack by what they cost to reach** (measured 2026-09-04).
    # A sweep page costs the same whatever it returns, so a parent's value per REQUEST is its
    # distinct hosts per capture row, and that spans 42x: `privatedances.co.uk` returns 1.5
    # rows per host and pays 657 EE per 1,000 rows, while `co.uk` returns 61.5 and pays 16.
    # TLD weight is per record and says nothing about this, which is how the highest-weight
    # namespace ended up first in a queue and paid least.
    #
    # The ratio cannot be predicted for a parent nobody has swept, so it is read from
    # `rows_per_host.tsv`, derived once from the journals of parents already walked, and a
    # parent with no measurement keeps its unadjusted score rather than being guessed at.
    ratios: dict[str, float] = {}
    ratio_file = REPO / "data/raw/cdx/rows_per_host.tsv"
    if ratio_file.is_file():
        for line in ratio_file.read_text().splitlines():
            if line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) == 4:
                try:
                    ratios[parts[0]] = float(parts[3])
                except ValueError:
                    continue

    def cost_of(parent: str) -> float:
        """Capture rows per distinct host, 1.0 where unmeasured so the score is unchanged."""
        return max(ratios.get(parent, 1.0), 1.0)

    # **Rank by what we LACK, not by what exists** (Ivo's standing priority, 2026-09-04).
    # His benchmark says which parents are real platforms, which is the right question for
    # "is this worth querying at all" and the wrong one for "what will the query add": a
    # parent whose sub-hosts we already hold spends requests to return records we have. The
    # store now holds 13.7M hostname rows, so the two orderings have genuinely diverged.
    #
    # Off by default, because the subtraction needs the store and this script must keep
    # running on a clone that has none.
    held: Counter[str] = Counter()
    held_years: Counter[str] = Counter()
    parent_years: Counter[str] = Counter()
    if args.net_new:
        from ark.db import connect_read_only_patiently

        conn = connect_read_only_patiently()
        try:
            for parent, hosts, host_years in conn.execute(
                "SELECT parent_domain, count(DISTINCT hostname), count(*) "
                "FROM hostname_year GROUP BY 1"
            ).fetchall():
                held[parent] = hosts
                held_years[parent] = host_years
            # **A host record needs its PARENT held in the same year.** That is the hostname
            # wall, and it is what actually bounds a sweep: a parent held in one year of six
            # can only ever yield one year per host, whatever the archive returns for the
            # other five. Measured 2026-09-08, ranking without it sent both clients at
            # `markettrix-seo1.com`, held at 2001 alone, and 907,446 hostname-year candidates
            # became 44,738 rows, a 4.9% acceptance rate.
            for parent, years in conn.execute(
                "SELECT domain, count(DISTINCT assigned_year) FROM domain_year GROUP BY 1"
            ).fetchall():
                parent_years[parent] = years
        finally:
            conn.close()

    # **The parent universe is his benchmark UNION our own store** (measured 2026-09-07).
    # Taking it from the benchmark alone spent the queue: 742 parents walked and 530 parked
    # left the ranking to thin registrables, and the two clients earned 210 EE/hour between
    # them overnight against the 193,000 EE/client-hour this same lane paid on 2026-09-04.
    # 6,937 parents carrying 4.1M of our own hostnames had never been asked domain-wide,
    # because a parent can only be ranked if it appears in a file this script reads.
    #
    # **The unit is host-YEARS lacked, not hosts.** A record is one (host, year), so a parent
    # whose hosts we hold in one year of six has five sixths of its records outstanding, and
    # that is invisible to a count of hosts. It is the normal case rather than an edge one:
    # ISC and the other hostname corpora are single-date snapshots, so they date every host
    # they name in exactly one year, and the never-asked parents sit at 1.0 to 1.5 years per
    # host. Both populations reduce to the same expression, which is why they can share one
    # ranking: whichever source knows more hosts bounds the parent, six years each is the
    # ceiling, and what we already hold is subtracted.
    universe = set(subhosts) | set(held)

    def headroom(parent: str) -> int:
        hosts_known = max(subhosts.get(parent, 0), held.get(parent, 0))
        # Years this parent is actually held, capped at the window, because a year the
        # parent lacks cannot carry a record for any host beneath it. Falls back to the
        # window when the store was not read, so the no-store path is unchanged.
        reachable = min(parent_years.get(parent, YEARS), YEARS) if args.net_new else YEARS
        taken = held_years.get(parent, 0) + reviewer_years.get(parent, 0)
        return max(hosts_known * reachable - taken, 0)

    if args.net_new:
        scored = (
            (headroom(p) * weight_of(p) / cost_of(p), max(subhosts.get(p, 0), held.get(p, 0)), p)
            for p in universe
        )
    else:
        # no store to subtract against, so the old benchmark-only ordering stands
        scored = (
            (count * weight_of(parent) / cost_of(parent), count, parent)
            for parent, count in subhosts.items()
        )
    ranked = sorted(scored, reverse=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as out:
        for _score, _count, parent in ranked[: args.top]:
            out.write(parent + "\n")
    for score, count, parent in ranked[:15]:
        gap = f"  {headroom(parent):>9,} host-years lacked" if args.net_new else ""
        cost = ratios.get(parent)
        seen_cost = f"  {cost:>5.1f} rows/host" if cost else "  unmeasured  "
        print(f"{parent:35s} {count:>8,} sub-hosts  score {score:>12,.0f}{gap}{seen_cost}")
    print(f"{len(ranked):,} parents ranked, top {args.top} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
