"""DuckDB schema and connection for the provenance store."""

from pathlib import Path

import duckdb

DEFAULT_DB_PATH = Path("data/ark.duckdb")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS source (
    source_id  INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    kind       TEXT NOT NULL CHECK (kind IN ('timestamped', 'candidate_only')),
    notes      TEXT
);

CREATE TABLE IF NOT EXISTS domain (
    domain            TEXT PRIMARY KEY,
    tld               TEXT,
    discovered_source INTEGER NOT NULL REFERENCES source(source_id),
    discovered_round  INTEGER NOT NULL DEFAULT 0,
    first_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE SEQUENCE IF NOT EXISTS evidence_seq START 1;

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id        BIGINT PRIMARY KEY DEFAULT nextval('evidence_seq'),
    domain             TEXT NOT NULL REFERENCES domain(domain),
    source_id          INTEGER NOT NULL REFERENCES source(source_id),
    evidence_year      INTEGER NOT NULL CHECK (evidence_year BETWEEN 1996 AND 2001),
    evidence_type      TEXT NOT NULL CHECK (evidence_type IN (
                           'cdx_timestamp', 'snapshot_date', 'dated_directory',
                           'dated_index', 'whois_creation', 'edgar_filing',
                           'prior_reused', 'other')),
    evidence_value     TEXT NOT NULL,
    evidence_url       TEXT,
    acquisition_method TEXT,
    captured_at        TIMESTAMPTZ,
    ingested_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS domain_year (
    domain        TEXT    NOT NULL REFERENCES domain(domain),
    assigned_year INTEGER NOT NULL CHECK (assigned_year BETWEEN 1996 AND 2001),
    evidence_id   BIGINT  NOT NULL REFERENCES evidence(evidence_id),
    verified_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (domain, assigned_year)
);
"""


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection, creating the parent folder for file paths."""
    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def init_db(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the tables and constraints. Safe to run repeatedly."""
    for statement in filter(str.strip, SCHEMA_SQL.split(";")):
        conn.execute(statement)
