"""Measure how fast Usenet's marginal yield decays as groups are added.

The single largest uncertainty in the Usenet extrapolation is not the per-group
rate, which is measured, but the **decay**: each group added overlaps the ones
before it, so multiplying a measured per-group figure by the number of remaining
groups is wrong by whatever the saturation curve does. The 5 August probe put
that band at 50,000 to 150,000 pairs, a factor of three, and the whole width of
it was this one unmeasured quantity.

This settles it by construction. Groups are parsed in a fixed order, pairs
accumulate into one set, and after each batch the script reports how many pairs
are net-new **against the store and against every earlier batch**. The marginal
column is the decay curve, read directly rather than assumed.

Ordering matters and is therefore explicit rather than incidental: the archives
are taken in the order given on the command line, so a shell glob sorts them by
name and the run is reproducible.

    uv run python scripts/measure_usenet_decay.py --batch 4 data/raw/usenet_probe*/*.zip
"""

import argparse
import sys
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402

from ark.english_share import weight_of  # noqa: E402
from ark.usenet import parse_usenet  # noqa: E402

STORE = Path("data/ark.duckdb")


def held_pairs() -> set[tuple[str, int]]:
    """Every (domain, year) the store already assigns, read without the lock."""
    for _ in range(6):
        try:
            conn = duckdb.connect(str(STORE), read_only=True)
            break
        except duckdb.IOException:
            time.sleep(10)
    else:
        raise SystemExit("store stayed locked")
    try:
        return {
            (d, y)
            for d, y in conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall()
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--batch", type=int, default=4, help="groups per reported batch")
    args = parser.parse_args()

    held = held_pairs()
    print(f"store holds {len(held):,} assigned pairs\n")

    seen: set[tuple[str, int]] = set()
    previous_new = 0
    previous_ee = Decimal(0)
    stats: Counter = Counter()

    header = (
        f"{'groups':>7}  {'cumulative new':>15}  {'marginal':>9}  "
        f"{'marginal EE':>12}  {'per group':>9}"
    )
    print(header, flush=True)
    for index, path in enumerate(args.archives, start=1):
        for record in parse_usenet(path, stats):
            seen.add((record.raw, record.year))
        if index % args.batch and index != len(args.archives):
            continue

        new_pairs = seen - held
        marginal = len(new_pairs) - previous_new
        total_ee = sum((weight_of(d) for d, _ in new_pairs), Decimal(0))
        marginal_ee = total_ee - previous_ee
        per_group = marginal / args.batch
        # Flushed per batch, for the same reason the journal writers flush: a run
        # over 28 archives takes minutes, and a buffered log is indistinguishable
        # from a hung process for most of it.
        print(
            f"{index:>7}  {len(new_pairs):>15,}  {marginal:>9,}  "
            f"{marginal_ee:>12.1f}  {per_group:>9.0f}",
            flush=True,
        )
        previous_new, previous_ee = len(new_pairs), total_ee

    new_pairs = seen - held
    total_ee = sum((weight_of(d) for d, _ in new_pairs), Decimal(0))
    mean = total_ee / len(new_pairs) if new_pairs else Decimal(0)
    print(f"\n{len(args.archives)} groups, {len(new_pairs):,} net-new pairs")
    print(f"equivalent-English {total_ee:.4f} (mean weight {mean:.4f})")
    print(f"parse stats: {dict(stats)}")


if __name__ == "__main__":
    main()
