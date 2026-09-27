"""The provenance export: the archive's answer to "why is this domain in this year?", and the
authority the store is rebuilt from."""

from pathlib import Path

import duckdb
import pytest
from his_release import WEB_METHOD, capture

from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.provenance import TABLES, load_provenance, write_provenance


def _store() -> duckdb.DuckDBPyConnection:
    conn = connect(":memory:")
    init_db(conn)
    cdx = ensure_source(conn, "ia_cdx_bulk", "timestamped")
    add_candidate(conn, "example.com", cdx)
    value = capture("example.com", 1998)
    assign_year(
        conn,
        record_evidence(
            conn,
            "example.com",
            cdx,
            1998,
            "cdx_timestamp",
            value,
            acquisition_method=WEB_METHOD,
            source_file="cdx-1998.txt.gz",
            record_location="record 1",
        ),
    )
    return conn


def _with_his_names(conn: duckdb.DuckDBPyConnection) -> None:
    """His source filed two names: one only he gives us, one a row of ours also names. A seed
    file filed a third with no evidence yet. Each of the three has a language verdict."""
    his = ensure_source(conn, "prior_task", "timestamped")
    seed = ensure_source(conn, "seed_list", "candidate_only")
    cdx = ensure_source(conn, "ia_cdx_bulk", "timestamped")
    add_candidate(conn, "already-his.com", his)
    add_candidate(conn, "both.com", his)
    add_candidate(conn, "seeded-only.com", seed)
    assign_year(
        conn,
        record_evidence(
            conn,
            "both.com",
            cdx,
            1999,
            "cdx_timestamp",
            capture("both.com", 1999),
            acquisition_method=WEB_METHOD,
            source_file="cdx-1999.txt.gz",
            record_location="record 4",
        ),
    )
    for name in ("already-his.com", "both.com", "seeded-only.com", "example.com"):
        conn.execute(
            "INSERT INTO domain_language (domain, assigned_year, verdict) "
            "VALUES (?, 1999, 'english')",
            [name],
        )


def _parquet(folder: Path, table: str) -> str:
    return f"read_parquet('{folder / table}.parquet')"


def test_every_provenance_table_is_exported(tmp_path) -> None:
    conn = _store()
    counts = write_provenance(conn, tmp_path)
    reader = duckdb.connect()
    for table in TABLES:
        assert (tmp_path / f"{table}.parquet").exists(), table
        # the count is the rows COPY wrote
        rows = reader.execute(f"SELECT count(*) FROM {_parquet(tmp_path, table)}").fetchone()[0]
        assert counts[table] == rows, table
    conn.close()


def test_the_export_reloads_and_still_joins(tmp_path) -> None:
    conn = _store()
    write_provenance(conn, tmp_path)
    conn.close()

    # a reader with only this folder must be able to rebuild the graph, which is
    # the whole reason the export exists rather than a flat list of pairs
    reader = duckdb.connect(":memory:")
    for table in TABLES:
        reader.execute(f"CREATE TABLE {table} AS SELECT * FROM {_parquet(tmp_path, table)}")
    traced = reader.execute(
        """
        SELECT s.name, e.evidence_type, e.evidence_value, e.source_file, e.record_location
        FROM domain_year dy
        JOIN evidence e ON e.evidence_id = dy.evidence_id
        JOIN source s ON s.source_id = e.source_id
        WHERE dy.domain = 'example.com' AND dy.assigned_year = 1998
        """
    ).fetchall()
    assert traced == [
        (
            "ia_cdx_bulk",
            "cdx_timestamp",
            capture("example.com", 1998),
            "cdx-1998.txt.gz",
            "record 1",
        )
    ]
    reader.close()


def test_the_export_ships_our_rows_whole_and_only_the_names_we_know(tmp_path) -> None:
    """The store holds only our rows, so evidence and assignments ship whole. A name his source
    filed and no row of ours names is his, not ours, and neither it nor a verdict on it ships;
    a name a seed file filed is ours before any evidence names it."""
    conn = _store()
    _with_his_names(conn)
    counts = write_provenance(conn, tmp_path)

    reader = duckdb.connect()
    names = reader.execute(f"SELECT domain FROM {_parquet(tmp_path, 'domain')} ORDER BY 1")
    assert [d for (d,) in names.fetchall()] == ["both.com", "example.com", "seeded-only.com"]
    verdicts = reader.execute(
        f"SELECT domain FROM {_parquet(tmp_path, 'domain_language')} ORDER BY 1"
    ).fetchall()
    assert [d for (d,) in verdicts] == ["both.com", "example.com", "seeded-only.com"]
    for table in ("evidence", "domain_year", "source"):
        stored = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        assert counts[table] == stored, table
    assert counts["domain"] == 3 and counts["domain_language"] == 3
    reader.close()
    conn.close()


def test_the_load_instructions_ship_next_to_the_data(tmp_path) -> None:
    conn = _store()
    write_provenance(conn, tmp_path)
    load = (tmp_path / "LOAD.sql").read_text()
    # the instructions name every table, so following them cannot leave a gap
    for table in TABLES:
        assert f"{table}.parquet" in load
    conn.close()


def test_the_load_keeps_every_key_and_value_and_the_store_takes_new_rows(tmp_path) -> None:
    """A rebuilt store is the schema's, not a copy of the Parquet's columns: its keys, CHECKs,
    NOT NULLs and defaults stand, so an ingest can write it. Every row comes back with every
    value it shipped with, `ingested_at` included, and each sequence goes on past the ids the
    export holds, so no id is issued twice."""
    conn = connect(":memory:")
    conn.execute("CREATE SEQUENCE evidence_seq START WITH 500")
    init_db(conn)
    cdx = ensure_source(conn, "ia_cdx_bulk", "timestamped")
    add_candidate(conn, "example.com", cdx)
    for year in (1997, 1998):
        assign_year(
            conn,
            record_evidence(
                conn,
                "example.com",
                cdx,
                year,
                "cdx_timestamp",
                capture("example.com", year),
                acquisition_method=WEB_METHOD,
                source_file="cdx.txt.gz",
                record_location=f"record {year}",
            ),
        )
    conn.execute("UPDATE evidence SET ingested_at = TIMESTAMPTZ '1999-12-31 23:59:59.123456+00'")
    first = tmp_path / "first"
    write_provenance(conn, first)
    conn.close()

    rebuilt = connect(":memory:")
    counts = load_provenance(rebuilt, first)
    assert counts["evidence"] == 2 and counts["domain_year"] == 2

    constraints = rebuilt.execute(
        "SELECT table_name, constraint_type FROM duckdb_constraints() "
        "WHERE constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')"
    ).fetchall()
    assert {t for t, kind in constraints if kind == "PRIMARY KEY"} == {
        "source",
        "domain",
        "domain_year",
        "hostname_year",
        "ingested_file",
        "domain_language",
    }
    assert not [c for c in constraints if c[1] == "FOREIGN KEY"]

    # every row, every value: the rebuilt store exports what it was loaded from
    second = tmp_path / "second"
    write_provenance(rebuilt, second)
    reader = duckdb.connect()
    for table in TABLES:
        a, b = _parquet(first, table), _parquet(second, table)
        for x, y in ((a, b), (b, a)):
            diff = reader.execute(f"SELECT count(*) FROM (FROM {x} EXCEPT ALL FROM {y})")
            assert diff.fetchone()[0] == 0, table
    kept = rebuilt.execute("SELECT DISTINCT epoch_us(ingested_at) FROM evidence").fetchall()
    assert kept == [(946684799123456,)]

    # the ids go on from the export's, and the defaults fill what a writer leaves out
    top = rebuilt.execute("SELECT max(evidence_id) FROM evidence").fetchone()[0]
    assert top == 501
    eid = record_evidence(rebuilt, "example.com", cdx, 1999, "cdx_timestamp", "19990101000000")
    assert eid == top + 1
    fresh = rebuilt.execute(
        "SELECT ingested_at > TIMESTAMPTZ '2020-01-01 00:00:00+00' FROM evidence "
        "WHERE evidence_id = ?",
        [eid],
    ).fetchone()
    assert fresh == (True,)
    assert ensure_source(rebuilt, "a_new_source", "timestamped") == cdx + 1
    with pytest.raises(duckdb.ConstraintException):
        rebuilt.execute(
            "INSERT INTO domain_year (domain, assigned_year, evidence_id) "
            "VALUES ('example.com', 1998, ?)",
            [eid],
        )
    with pytest.raises(duckdb.ConstraintException):
        record_evidence(rebuilt, "example.com", cdx, 2005, "cdx_timestamp", "20050101000000")
    rebuilt.close()


def test_a_later_start_is_kept_and_an_earlier_one_never_reissues_an_id(tmp_path) -> None:
    conn = _store()
    write_provenance(conn, tmp_path)
    conn.close()
    for asked, expected in ((1000, 1000), (1, 2)):
        rebuilt = connect(":memory:")
        load_provenance(rebuilt, tmp_path, starts={"evidence_seq": asked})
        assert rebuilt.execute("SELECT nextval('evidence_seq')").fetchone() == (expected,)
        start = rebuilt.execute(
            "SELECT start_value FROM duckdb_sequences() WHERE sequence_name = 'evidence_seq'"
        ).fetchone()
        assert start == (expected,)
        rebuilt.close()


def test_an_export_from_before_the_columns_loads_them_empty(tmp_path) -> None:
    """An archive written before `source_file` and `record_location`, or before a verdict's
    `engine_version`, still rebuilds: the missing column loads as its default or NULL."""
    conn = _store()
    conn.execute(
        "INSERT INTO domain_language (domain, assigned_year, verdict, engine_version) "
        "VALUES ('example.com', 1998, 'english', 3)"
    )
    write_provenance(conn, tmp_path)
    conn.close()
    reader = duckdb.connect()
    for table, dropped in (
        ("evidence", "source_file, record_location"),
        ("domain_language", "engine_version"),
    ):
        old = tmp_path / f"{table}.old.parquet"
        reader.execute(
            f"COPY (SELECT * EXCLUDE ({dropped}) FROM {_parquet(tmp_path, table)}) TO '{old}'"
        )
        old.replace(tmp_path / f"{table}.parquet")
    reader.close()

    rebuilt = connect(":memory:")
    load_provenance(rebuilt, tmp_path)
    assert rebuilt.execute(
        "SELECT domain, source_file, record_location FROM evidence"
    ).fetchall() == [("example.com", None, None)]
    assert rebuilt.execute("SELECT engine_version FROM domain_language").fetchall() == [(0,)]
    rebuilt.close()


def test_a_store_that_still_has_foreign_keys_is_rebuilt_in_place(tmp_path) -> None:
    """The store before the rebuild may be one made while tables carried foreign keys; DuckDB
    drops a referenced table only after its referrers, so every table goes, referrers first."""
    conn = _store()
    write_provenance(conn, tmp_path)
    conn.close()
    old = connect(":memory:")
    old.execute("CREATE TABLE source (source_id INTEGER PRIMARY KEY, name TEXT)")
    old.execute(
        "CREATE TABLE domain (domain TEXT PRIMARY KEY, "
        "discovered_source INTEGER REFERENCES source(source_id))"
    )
    old.execute(
        "CREATE TABLE evidence (evidence_id BIGINT PRIMARY KEY, "
        "domain TEXT REFERENCES domain(domain))"
    )
    old.execute(
        "CREATE TABLE domain_year (domain TEXT REFERENCES domain(domain), assigned_year INT, "
        "evidence_id BIGINT REFERENCES evidence(evidence_id), PRIMARY KEY (domain, assigned_year))"
    )
    old.execute(
        "CREATE TABLE hostname_year (hostname TEXT, parent_domain TEXT REFERENCES domain(domain),"
        " assigned_year INT, evidence_id BIGINT REFERENCES evidence(evidence_id))"
    )
    load_provenance(old, tmp_path)
    fks = old.execute(
        "SELECT count(*) FROM duckdb_constraints() WHERE constraint_type = 'FOREIGN KEY'"
    ).fetchone()
    assert fks == (0,)
    assert old.execute("SELECT domain FROM evidence").fetchall() == [("example.com",)]
    old.close()


def test_a_provenance_export_rebuilds_the_same_result(tmp_path, his_files) -> None:
    """The export must regenerate the deliverable, not merely describe it. This is the
    reproduction path that needs no source data: a store rebuilt from the export, diffed
    against the same release of his, writes every claim file back byte for byte.
    """
    from ark.export import claim_files, export_all

    conn = _store()
    _with_his_names(conn)
    first = tmp_path / "first"
    export_all(
        conn,
        netnew_dir=first / "netnew",
        candidates_path=first / "cand.txt",
        report_dir=first / "reports",
        provenance_dir=first / "prov",
        baseline=his_files,
        with_provenance=True,
    )
    conn.close()

    # a reader who has only the export rebuilds the store from it, then re-exports
    rebuilt = connect(":memory:")
    load_provenance(rebuilt, first / "prov")
    names = rebuilt.execute("SELECT domain FROM domain ORDER BY 1").fetchall()
    assert [d for (d,) in names] == ["both.com", "example.com", "seeded-only.com"]
    second = tmp_path / "second"
    export_all(
        rebuilt,
        netnew_dir=second / "netnew",
        candidates_path=second / "cand.txt",
        report_dir=second / "reports",
        provenance_dir=second / "prov",
        baseline=his_files,
        with_provenance=True,
    )
    rebuilt.close()

    assert (first / "netnew" / "1998.txt").read_text() == "example.com\n"
    assert (first / "netnew" / "1999.txt").read_text() == "both.com\n"
    assert "seeded-only.com" in (first / "cand.txt").read_text().split()
    before, after = (claim_files(out / "netnew", out / "cand.txt") for out in (first, second))
    for a, b in zip(before, after, strict=True):
        assert a.read_bytes() == b.read_bytes(), f"{a.name} differs after rebuild"
