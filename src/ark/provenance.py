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

Six tables, which together are the whole provenance graph:

    source          who observed anything, and by what acquisition method
    domain          every registered domain, and which source first saw it
    evidence        one row per observation: domain, year, type, value, url
    domain_year     the annual assignments, each pointing at one evidence row
    ingested_file   the sha256 ledger, so a file's contribution is traceable

**The reviewer's own rows are excluded, since 2026-09-11.** They were included
deliberately for eight rounds, so that a reader holding only this archive could
trace a baseline pair too. It cost more than it was worth: 362.6 million of the
442.2 million evidence rows were `prior_reused`, one per pair his own release
already holds, and they were 3 GB of a 6.9 GB archive that then exceeded his
5 GB limit and had to go by a private link. Measured: 4.544 GB to 1.62 GB.

What is lost is tracing a pair he already has, which he can trace in his own
release. What is kept is every row this project claims: nothing in `additions/`
or `hostnames/` rests on a `prior_reused` row, and `ark check` asserts exactly
that. The assignments that cite an excluded row go with it, so the export never
points at evidence it does not carry, which the shipped `verify.sh` checks.
"""

import shutil
from pathlib import Path

import duckdb
from loguru import logger

from ark.evidence_types import CANDIDATE_ONLY_TYPES

_CANDIDATE_LIST = ", ".join(f"'{t}'" for t in sorted(CANDIDATE_ONLY_TYPES))

PROVENANCE_DIR = Path("output/provenance")
CORE_TABLES = ("source", "domain", "evidence", "domain_year", "ingested_file")

# Page-language verdicts, from the standard the reviewer retired in August 2026
# (the engine was retired and removed). Still exported and still loaded, because a reviewer
# holding an archive from a round that shipped them must be able to rebuild it,
# and because a verdict that was acted on once should stay auditable. Optional on
# load in both directions: an export from before the standard existed has no such
# file, and one from after it was retired need not either, so neither may raise
# FileNotFoundError.
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
# **The row it is re-pointed at has to be one the assigner would have accepted.** The
# first version took any observation of the pair, which pointed 1,029,947 assignments at
# candidate-only evidence and 886,252 at a capture of `www.` in front of the name, and
# the rebuilt store failed `no_candidate_leakage` and `a_bare_record_is_not_inferred_from_www`
# on exactly those. So the candidate types and the www-only captures are excluded here,
# which are the same two rules those checks read, and a pair with nothing left is dropped
# rather than re-pointed: we cannot prove it, and he can.
#
# **An assignment is re-pointed before it is dropped.** A pair he already held was
# assigned against his marker simply because his release was ingested first, and many of
# those pairs we can prove ourselves. Dropping them with his evidence row left 32,432,586
# of our own observations with no assignment, which `nothing_earned_is_left_unassigned`
# reads, correctly, as a domain sitting in the candidate pool while holding proof of a
# year. So an assignment citing one of his rows is re-pointed at our own observation of
# the same pair where one exists, and only the rest go.
SHIPPED = {
    "evidence": "SELECT * FROM evidence WHERE evidence_type <> 'prior_reused'",
    "domain_year": f"""
        WITH ours AS (
            SELECT domain, evidence_year, min(evidence_id) AS evidence_id
            FROM evidence
            WHERE evidence_type <> 'prior_reused'
              AND evidence_type NOT IN ({_CANDIDATE_LIST})
              AND evidence_value NOT LIKE 'cdx capture % www.' || domain
            GROUP BY 1, 2
        )
        SELECT dy.* REPLACE (COALESCE(o.evidence_id, dy.evidence_id) AS evidence_id)
        FROM domain_year dy
        JOIN evidence e ON e.evidence_id = dy.evidence_id
        LEFT JOIN ours o ON o.domain = dy.domain AND o.evidence_year = dy.assigned_year
        WHERE e.evidence_type <> 'prior_reused' OR o.evidence_id IS NOT NULL
    """,
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

    This is the reproduction path that needs no source data: the export holds
    every observation and every assignment, so re-running the exporter over it
    regenerates the annual files, and the integrity gate re-runs against it too.
    Measured on the shipped export: the fourteen result files come back
    byte-identical in about six seconds.

    **Every table is dropped before any is created, in reverse dependency
    order.** Dropping and recreating one at a time works only on an empty store,
    because `domain` references `source` and DuckDB refuses to drop a table a
    foreign key still points at. That made this fail on any store that had
    already been initialised, which is the ordinary case for anyone told to run
    `ark export` before rebuilding.
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
