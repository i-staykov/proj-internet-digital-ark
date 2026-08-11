"""Build one archive-query queue from both populations, best expected value first.

Until now the two populations that can be sent to the CDX index were two separate
lists worked by two separate supervisors:

- the **gap pool**, held domains with a bracketed missing year. A hit adds a year
  to a domain the master files already carry.
- the **candidate pool**, domains the store carries with no year at all. A hit
  adds a name the master files do not have yet.

Keeping them apart forced a choice that should never have been a choice. On
7 August the MacBook was working the candidate pool at 0.476 equivalent-English
per query while gap targets worth twice that sat untouched, because they were in
the other file. Ordering within each list was careful and the allocation between
them was not, which is the more expensive of the two mistakes.

So there is now one queue. Both populations are scored on the same scale, the
only scale that matters for the allocation decision: **expected net-new
equivalent-English per archive query.**

    gap target   fill rate x English share x bracketed years it could fill
    pool target  P(hit) x English share x years a hit returns

The two factors that make these comparable are measured, not assumed, and both
are printed with the queue so a wrong one is visible rather than silent:

**Fill rate, 0.886 for a one-slot domain and 0.667 for a two-slot one.** A gap
query returns every in-window year at once, but most of them are years already
held, and it need not return the missing one at all. Measured over 6,168 answered
domains. It is not flat, and the first version of this queue assumed it was: see
`GAP_FILL_RATE` for what that cost and why the damage was contained.

**Years per hit, 1.55.** A candidate-pool hit is a domain with no year at all, so
every year it returns is net-new; measured at 1.55 years per hit over the last
eight batches. This is why realisation for the pool is 100% and the two
populations cannot be compared on hit rate alone.

**Pool plausibility, `dated / (dated + pool)` per TLD.** The third factor, and the
one whose absence cost the most. Where no hit rate has been measured for a
(source, TLD) cell the score fell back to the pool-wide rate, so a namespace whose
pool is fabricated ranked on English share alone. On 11 August that put 2,675
`.mil` names in the queue's first 3,000 and **two batches, 1,200 queries, returned
zero in-window captures**. `pool_plausibility` measures the same discriminator the
RDAP builder already reports and multiplies the pool score by it, so `.mil` drops
about 2,000x and `.com` is barely touched, with no TLD named anywhere.

Era eligibility stays a hard gate ahead of the score, for the reason
`build_pool_candidates.py` records at length: the English-share model is built
from 2024 crawl data and scores today's brand gTLDs near 100%, so parse noise out
of Usenet headers sorts to the top of a list meant to hold the best targets. A
TLD that did not exist in the window cannot hold an in-window capture.

Shares are sized by measured throughput rather than split evenly. See
`take_weighted_shard`.

    uv run python scripts/build_query_queue.py --weights 78,22
    uv run python scripts/build_query_queue.py --dry-run

Read-only against the store. Writes the shard files and a manifest.
"""

import argparse
import gzip
import json
import sys
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import duckdb  # noqa: E402
from build_pool_candidates import (  # noqa: E402
    ATTESTED_MIN,
    ATTESTED_SQL,
    POOL_SQL,
    hit_rates,
    in_window_era,
    journal_outcomes,
    sources_for,
)

from ark.cdx import answered as cdx_answered  # noqa: E402
from ark.english_share import english_weights  # noqa: E402
from ark.gaps import sandwich_gap_domains, spread, take_weighted_shard  # noqa: E402
from ark.journal import queried_domains  # noqa: E402

STORE = ROOT / "data/ark.duckdb"
JOURNAL_DIR = ROOT / "data/raw/cdx"
MANIFEST = JOURNAL_DIR / "queue_manifest.tsv.gz"
SHARD = "queue_shard{}.txt"

# Net-new pairs a gap query writes per bracketed slot it consumes, BY how many
# slots that domain offers. Below one because the years a capture returns are
# mostly years already held.
#
# The rate is not flat, and assuming it was cost this queue its first estimate.
# Measured on 7 August over 6,168 answered domains: a domain with one bracketed
# slot fills it 88.6% of the time, while a domain with two fills each of them only
# 66.7% of the time. Filling one specific missing year is a far easier thing to
# ask than filling two, and the failure is correlated at the domain rather than
# the slot: of 600 two-slot domains, 104 filled neither and 269 filled both, where
# independent slots would have predicted 34% filling both against the 45% seen. A
# domain is either well archived or it is not.
#
# The first version used a flat 0.95 taken from net-new pairs per query divided by
# the mean slots per queued domain. That denominator was the mean of the queue as
# it stood AFTER the high-slot domains had been consumed, so it was never the
# per-slot rate, and it overvalued the two-slot head by half. What saved the
# estimate is that the queue is 458,707 one-slot domains against 11,170 two-slot,
# so the error touched about 4% of it.
#
# Three or more slots is not measured; the queue holds none right now, and the
# value continues the observed decline rather than claiming to know.
GAP_FILL_RATE = {1: Decimal("0.886"), 2: Decimal("0.667")}
GAP_FILL_RATE_DEEP = Decimal("0.60")


def gap_fill_rate(slots: int) -> Decimal:
    """Share of a domain's bracketed slots a single capture query actually fills."""
    return GAP_FILL_RATE.get(slots, GAP_FILL_RATE_DEEP)


# In-window years a candidate-pool hit returns. Every one is net-new, the domain
# having held no year at all before the query.
DEFAULT_YEARS_PER_HIT = Decimal("1.55")

# How fast a pool query is against a gap query on the same machine, measured
# 7 August as 562 queries an hour against 916. A miss escalates through more
# request strategies than a hit, and the pool misses far more often.
POOL_SPEED_RATIO = 562 / 916


def read_only_store(path: Path, attempts: int = 80) -> duckdb.DuckDBPyConnection:
    """Wait out the maintenance loop's writer rather than failing the build."""
    for attempt in range(attempts):
        try:
            return duckdb.connect(str(path), read_only=True)
        except duckdb.IOException:
            if attempt == attempts - 1:
                raise
            time.sleep(15)
    raise AssertionError("unreachable")


def previous_pool_answers() -> set[str]:
    """Domains answered while they were candidate-pool targets.

    Needed because the hit rate that scores the pool must be measured over the
    pool and nothing else. A gap domain answers 85-99% of the time and a pool
    domain 41%, so letting the two mix would triple the pool's apparent value and
    push its whole tail to the head of the queue.

    Two sources, because the queue that replaces them is mixed: the old
    `cdx_pool_*` journals, whose whole population was the pool, and the manifest
    this script writes, which records the population of every domain it queues.
    """
    named = set(journal_outcomes(JOURNAL_DIR))
    if MANIFEST.is_file():
        with gzip.open(MANIFEST, "rt", encoding="utf-8") as fh:
            for line in fh:
                domain, population, _score = line.rstrip("\n").split("\t")
                if population == "pool":
                    named.add(domain)
    return named


def measured_years_per_hit(pool: set[str]) -> Decimal:
    """In-window years a pool hit returns, from the journals rather than a guess.

    Restricted to the pool population, because a gap hit returns about 3.4 years
    of which most are already held, and averaging the two would inflate what a
    pool hit is expected to be worth by more than double.
    """
    hits = years = 0
    for path in sorted(JOURNAL_DIR.glob("cdx_*.jsonl.gz")):
        try:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if record.get("domain") not in pool:
                        continue
                    found = [y for y in record.get("years") or [] if 1996 <= y <= 2001]
                    if found:
                        hits += 1
                        years += len(found)
        except (EOFError, OSError):
            continue
    return Decimal(years) / Decimal(hits) if hits else DEFAULT_YEARS_PER_HIT


def round_netnew_by_tld(conn: duckdb.DuckDBPyConnection, since: str) -> list[tuple[str, int]]:
    """Net-new pairs per TLD assigned since the round opened.

    The cast is written `CAST(? AS TIMESTAMPTZ)` rather than `TIMESTAMPTZ ?`,
    which DuckDB's parser rejects: a type name may prefix a literal but not a
    placeholder. Named and tested because the placeholder arrived when the round
    window moved into `ark.baseline`, and it silently took the whole queue
    builder with it.
    """
    return conn.execute(
        """
        SELECT split_part(y.domain, '.', -1) AS tld, count(*)
        FROM domain_year y
        WHERE y.verified_at >= CAST(? AS TIMESTAMPTZ)
          AND NOT EXISTS (
            SELECT 1 FROM evidence p
            WHERE p.domain = y.domain AND p.evidence_year = y.assigned_year
              AND p.evidence_type = 'prior_reused')
        GROUP BY 1
        """,
        [since],
    ).fetchall()


# Reverse-DNS zones are not websites and never were, so a capture query against one
# is a wasted request by construction. 57 of them reached the queue and 41 sorted into
# its first 3,000 rows, because `arpa` is an in-window gTLD and carries a high English
# share. This is a fact about the namespace rather than a judgement about the corpus,
# which is why it is enforced here and the ranking factor below is not.
_REVERSE_DNS = (".in-addr.arpa", ".ip6.arpa")


def is_reverse_dns(domain: str) -> bool:
    return domain.endswith(_REVERSE_DNS)


def pool_plausibility(pool_source: dict[str, str], attested: dict[str, int]) -> dict[str, Decimal]:
    """Per TLD, the share of its known names that carry a year: `dated / (dated + pool)`.

    **The factor that was missing, and it cost a fortnight of collector time.** Ranking
    the pool by expected equivalent-English needs a probability, and where none has been
    measured the score fell back to the pool-wide rate. That is the guess this project
    keeps paying for: `0.9825 x a fabricated name is still zero`, in the words of the
    RDAP builder, which already excluded `.gov` and `.mil` by hand for exactly this
    reason (C-2). The CDX queue never got that judgement, so on 2026-08-11 its rebuilt
    head was 2,675 `.mil` names in the first 3,000 and **two batches, 1,200 queries,
    returned zero in-window captures.** 371,465 `.gov` and `.mil` names stood in front of
    the first real domain, roughly 25 days of the engine finding nothing.

    A hand-maintained exclusion list would have fixed those two and rotted. This is the
    same discriminator measured instead: a real namespace has far fewer undated
    candidates than dated ones, so the ratio separates them cleanly and updates itself as
    the store grows. Measured 2026-08-11, `dated / (dated + pool)`:

        com 0.78   uk 0.76   org 0.48   net 0.42      real namespaces
        edu 0.029  gov 0.0055  mil 0.00038           fabricated or unreachable

    So `.mil` is pushed down roughly 2,000x and `.com` is barely touched, without naming
    either. The tiny ccTLDs that also litter the head (`.nr` at 0.18, `.mh` at 0.08) land
    in between, which is right: they are unproven rather than impossible.

    A TLD with no pool names at all returns 1, since there is nothing to rank.
    """
    pool_count: Counter[str] = Counter(domain.rsplit(".", 1)[-1] for domain in pool_source)
    out: dict[str, Decimal] = {}
    for tld, pool_n in pool_count.items():
        dated = attested.get(tld, 0)
        out[tld] = Decimal(dated) / Decimal(dated + pool_n) if dated + pool_n else Decimal(1)
    return out


def build(weights: list[int]) -> dict:
    tld_weight = english_weights()
    # Every answer on disk, not just the pool-prefixed journals, because the queue
    # this writes is mixed and its journals carry both populations. The manifest
    # is what says which is which, and `pool_answered` does the restricting.
    outcomes = journal_outcomes(JOURNAL_DIR, pattern="cdx_*.jsonl*")
    pool_answered = previous_pool_answers()
    years_per_hit = measured_years_per_hit(pool_answered)

    conn = read_only_store(STORE)
    try:
        pool_source = dict(conn.execute(POOL_SQL).fetchall())
        attested = dict(conn.execute(ATTESTED_SQL).fetchall())
        answered_source = sources_for(conn, list(outcomes))
        gap_rows = sandwich_gap_domains(conn)
    finally:
        conn.close()

    # Hit rates are estimated over pool answers only, at the finest grain the
    # sample supports: per (source, TLD), then per source, then pool-wide.
    cell_rate, source_rate, pool_rate = hit_rates(
        {d: hit for d, hit in outcomes.items() if d in pool_answered}, answered_source
    )
    already = queried_domains(JOURNAL_DIR, "cdx", answered=cdx_answered)

    rows = []
    for domain, _rank, gap_count in gap_rows:
        if domain in already:
            continue
        tld = domain.rsplit(".", 1)[-1]
        score = gap_fill_rate(gap_count) * tld_weight.get(tld, Decimal(0)) * gap_count
        rows.append(
            (in_window_era(tld), score, attested.get(tld, 0) >= ATTESTED_MIN, domain, "gap")
        )
    held = {domain for domain, _r, _g in gap_rows}
    plausible = pool_plausibility(pool_source, attested)
    for domain, source in pool_source.items():
        if domain in already or domain in held or is_reverse_dns(domain):
            continue
        tld = domain.rsplit(".", 1)[-1]
        rate = cell_rate.get((source, tld), source_rate.get(source, pool_rate))
        score = rate * tld_weight.get(tld, Decimal(0)) * years_per_hit * plausible[tld]
        rows.append(
            (in_window_era(tld), score, attested.get(tld, 0) >= ATTESTED_MIN, domain, "pool")
        )

    rows.sort(key=lambda row: (not row[0], -row[1], not row[2], spread(row[3])))
    return {
        "rows": rows,
        "years_per_hit": years_per_hit,
        "plausibility": plausible,
        "pool_rate": pool_rate,
        "source_rate": source_rate,
        "weights": weights,
        "answered": len(already),
    }


def report(built: dict, need: Decimal | None, rates: list[float]) -> None:
    rows = built["rows"]
    live = [r for r in rows if r[0] and r[1] > 0]
    print(
        f"queue {len(rows):,} targets, {len(live):,} of them era-eligible and worth "
        f"something\n  already answered and skipped: {built['answered']:,}"
    )
    print(f"  measured years per pool hit : {built['years_per_hit']:.3f}")
    print(f"  measured pool-wide hit rate : {built['pool_rate']:.1%}")
    fill_rates = ", ".join(f"{k} slot {v}" for k, v in sorted(GAP_FILL_RATE.items()))
    print(f"  gap fill rate applied       : {fill_rates}, deeper {GAP_FILL_RATE_DEEP}")

    counts = Counter(r[4] for r in live)
    print(f"  gap targets {counts['gap']:,}, pool targets {counts['pool']:,}")

    # Printed because it is the factor whose absence cost 1,200 queries at zero yield,
    # and a ranking factor nobody can see is one nobody checks.
    plausible = built.get("plausibility") or {}
    if plausible:
        worst = sorted(plausible.items(), key=lambda kv: kv[1])[:5]
        best = sorted(plausible.items(), key=lambda kv: -kv[1])[:5]
        show = ", ".join(f"{t} {v:.3f}" for t, v in best)
        print(f"  pool plausibility, highest   : {show}")
        show = ", ".join(f"{t} {v:.4f}" for t, v in worst)
        print(f"  pool plausibility, lowest    : {show}")
        print("    (dated / (dated + pool) per TLD; it multiplies the pool score, so a")
        print("     namespace whose pool is fabricated cannot rank on English share alone)")
    for cut in (10_000, 50_000, 100_000, 250_000):
        head = live[:cut]
        if len(head) < cut:
            break
        mix = Counter(r[4] for r in head)
        value = sum((r[1] for r in head), Decimal(0))
        print(
            f"  best {cut:>7,}: {value:>10,.0f} EE expected, "
            f"{mix['gap']:>7,} gap / {mix['pool']:>7,} pool, "
            f"{value / cut:.4f} per query"
        )

    total = sum((r[1] for r in live), Decimal(0))
    if need is None:
        # No target, so there is no "how long to reach it" to report. Saying nothing
        # is right here: the alternative, substituting some default target, prints a
        # deadline for a goal nobody set.
        print(f"\n  whole queue expected value {total:,.0f} EE, no target set")
        return
    print(f"\n  whole queue expected value {total:,.0f} EE against {need:,.0f} needed")
    cum = Decimal(0)
    reached = None
    for i, row in enumerate(live, 1):
        cum += row[1]
        if cum >= need:
            reached = i
            break
    if reached is None:
        print("  the queue alone does NOT reach the target")
        return
    print(
        f"  reaches the target after {reached:,} queries "
        f"({reached / len(live) * 100:.0f}% of the queue)"
    )
    # A pool query costs more wall-clock than a gap query, and quoting the gap
    # rate over a mixed queue would understate the time by about a fifth. The
    # measured ratio is 562 queries an hour against 916 on the same machine, the
    # difference being that a miss escalates through more request strategies than
    # a hit does, and the pool misses far more often.
    pool_share = Counter(r[4] for r in live[:reached])["pool"] / reached
    blended = sum(rates) * (1 - pool_share * (1 - POOL_SPEED_RATIO))
    print(
        f"  {pool_share * 100:.0f}% of those are pool targets, which run at "
        f"{POOL_SPEED_RATIO:.2f}x the speed of a gap query"
    )
    for label, qph in (("gap speed throughout", sum(rates)), ("blended for the mix", blended)):
        print(
            f"    {label:<22} {qph:>6,.0f} queries/h -> {reached / qph:>4.0f}h = "
            f"{reached / qph / 24:.1f} days"
        )


def write_single(built: dict, population: str, out: Path) -> None:
    """One ranked list for one population, for one machine.

    The two populations answer different questions and belong on different
    machines, which is Ivo's design of 2026-08-11.

    **`gap`** is a held domain missing a year that is bracketed by two years it
    already holds. A hit adds a *pair* and never a domain, so this is the
    completeness half. Its measured hit rate is 96.0% to 97.5% and is effectively
    flat across TLDs, which is exactly why ranking it by English share is right
    here and wrong for the pool: when the probability factor is near 1 and
    uniform, expected value collapses to share times the years one query can fill.
    It also changes slowly, so a machine can work it for days without a refresh.

    **`pool`** is a domain held with no year at all. A hit makes the name net-new,
    so this is the discovery half that the reviewer asked to be prioritised, and
    its hit rate varies from 36.9% for a name merely mentioned in Usenet text to
    90.6% for a link harvested off an archived page. That spread is why it needs
    the measured per-source rate as a multiplier, and why it belongs on the faster
    machine next to the discovery loop that keeps feeding it.
    """
    rows = [row for row in built["rows"] if row[4] == population]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(f"{row[3]}\n")
    live = [r for r in rows if r[0] and r[1] > 0]
    value = sum((r[1] for r in live), Decimal(0))
    print(f"  wrote {out} : {len(rows):,} {population} targets, {value:,.0f} EE expected")
    if population == "gap":
        print("    completeness: every hit is a new pair on a domain already held")
    else:
        print("    discovery: every hit makes a name net-new, which is the prioritised half")


def write(built: dict) -> None:
    rows = built["rows"]
    weights = built["weights"]
    with gzip.open(MANIFEST, "wt", encoding="utf-8") as fh:
        for _era, score, _att, domain, population in rows:
            fh.write(f"{domain}\t{population}\t{score:.6f}\n")
    for shard in range(len(weights)):
        mine = take_weighted_shard(rows, weights, shard, key=lambda row: row[3])
        path = JOURNAL_DIR / SHARD.format(shard)
        with path.open("w", encoding="utf-8") as fh:
            for row in mine:
                fh.write(f"{row[3]}\n")
        live = [r for r in mine if r[0] and r[1] > 0]
        value = sum((r[1] for r in live), Decimal(0))
        print(
            f"  wrote {path} : {len(mine):,} targets, "
            f"{value:,.0f} EE expected, weight {weights[shard]}"
        )
    print(f"  wrote {MANIFEST}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--weights",
        default="78,22",
        help="share sizes, one per machine, in proportion to its measured speed",
    )
    ap.add_argument(
        "--rates",
        default="916,262",
        help="measured queries per hour per machine, for the projection only",
    )
    ap.add_argument(
        "--need",
        type=Decimal,
        default=None,
        help="equivalent-English still needed, for the projection only",
    )
    ap.add_argument("--dry-run", action="store_true", help="report without writing")
    ap.add_argument(
        "--population",
        choices=("both", "gap", "pool"),
        default="both",
        help="both writes the hash-sharded mixed queue. `gap` or `pool` writes ONE ranked "
        "list for that population alone, which is how the two machines are split: the VPS "
        "works gaps as a steady completeness baseline, the local engine works the pool "
        "beside the discovery loop that feeds it.",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="destination for a single-population list; required with --population gap|pool",
    )
    args = ap.parse_args()

    weights = [int(w) for w in args.weights.split(",")]
    rates = [float(r) for r in args.rates.split(",")]
    if len(weights) != len(rates):
        raise SystemExit("--weights and --rates must have the same number of entries")

    need = args.need
    if need is None:
        from ark.baseline import CURRENT_ROUND_SINCE, REVIEWER_BASELINE_EE

        conn = read_only_store(STORE)
        try:
            # The round window comes from `ark.baseline` for the same reason the
            # baseline total does: retyped here it drifts, and a window still open
            # on the last round counts work the reviewer has already credited.
            rows = round_netnew_by_tld(conn, CURRENT_ROUND_SINCE)
        finally:
            conn.close()
        weight = english_weights()
        now = sum((weight.get(t, Decimal(0)) * n for t, n in rows), Decimal(0))
        # No target is set for this round, and `need` stays None. The 10% goal was
        # phase-4's and was met at 10.7310%; carrying it forward would silently
        # retarget a tenth of a baseline that has itself grown, which is a number
        # nobody asked for. Pass `--need` to size the queue against a chosen goal.
        print(
            f"round stands at {now:,.1f} EE, "
            f"{now / REVIEWER_BASELINE_EE * 100:.4f}% of the "
            f"{REVIEWER_BASELINE_EE:,.4f} baseline. No target set; pass --need to set one\n"
        )

    built = build(weights)
    report(built, need, rates)
    if args.dry_run:
        print("\ndry run, nothing written")
        return
    print()
    if args.population != "both":
        if args.out is None:
            raise SystemExit("--population gap|pool needs --out")
        write_single(built, args.population, args.out)
        return
    write(built)


if __name__ == "__main__":
    main()
