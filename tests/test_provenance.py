"""The provenance export: the archive's answer to "why is this domain in this year?", the
authority the store is rebuilt from, and `trace.py`, the copy the reviewer runs blind."""

import runpy
import sys
from pathlib import Path

import duckdb
import pytest
from his_release import WEB_METHOD, capture

from ark.bulk import ingest_files
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.export import claim_files, export_all
from ark.provenance import TABLES, load_provenance, write_provenance
from ark.sources import SOURCES

URL = "https://web.archive.org/web/19980101000000/http://example.com/"


def _dated(conn: duckdb.DuckDBPyConnection, domain: str, year: int, url: str | None = None) -> int:
    """An assigned exact-host capture of `domain` in `year`, read from record `year` of a file."""
    cdx = ensure_source(conn, "ia_cdx_bulk", "timestamped")
    add_candidate(conn, domain, cdx)
    value = capture(domain, year)
    where = {"source_file": f"cdx-{year}.txt.gz", "record_location": f"record {year}"}
    row = record_evidence(conn, domain, cdx, year, "cdx_timestamp", value, url, WEB_METHOD, **where)
    assign_year(conn, row)
    return row


def _store(his: bool = False) -> duckdb.DuckDBPyConnection:
    """example.com dated 1998. With `his`: his source filed already-his.com and both.com, a row
    of ours dates both.com 1999, a seed file filed seeded-only.com, and each has a verdict."""
    conn = connect(":memory:")
    init_db(conn)
    _dated(conn, "example.com", 1998, URL)
    if his:
        prior = ensure_source(conn, "prior_task", "timestamped")
        add_candidate(conn, "already-his.com", prior)
        add_candidate(conn, "both.com", prior)
        add_candidate(conn, "seeded-only.com", ensure_source(conn, "seed_list", "candidate_only"))
        _dated(conn, "both.com", 1999)
        conn.execute(
            "INSERT INTO domain_language (domain, assigned_year, verdict) "
            "SELECT domain, 1999, 'english' FROM domain"
        )
    return conn


def _parquet(folder: Path, table: str) -> str:
    return f"read_parquet('{folder / table}.parquet')"


def _export(conn: duckdb.DuckDBPyConnection, out: Path, his_files: Path) -> None:
    export_all(
        conn,
        netnew_dir=out / "netnew",
        candidates_path=out / "cand.txt",
        report_dir=out / "reports",
        provenance_dir=out / "prov",
        baseline=his_files,
        with_provenance=True,
    )


def test_every_table_ships_with_its_load_line_and_the_reload_still_joins(tmp_path) -> None:
    conn = _store()
    counts = write_provenance(conn, tmp_path)
    load = (tmp_path / "LOAD.sql").read_text()
    reader = duckdb.connect()
    for table in TABLES:
        assert f"{table}.parquet" in load, table
        reader.execute(f"CREATE TABLE {table} AS SELECT * FROM {_parquet(tmp_path, table)}")
        # the count is the rows COPY wrote
        assert counts[table] == reader.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    # a reader with only this folder rebuilds the graph, the reason it is not a list of pairs
    traced = reader.execute(
        """
        SELECT s.name, e.evidence_type, e.evidence_value, e.source_file, e.record_location
        FROM domain_year dy
        JOIN evidence e ON e.evidence_id = dy.evidence_id
        JOIN source s ON s.source_id = e.source_id
        WHERE dy.domain = 'example.com' AND dy.assigned_year = 1998
        """
    ).fetchall()
    value = capture("example.com", 1998)
    assert traced == [("ia_cdx_bulk", "cdx_timestamp", value, "cdx-1998.txt.gz", "record 1998")]


def test_the_export_ships_our_rows_whole_and_only_the_names_we_know(tmp_path) -> None:
    """A name his source filed and no row of ours names is his, and neither it nor a verdict on
    it ships; a name a seed file filed is ours before any evidence names it."""
    conn = _store(his=True)
    counts = write_provenance(conn, tmp_path)
    reader = duckdb.connect()
    for table in ("domain", "domain_language"):
        names = reader.execute(f"SELECT domain FROM {_parquet(tmp_path, table)} ORDER BY 1")
        assert [d for (d,) in names.fetchall()] == ["both.com", "example.com", "seeded-only.com"]
        assert counts[table] == 3
    for table in ("evidence", "domain_year", "source"):
        assert counts[table] == conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def test_the_load_keeps_every_key_and_value_and_the_store_takes_new_rows(tmp_path) -> None:
    """A rebuilt store is the schema's, not a copy of the Parquet's columns: its keys, CHECKs,
    NOT NULLs and defaults stand, so an ingest can write it. Every row comes back with every
    value it shipped with, `ingested_at` included, and each sequence goes on past the ids the
    export holds, so no id is issued twice."""
    conn = connect(":memory:")
    conn.execute("CREATE SEQUENCE evidence_seq START WITH 500")
    init_db(conn)
    for year in (1997, 1998):
        _dated(conn, "example.com", year)
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
    assert {t for t, kind in constraints if kind == "PRIMARY KEY"} == set(TABLES) - {"evidence"}
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
    cdx = ensure_source(rebuilt, "ia_cdx_bulk", "timestamped")
    eid = record_evidence(rebuilt, "example.com", cdx, 1999, "cdx_timestamp", "19990101000000")
    assert eid == top + 1
    fresh = "SELECT max(ingested_at) > TIMESTAMPTZ '2020-01-01 00:00:00+00' FROM evidence"
    assert rebuilt.execute(fresh).fetchone() == (True,)
    assert ensure_source(rebuilt, "a_new_source", "timestamped") == cdx + 1
    twice = "INSERT INTO domain_year (domain, assigned_year, evidence_id) VALUES (?, 1998, ?)"
    with pytest.raises(duckdb.ConstraintException):
        rebuilt.execute(twice, ["example.com", eid])
    with pytest.raises(duckdb.ConstraintException):
        record_evidence(rebuilt, "example.com", cdx, 2005, "cdx_timestamp", "20050101000000")


def test_a_rebuilt_store_asks_a_file_and_a_place_only_of_the_rows_it_writes(tmp_path) -> None:
    write_provenance(_store(), tmp_path)
    rebuilt = connect(":memory:")
    load_provenance(rebuilt, tmp_path)
    start = "SELECT start_value FROM duckdb_sequences() WHERE sequence_name = 'located_from'"
    assert rebuilt.execute(start).fetchone() == (2,)


def test_an_older_export_rebuilds_an_older_store_in_place(tmp_path) -> None:
    """An archive written before `source_file` and `record_location`, or before a verdict's
    `engine_version`, loads each missing column as its default or NULL. A store made while
    tables carried foreign keys loses every table, referrers first, as DuckDB requires."""
    conn = _store(his=True)
    conn.execute("UPDATE domain_language SET engine_version = 3, reason = 'r'")
    write_provenance(conn, tmp_path)
    reader = duckdb.connect()
    old = {"evidence": "source_file, record_location", "domain_language": "engine_version"}
    for table, dropped in old.items():
        path = tmp_path / f"{table}.parquet"
        reader.execute(f"CREATE OR REPLACE TABLE t AS SELECT * EXCLUDE ({dropped}) FROM '{path}'")
        reader.execute(f"COPY t TO '{path}'")

    store = connect(":memory:")
    store.execute("CREATE TABLE source (id INT PRIMARY KEY)")
    store.execute("CREATE TABLE domain (domain TEXT PRIMARY KEY, s INT REFERENCES source(id))")
    store.execute("CREATE TABLE evidence (id BIGINT PRIMARY KEY, d TEXT REFERENCES domain(domain))")
    store.execute("CREATE TABLE hostname_year (h TEXT, e BIGINT REFERENCES evidence(id))")
    load_provenance(store, tmp_path)
    fks = "SELECT count(*) FROM duckdb_constraints() WHERE constraint_type = 'FOREIGN KEY'"
    assert store.execute(fks).fetchone() == (0,)
    rows = store.execute("SELECT DISTINCT source_file, record_location FROM evidence")
    assert rows.fetchall() == [(None, None)]
    verdicts = store.execute("SELECT DISTINCT engine_version, reason FROM domain_language")
    assert verdicts.fetchall() == [(0, "r")]


def test_a_provenance_export_rebuilds_the_same_result(tmp_path, his_files) -> None:
    """The reproduction path that needs no source data: a store rebuilt from the export, diffed
    against the same release of his, writes every claim file back byte for byte."""
    first, second = tmp_path / "first", tmp_path / "second"
    conn = _store(his=True)
    for out in (first, second):
        _export(conn, out, his_files)
        # a reader who has only the export rebuilds the store from it, then re-exports
        conn = connect(":memory:")
        load_provenance(conn, out / "prov")
    names = conn.execute("SELECT domain FROM domain ORDER BY 1").fetchall()
    assert [d for (d,) in names] == ["both.com", "example.com", "seeded-only.com"]
    assert (first / "netnew" / "1998.txt").read_text() == "example.com\n"
    assert (first / "netnew" / "1999.txt").read_text() == "both.com\n"
    assert "seeded-only.com" in (first / "cand.txt").read_text().split()
    before, after = (claim_files(out / "netnew", out / "cand.txt") for out in (first, second))
    for a, b in zip(before, after, strict=True):
        assert a.read_bytes() == b.read_bytes(), f"{a.name} differs after rebuild"


def test_every_shipped_evidence_row_names_its_extraction_method(tmp_path, his_files) -> None:
    """The reviewer's per-item extraction method is `evidence.acquisition_method`. The column is
    nullable; the bulk loader stamps it with whatever the source's `SourceSpec` declares."""
    assert [key for key, spec in SOURCES.items() if not spec.acquisition_method] == []
    cdx = tmp_path / "sample.cdx"
    cdx.write_text("com,example)/ 19970601120000 http://example.com:80/ text/html 200 B - - 9 f\n")
    conn = connect(":memory:")
    init_db(conn)
    ingest_files(conn, SOURCES["early_web"], [cdx], report_dir=tmp_path / "reports")
    out = tmp_path / "out"
    _export(conn, out, his_files)
    manifest = f"read_csv_auto('{out}/netnew/evidence_manifest.csv', header = true)"
    for rows in ("evidence", _parquet(out / "prov", "evidence"), manifest):
        methods = conn.execute(f"SELECT list(acquisition_method) FROM {rows}").fetchone()
        assert methods == (["bulk_cdx_file"],), rows


@pytest.fixture
def trace(tmp_path: Path, monkeypatch, capsys):
    """The export's own `trace.py`, run as `__main__` the way the reviewer runs it."""
    conn = _store()
    add_candidate(conn, "candidate.org", ensure_source(conn, "ia_cdx_bulk", "timestamped"))
    write_provenance(conn, tmp_path)

    def run(*args: str) -> str:
        monkeypatch.setattr(sys, "argv", ["trace.py", *args])
        runpy.run_path(str(tmp_path / "trace.py"), run_name="__main__")
        return capsys.readouterr().out

    return run


def test_trace_py_names_the_observation_behind_a_year(trace) -> None:
    # typed carelessly on purpose: `main` is what normalises the name
    out = trace(" Example.COM ", "1998")
    assert out.startswith("example.com\n") and "  1998\n" in out
    row = next(line for line in out.splitlines() if "cdx_timestamp" in line)
    assert "ia_cdx_bulk" in row and capture("example.com", 1998) in row
    assert URL in out


def test_trace_py_summarises_every_table_and_tells_a_candidate_from_a_stranger(trace) -> None:
    out = trace()
    assert out.startswith("Provenance export loaded.")
    # every shipped table, the optional ones included, or the reviewer is told of fewer
    for table in TABLES:
        assert f"  {table:<16}" in out, table
    assert out.rstrip().endswith("python trace.py example.com 1998")
    assert "no year assigned" in trace("candidate.org")
    assert "not in the dataset" in trace("nobody.net", "1998")
