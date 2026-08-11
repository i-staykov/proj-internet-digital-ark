"""Schema and write helpers: tables exist, the evidence wall holds, rules apply."""

import duckdb
import pytest

from ark.db import (
    add_candidate,
    add_candidates,
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


def test_add_candidates_batches_and_stays_idempotent() -> None:
    """One statement for many names, and re-offering them changes nothing.

    Batched because a row-at-a-time loop over 29,432 names held the store's only
    write lock for more than twenty minutes, which blocks every reader too.
    """
    conn, sid = _db_with_source()
    written = add_candidates(conn, ["a.com", "b.co.uk", "c.org"], sid)
    assert written == 3
    assert conn.execute("SELECT count(*) FROM domain").fetchone()[0] == 3
    # the tld column is the registrable suffix, as add_candidate writes it
    assert conn.execute("SELECT tld FROM domain WHERE domain = 'b.co.uk'").fetchone()[0] == "co.uk"
    # INSERT OR IGNORE, so a second offer is a no-op rather than an error
    add_candidates(conn, ["a.com", "d.net"], sid)
    assert conn.execute("SELECT count(*) FROM domain").fetchone()[0] == 4


def test_add_candidates_on_an_empty_list_touches_nothing() -> None:
    conn, sid = _db_with_source()
    assert add_candidates(conn, [], sid) == 0
    assert conn.execute("SELECT count(*) FROM domain").fetchone()[0] == 0


def test_add_candidates_dedupes_within_one_batch() -> None:
    """`INSERT OR IGNORE` used to absorb an intra-batch duplicate implicitly. The
    set-based form tests each row against the TABLE, so two identical names inside one
    batch would both pass the anti-join and collide on the primary key."""
    conn = connect(":memory:")
    init_db(conn)
    sid = ensure_source(conn, "s", "candidate_only")
    written = add_candidates(conn, ["dup.com", "dup.com", "other.net", "dup.com"], sid)
    assert written == 2
    held = {row[0] for row in conn.execute("SELECT domain FROM domain").fetchall()}
    assert held == {"dup.com", "other.net"}


def test_add_candidates_leaves_an_existing_row_untouched() -> None:
    """The anti-join must reproduce OR IGNORE exactly: an existing domain keeps its
    original source and round rather than being overwritten by a later batch."""
    conn = connect(":memory:")
    init_db(conn)
    first = ensure_source(conn, "first", "candidate_only")
    second = ensure_source(conn, "second", "candidate_only")
    add_candidates(conn, ["keep.com"], first, discovered_round=1)
    add_candidates(conn, ["keep.com", "new.org"], second, discovered_round=7)
    rows = dict(
        conn.execute("SELECT domain, discovered_source FROM domain ORDER BY domain").fetchall()
    )
    assert rows["keep.com"] == first
    assert rows["new.org"] == second
    round_of = dict(conn.execute("SELECT domain, discovered_round FROM domain").fetchall())
    assert round_of["keep.com"] == 1
