"""Select which held domains are worth a per-domain archive query, best first.

A domain assigned in year Y-1 and again in Y+1, but missing Y, almost certainly
existed in Y: the two flanking years bracket it. That makes it the highest-yield
target for a year-specific lookup, and it is why the candidate set is restricted
to this shape rather than to every year adjacent to a held one, which is 17.5x
larger and far more speculative.

The unit of work is the domain, not the gap, because one archive query answers
every year at once.

**Ordering is by expected equivalent-English, since August 2026 that is the
score.** A query is worth `English share of the TLD x the number of bracketed
years it could fill`, because the hit rate is close to uniform across this
population: measured 96.0% and 96.9% on consecutive batches, so what separates
one target from another is not the chance of an answer but what the answer is
worth. Both factors matter. Share alone would rank a domain with one missing year
above one with three; count alone would spend the week on `.de` at 13.2% English
while 13,503 `.uk` domains at 98.1% waited.

The order this replaced ranked by thinnest gap year first, which was right when
the goal was per-year completeness and predates the metric entirely. Measured
against it over the next 50,000 queries, expected equivalent-English per query
went from 0.813 to 1.249, about **54% better**, because the old order was feeding
2,249 `.de`, 833 `.dk` and 656 `.it` domains into the queue ahead of `.uk`. It is
kept as `year_priority_order` for reproducing earlier rounds, and it survives as
the tiebreak inside an equal-value tier, so year balance still guides the choice
between two targets worth the same.

Ties break on a content hash rather than alphabetically, because alphabetical
clusters the numeric-prefix junk ("0171.com", "1-800-...") that was never
archived, so a run that cannot finish the pool would spend its budget on the
least promising names and badly understate the true hit rate.
"""

import hashlib
from pathlib import Path

import duckdb

from ark.english_share import english_weights
from ark.ingest import YEARS

# thinnest year first, measured from net-new pairs per year. Superseded as the
# primary key by expected equivalent-English; retained as the tiebreak within an
# equal-value tier, and available whole via `year_priority_order`.
YEAR_PRIORITY = [1998, 1999, 2000, 2001, 1996, 1997]

_SANDWICH_SQL = """
WITH held AS (SELECT DISTINCT domain, assigned_year AS y FROM domain_year),
     gaps AS (
       SELECT h1.domain, h1.y + 1 AS gap_year
       FROM held h1
       JOIN held h2 ON h2.domain = h1.domain AND h2.y = h1.y + 2
       WHERE NOT EXISTS (
         SELECT 1 FROM held h3 WHERE h3.domain = h1.domain AND h3.y = h1.y + 1
       )
     )
SELECT domain, min(list_position($priority, gap_year)) AS rank, count(*) AS gap_count
FROM gaps
WHERE gap_year BETWEEN $first AND $last
GROUP BY domain
"""


def sandwich_gap_domains(
    conn: duckdb.DuckDBPyConnection,
    first: int = min(YEARS),
    last: int = max(YEARS),
) -> list[tuple[str, int, int]]:
    """Held domains with a bracketed missing year, as (domain, year rank, gaps)."""
    return conn.execute(
        _SANDWICH_SQL, {"priority": YEAR_PRIORITY, "first": first, "last": last}
    ).fetchall()


def spread(domain: str) -> bytes:
    """Deterministic tiebreak, stable across processes and machines.

    `hash()` on a str is salted per interpreter run, so it cannot be used: two
    machines sharding the same list would disagree about the order and, worse,
    about which share a domain belongs to.
    """
    return hashlib.blake2b(domain.encode(), digest_size=8).digest()


def expected_equivalent_english(domain: str, gap_count: int) -> object:
    """What querying this domain is worth to the score, in expectation.

    The English share of its TLD times the number of bracketed years a capture
    could fill. The near-uniform hit rate is left out deliberately: it is a
    constant factor across this population, so it scales every target equally and
    changes no ordering.
    """
    return english_weights().get(domain.rsplit(".", 1)[-1], 0) * gap_count


def equivalent_english_order(rows: list[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    """Best expected equivalent-English first, year priority then hash as tiebreaks."""
    return sorted(
        rows,
        key=lambda row: (
            -expected_equivalent_english(row[0], row[2]),
            row[1],
            spread(row[0]),
        ),
    )


def year_priority_order(rows: list[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    """The pre-August-2026 order: thinnest gap year first, then hash. Legacy."""
    return sorted(rows, key=lambda row: (row[1], spread(row[0])))


def take_shard(rows: list[tuple[str, int, int]], shards: int, shard: int) -> list:
    """One of `shards` disjoint slices, so two machines never query the same name.

    Assignment is by content hash, not by position, which is what makes it safe
    without any coordination: each machine computes the same answer from the
    domain alone, so the slices are disjoint and jointly complete however often
    either side regenerates its list. Slicing by position would instead hand the
    whole high-value head to one machine, and this ordering puts real money in
    that head.
    """
    if shards < 1 or not 0 <= shard < shards:
        raise ValueError(f"shard {shard} is not in range for {shards} shards")
    if shards == 1:
        return rows
    return [row for row in rows if spread(row[0])[0] % shards == shard]


def take_weighted_shard(rows: list, weights: list[int], shard: int, key=lambda row: row[0]) -> list:
    """A slice sized in proportion to how fast the machine working it is.

    Equal shares were right while both collectors ran at similar speeds. Measured
    on 7 August they do not: the MacBook sustains 916 queries an hour against the
    VPS's 262, so an even split leaves the fast machine grinding the cheap tail of
    its own half while the expensive head of the other half is untouched. Sizing
    each share by throughput means both finish at the same time, which is the only
    arrangement where no high-value target is left waiting behind a low-value one.

    Assignment stays a content hash for the reason `take_shard` gives, and takes
    two bytes rather than one so a 78/22 split lands within a tenth of a percent
    instead of being rounded to the nearest 1/256th. Because the hash is
    independent of the ordering, each share is a representative sample of the
    whole value curve rather than a contiguous block of it.
    """
    if any(weight < 0 for weight in weights) or not any(weights):
        raise ValueError(f"weights must be non-negative and not all zero: {weights}")
    if not 0 <= shard < len(weights):
        raise ValueError(f"shard {shard} is not in range for {len(weights)} weights")
    total = sum(weights)
    lower = sum(weights[:shard])
    scale = 1 << 16
    start = lower * scale // total
    stop = (lower + weights[shard]) * scale // total
    return [row for row in rows if start <= int.from_bytes(spread(key(row))[:2], "big") < stop]


# Domains a registry creation date could still add a year to. A creation date
# attests exactly one year, and crucially that year is NOT bounded by the years
# already held: because the date resets when a name is dropped and re-registered,
# a domain held in 1997 can legitimately report creation in 1999, which then
# evidences 1999. So the population is every domain with a missing in-window year
# next to a held one, and the useful ordering is by how many years are missing,
# since each missing year is another chance for the date to land somewhere new.
_MISSING_ADJACENT_SQL = """
WITH held AS (SELECT DISTINCT domain, assigned_year AS y FROM domain_year),
     wanted AS (
       SELECT DISTINCT h.domain, t.y AS target
       FROM held h
       CROSS JOIN (SELECT unnest($window) AS y) t
       WHERE abs(t.y - h.y) = 1
     ),
     missing AS (
       SELECT w.domain, w.target FROM wanted w
       WHERE NOT EXISTS (
         SELECT 1 FROM held h2 WHERE h2.domain = w.domain AND h2.y = w.target
       )
     )
SELECT domain, count(*) AS missing_years
FROM missing
GROUP BY domain
ORDER BY missing_years DESC, hash(domain)
"""


def creation_addressable_domains(
    conn: duckdb.DuckDBPyConnection,
    window: list[int] | None = None,
) -> list[tuple[str, int]]:
    """Held domains missing an in-window year adjacent to one they hold."""
    return conn.execute(_MISSING_ADJACENT_SQL, {"window": window or list(YEARS)}).fetchall()


def write_creation_candidates(conn: duckdb.DuckDBPyConnection, path: Path) -> dict[str, int]:
    """Write the creation-date-addressable domain list, most-missing first."""
    rows = creation_addressable_domains(conn)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for domain, _missing in rows:
            fh.write(f"{domain}\n")
    return {
        "domains": len(rows),
        # every missing year is a chance for a creation date to land on it
        "addressable_years": sum(missing for _d, missing in rows),
    }


def write_gap_candidates(
    conn: duckdb.DuckDBPyConnection,
    path: Path,
    legacy_year_order: bool = False,
    shards: int = 1,
    shard: int = 0,
) -> dict[str, int]:
    """Write the prioritised domain list and report what it contains."""
    rows = sandwich_gap_domains(conn)
    ordered = year_priority_order(rows) if legacy_year_order else equivalent_english_order(rows)
    mine = take_shard(ordered, shards, shard)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for domain, _rank, _count in mine:
            fh.write(f"{domain}\n")
    weights = english_weights()
    reachable = sum(
        weights.get(domain.rsplit(".", 1)[-1], 0) * count for domain, _rank, count in mine
    )
    return {
        "domains": len(mine),
        "gap_pairs": sum(count for _d, _r, count in mine),
        # what the whole list is worth if every bracketed year comes back
        "equivalent_english_ceiling": int(reachable),
        "of_total_domains": len(ordered),
        "shards": shards,
        "shard": shard,
    }
