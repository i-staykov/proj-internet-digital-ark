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


def test_evidence_has_no_key_no_table_a_foreign_key_and_the_rest_keep_theirs() -> None:
    """`evidence` carries no index for DuckDB to hold while it writes, and no table a foreign
    key; `ark check` asserts those walls instead. The keys `INSERT OR IGNORE` relies on stay,
    and the type CHECK refuses his `prior_reused`."""
    conn, sid = _db_with_source()
    constraints = conn.execute(
        "SELECT table_name, constraint_type FROM duckdb_constraints() "
        "WHERE constraint_type IN ('PRIMARY KEY', 'UNIQUE', 'FOREIGN KEY')"
    ).fetchall()
    assert not [c for c in constraints if c[1] == "FOREIGN KEY"]
    keyed = {table for table, kind in constraints if kind == "PRIMARY KEY"}
    assert keyed == {
        "source",
        "domain",
        "domain_year",
        "hostname_year",
        "ingested_file",
        "domain_language",
    }
    assert not [c for c in constraints if c[0] == "evidence"]
    # no key, so two rows may share an id; `evidence_id_unique` is what refuses it
    for _ in range(2):
        conn.execute(
            "INSERT INTO evidence (evidence_id, domain, source_id, evidence_year, "
            "evidence_type, evidence_value) VALUES (7, 'nowhere.com', 99, 1998, "
            "'cdx_timestamp', '19980101000000')"
        )
    assert conn.execute("SELECT count(*) FROM evidence WHERE evidence_id = 7").fetchone() == (2,)
    with pytest.raises(duckdb.ConstraintException):
        record_evidence(conn, "example.com", sid, 1998, "prior_reused", "1998.txt")


def test_record_evidence_names_the_file_and_the_place_in_it() -> None:
    conn, sid = _db_with_source()
    domain = add_candidate(conn, "example.com", sid)
    eid = record_evidence(
        conn,
        domain,
        sid,
        1998,
        "cdx_timestamp",
        "cdx capture 19980101000000 example.com",
        source_file="cdx-1998.txt.gz",
        record_location="record 12",
    )
    row = conn.execute(
        "SELECT source_file, record_location FROM evidence WHERE evidence_id = ?", [eid]
    ).fetchone()
    assert row == ("cdx-1998.txt.gz", "record 12")
    # keyword-only, so no existing positional call can land a value in them
    with pytest.raises(TypeError):
        record_evidence(conn, domain, sid, 1998, "cdx_timestamp", "v", None, None, None, "f.gz")
    unnamed = record_evidence(conn, domain, sid, 1999, "cdx_timestamp", "19990101000000")
    assert conn.execute(
        "SELECT source_file, record_location FROM evidence WHERE evidence_id = ?", [unnamed]
    ).fetchone() == (None, None)


def test_an_older_store_gains_both_columns_and_keeps_its_rows() -> None:
    """A store made before the columns, keys and foreign keys included: `init_db` adds both
    columns last, empty on the rows it holds, and the store takes a row naming its file."""
    conn = connect(":memory:")
    conn.execute(
        "CREATE TABLE source (source_id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, "
        "kind TEXT NOT NULL, notes TEXT)"
    )
    conn.execute(
        "CREATE TABLE domain (domain TEXT PRIMARY KEY, tld TEXT, discovered_source INTEGER "
        "NOT NULL REFERENCES source(source_id), discovered_round INTEGER NOT NULL DEFAULT 0, "
        "first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    conn.execute("CREATE SEQUENCE evidence_seq START 1")
    conn.execute(
        "CREATE TABLE evidence (evidence_id BIGINT PRIMARY KEY DEFAULT nextval('evidence_seq'), "
        "domain TEXT NOT NULL REFERENCES domain(domain), source_id INTEGER NOT NULL "
        "REFERENCES source(source_id), evidence_year INTEGER NOT NULL, evidence_type TEXT NOT "
        "NULL, evidence_value TEXT NOT NULL, evidence_url TEXT, acquisition_method TEXT, "
        "captured_at TIMESTAMPTZ, ingested_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    conn.execute(
        "CREATE TABLE domain_year (domain TEXT NOT NULL REFERENCES domain(domain), "
        "assigned_year INTEGER NOT NULL, evidence_id BIGINT NOT NULL REFERENCES "
        "evidence(evidence_id), verified_at TIMESTAMPTZ NOT NULL DEFAULT now(), "
        "PRIMARY KEY (domain, assigned_year))"
    )
    conn.execute("INSERT INTO source VALUES (1, 'wayback_cdx', 'timestamped', NULL)")
    conn.execute("INSERT INTO domain (domain, tld, discovered_source) VALUES ('old.com', 'com', 1)")
    conn.execute(
        "INSERT INTO evidence (domain, source_id, evidence_year, evidence_type, evidence_value) "
        "VALUES ('old.com', 1, 1997, 'cdx_timestamp', '19970101000000')"
    )
    conn.execute(
        "INSERT INTO domain_year (domain, assigned_year, evidence_id) VALUES ('old.com', 1997, 1)"
    )

    init_db(conn)
    columns = [
        c
        for (c,) in conn.execute(
            "SELECT column_name FROM duckdb_columns() WHERE table_name = 'evidence' "
            "ORDER BY column_index"
        ).fetchall()
    ]
    assert columns[-2:] == ["source_file", "record_location"]
    assert conn.execute(
        "SELECT domain, evidence_value, source_file, record_location FROM evidence"
    ).fetchall() == [("old.com", "19970101000000", None, None)]
    eid = record_evidence(
        conn,
        "old.com",
        1,
        1998,
        "cdx_timestamp",
        "19980101000000",
        source_file="cdx-1998.txt.gz",
        record_location="record 3",
    )
    assert eid == 2
    assert conn.execute(
        "SELECT source_file, record_location FROM evidence WHERE evidence_id = 2"
    ).fetchone() == ("cdx-1998.txt.gz", "record 3")


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
    """One statement for many names, and re-offering them changes nothing. Batched because a
    row-at-a-time loop over 29,432 names held the store's only write lock for more than
    twenty minutes, which blocks every reader too.
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


def test_read_only_patient_connect_waits_out_a_writer(tmp_path, monkeypatch):
    """A reporting command must queue behind the ingest loop, not crash into it. DuckDB's
    single writer excludes readers too, so anything that opens the store read-only meets
    the lock every few minutes while journals are being banked.
    """
    import duckdb

    from ark.db import connect_read_only_patiently

    calls = {"n": 0}
    real = duckdb.connect

    def flaky(path, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise duckdb.IOException("IO Error: Conflicting lock is held in ...")
        return real(path, **kwargs)

    store = tmp_path / "s.duckdb"
    real(str(store)).close()
    monkeypatch.setattr(duckdb, "connect", flaky)
    monkeypatch.setattr("time.sleep", lambda _s: None)
    conn = connect_read_only_patiently(store, patience_s=60)
    assert calls["n"] == 3
    conn.close()


def test_read_only_patient_connect_reraises_anything_that_is_not_the_lock(tmp_path, monkeypatch):
    """Patience is for the lock alone. A corrupt file must fail immediately, or a real
    fault turns into a fifteen-minute silence."""
    import duckdb
    import pytest

    from ark.db import connect_read_only_patiently

    def broken(path, **kwargs):
        raise duckdb.IOException("IO Error: file is not a valid DuckDB database")

    monkeypatch.setattr(duckdb, "connect", broken)
    with pytest.raises(duckdb.IOException, match="not a valid"):
        connect_read_only_patiently(tmp_path / "x.duckdb", patience_s=60)


def test_every_store_opener_is_capped_and_ark_check_writes_nothing(tmp_path, monkeypatch) -> None:
    """**DuckDB takes 80% of the machine unless told otherwise**, and the store is tens of GB,
    so every opener goes through `ark.db` for the cap. `ark check` is a reader: it moves
    neither the store file nor its metrics rows.
    """
    import importlib.util
    import os
    import subprocess
    import sys
    from pathlib import Path

    from typer.testing import CliRunner

    import ark.db
    from ark.cli import app
    from ark.metrics import record_metrics

    probe = "import ark.db; print(ark.db.DB_MEMORY_LIMIT)"
    env = {**os.environ, "ARK_DB_MEMORY_LIMIT": "3GiB"}
    done = subprocess.run(
        [sys.executable, "-c", probe], env=env, capture_output=True, text=True, check=True
    )
    assert done.stdout.strip() == "3GiB"

    # DuckDB reads the limit back rounded, so the expected value is its own readback
    raw = duckdb.connect(":memory:")
    raw.execute("SET memory_limit='3GiB'")
    expected = raw.execute("SELECT current_setting('memory_limit')").fetchone()[0]
    raw.close()
    monkeypatch.setattr(ark.db, "DB_MEMORY_LIMIT", "3GiB")
    seen = []
    real = ark.db._tune

    def spy(conn):
        conn = real(conn)
        seen.append(conn.execute("SELECT current_setting('memory_limit')").fetchone()[0])
        return conn

    monkeypatch.setattr(ark.db, "_tune", spy)

    monkeypatch.chdir(tmp_path)
    store = tmp_path / "data/ark.duckdb"
    conn = ark.db.connect(store)
    init_db(conn)
    record_metrics(conn, "seed", "fixture", {})
    conn.close()

    # Each script gets the tmp store: its own STORE sits under the live data/.
    scripts = Path(__file__).resolve().parents[1] / "scripts"

    def load(rel: str):
        spec = importlib.util.spec_from_file_location(Path(rel).stem, scripts / rel)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    audit_residual = load("harness/audit_residual.py")
    price_items = load("pricing/price_items.py")
    ack_journals = load("harness/ack_journals.py")
    fleet_findings = load("harness/fleet_findings.py")
    monkeypatch.setattr(price_items, "STORE", store)

    # one at a time: a read-write open fails while a read-only one lives in this process
    ark.db.connect_patiently(store).close()
    ark.db.connect_read_only_patiently(store).close()
    audit_residual.read_only_store(store).close()
    price_items.read_only_store().close()
    assert ack_journals.acks(store) == []
    assert fleet_findings.ingested(store) == set()

    st = store.stat()
    before = (st.st_size, st.st_mtime_ns)
    result = CliRunner().invoke(app, ["check"])
    assert result.exit_code == 0 and "ALL PASS" in result.output, result.output
    st = store.stat()
    assert (st.st_size, st.st_mtime_ns) == before
    reader = duckdb.connect(str(store), read_only=True)
    assert reader.execute("SELECT command FROM run_metrics").fetchall() == [("seed",)]
    reader.close()

    assert len(seen) == 8 and set(seen) == {expected}, seen
    for rel in (
        "harness/audit_residual.py",
        "harness/ack_journals.py",
        "pricing/price_items.py",
        "round/lead_queue.py",
        "harness/fleet_findings.py",
        "round/package_delivery.sh",
    ):
        assert "duckdb.connect(" not in (scripts / rel).read_text(encoding="utf-8"), rel
