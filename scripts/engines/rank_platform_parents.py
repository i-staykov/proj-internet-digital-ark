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


def weight_of(parent: str) -> float:
    return WEIGHTS.get(parent.rsplit(".", 1)[-1], 0.0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=60)
    parser.add_argument("--out", type=Path, default=REPO / "data/raw/cdx/platform_parents.txt")
    parser.add_argument(
        "--net-new",
        action="store_true",
        help="rank by the sub-hosts we do NOT already hold, not by all of them",
    )
    args = parser.parse_args()

    subhosts: Counter[str] = Counter()
    seen: set[str] = set()
    for year_file in sorted(CURRENT_BASELINE_DIR.glob("[12]*.txt")):
        with year_file.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                host = line.strip().lower()
                # a hostname record has at least three labels; two-label lines are
                # their own registrable almost always and the PSL call is the cost
                if host.count(".") < 2 or host in seen:
                    continue
                seen.add(host)
                parent = to_registrable(host)
                if parent and parent != host:
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
    if args.net_new:
        from ark.db import connect_read_only_patiently

        conn = connect_read_only_patiently()
        try:
            for parent, n in conn.execute(
                "SELECT parent_domain, count(DISTINCT hostname) FROM hostname_year GROUP BY 1"
            ).fetchall():
                held[parent] = n
        finally:
            conn.close()

    ranked = sorted(
        (
            (max(count - held[parent], 0) * weight_of(parent) / cost_of(parent), count, parent)
            for parent, count in subhosts.items()
        ),
        reverse=True,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as out:
        for _score, _count, parent in ranked[: args.top]:
            out.write(parent + "\n")
    for score, count, parent in ranked[:15]:
        gap = f"  {count - held[parent]:>8,} we lack" if args.net_new else ""
        cost = ratios.get(parent)
        seen_cost = f"  {cost:>5.1f} rows/host" if cost else "  unmeasured  "
        print(f"{parent:35s} {count:>8,} sub-hosts  score {score:>12,.0f}{gap}{seen_cost}")
    print(f"{len(ranked):,} parents ranked, top {args.top} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
