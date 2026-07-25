"""Select which held domains are worth a per-domain archive query.

A domain assigned in year Y-1 and again in Y+1, but missing Y, almost certainly
existed in Y: the two flanking years bracket it. That makes it the highest-yield
target for a year-specific lookup, and it is why the candidate set is restricted
to this shape rather than to every year adjacent to a held one, which is 17.5x
larger and far more speculative.

The unit of work is the domain, not the gap, because one archive query answers
every year at once. Ordering therefore ranks domains, thinnest gap year first, so
a run that is cut short has still spent its requests where the annual files are
weakest.
"""

from pathlib import Path

import duckdb

from ark.ingest import YEARS

# thinnest year first, measured from net-new pairs per year; a run that stops
# early should have spent its budget on the years that need it most
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
-- spread deterministically inside each year tier rather than alphabetically:
-- alphabetical order clusters numeric-prefix junk ("0171.com", "1-800-...") that
-- was never archived, so a run that cannot finish the pool would spend its whole
-- budget on the least promising names and badly understate the true hit rate
ORDER BY rank, hash(domain)
"""


def sandwich_gap_domains(
    conn: duckdb.DuckDBPyConnection,
    first: int = min(YEARS),
    last: int = max(YEARS),
) -> list[tuple[str, int, int]]:
    """Held domains with a bracketed missing year, best target first."""
    return conn.execute(
        _SANDWICH_SQL, {"priority": YEAR_PRIORITY, "first": first, "last": last}
    ).fetchall()


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


def write_gap_candidates(conn: duckdb.DuckDBPyConnection, path: Path) -> dict[str, int]:
    """Write the prioritised domain list and report what it contains."""
    rows = sandwich_gap_domains(conn)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for domain, _rank, _count in rows:
            fh.write(f"{domain}\n")
    return {"domains": len(rows), "gap_pairs": sum(count for _d, _r, count in rows)}
