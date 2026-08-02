"""Measure what a Usenet archive would add, and how much of it is trustworthy.

Read-only. Written before any Usenet ingest, because the previous source
assessed this way (NYPW) was estimated at 27,276 net-new domains and measured at
53, and the difference was entirely in what it was compared against.

Three numbers matter, and only the first is usually reported:

- **net-new domains and pairs against the store**, which is the headline;
- **how many of the net-new names are within one edit of a name already held**,
  which upper-bounds typo contamination, because a human typed these URLs;
- **the corroborated split**, since a domain some other source attests can carry
  the post date as evidence while a name appearing only here cannot.

    uv run python scripts/measure_usenet_yield.py data/raw/usenet/*.zip
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402

from ark.usenet import parse_usenet  # noqa: E402

STORE = Path("data/ark.duckdb")


def within_one_edit(name: str, held: set[str]) -> bool:
    """Whether a single edit of `name` is a domain the store already holds.

    Generates the neighbourhood of `name` rather than scanning `held`, so this
    is a few hundred set lookups per name instead of millions of comparisons.
    """
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789-."
    for i in range(len(name)):
        if name[:i] + name[i + 1 :] in held:
            return True
        for ch in alphabet:
            if ch != name[i] and name[:i] + ch + name[i + 1 :] in held:
                return True
    for i in range(len(name) + 1):
        for ch in alphabet:
            if name[:i] + ch + name[i:] in held:
                return True
    return False


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]]
    if not paths:
        raise SystemExit("usage: measure_usenet_yield.py <archive> [...]")

    stats: Counter = Counter()
    pairs: set[tuple[str, int]] = set()
    for path in paths:
        before = stats["records"]
        for record in parse_usenet(path, stats):
            pairs.add((record.raw, record.year))
        print(f"{path.name}: {stats['records'] - before:,} records")
    print(f"parse stats: {dict(stats)}")
    print()

    conn = duckdb.connect(str(STORE), read_only=True)
    try:
        held_pairs = {
            (d, y)
            for d, y in conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall()
        }
        known_domains = {r[0] for r in conn.execute("SELECT domain FROM domain").fetchall()}
    finally:
        conn.close()
    held_domains = {d for d, _ in held_pairs}

    domains = {d for d, _ in pairs}
    new_pairs = pairs - held_pairs
    new_domains = domains - held_domains
    print(f"extracted {len(pairs):,} pairs over {len(domains):,} domains")
    print(f"net-new pairs  : {len(new_pairs):,}")
    print(f"net-new domains: {len(new_domains):,}")
    print()

    by_year: dict[int, int] = defaultdict(int)
    for _, year in new_pairs:
        by_year[year] += 1
    print("net-new pairs by year:")
    for year in sorted(by_year):
        print(f"  {year}  {by_year[year]:>8,}")
    print()

    # The corroboration split: what could carry the post date as evidence, and
    # what has to earn its year in the candidate pool first.
    corroborated_pairs = {(d, y) for d, y in new_pairs if d in known_domains}
    print(f"net-new pairs on domains some other source attests: {len(corroborated_pairs):,}")
    print(
        f"net-new pairs on names appearing only here        : "
        f"{len(new_pairs) - len(corroborated_pairs):,}"
    )
    print()

    sample = sorted(new_domains)[:4000]
    near = sum(1 for d in sample if within_one_edit(d, known_domains))
    if sample:
        print(
            f"typo upper bound: {near:,} of {len(sample):,} sampled net-new names "
            f"({near / len(sample) * 100:.1f}%) are within one edit of a name already held"
        )


if __name__ == "__main__":
    main()
