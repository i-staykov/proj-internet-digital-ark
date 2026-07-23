"""DuckDB schema, connection, and the only write path into the provenance store.

The schema enforces what it can (an assignment cannot exist without evidence).
The helpers enforce the cross-row rules: every domain passes through
to_registrable(), and a year assignment is derived from its evidence row,
so a mismatched assignment cannot be expressed.
"""

from datetime import datetime
from pathlib import Path

import duckdb

from ark.canonical import to_registrable
from ark.evidence_types import ALL_TYPES, CANDIDATE_ONLY_TYPES

DEFAULT_DB_PATH = Path("data/ark.duckdb")

# the evidence_type CHECK is generated from the taxonomy, so code and schema
# cannot drift apart
_EVIDENCE_TYPE_LIST = ", ".join(f"'{name}'" for name in sorted(ALL_TYPES))

SCHEMA_SQL = f"""
CREATE SEQUENCE IF NOT EXISTS source_seq START 1;

CREATE TABLE IF NOT EXISTS source (
    source_id  INTEGER PRIMARY KEY DEFAULT nextval('source_seq'),
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
    evidence_type      TEXT NOT NULL CHECK (evidence_type IN ({_EVIDENCE_TYPE_LIST})),
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

CREATE TABLE IF NOT EXISTS ingested_file (
    source_name TEXT NOT NULL,
    file_name   TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    record_rows BIGINT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source_name, file_name)
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


def ensure_source(conn: duckdb.DuckDBPyConnection, name: str, kind: str) -> int:
    """Get or create a source by name and return its id.

    A name re-registered with a different kind is refused, so the source
    table can never silently misdescribe a source's semantics.
    """
    row = conn.execute("SELECT source_id, kind FROM source WHERE name = ?", [name]).fetchone()
    if row is not None:
        source_id, existing_kind = row
        if existing_kind != kind:
            raise ValueError(f"source {name} is registered as {existing_kind}, not {kind}")
        return source_id
    return conn.execute(
        "INSERT INTO source (name, kind) VALUES (?, ?) RETURNING source_id",
        [name, kind],
    ).fetchone()[0]


def add_candidate(
    conn: duckdb.DuckDBPyConnection,
    raw: str,
    source_id: int,
    discovered_round: int = 0,
) -> str | None:
    """Canonicalize and register a domain; returns it, or None for garbage input."""
    domain = to_registrable(raw)
    if domain is None:
        return None
    tld = domain.split(".", 1)[1]
    conn.execute(
        "INSERT OR IGNORE INTO domain (domain, tld, discovered_source, discovered_round) "
        "VALUES (?, ?, ?, ?)",
        [domain, tld, source_id, discovered_round],
    )
    return domain


def record_evidence(
    conn: duckdb.DuckDBPyConnection,
    domain: str,
    source_id: int,
    year: int,
    evidence_type: str,
    value: str,
    url: str | None = None,
    acquisition_method: str | None = None,
    captured_at: datetime | None = None,
) -> int:
    """Store one per-year proof for a registered domain and return its id."""
    return conn.execute(
        "INSERT INTO evidence (domain, source_id, evidence_year, evidence_type, "
        "evidence_value, evidence_url, acquisition_method, captured_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING evidence_id",
        [domain, source_id, year, evidence_type, value, url, acquisition_method, captured_at],
    ).fetchone()[0]


def assign_year(conn: duckdb.DuckDBPyConnection, evidence_id: int) -> bool:
    """Assign the (domain, year) named by an evidence row to that year's file.

    Domain and year come from the evidence itself, so an assignment backed by
    the wrong proof cannot be expressed, and candidate-only evidence is
    refused outright (the taxonomy wall). Returns False if already assigned.
    """
    row = conn.execute(
        "SELECT domain, evidence_year, evidence_type FROM evidence WHERE evidence_id = ?",
        [evidence_id],
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown evidence_id: {evidence_id}")
    domain, year, evidence_type = row
    if evidence_type in CANDIDATE_ONLY_TYPES:
        raise ValueError(f"candidate-only evidence ({evidence_type}) cannot assign a year")
    inserted = conn.execute(
        "INSERT OR IGNORE INTO domain_year (domain, assigned_year, evidence_id) "
        "VALUES (?, ?, ?) RETURNING domain",
        [domain, year, evidence_id],
    ).fetchone()
    return inserted is not None
