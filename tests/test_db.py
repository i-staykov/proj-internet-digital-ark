"""Schema and write helpers: tables exist, the evidence wall holds, rules apply."""

import duckdb
import pytest

from ark.db import (
    add_candidate,
    assign_year,
    connect,
    ensure_source,
    init_db,
    record_evidence,
)


def _fresh_db() -> duckdb.DuckDBPyConnection:
    conn = connect(":memory:")
    init_db(conn)
    return conn


def _db_with_source() -> tuple[duckdb.DuckDBPyConnection, int]:
    conn = _fresh_db()
    return conn, ensure_source(conn, "test_source", "timestamped")


def test_core_tables_exist() -> None:
    conn = _fresh_db()
    tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    assert {"source", "domain", "evidence", "domain_year"} <= tables


def test_year_assignment_requires_evidence() -> None:
    conn, sid = _db_with_source()
    conn.execute("INSERT INTO domain (domain, discovered_source) VALUES ('example.com', ?)", [sid])
    # a year assignment with no evidence must be rejected by the NOT NULL wall
    with pytest.raises(duckdb.Error):
        conn.execute(
            "INSERT INTO domain_year (domain, assigned_year, evidence_id) "
            "VALUES ('example.com', 1998, NULL)"
        )


def test_ensure_source_is_idempotent() -> None:
    conn = _fresh_db()
    first = ensure_source(conn, "wayback_cdx", "timestamped")
    second = ensure_source(conn, "wayback_cdx", "timestamped")
    other = ensure_source(conn, "dmoz_rdf", "candidate_only")
    assert first == second
    assert first != other


def test_add_candidate_canonicalizes_and_dedups() -> None:
    conn, sid = _db_with_source()
    assert add_candidate(conn, "HTTP://WWW.Example.COM/page", sid) == "example.com"
    assert add_candidate(conn, "example.com.", sid) == "example.com"
    count = conn.execute("SELECT count(*) FROM domain").fetchone()[0]
    assert count == 1


def test_add_candidate_rejects_garbage() -> None:
    conn, sid = _db_with_source()
    assert add_candidate(conn, "$b#m#e#m#b#e#r.ne.jp", sid) is None
    assert conn.execute("SELECT count(*) FROM domain").fetchone()[0] == 0


def test_record_evidence_requires_registered_domain() -> None:
    conn, sid = _db_with_source()
    with pytest.raises(duckdb.Error):
        record_evidence(conn, "never-added.com", sid, 1997, "cdx_timestamp", "19970412093015")


def test_assign_year_derives_from_evidence() -> None:
    conn, sid = _db_with_source()
    domain = add_candidate(conn, "example.com", sid)
    eid = record_evidence(conn, domain, sid, 1997, "cdx_timestamp", "19970412093015")
    assert assign_year(conn, eid) is True
    # idempotent: the same (domain, year) is not added twice
    assert assign_year(conn, eid) is False
    rows = conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall()
    assert rows == [("example.com", 1997)]


def test_assign_year_rejects_unknown_evidence() -> None:
    conn, _ = _db_with_source()
    with pytest.raises(ValueError, match="unknown evidence_id"):
        assign_year(conn, 424242)


def test_assign_year_refuses_candidate_only_evidence() -> None:
    conn, sid = _db_with_source()
    domain = add_candidate(conn, "linked.com", sid)
    eid = record_evidence(conn, domain, sid, 1999, "link_target", "graph-row")
    # the taxonomy wall: candidate-only evidence can never reach domain_year
    with pytest.raises(ValueError, match="candidate-only"):
        assign_year(conn, eid)
    assert conn.execute("SELECT count(*) FROM domain_year").fetchone()[0] == 0


def test_ensure_source_refuses_kind_change() -> None:
    conn = _fresh_db()
    ensure_source(conn, "some_source", "timestamped")
    with pytest.raises(ValueError, match="registered as timestamped"):
        ensure_source(conn, "some_source", "candidate_only")
