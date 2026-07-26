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

import shutil
from pathlib import Path

import duckdb
from loguru import logger

PROVENANCE_DIR = Path("output/provenance")
TABLES = ("source", "domain", "evidence", "domain_year", "ingested_file")

LOAD_SQL = """-- For the DuckDB command-line tool, run from INSIDE this folder:
--     duckdb -init LOAD.sql
-- The paths below are relative, so a different working directory will fail.
--
-- If you do not have the DuckDB CLI, do not install it. `trace.py` next to this
-- file answers the same question with only `uv`:
--     uv run --with duckdb --no-project python trace.py example.com 1998

CREATE TABLE source        AS SELECT * FROM read_parquet('source.parquet');
CREATE TABLE domain        AS SELECT * FROM read_parquet('domain.parquet');
CREATE TABLE evidence      AS SELECT * FROM read_parquet('evidence.parquet');
CREATE TABLE domain_year   AS SELECT * FROM read_parquet('domain_year.parquet');
CREATE TABLE ingested_file AS SELECT * FROM read_parquet('ingested_file.parquet');

-- Why is a domain in a given annual file? One row per supporting observation.
-- Replace the domain and year with any line from additions/ or masters/.
SELECT dy.assigned_year, s.name AS source, e.evidence_type, e.evidence_value
FROM domain_year dy
JOIN evidence e ON e.domain = dy.domain AND e.evidence_year = dy.assigned_year
JOIN source   s ON s.source_id = e.source_id
WHERE dy.domain = 'example.com'
ORDER BY dy.assigned_year;
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
    # the query tool ships beside the data, so the export is usable on its own
    shutil.copyfile(Path(__file__).with_name("provenance_trace.py"), out_dir / "trace.py")
    megabytes = sum(p.stat().st_size for p in out_dir.glob("*.parquet")) / 1024 / 1024
    counts["megabytes"] = round(megabytes)
    logger.info(f"provenance export: {counts}")
    return counts


def load_provenance(conn: duckdb.DuckDBPyConnection, source_dir: Path = PROVENANCE_DIR) -> dict:
    """Recreate the store's tables from a provenance export.

    This is the reproduction path that needs no source data: the export holds
    every observation and every assignment, so re-running the exporter over it
    regenerates the annual files, and the integrity gate re-runs against it too.
    Measured on the shipped export: the fourteen result files come back
    byte-identical in about six seconds.
    """
    counts: dict[str, int] = {}
    for table in TABLES:
        path = source_dir / f"{table}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found; point this at a provenance/ folder")
        conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute(f"CREATE TABLE {table} AS SELECT * FROM read_parquet('{path}')")
        counts[table] = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    logger.info(f"provenance loaded: {counts}")
    return counts
