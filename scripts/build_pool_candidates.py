"""Build the archive-query list for the candidate pool, best English yield first.

Two populations can be sent to the CDX index, and they are disjoint:

- the **gap pool**, held domains with a bracketed missing year (`ark gaps`). A hit
  adds one pair to a domain that is already in the master files.
- the **candidate pool**, this script: domains carried in the store with no year
  at all. A hit turns a candidate into a dated domain, so it adds a name the
  master files do not have yet.

Both are worth querying, and the pool is the better buy under the reviewer's
equivalent-English metric: its per-domain English weight is higher and every hit
is a new name rather than a new year on an old one. So this list exists
separately from `gap_candidates.txt` and is never merged into it.

Ordering is by the English share of the domain's TLD, taken from the reviewer's
own `q2_tld_top_langs.json` under exactly his rule: right-most label, `lang ==
'eng'`, share as a fraction, zero when the model does not know the TLD. Ordering
by it means a run that never finishes the pool has still spent its requests where
the metric pays most. Inside one share tier the order is a content hash rather
than alphabetical, because alphabetical clusters the numeric-prefix junk
("0171.com", "1-800-...") that was never archived, and a truncated run would then
badly understate the real hit rate.

Share alone is not enough, and the first version of this list proved it twice.

The model is built from CC-MAIN-2024-10, so it scores today's brand gTLDs near
100% English, and the pinned PSL accepts them as registrable. Parse noise out of
Usenet headers and mail addresses (`stopspam.aol`, `redneck.nec`, `aaaa.aaa`)
therefore sorted to the very top of a list meant to hold the best targets, and a
three-domain probe of that head came back 3 for 3 with no capture. A TLD that did
not exist in the window cannot hold an in-window capture, so era eligibility is
the first sort key.

That still left the two-letter coincidences, which era eligibility cannot catch
because they are real ccTLDs: `what.ev.er`, `bother.co.ck`, and 241 forged
`.mil` hostnames (`dumicsamvfs.mil`, `zydagy.mil`) that the model scores near
100%. The signal that separates them is in the store, not in a guess about the
names: how many dated domains the whole collection holds for that TLD. Measured,
it splits cleanly. `.uk` 187,063, `.au` 78,952, `.nz` 24,365, `.gov` 1,017,
against `.mil` 69, `.gu` 69, `.vi` 67, `.bb` 64, `.ck` 54, `.gh` 53. A TLD that
contributes fewer than a thousand dated domains to a 10.2M-pair store cannot move
the equivalent-English score either way, so where it sits in the queue does not
matter and it belongs behind every TLD that can. This does demote genuinely tiny
ccTLDs along with the junk, which is the right call for the same reason: the
question is only what to spend the next thousand requests on.

Nothing is deleted. Ineligible and thinly-attested names go to the tail, because
the week will not reach them anyway and deleting rows on a judgement the store
cannot back is worse than leaving them last.

**Then 14,686 real answers arrived and showed the whole share-first idea was only
half right.** English share says what a hit is worth. It says nothing about
whether there will be a hit, and that second factor turned out to vary far more
than the first. `.edu` scores 97.2% English and returned **5 hits in 1,709
queries**; `.gov` and `.mil` returned zero in 614. Meanwhile the store knew why
all along: a domain merely *mentioned* in Usenet text hits 37.4%, while a link
harvested from a real archived page hits **90.0%** (`ukwa_link_target`, 2,645
answered). The `.edu` and `.mil` disasters are forged header hostnames from the
same family as `dumicsamvfs.mil`, and provenance separates them where the TLD
table cannot.

So the sort key is now the thing actually being maximised: **expected
equivalent-English per query, which is P(hit) x English share.** P(hit) is
estimated from the journals at the finest grain the sample supports, per
(source, TLD) cell where that cell has at least MIN_SAMPLE answers, falling back
to the source's own rate, then to the pool-wide rate. Both factors are needed:
source alone would rank a `.mil` Usenet name highly on its 99.8% share, and the
(source, TLD) cell is what knows it has never once hit.

Domains any journal has already answered are dropped here as well as by the
engine's own resume scan. An earlier version of this note claimed the engine skips
them only after counting out `-n`, so a batch of 1,200 would query far fewer than
1,200 new names. **That was wrong**: `ark cdx` appends only unanswered domains to
its target list and stops when that list reaches `-n`, so a batch always gets a
full `-n` of fresh names and no budget is wasted. The real reasons to filter here
are that the hit rates and the ordering are then computed over what is actually
left rather than over history, and that the file stays a readable size.

Read-only. Writes the target list and nothing else.

    uv run python scripts/build_pool_candidates.py
"""

import hashlib
import json
import sys
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402

from ark.cdx import answered as cdx_answered  # noqa: E402
from ark.journal import open_journal, queried_domains  # noqa: E402

STORE = Path("data/ark.duckdb")
MODEL = Path("feedback-phase-3/equivalent_english_domain_calculator/q2_tld_top_langs.json")
JOURNAL_DIR = Path("data/raw/cdx")
OUT = Path("data/raw/cdx/pool_candidates.txt")

# TLDs that could hold a capture between 1996 and 2001. The original gTLDs, plus
# the 2000 ICANN round, which was delegated from 2001 and so can only appear at
# the very end of the window. Every ccTLD is two letters and they were delegated
# through the 1990s, so length carries them without listing 250 codes.
ERA_GTLDS = frozenset({"com", "net", "org", "edu", "gov", "mil", "int", "arpa"})
ERA_2001 = frozenset({"biz", "info", "name", "pro", "aero", "coop", "museum"})


def in_window_era(tld: str) -> bool:
    """Whether the TLD existed in time to be captured in the window."""
    return len(tld) == 2 or tld in ERA_GTLDS or tld in ERA_2001


# Below this many dated domains in the whole store, a TLD cannot move the
# equivalent-English score whatever we find in it, so its place in the queue is
# not worth an argument and it goes behind the ones that can. Kept as a tiebreak
# only: measured hit rate now does this job directly and better.
ATTESTED_MIN = 1000

# Answers needed before a measured hit rate is trusted over the coarser estimate
# above it. Low enough that most (source, TLD) cells qualify, high enough that a
# handful of unlucky timeouts cannot condemn a whole block.
MIN_SAMPLE = 25

# Domains the store holds with no in-window year, and where each came from.
# `domain_year` is the master table, so absence from it is exactly what "still
# only a candidate" means. The source is what predicts a hit.
POOL_SQL = """
SELECT d.domain, s.name
FROM domain d
JOIN source s ON s.source_id = d.discovered_source
WHERE NOT EXISTS (SELECT 1 FROM domain_year y WHERE y.domain = d.domain)
"""

# Source for named domains, which must be asked separately from the pool query
# and NOT derived from it. A domain that hit has been given a year by the ingest,
# so it is no longer in the pool at all. Reading provenance out of the pool query
# therefore sees only the misses, which silently reported the two sources at 1.5%
# and 0.9% instead of the true 90.0% and 37.4%: a hit-rate estimate over a
# population that structurally excludes hits.
_SOURCE_FOR_SQL = """
SELECT d.domain, s.name
FROM domain d
JOIN source s ON s.source_id = d.discovered_source
WHERE d.domain IN ({placeholders})
"""

# Dated domains per right-most label, which is the unit the reviewer's model and
# this ranking both key on. `domain.tld` holds the public suffix (`co.uk`), so it
# is the wrong column here and would report .uk as 28 rather than 187,063.
ATTESTED_SQL = """
SELECT split_part(domain, '.', -1) AS tld, count(DISTINCT domain) AS dated
FROM domain_year
GROUP BY tld
"""


def english_weights(path: Path) -> dict[str, Decimal]:
    """TLD -> English primary-page-language share, the reviewer's own table."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(tld).lower(): Decimal(str(share)) / Decimal("100")
        for tld, lang, share in zip(raw["tld"], raw["lang"], raw["perc_of_tld"], strict=True)
        if tld and lang == "eng"
    }


def read_only_store(path: Path, attempts: int = 20) -> duckdb.DuckDBPyConnection:
    """Open the store for reading, waiting out the maintenance loop's writer.

    DuckDB takes a single writer per file and refuses every other opener while it
    is held, read-only included. The ingest loop holds it for seconds every 15
    minutes, so a retry lands rather than fails.
    """
    for attempt in range(attempts):
        try:
            return duckdb.connect(str(path), read_only=True)
        except duckdb.IOException:
            if attempt == attempts - 1:
                raise
            time.sleep(15)
    raise AssertionError("unreachable")


def spread(domain: str) -> bytes:
    """Deterministic tiebreak inside a share tier, stable across processes."""
    return hashlib.blake2b(domain.encode(), digest_size=8).digest()


def journal_outcomes(directory: Path, pattern: str = "cdx_pool_*.jsonl*") -> dict[str, bool]:
    """Every pool domain the archive actually answered, and whether it held a capture.

    Only status 200 counts. A transport failure says nothing about whether a
    capture exists, so counting it as a miss would slander a whole source.

    The default pattern is the journals whose whole population was the pool, which
    is what this script needs. `build_query_queue.py` passes a wider one and does
    the restricting itself, because its journals mix both populations and it holds
    a manifest saying which is which. Widening the pattern without restricting
    afterwards would fold in the gap pool, which answers at 85-99% against the
    pool's 41%, and roughly double every hit rate this returns.
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
                    if record.get("status") == 200 and record.get("domain"):
                        outcomes[record["domain"]] = bool(record.get("years"))
        except (EOFError, OSError):
            continue
    return outcomes


def sources_for(
    conn: duckdb.DuckDBPyConnection, domains: list[str], chunk: int = 2000
) -> dict[str, str]:
    """Discovery source per domain, asked in chunks to keep the SQL bounded."""
    found: dict[str, str] = {}
    for start in range(0, len(domains), chunk):
        batch = domains[start : start + chunk]
        sql = _SOURCE_FOR_SQL.format(placeholders=", ".join("?" * len(batch)))
        found.update(dict(conn.execute(sql, batch).fetchall()))
    return found


def hit_rates(
    outcomes: dict[str, bool], source_of: dict[str, str]
) -> tuple[dict[tuple[str, str], Decimal], dict[str, Decimal], Decimal]:
    """P(the archive holds an in-window capture), at four grains.

    Coarsening as the sample thins: per (source, TLD), **per TLD**, per source,
    pool-wide. Both factors are needed. Source alone would rank a `.mil` Usenet name
    highly on its 99.8% English share; the (source, TLD) cell is what knows that block
    has never once hit in 220 answers.

    **The per-TLD grain was missing and its absence cost a fortnight of collector
    time.** The chain ran (source, TLD) then straight to per-source, so an *unmeasured*
    cell inherited a source's optimistic average and English share did the rest. On
    2026-08-11 a rebuilt queue led with 2,675 `.mil` names and returned zero captures in
    1,200 queries, while the journals already held the answer at the grain nobody
    consulted:

        .mil  0.000 over 1,372 answers        .com  0.898 over 2,492
        .gov  0.000 over   394               .net  0.915 over   330
        .edu  0.003 over 1,709               .uk   0.640 over 9,310
        .bb   0.004 over   262               .org  0.468 over 4,298

    The spread across TLDs is roughly 900x, far wider than across sources, which is why
    this is the grain that matters most when a cell is thin. Its absence was not a
    missing measurement, it was a measurement never read.
    """
    cells: dict[tuple[str, str], Counter] = {}
    per_tld: dict[str, Counter] = {}
    per_source: dict[str, Counter] = {}
    overall: Counter = Counter()
    for domain, hit in outcomes.items():
        source = source_of.get(domain)
        if not source:
            continue
        tld = domain.rsplit(".", 1)[-1]
        for bucket in (
            cells.setdefault((source, tld), Counter()),
            per_tld.setdefault(tld, Counter()),
            per_source.setdefault(source, Counter()),
            overall,
        ):
            bucket["n"] += 1
            bucket["hit"] += hit

    def rate(bucket: Counter) -> Decimal:
        return Decimal(bucket["hit"]) / Decimal(bucket["n"])

    return (
        {k: rate(v) for k, v in cells.items() if v["n"] >= MIN_SAMPLE},
        {k: rate(v) for k, v in per_tld.items() if v["n"] >= MIN_SAMPLE},
        {k: rate(v) for k, v in per_source.items() if v["n"] >= MIN_SAMPLE},
        rate(overall) if overall["n"] else Decimal("0.5"),
    )


def expected_hit_rate(
    source: str,
    tld: str,
    cell_rate: dict[tuple[str, str], Decimal],
    tld_rate: dict[str, Decimal],
    source_rate: dict[str, Decimal],
    pool_rate: Decimal,
) -> Decimal:
    """The rate to score one pool target with, coarsening only as far as it must.

    An exact (source, TLD) measurement wins outright. Failing that it takes the
    **lower** of the TLD and source rates, which is the conservative reading: with two
    partial views and no measurement of the pair, an unmeasured cell must not outrank a
    cell that has actually been measured well. That is the whole correction. The old
    chain skipped to the source average, so `(some_source, .mil)` inherited a
    pool-average optimism that 1,372 answered `.mil` domains had already refuted.

    Unproven is still not impossible: a TLD nothing has answered yet falls through to
    the pool rate and ranks in the middle, because the only way a namespace earns its
    first measurement is by being queried.
    """
    exact = cell_rate.get((source, tld))
    if exact is not None:
        return exact
    partial = [r for r in (tld_rate.get(tld), source_rate.get(source)) if r is not None]
    return min(partial) if partial else pool_rate


def main() -> None:
    weights = english_weights(MODEL)
    outcomes = journal_outcomes(JOURNAL_DIR)
    conn = read_only_store(STORE)
    try:
        pool_source = dict(conn.execute(POOL_SQL).fetchall())
        attested = dict(conn.execute(ATTESTED_SQL).fetchall())
        answered_source = sources_for(conn, list(outcomes))
    finally:
        conn.close()

    cell_rate, tld_rate, source_rate, pool_rate = hit_rates(outcomes, answered_source)
    answered = queried_domains(JOURNAL_DIR, "cdx", answered=cdx_answered)
    fresh = [d for d in pool_source if d not in answered]

    def expected_ee(domain: str, tld: str) -> Decimal:
        """Equivalent-English this query is worth in expectation."""
        source = pool_source[domain]
        hit = expected_hit_rate(source, tld, cell_rate, tld_rate, source_rate, pool_rate)
        return hit * weights.get(tld, Decimal("0"))

    ranked = sorted(
        (
            (
                in_window_era(tld),
                expected_ee(domain, tld),
                attested.get(tld, 0) >= ATTESTED_MIN,
                domain,
            )
            for domain, tld in ((d, d.rsplit(".", 1)[-1]) for d in fresh)
        ),
        key=lambda item: (not item[0], -item[1], not item[2], spread(item[3])),
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for _era, _ee, _attested, domain in ranked:
            fh.write(f"{domain}\n")

    head = [row for row in ranked if row[0]]
    expected_total = sum((ee for _e, ee, _a, _d in head), Decimal("0"))
    print(f"pool with no assigned year   : {len(pool_source):,}")
    print(f"already answered by a query  : {len(pool_source) - len(fresh):,}")
    print(f"written to {OUT}: {len(ranked):,}")
    print(f"  in-window TLD  : {len(head):,} (queried first)")
    print(f"  post-dates it  : {len(ranked) - len(head):,} (tail, not reached)")
    print(f"pool-wide measured hit rate  : {pool_rate:.1%}")
    print(f"expected equivalent-English if the whole head is queried: {expected_total:.0f}")
    print(f"\nmeasured hit rate per source (>= {MIN_SAMPLE} answers):")
    for src, r in sorted(source_rate.items(), key=lambda kv: -kv[1]):
        print(f"  {src:<26} {r:>6.1%}")
    print("\nfirst 3,000 of the new queue, by (source, TLD):")
    by_pair: Counter = Counter(
        (pool_source[d], d.rsplit(".", 1)[-1]) for _e, _ee, _a, d in ranked[:3000]
    )
    for (src, tld), n in by_pair.most_common(8):
        print(f"  {src:<26} .{tld:<8} {n:>6,}")
    print("\ntop of the queue by expected EE per query:")
    for _era, ee, _a, domain in ranked[:6]:
        print(f"  {domain:<42} {ee:.3f}   [{pool_source[domain]}]")
    print("\nwhat the first 10,000 queries are now expected to return:")
    first = sum((ee for _e, ee, _a, _d in ranked[:10000]), Decimal("0"))
    print(f"  {first:.0f} equivalent-English, {first / 10000:.3f} per query")


if __name__ == "__main__":
    main()
