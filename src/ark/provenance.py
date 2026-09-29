"""The provenance Parquet: the evidence authority, and the store is an index rebuilt from it.

The annual files say which domains belong to which years, not why, and "why" is the whole
claim: every assignment points at an evidence row recording which source saw the domain, in
which artifact, at which timestamp. Parquet carries the same tables in a fraction of the
store's size, loads in any engine, and is cheap enough to regenerate per delivery;
`load_provenance` rebuilds the store from it.

Seven tables, which together are the whole provenance graph:

    source           who observed anything, and by what acquisition method
    domain           every name we know, and which source first saw it
    evidence         one row per observation: domain, year, type, value, url, and the file
                     it was read from and its place in it, where known
    domain_year      the annual assignments, each pointing at one evidence row
    ingested_file    the sha256 ledger, so a file's contribution is traceable
    domain_language  page-language verdicts, from a retired standard
    hostname_year    the hostname records, each pointing at one evidence row
"""

import shutil
from pathlib import Path

import duckdb
from loguru import logger

from ark.db import init_db

PROVENANCE_DIR = Path("output/provenance")
CORE_TABLES = ("source", "domain", "evidence", "domain_year", "ingested_file")

# Page-language verdicts, from the standard the reviewer retired in August 2026. Still
# exported and loaded, so an archive from a round that shipped them rebuilds and a verdict
# acted on once stays auditable. Optional on load in both directions: an export from either
# side of the standard's life may lack the file, so neither may raise FileNotFoundError.
OPTIONAL_TABLES = ("domain_language", "hostname_year")

TABLES = CORE_TABLES + OPTIONAL_TABLES

# The order each table loads in, its key: a rebuilt table reads in the order its ids were
# issued, so zone maps serve a lookup by `evidence_id` without an index.
KEYS = {
    "source": "source_id",
    "domain": "domain",
    "evidence": "evidence_id",
    "domain_year": "domain, assigned_year",
    "ingested_file": "source_name, file_name",
    "domain_language": "domain, assigned_year",
    "hostname_year": "hostname, assigned_year",
}
# each sequence, and the table and column whose ids it issues
SEQUENCES = {"source_seq": ("source", "source_id"), "evidence_seq": ("evidence", "evidence_id")}

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
-- Replace the domain and year with any line from additions/.
SELECT dy.assigned_year, s.name AS source, e.evidence_type, e.evidence_value
FROM domain_year dy
JOIN evidence e ON e.domain = dy.domain AND e.evidence_year = dy.assigned_year
JOIN source   s ON s.source_id = e.source_id
WHERE dy.domain = 'example.com'
ORDER BY dy.assigned_year;
"""


# **A name we know**: a source of ours found it, or a row of ours names it. His release filed
# every name it holds under his source, `prior_task`, and a name only he gave us is his, not
# ours to ship; a name `ark seed` filed before any evidence is ours and stays.
_KNOWN = """
    d.discovered_source IS DISTINCT FROM (SELECT source_id FROM source WHERE name = 'prior_task')
    OR d.domain IN (SELECT domain FROM evidence)
"""
# **What the export ships, as opposed to what the store holds.** Every table whole but two:
# `domain` ships the names we know, and `domain_language` the verdicts on those names, so no
# verdict names a domain the export lacks. A store rebuilt from the export holds nothing else,
# so there both keep every row.
SHIPPED = {
    "domain": f"SELECT d.* FROM domain d WHERE {_KNOWN}",
    "domain_language": (
        f"SELECT l.* FROM domain_language l JOIN domain d ON d.domain = l.domain WHERE {_KNOWN}"
    ),
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
        # COPY answers with the rows it wrote, so no query runs twice
        counts[table] = conn.execute(
            f"COPY ({query}) TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        ).fetchone()[0]
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
    every assignment, so re-running the exporter over it regenerates the result files and the
    integrity gate re-runs too.

    `init_db` creates every table before its rows go in, so the rebuilt store keeps each
    primary key, CHECK, NOT NULL and DEFAULT and takes new ingests. A row keeps every value it
    shipped with, `ingested_at` included; a column an older export lacks loads as its default
    or NULL. Each sequence starts one past the ids the export holds, so no id is issued twice.
    Run it outside a transaction: each table is checkpointed once loaded, which frees the
    memory its index held.
    """
    missing = [t for t in CORE_TABLES if not (source_dir / f"{t}.parquet").exists()]
    if missing:
        absent = source_dir / f"{missing[0]}.parquet"
        raise FileNotFoundError(f"{absent} not found; point this at a provenance/ folder")

    # An older store still carries foreign keys, and DuckDB drops a table only once nothing
    # references it, so every table goes, referrers first, before any is created.
    for table in reversed(TABLES):
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    for name, (table, column) in SEQUENCES.items():
        start = conn.execute(
            f"SELECT coalesce(max({column}), 0) + 1 FROM read_parquet(?)",
            [str(source_dir / f"{table}.parquet")],
        ).fetchone()[0]
        conn.execute(f"DROP SEQUENCE IF EXISTS {name}")
        conn.execute(f"CREATE SEQUENCE {name} START WITH {int(start)}")
        if name == "evidence_seq":
            conn.execute("DROP SEQUENCE IF EXISTS located_from")
            conn.execute(f"CREATE SEQUENCE located_from START WITH {int(start)}")
    init_db(conn)  # `IF NOT EXISTS` keeps the starts just set

    counts: dict[str, int] = {}
    for table in TABLES:
        path = source_dir / f"{table}.parquet"
        # an optional table an older export lacks stays empty, so every reader can query it
        if path.exists():
            conn.execute(
                f"INSERT INTO {table} BY NAME SELECT * FROM read_parquet(?) ORDER BY {KEYS[table]}",
                [str(path)],
            )
            conn.execute("CHECKPOINT")
        counts[table] = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    logger.info(f"provenance loaded: {counts}")
    return counts
