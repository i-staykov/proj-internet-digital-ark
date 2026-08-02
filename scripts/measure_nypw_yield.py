"""Measure what the NYPW first-capture index would actually add, before ingesting it.

Written because the first estimate of this source compared NYPW's *registrable
domains* against the baseline's *raw hostname lines*. Those are different units:
a baseline holding only `www.foo.com` would make `foo.com` look net-new when
canonicalization collapses both to the same domain. The number that matters is
measured against the store, whose contents have already been through
`to_registrable` and already include merged260730.

Read-only. Writes nothing to the store.

    uv run python scripts/measure_nypw_yield.py data/raw/nypw/*.gz
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402

from ark.canonical import to_registrable  # noqa: E402
from ark.sources import SOURCES  # noqa: E402

STORE = Path("data/ark.duckdb")


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]]
    if not paths:
        raise SystemExit("usage: measure_nypw_yield.py <file.gz> [...]")

    spec = SOURCES["nypw_firstcdx"]
    stats: Counter = Counter()
    pairs: set[tuple[str, int]] = set()
    for path in paths:
        for record in spec.parse(path, stats):
            domain = to_registrable(record.raw)
            if domain is None:
                stats["unusable_domain"] += 1
                continue
            pairs.add((domain, record.year))
    print(f"parse stats: {dict(stats)}")
    print(f"in-window (domain, year) pairs: {len(pairs):,}")
    print(f"distinct in-window domains    : {len({d for d, _ in pairs}):,}")

    conn = duckdb.connect(str(STORE), read_only=True)
    try:
        held_pairs = {
            (d, y)
            for d, y in conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall()
        }
        held_domains = {d for d, _ in held_pairs}
    finally:
        conn.close()
    print(f"store holds {len(held_pairs):,} pairs over {len(held_domains):,} domains")
    print()

    new_pairs = pairs - held_pairs
    new_domains = {d for d, _ in pairs} - held_domains
    by_year: dict[int, int] = defaultdict(int)
    new_domain_by_year: dict[int, set[str]] = defaultdict(set)
    for domain, year in new_pairs:
        by_year[year] += 1
        if domain in new_domains:
            new_domain_by_year[year].add(domain)

    print("=== NET-NEW against the current store ===")
    print(f"{'year':<8}{'new pairs':>12}{'of which on brand-new domains':>32}")
    for year in sorted(by_year):
        print(f"{year:<8}{by_year[year]:>12,}{len(new_domain_by_year[year]):>32,}")
    print(f"{'TOTAL':<8}{len(new_pairs):>12,}{len(new_domains):>32,}")
    print()
    print(f"net-new PAIRS  : {len(new_pairs):,}")
    print(f"net-new DOMAINS: {len(new_domains):,}")


if __name__ == "__main__":
    main()
