"""Export the provenance store as Parquet, so the result can be checked offline.

The annual files say which domains belong to which years, not why, and "why" is the whole
claim: every assignment points at an evidence row recording which source saw the domain, in
which artifact, at which timestamp. Parquet carries the same tables in a fraction of the
store's size, loads in any engine, and is cheap enough to regenerate per delivery.

Six tables, which together are the whole provenance graph:

    source          who observed anything, and by what acquisition method
    domain          every registered domain, and which source first saw it
    evidence        one row per observation: domain, year, type, value, url
    domain_year     the annual assignments, each pointing at one evidence row
    ingested_file   the sha256 ledger, so a file's contribution is traceable

**The reviewer's own rows are excluded.** 362.6 million of 442.2 million evidence rows were
`prior_reused`, one per pair his release already holds, and 3 GB of an archive that then
exceeded his 5 GB limit. What is lost is tracing a pair he can trace in his own release;
what is kept is every row this project claims, and `ark check` asserts that nothing in
`additions/` or `hostnames/` rests on a `prior_reused` row. Assignments citing an excluded
row go with it, so the export never points at evidence it does not carry.
"""

import shutil
from pathlib import Path

import duckdb
from loguru import logger

from ark.evidence_types import HIS_TYPE
from ark.held import OUR_DOMAIN_YEAR_SQL

PROVENANCE_DIR = Path("output/provenance")
CORE_TABLES = ("source", "domain", "evidence", "domain_year", "ingested_file")

# Page-language verdicts, from the standard the reviewer retired in August 2026. Still
# exported and loaded, so an archive from a round that shipped them rebuilds and a verdict
# acted on once stays auditable. Optional on load in both directions: an export from either
# side of the standard's life may lack the file, so neither may raise FileNotFoundError.
# `hostname_year` is last on purpose: it references both `domain` and `evidence`,
# and the rebuild drops in reverse order, so it must go before either of them.
OPTIONAL_TABLES = ("domain_language", "hostname_year")

TABLES = CORE_TABLES + OPTIONAL_TABLES

LOAD_SQL = """-- Seven tables: the five that make up the evidence graph, the language
-- verdicts, and the hostname records (the second output unit, accepted 2026-09-01).
-- For the DuckDB command-line tool, run from INSIDE this folder:
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

-- Page-language verdicts per (domain, year), with the snapshot URLs that were read.
-- From a standard retired in August 2026, kept so a round that shipped them stays
-- rebuildable. Absent from exports written before it existed.
CREATE TABLE domain_language AS SELECT * FROM read_parquet('domain_language.parquet');

-- Hostname records beneath held registrables, each pointing at the evidence row
-- whose capture timestamp dates it. Absent from exports written before 2026-09-01.
CREATE TABLE hostname_year AS SELECT * FROM read_parquet('hostname_year.parquet');

-- Why is a domain in a given annual file? One row per supporting observation.
-- Replace the domain and year with any line from additions/ or masters/.
SELECT dy.assigned_year, s.name AS source, e.evidence_type, e.evidence_value
FROM domain_year dy
JOIN evidence e ON e.domain = dy.domain AND e.evidence_year = dy.assigned_year
JOIN source   s ON s.source_id = e.source_id
WHERE dy.domain = 'example.com'
ORDER BY dy.assigned_year;
"""


# **What the export ships, as opposed to what the store holds.** Only two tables differ,
# and they differ together: an assignment whose evidence row is not shipped would be a
# reference into nothing, and the archive's own `verify.sh` refuses that. Everything else
# goes whole, because the tables are small and a reader guessing at gaps is worse than a
# reader holding the lot.
# `domain_year` ships as `held.OUR_DOMAIN_YEAR_SQL`, which says why and how it re-points.
SHIPPED = {
    "evidence": f"SELECT * FROM evidence WHERE evidence_type <> '{HIS_TYPE}'",
    "domain_year": OUR_DOMAIN_YEAR_SQL,
}


def write_provenance(
    conn: duckdb.DuckDBPyConnection, out_dir: Path = PROVENANCE_DIR
) -> dict[str, int]:
    """Write every provenance table to Parquet and report the row counts."""
    out_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for table in TABLES:
        path = out_dir / f"{table}.parquet"
        query = SHIPPED.get(table, f"SELECT * FROM {table}")
        conn.execute(f"COPY ({query}) TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        counts[table] = conn.execute(f"SELECT count(*) FROM ({query})").fetchone()[0]
    (out_dir / "LOAD.sql").write_text(LOAD_SQL, encoding="utf-8")
    # the query tool ships beside the data, so the export is usable on its own
    shutil.copyfile(Path(__file__).with_name("provenance_trace.py"), out_dir / "trace.py")
    megabytes = sum(p.stat().st_size for p in out_dir.glob("*.parquet")) / 1024 / 1024
    counts["megabytes"] = round(megabytes)
    logger.info(f"provenance export: {counts}")
    return counts


def load_provenance(conn: duckdb.DuckDBPyConnection, source_dir: Path = PROVENANCE_DIR) -> dict:
    """Recreate the store's tables from a provenance export.

    The reproduction path that needs no source data: the export holds every observation and
    every assignment, so re-running the exporter over it regenerates the annual files and
    the integrity gate re-runs too. On the shipped export the fourteen result files come
    back byte-identical in about six seconds.

    **Every table is dropped before any is created, in reverse dependency order.** Dropping
    and recreating one at a time works only on an empty store, because `domain` references
    `source` and DuckDB refuses to drop a table a foreign key still points at.
    """
    missing = [t for t in CORE_TABLES if not (source_dir / f"{t}.parquet").exists()]
    if missing:
        absent = source_dir / f"{missing[0]}.parquet"
        raise FileNotFoundError(f"{absent} not found; point this at a provenance/ folder")

    for table in reversed(TABLES):
        conn.execute(f"DROP TABLE IF EXISTS {table}")

    counts: dict[str, int] = {}
    for table in TABLES:
        path = source_dir / f"{table}.parquet"
        if not path.exists():
            # An optional table absent from an older export is created empty
            # rather than skipped, so everything downstream can query it
            # unconditionally instead of guarding.
            from ark.db import init_db

            init_db(conn)
            counts[table] = 0
            continue
        conn.execute(f"CREATE TABLE {table} AS SELECT * FROM read_parquet('{path}')")
        counts[table] = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    logger.info(f"provenance loaded: {counts}")
    return counts
