"""Schema: the core tables get created and the evidence wall holds."""

import duckdb
import pytest

from ark.db import connect, init_db


def _fresh_db() -> duckdb.DuckDBPyConnection:
    conn = connect(":memory:")
    init_db(conn)
    return conn


def test_core_tables_exist() -> None:
    conn = _fresh_db()
    tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    assert {"source", "domain", "evidence", "domain_year"} <= tables


def test_year_assignment_requires_evidence() -> None:
    conn = _fresh_db()
    conn.execute("INSERT INTO source VALUES (1, 'test', 'timestamped', NULL)")
    conn.execute("INSERT INTO domain (domain, discovered_source) VALUES ('example.com', 1)")
    # a year assignment with no evidence must be rejected by the NOT NULL wall
    with pytest.raises(duckdb.Error):
        conn.execute(
            "INSERT INTO domain_year (domain, assigned_year, evidence_id) "
            "VALUES ('example.com', 1998, NULL)"
        )
