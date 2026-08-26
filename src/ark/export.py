"""Write the human-facing result files out of the provenance store.

Three targets: net-new year files and their evidence manifest (small, the
committed work product), the candidate list, and the merged master lists
(baseline + additions, large, delivery-archive material).
"""

from pathlib import Path

import duckdb
from loguru import logger

from ark.contribution import DEFAULT_REPORT_DIR, write_contribution_tables
from ark.delegation import shipping_filter as _shipping_filter
from ark.ingest import YEARS
from ark.provenance import PROVENANCE_DIR, write_provenance
from ark.stats import BASELINE_TYPE

NETNEW_DIR = Path("output/netnew")
CANDIDATES_PATH = Path("output/candidate_unverified.txt")
MASTERS_DIR = Path("data/exports")

# A pair is an addition when the baseline holds NO evidence for that (domain, year),
# which is the same test `stats.py` and `contribution.py` apply. It is deliberately
# not "the row this assignment happens to point at is not baseline": the baseline
# rolls forward, so once a release absorbs an earlier addition, that pair still
# points at the original CDX row while now also carrying baseline evidence. Under
# the weaker test every past addition would be re-exported as new against the
# current baseline, which is exactly the double count the brief forbids.
_NOT_IN_BASELINE = f"""
    NOT EXISTS (
        SELECT 1 FROM evidence p
        WHERE p.domain = dy.domain AND p.evidence_year = dy.assigned_year
          AND p.evidence_type = '{BASELINE_TYPE}'
    )
"""


# **A reverse-DNS zone is not a website and must not ship, whoever listed it first.**
#
# `ark.canonical` refuses them at the funnel since 2026-08-18, so no new one can arrive, but 63
# assigned pairs across 18 zones had already got in from Usenet `From:` headers and from the
# reviewer's own baseline, and all six shipped annual files carried them. The reason it matters
# more than 63 rows should is the weight: `.arpa` scores **1.0000** in the CC-MAIN model, the
# highest value in the table, above `.mil` at 0.9981. So it is junk concentrated in the top
# weight, and the reviewer's validator accepts `206.in-addr.arpa` as well formed, so his side
# would score it too.
#
# Filtered here rather than deleted from the store, because deleting rows is a destructive
# migration and the store's history is harmless once nothing can add to it or ship it.
# `dropped_domains.txt` already ships the baseline lines this pipeline excludes, and these join
# them.
#
# **And the rule is the whole TLD rather than the reverse-DNS pattern, which is the stronger and
# simpler statement.** No website ever lived under `.arpa` in 1996-2001: the ARPANET host
# transition finished in 1990, and every zone delegated under `.arpa` since is infrastructure
# (`in-addr`, `ip6`, `e164`, `uri`, `urn`, `iris`). Narrowing to `in-addr` and `ip6` left exactly
# one survivor in the annual files, `ignore.arpa` in 2000, which is a placeholder scoring 1.0000,
# so the narrow rule was catching the shape and missing the class.
#
# **The same filter now also drops a pair whose TLD did not yet exist**, which is the general form
# of the same mistake: 1,087 assigned pairs predated their own TLD's delegation, `.eu` 409 and
# `.info` 202 among them. `ark.delegation` owns the years, so the list is in one place rather than
# repeated at each of the four destinations this predicate reaches.
_NOT_REVERSE_DNS = _shipping_filter()


def _copy_query(conn: duckdb.DuckDBPyConnection, query: str, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(f"COPY ({query}) TO '{path}' (HEADER false)")
    return conn.execute(f"SELECT count(*) FROM ({query})").fetchone()[0]


def netnew_shipped_pairs(conn: duckdb.DuckDBPyConnection) -> int:
    """Net-new pairs that will actually reach the annual files.

    **Not the same as the store's raw net-new total, and the difference is the point.**
    `_shipping_filter` drops a pair whose TLD did not exist in its year, so the store can
    hold more net-new pairs than any export will ever write. Packaging compares its
    exported line count against this, because comparing it against the raw total made a
    current export look permanently stale: 726,344 against 726,336, a difference that is
    the filter doing its job.
    """
    total = 0
    for year in YEARS:
        total += conn.execute(
            f"""
            SELECT COUNT(DISTINCT dy.domain) FROM domain_year dy
            WHERE dy.assigned_year = {year} AND {_NOT_IN_BASELINE}
              AND {_shipping_filter("dy.")}
            """
        ).fetchone()[0]
    return total


def export_all(
    conn: duckdb.DuckDBPyConnection,
    netnew_dir: Path = NETNEW_DIR,
    candidates_path: Path = CANDIDATES_PATH,
    masters_dir: Path = MASTERS_DIR,
    report_dir: Path = DEFAULT_REPORT_DIR,
    provenance_dir: Path = PROVENANCE_DIR,
) -> dict[str, int]:
    """Write every result file. Every destination is a parameter, so a caller
    that redirects the outputs redirects all of them; leaving one hardcoded let
    the test suite overwrite the real contribution tables with a test store."""
    stats: dict[str, int] = {}

    for year in YEARS:
        netnew_query = f"""
            SELECT DISTINCT dy.domain FROM domain_year dy
            WHERE dy.assigned_year = {year} AND {_NOT_IN_BASELINE}
              AND {_shipping_filter("dy.")}
            ORDER BY dy.domain
        """
        count = _copy_query(conn, netnew_query, netnew_dir / f"{year}.txt")
        stats[f"netnew_{year}"] = count
        masters_query = f"""
            SELECT DISTINCT domain FROM domain_year
            WHERE assigned_year = {year} AND {_NOT_REVERSE_DNS} ORDER BY domain
        """
        stats[f"master_{year}"] = _copy_query(conn, masters_query, masters_dir / f"{year}.txt")

    manifest_query = f"""
        SELECT dy.domain, dy.assigned_year, e.evidence_type, e.evidence_value,
               s.name AS source, e.acquisition_method, e.evidence_url
        FROM domain_year dy
        JOIN evidence e ON dy.evidence_id = e.evidence_id
        JOIN source s ON e.source_id = s.source_id
        WHERE e.evidence_type != '{BASELINE_TYPE}' AND {_NOT_IN_BASELINE}
          AND {_shipping_filter("dy.")}
        ORDER BY dy.domain, dy.assigned_year
    """
    path = netnew_dir / "evidence_manifest.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(f"COPY ({manifest_query}) TO '{path}' (HEADER true)")

    candidates_query = (
        """
        SELECT d.domain FROM domain d
        WHERE NOT EXISTS (SELECT 1 FROM domain_year dy WHERE dy.domain = d.domain)
          AND """
        + _shipping_filter("d.", with_year=False)
        + """
        ORDER BY d.domain
    """
    )
    stats["candidates"] = _copy_query(conn, candidates_query, candidates_path)

    # per-source and per-year contribution tables, which ship in the audit folder
    stats.update(write_contribution_tables(conn, report_dir))

    # the provenance graph itself, so a reader can ask "why is this domain in
    # this year?" without the source data or a copy of the database
    provenance = write_provenance(conn, provenance_dir)
    stats["provenance_mb"] = provenance["megabytes"]

    logger.info(f"export: {stats}")
    return stats
