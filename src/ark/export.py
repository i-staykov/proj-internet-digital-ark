"""Write the human-facing result files out of the provenance store.

Three targets: net-new year files and their evidence manifest (small, the
committed work product), the candidate list, and the merged master lists
(baseline + additions, large, delivery-archive material).
"""

from pathlib import Path

import duckdb
from loguru import logger

from ark.contribution import DEFAULT_REPORT_DIR, write_contribution_tables
from ark.ingest import YEARS

NETNEW_DIR = Path("output/netnew")
CANDIDATES_PATH = Path("output/candidate_unverified.txt")
MASTERS_DIR = Path("data/exports")


def _copy_query(conn: duckdb.DuckDBPyConnection, query: str, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(f"COPY ({query}) TO '{path}' (HEADER false)")
    return conn.execute(f"SELECT count(*) FROM ({query})").fetchone()[0]


def export_all(
    conn: duckdb.DuckDBPyConnection,
    netnew_dir: Path = NETNEW_DIR,
    candidates_path: Path = CANDIDATES_PATH,
    masters_dir: Path = MASTERS_DIR,
    report_dir: Path = DEFAULT_REPORT_DIR,
) -> dict[str, int]:
    """Write every result file. Every destination is a parameter, so a caller
    that redirects the outputs redirects all of them; leaving one hardcoded let
    the test suite overwrite the real contribution tables with a test store."""
    stats: dict[str, int] = {}

    for year in YEARS:
        netnew_query = f"""
            SELECT dy.domain FROM domain_year dy
            JOIN evidence e ON dy.evidence_id = e.evidence_id
            WHERE e.evidence_type != 'prior_reused' AND dy.assigned_year = {year}
            ORDER BY dy.domain
        """
        count = _copy_query(conn, netnew_query, netnew_dir / f"{year}.txt")
        stats[f"netnew_{year}"] = count
        masters_query = f"""
            SELECT DISTINCT domain FROM domain_year
            WHERE assigned_year = {year} ORDER BY domain
        """
        stats[f"master_{year}"] = _copy_query(conn, masters_query, masters_dir / f"{year}.txt")

    manifest_query = """
        SELECT dy.domain, dy.assigned_year, e.evidence_type, e.evidence_value,
               s.name AS source, e.acquisition_method, e.evidence_url
        FROM domain_year dy
        JOIN evidence e ON dy.evidence_id = e.evidence_id
        JOIN source s ON e.source_id = s.source_id
        WHERE e.evidence_type != 'prior_reused'
        ORDER BY dy.domain, dy.assigned_year
    """
    path = netnew_dir / "evidence_manifest.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(f"COPY ({manifest_query}) TO '{path}' (HEADER true)")

    candidates_query = """
        SELECT d.domain FROM domain d
        WHERE NOT EXISTS (SELECT 1 FROM domain_year dy WHERE dy.domain = d.domain)
        ORDER BY d.domain
    """
    stats["candidates"] = _copy_query(conn, candidates_query, candidates_path)

    # per-source and per-year contribution tables, which ship in the audit folder
    stats.update(write_contribution_tables(conn, report_dir))

    logger.info(f"export: {stats}")
    return stats
