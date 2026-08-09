"""Build the RDAP query list for the candidate pool, best equivalent-English first.

`ark gaps --creation` addresses only domains that ALREADY hold a year: it looks
for a missing year next to a held one. The candidate pool is the other
population, 2,537,091 names the store carries with no year at all, and until
2026-08-08 it had never been asked. A registry creation date landing in window
gives such a name its FIRST year, which makes it a net-new domain rather than
only a net-new pair.

Four filters, all cheap:

- **A registry that answers.** Only TLDs the IANA bootstrap file maps to an RDAP
  service, since a name whose TLD has no service cannot be dated however real it
  is. That removes `.mil`, `.gov`, `.edu`, `.de`, `.us`, `.nz` and the rest of
  the no-service set, 588,000 pool names between them.
- **A TLD that existed in the window.** A creation date cannot fall in 1996-2001
  in a namespace delegated in 2014, so a query there is a certain miss, not a
  long shot. This is not a demotion like the CDX list makes, it is a deletion:
  the first build without it put `.you`, `.dot`, `.sucks`, `.box`, `.hot`,
  `.free` and `.aol` at the very head of the queue, because the reviewer's
  English-share model is built from 2024 crawl data and scores modern brand
  gTLDs near 100% English.
- **A TLD worth the query.** Zero English share means a hit scores nothing.
- **Not already answered.** A domain settled by an earlier journal is dropped
  here as well as by the engine's own resume scan, so the ordering below is
  computed over what is actually left.

Ordering is expected equivalent-English per query, P(creation date in window) x
English share of the TLD. Both factors move, and neither is optional:

- Share alone would put `.uk` (0.9813) ahead of `.com` (0.6321) everywhere, when
  `.com` is 921,583 of the pool against `.uk`'s 69,814.
- P alone would ignore that a `.de` hit is worth a fifth of a `.com` hit.

P is estimated from the RDAP journals at the finest grain the sample supports,
per TLD where that TLD has at least MIN_SAMPLE answers, falling back to the
pool-wide rate. Only journals whose population was the pool are used: the
2026-07 tranche asked domains that already hold a year, which is a different and
much better-dated population, and folding it in would inflate every rate.

Inside one expected-EE tier the order is by how many distinct sources saw the
name, most first. A name three independent collectors saw is far likelier to be
a real registration than one that appeared once in one Usenet message, and the
pool is full of the latter, including addresses munged against harvesters. The
final tiebreak is a content hash rather than alphabetical, because alphabetical
clusters the numeric-prefix junk and a truncated run would then understate the
real yield.

Read-only. Writes the target list and nothing else.

    uv run python scripts/build_rdap_pool_list.py --limit 400000
"""

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402

from ark.english_share import english_weights  # noqa: E402
from ark.journal import open_journal  # noqa: E402
from ark.rdap import JOURNAL_DIR, load_registries  # noqa: E402
from ark.rdap import answered as rdap_answered

STORE = Path("data/ark.duckdb")
OUT = Path("data/raw/rdap/pool_targets.txt")

# Answers needed before a measured per-TLD rate is trusted over the pool-wide one.
MIN_SAMPLE = 40

# Journals whose population was the candidate pool. The 2026-07 tranche asked
# `ark gaps --creation` names, which already hold a year, so its dating rate says
# nothing about this population.
POOL_JOURNAL_GLOB = "rdap_pool*.jsonl*"

# TLDs that existed in time to carry a 1996-2001 creation date: the original
# gTLDs, plus the 2000 ICANN round, delegated from 2001 and so reachable only at
# the very end of the window. Every ccTLD is two letters and they were delegated
# through the 1990s, so length carries them without listing 250 codes, minus the
# handful delegated later.
ERA_GTLDS = frozenset({"com", "net", "org", "edu", "gov", "mil", "int", "arpa"})
ERA_2001 = frozenset({"biz", "info", "name", "pro", "aero", "coop", "museum"})
POST_2001_CCTLDS = frozenset({"eu", "ax", "cw", "sx", "ss", "bl", "mf", "bq", "me", "rs", "tl"})


def in_window_era(tld: str) -> bool:
    """Whether the TLD existed in time for a creation date to fall in the window."""
    if tld in POST_2001_CCTLDS:
        return False
    return len(tld) == 2 or tld in ERA_GTLDS or tld in ERA_2001


# Pool domains and how many distinct sources saw each. `domain_year` is the
# master table, so absence from it is exactly what "still only a candidate" means.
POOL_SQL = """
SELECT d.domain, count(DISTINCT e.source_id) AS srcs
FROM domain d
JOIN evidence e ON e.domain = d.domain
WHERE NOT EXISTS (SELECT 1 FROM domain_year y WHERE y.domain = d.domain)
  AND split_part(d.domain, '.', -1) IN ({tlds})
GROUP BY d.domain
"""


def read_only_store(path: Path, attempts: int = 30) -> duckdb.DuckDBPyConnection:
    """Open the store for reading, waiting out the maintenance loop's writer.

    DuckDB takes a single writer per file and refuses every other opener while it
    is held, read-only included. The maintain loop holds it for seconds every few
    minutes, so a retry lands rather than fails.
    """
    for attempt in range(attempts):
        try:
            return duckdb.connect(str(path), read_only=True)
        except duckdb.IOException:
            if attempt == attempts - 1:
                raise
            time.sleep(10)
    raise AssertionError("unreachable")


def spread(domain: str) -> bytes:
    """Deterministic tiebreak inside a tier, stable across processes."""
    return hashlib.blake2b(domain.encode(), digest_size=8).digest()


def pool_outcomes(directory: Path, pattern: str = POOL_JOURNAL_GLOB) -> dict[str, bool]:
    """Every pool domain RDAP answered, and whether its creation year is in window.

    Only an answer counts, meaning a 200 or a 404. A 429 or a transport failure
    says nothing about whether the name is datable, and counting it as a miss
    would slander whatever TLD happened to be in flight when a registry pushed
    back.
    """
    outcomes: dict[str, bool] = {}
    for path in sorted(directory.glob(pattern)):
        try:
            with open_journal(path) as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    if not record.get("domain") or not rdap_answered(record):
                        continue
                    year = record.get("creation_year")
                    outcomes[record["domain"]] = isinstance(year, int) and 1996 <= year <= 2001
        except (EOFError, OSError):
            continue
    return outcomes


def dating_rates(outcomes: dict[str, bool]) -> tuple[dict[str, Decimal], Decimal]:
    """P(creation date lands in 1996-2001), per TLD and pool-wide."""
    per_tld: dict[str, Counter] = {}
    overall: Counter = Counter()
    for domain, hit in outcomes.items():
        for bucket in (per_tld.setdefault(domain.rsplit(".", 1)[-1], Counter()), overall):
            bucket["n"] += 1
            bucket["hit"] += hit

    def rate(bucket: Counter) -> Decimal:
        return Decimal(bucket["hit"]) / Decimal(bucket["n"])

    pool_rate = rate(overall) if overall["n"] else Decimal("0.3")
    return {t: rate(c) for t, c in per_tld.items() if c["n"] >= MIN_SAMPLE}, pool_rate


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=400_000, help="Most targets to write.")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument(
        "--tlds",
        default="",
        help="Comma-separated TLDs to restrict to. Use it once a probe has shown which "
        "registries are worth a night: expected EE alone ranks an unmeasured TLD on the "
        "pool-wide prior, and .au ranked first that way while returning 0 in-window "
        "creation dates from 3 datings, at 11 answers in 10 minutes.",
    )
    args = ap.parse_args()

    weights = english_weights()
    registries = load_registries()
    # a TLD is worth asking only if some registry answers for it, it existed in
    # the window, and a hit there scores something
    askable = sorted(t for t in registries if weights.get(t, Decimal("0")) > 0 and in_window_era(t))
    if args.tlds:
        wanted = {t.strip().lower().lstrip(".") for t in args.tlds.split(",") if t.strip()}
        askable = [t for t in askable if t in wanted]

    outcomes = pool_outcomes(JOURNAL_DIR)
    tld_rate, pool_rate = dating_rates(outcomes)

    conn = read_only_store(STORE)
    try:
        sql = POOL_SQL.format(tlds=", ".join(f"'{t}'" for t in askable))
        rows = conn.execute(sql).fetchall()
    finally:
        conn.close()

    fresh = [(d, s) for d, s in rows if d not in outcomes]

    def expected_ee(tld: str) -> Decimal:
        return tld_rate.get(tld, pool_rate) * weights.get(tld, Decimal("0"))

    ranked = sorted(
        ((expected_ee(d.rsplit(".", 1)[-1]), srcs, d) for d, srcs in fresh),
        key=lambda item: (-item[0], -item[1], spread(item[2])),
    )[: args.limit]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for _ee, _srcs, domain in ranked:
            fh.write(f"{domain}\n")

    expected_total = sum((ee for ee, _s, _d in ranked), Decimal("0"))
    print(f"registries in the IANA bootstrap : {len(registries):,}")
    print(f"askable TLDs (service + share>0) : {len(askable):,}")
    print(f"pool names in an askable TLD     : {len(rows):,}")
    print(f"already answered by an RDAP query: {len(rows) - len(fresh):,}")
    print(f"written to {args.out}: {len(ranked):,}")
    print(f"pool-wide measured in-window rate: {pool_rate:.1%} over {len(outcomes):,} answers")
    print(f"expected equivalent-English if the whole list is queried: {expected_total:,.0f}")
    print(f"  per query: {expected_total / max(len(ranked), 1):.3f}")
    print(f"\nmeasured in-window rate per TLD (>= {MIN_SAMPLE} answers):")
    for tld, r in sorted(tld_rate.items(), key=lambda kv: -kv[1]):
        print(f"  .{tld:<8} {r:>6.1%}")
    print("\nhead of the list by TLD (first 20,000):")
    for tld, n in Counter(d.rsplit(".", 1)[-1] for _e, _s, d in ranked[:20000]).most_common(8):
        print(f"  .{tld:<8} {n:>7,}")


if __name__ == "__main__":
    main()
