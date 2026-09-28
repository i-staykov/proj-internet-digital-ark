"""Measure what a Usenet archive would add, and how much of it is trustworthy.

Read-only. Written before any Usenet ingest, because the previous source
assessed this way (NYPW) was estimated at 27,276 net-new domains and measured at
53, and the difference was entirely in what it was compared against.

Three numbers matter, and only the first is usually reported:

- **net-new domains and pairs against what we date and his files hold**, which is
  the headline;
- **how many of the net-new names are within one edit of a dated name**, which
  upper-bounds typo contamination, because a human typed these URLs;
- **the corroborated split**, since a domain already dated, by a year of ours or
  by his files naming it exactly, can carry the post date as evidence while a
  name appearing only here cannot.

    uv run python scripts/sources/usenet/measure_usenet_yield.py data/raw/usenet/*.zip
"""

import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

import duckdb  # noqa: E402

from ark import held  # noqa: E402
from ark.english_share import weight_of  # noqa: E402
from ark.usenet import parse_usenet  # noqa: E402

STORE = Path("data/ark.duckdb")
ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789-."


def one_edit_variants(name: str) -> set[str]:
    """Every name one deletion, substitution or insertion away from `name`.

    Asking about this neighbourhood rather than scanning every dated name is a
    few hundred names per sample instead of millions of comparisons.
    """
    out: set[str] = set()
    for i in range(len(name)):
        out.add(name[:i] + name[i + 1 :])
        out.update(name[:i] + ch + name[i + 1 :] for ch in ALPHABET if ch != name[i])
    for i in range(len(name) + 1):
        out.update(name[:i] + ch + name[i:] for ch in ALPHABET)
    return out


def within_one_edit(name: str, known: set[str]) -> bool:
    """Whether a single edit of `name` is in `known`."""
    return not known.isdisjoint(one_edit_variants(name))


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]]
    if not paths:
        raise SystemExit("usage: measure_usenet_yield.py <archive> [...]")
    try:
        his = held.load()
    except held.HeldError as error:
        raise SystemExit(str(error)) from None

    stats: Counter = Counter()
    pairs: set[tuple[str, int]] = set()
    for path in paths:
        before = stats["records"]
        for record in parse_usenet(path, stats):
            pairs.add((record.raw, record.year))
        print(f"{path.name}: {stats['records'] - before:,} records")
    print(f"parse stats: {dict(stats)}")
    print()

    domains = {d for d, _ in pairs}
    conn = duckdb.connect(str(STORE), read_only=True)
    try:
        held_pairs = held.known_years(conn, domains, his)
        known_domains = held.attested(conn, domains, his)
        held_domains = {d for d, _ in held_pairs}
        new_pairs = pairs - held_pairs
        new_domains = domains - held_domains
        # The typo bound asks only about the one-edit neighbourhood of the sample,
        # a few million names, and never loads a whole name set.
        sample = sorted(new_domains)[:4000]
        variants = {v for d in sample for v in one_edit_variants(d)}
        dated_variants = held.attested(conn, variants, his)
    finally:
        conn.close()

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
    print(f"net-new pairs on names dated by us or his files   : {len(corroborated_pairs):,}")
    print(
        f"net-new pairs on names appearing only here        : "
        f"{len(new_pairs) - len(corroborated_pairs):,}"
    )
    print()

    # The scored metric is equivalent-English domains, so a
    # count of pairs does not say what a tranche is worth: 10,000 `.de` pairs
    # score less than 1,500 `.uk` ones. Both totals are reported because only
    # the corroborated half can enter the annual files immediately.
    total = sum((weight_of(d) for d, _ in new_pairs), Decimal(0))
    mean = total / len(new_pairs) if new_pairs else Decimal(0)
    print(f"equivalent-English of net-new pairs: {total:.4f} (mean weight {mean:.4f})")
    corroborated_ee = sum((weight_of(d) for d, _ in corroborated_pairs), Decimal(0))
    print(f"equivalent-English of the corroborated half       : {corroborated_ee:.4f}")
    print()

    near = sum(1 for d in sample if within_one_edit(d, dated_variants))
    if sample:
        print(
            f"typo upper bound: {near:,} of {len(sample):,} sampled net-new names "
            f"({near / len(sample) * 100:.1f}%) are within one edit of a dated name"
        )


if __name__ == "__main__":
    main()
