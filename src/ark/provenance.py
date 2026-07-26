"""Export the provenance store as Parquet, so the result can be checked offline.

The annual files say which domains belong to which years. They do not say why,
and "why" is the whole claim: every assignment points at a specific evidence row
recording which source saw the domain, in which artifact, at which timestamp.
That relationship lives in the store, and the store is 3.5 GB.

Shipping the database itself would cost 1.09 GB gzipped and tie the reader to a
DuckDB version. Parquet carries the same five tables in 241 MB, loads in any
engine, and reloads into a queryable database with one statement per table. It
takes about a second to write, so it is regenerated with every delivery rather
than maintained.

Five tables, which together are the whole provenance graph:

    source          who observed anything, and by what acquisition method
    domain          every registered domain, and which source first saw it
    evidence        one row per observation: domain, year, type, value, url
    domain_year     the annual assignments, each pointing at one evidence row
    ingested_file   the sha256 ledger, so a file's contribution is traceable

The baseline rows are included deliberately. Excluding them is smaller, but then
a reader holding only this archive cannot trace a baseline pair, and the point of
the export is that it answers questions without anything else on hand.
"""

from pathlib import Path

import duckdb
from loguru import logger

PROVENANCE_DIR = Path("output/provenance")
TABLES = ("source", "domain", "evidence", "domain_year", "ingested_file")

LOAD_SQL = """-- Rebuild a queryable provenance store from this folder:
CREATE TABLE source        AS SELECT * FROM read_parquet('source.parquet');
CREATE TABLE domain        AS SELECT * FROM read_parquet('domain.parquet');
CREATE TABLE evidence      AS SELECT * FROM read_parquet('evidence.parquet');
CREATE TABLE domain_year   AS SELECT * FROM read_parquet('domain_year.parquet');
CREATE TABLE ingested_file AS SELECT * FROM read_parquet('ingested_file.parquet');

-- Why is a domain in a given annual file? One row per supporting observation:
SELECT s.name AS source, e.evidence_type, e.evidence_value, e.evidence_url
FROM domain_year dy
JOIN evidence e ON e.evidence_id = dy.evidence_id
JOIN source   s ON s.source_id   = e.source_id
WHERE dy.domain = 'example.com' AND dy.assigned_year = 1998;
"""


def write_provenance(
    conn: duckdb.DuckDBPyConnection, out_dir: Path = PROVENANCE_DIR
) -> dict[str, int]:
    """Write every provenance table to Parquet and report the row counts."""
    out_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for table in TABLES:
        path = out_dir / f"{table}.parquet"
        conn.execute(f"COPY {table} TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        counts[table] = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    (out_dir / "LOAD.sql").write_text(LOAD_SQL, encoding="utf-8")
    megabytes = sum(p.stat().st_size for p in out_dir.glob("*.parquet")) / 1024 / 1024
    counts["megabytes"] = round(megabytes)
    logger.info(f"provenance export: {counts}")
    return counts
