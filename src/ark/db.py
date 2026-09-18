"""DuckDB schema, connection, and the only write path into the provenance store.

The schema enforces what it can (an assignment cannot exist without evidence).
The helpers enforce the cross-row rules: every domain passes through
to_registrable(), and a year assignment is derived from its evidence row,
so a mismatched assignment cannot be expressed.
"""

import os
import time
from datetime import datetime
from pathlib import Path

import duckdb
import pyarrow as pa

from ark.canonical import to_registrable
from ark.evidence_types import ALL_TYPES, CANDIDATE_ONLY_TYPES

DEFAULT_DB_PATH = Path("data/ark.duckdb")


# **DuckDB takes 80% of the machine by default, and this store is 52 GB**: one
# `build_round_state.py` at 28 GB resident on a 36 GB laptop, swapping, while `just sync`,
# `just state` and `just cycle` each spawn one. These are aggregations over a few wide
# tables and DuckDB spills to `temp_directory`, so a cap costs disk and no correctness.
# ARK_DB_MEMORY_LIMIT overrides it, the VPS and CI being much smaller.
def _default_memory_limit() -> str:
    """40% of physical memory, floored at 2 GB.

    A fraction, not an absolute: 14GB is right on the 36 GB laptop and absurd on the
    7 GB VPS. The floor keeps CI containers and in-memory test databases working.
    """
    try:
        total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (AttributeError, ValueError, OSError):
        return "4GB"
    return f"{max(2, int(total * 0.4 // 1024**3))}GB"


DB_MEMORY_LIMIT = os.environ.get("ARK_DB_MEMORY_LIMIT") or _default_memory_limit()
# **Two, and not only about the cores.** Peak memory scales with threads and not every
# operator can spill: `build_round_state.py` fails outright at a 10 GB limit with 4
# threads and completes at 14 GB with 2. The limit and the thread count were tested as a
# pair, so do not move one alone.
DB_THREADS = os.environ.get("ARK_DB_THREADS", "2")
DB_TEMP_DIR = os.environ.get("ARK_DB_TEMP_DIR", "data/duckdb_tmp")


def _tune(conn: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    """Apply the memory, thread and spill settings to a fresh connection.

    Failures are ignored deliberately: an unknown setting on an older DuckDB must not
    take down an ingest, and the default behaviour without them is what we had before.
    """
    Path(DB_TEMP_DIR).mkdir(parents=True, exist_ok=True)
    for statement in (
        f"SET memory_limit='{DB_MEMORY_LIMIT}'",
        f"SET threads={DB_THREADS}",
        f"SET temp_directory='{DB_TEMP_DIR}'",
    ):
        try:
            conn.execute(statement)
        except duckdb.Error:
            pass
    return conn


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

-- Hostname records: the reviewer accepts "both registrable domains and valid hostnames
-- as annual database records" (his words, in private/personal-context.md). Same evidence
-- wall as domain_year, and the checks enforce that the hostname reduces to parent_domain
-- and is not itself a bare registrable (those stay in domain_year). Registrables remain
-- the prioritized unit; hostnames ship as separate per-year files.
CREATE TABLE IF NOT EXISTS hostname_year (
    hostname      TEXT    NOT NULL,
    parent_domain TEXT    NOT NULL REFERENCES domain(domain),
    assigned_year INTEGER NOT NULL CHECK (assigned_year BETWEEN 1996 AND 2001),
    evidence_id   BIGINT  NOT NULL REFERENCES evidence(evidence_id),
    verified_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (hostname, assigned_year)
);

CREATE TABLE IF NOT EXISTS ingested_file (
    source_name TEXT NOT NULL,
    file_name   TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    record_rows BIGINT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source_name, file_name)
);

-- Language verification, deliberately NOT an evidence type. `evidence` answers "did this
-- domain exist in this year"; a verdict answers "what was this website", which is
-- orthogonal, and mixing them corrupts the taxonomy MASTER_TYPES, the evidence_type
-- CHECK and four integrity checks depend on. `evidence_urls` names the exact snapshots
-- read, so a reviewer can refetch them and recompute the verdict.
CREATE TABLE IF NOT EXISTS domain_language (
    domain        TEXT    NOT NULL REFERENCES domain(domain),
    assigned_year INTEGER NOT NULL CHECK (assigned_year BETWEEN 1996 AND 2001),
    verdict       TEXT    NOT NULL CHECK (verdict IN ('english', 'other', 'undetermined')),
    english_share DOUBLE,
    samples       INTEGER NOT NULL DEFAULT 0,
    top_other     TEXT,
    evidence_urls TEXT    NOT NULL DEFAULT '',
    reason        TEXT,
    engine_version INTEGER NOT NULL DEFAULT 0,
    classified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (domain, assigned_year)
);
"""

# Columns added after a store already existed. `CREATE TABLE IF NOT EXISTS` does nothing
# to a table already there, so a new column in SCHEMA_SQL reaches fresh stores only.
MIGRATIONS = (
    ("domain_language", "reason", "TEXT"),
    ("domain_language", "engine_version", "INTEGER DEFAULT 0"),
)


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection, creating the parent folder for file paths."""
    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    return _tune(duckdb.connect(str(path)))


def connect_patiently(
    db_path: Path | str = DEFAULT_DB_PATH, patience_s: int = 900
) -> duckdb.DuckDBPyConnection:
    """Wait out a writer instead of crashing against one, for a reporting command.

    For `ark check` and `ark stats`, which need the write lock themselves to record a
    metrics row. ADR-001 puts banking a collector's journal above measuring, so the
    reporting side yields rather than emitting a traceback a scheduled run reads as broken.
    """
    deadline = time.monotonic() + patience_s
    while True:
        try:
            return connect(db_path)
        except duckdb.Error as exc:
            if "Conflicting lock" not in str(exc) or time.monotonic() >= deadline:
                raise
            time.sleep(5)


def connect_read_only_patiently(
    db_path: Path | str = DEFAULT_DB_PATH, patience_s: int = 900
) -> duckdb.DuckDBPyConnection:
    """Read-only, and waits out a writer instead of crashing against one.

    **DuckDB's single writer excludes readers too**, so even a read-only reporting
    command meets the lock every few minutes while the ingest loop banks journals. Use
    this for anything that must not write; `connect_patiently` for the rest.
    """
    deadline = time.monotonic() + patience_s
    while True:
        try:
            return _tune(duckdb.connect(str(Path(db_path)), read_only=True))
        except duckdb.Error as exc:
            if "Conflicting lock" not in str(exc) or time.monotonic() >= deadline:
                raise
            time.sleep(5)


def _statements(schema: str) -> list[str]:
    """Split the schema into statements, ignoring `--` comment lines.

    Comments are stripped BEFORE the split on `;`, or a semicolon inside a comment cuts
    a CREATE TABLE in half and fails with a parser error pointing at prose.
    """
    body = "\n".join(line for line in schema.splitlines() if not line.lstrip().startswith("--"))
    return [statement for statement in body.split(";") if statement.strip()]


def init_db(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the tables and constraints, then migrate. Safe to run repeatedly."""
    for statement in _statements(SCHEMA_SQL):
        conn.execute(statement)
    for table, column, column_type in MIGRATIONS:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {column_type}")


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


def add_candidates(
    conn: duckdb.DuckDBPyConnection,
    domains: list[str],
    source_id: int,
    discovered_round: int = 0,
) -> int:
    """Register many already-canonical domains in ONE set-based statement.

    **Never a Python loop and never `executemany`**, which is N prepared-statement
    executions against a columnar store: on a 4,000,000-row table inserting 13,078,
    `executemany` takes 13.47 s (971 rows/s) against the set-based anti-join from an Arrow
    table at 0.05 s (259,242 rows/s), 267x. That is what held the only write lock for 26
    minutes on a 6,079-name seed.

    **Deduplicate the batch first**: the anti-join tests each row against the TABLE, so two
    identical names inside one batch both pass and collide on the primary key.

    Takes canonical names; the caller has parsed them. An interrupted call keeps nothing.
    """
    if not domains:
        return 0
    unique = list(dict.fromkeys(domains))
    batch = pa.table(
        {
            "domain": unique,
            "tld": [d.split(".", 1)[1] for d in unique],
            "discovered_source": [source_id] * len(unique),
            "discovered_round": [discovered_round] * len(unique),
        }
    )
    conn.register("_candidate_batch", batch)
    try:
        conn.execute(
            "INSERT INTO domain (domain, tld, discovered_source, discovered_round) "
            "SELECT b.domain, b.tld, b.discovered_source, b.discovered_round "
            "FROM _candidate_batch b "
            "WHERE NOT EXISTS (SELECT 1 FROM domain d WHERE d.domain = b.domain)"
        )
    finally:
        conn.unregister("_candidate_batch")
    return len(unique)


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
