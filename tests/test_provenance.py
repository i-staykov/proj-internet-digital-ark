"""The provenance export: the archive's answer to "why is this domain in this year?"."""

import duckdb

from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.provenance import TABLES, write_provenance


def _store() -> duckdb.DuckDBPyConnection:
    conn = connect(":memory:")
    init_db(conn)
    cdx = ensure_source(conn, "ia_cdx_bulk", "timestamped")
    add_candidate(conn, "example.com", cdx)
    assign_year(
        conn, record_evidence(conn, "example.com", cdx, 1998, "cdx_timestamp", "19980101000000")
    )
    return conn


def test_every_provenance_table_is_exported(tmp_path) -> None:
    conn = _store()
    counts = write_provenance(conn, tmp_path)
    for table in TABLES:
        assert (tmp_path / f"{table}.parquet").exists(), table
        assert table in counts
    conn.close()


def test_the_export_reloads_and_still_joins(tmp_path) -> None:
    conn = _store()
    write_provenance(conn, tmp_path)
    conn.close()

    # a reader with only this folder must be able to rebuild the graph, which is
    # the whole reason the export exists rather than a flat list of pairs
    reader = duckdb.connect(":memory:")
    for table in TABLES:
        reader.execute(
            f"CREATE TABLE {table} AS SELECT * FROM read_parquet('{tmp_path / table}.parquet')"
        )
    traced = reader.execute(
        """
        SELECT s.name, e.evidence_type, e.evidence_value
        FROM domain_year dy
        JOIN evidence e ON e.evidence_id = dy.evidence_id
        JOIN source s ON s.source_id = e.source_id
        WHERE dy.domain = 'example.com' AND dy.assigned_year = 1998
        """
    ).fetchall()
    assert traced == [("ia_cdx_bulk", "cdx_timestamp", "19980101000000")]
    reader.close()


def test_the_load_instructions_ship_next_to_the_data(tmp_path) -> None:
    conn = _store()
    write_provenance(conn, tmp_path)
    load = (tmp_path / "LOAD.sql").read_text()
    # the instructions name every table, so following them cannot leave a gap
    for table in TABLES:
        assert f"{table}.parquet" in load
    conn.close()


def test_a_provenance_export_rebuilds_the_same_result(tmp_path) -> None:
    """The export must regenerate the deliverable, not merely describe it.

    This is the reproduction path that needs no source data, so it has to
    produce the same files. Measured on the shipped export, all thirteen result
    files come back byte-identical in about six seconds.
    """
    from ark.export import export_all
    from ark.provenance import load_provenance

    conn = _store()
    first = tmp_path / "first"
    export_all(
        conn,
        netnew_dir=first / "netnew",
        candidates_path=first / "cand.txt",
        masters_dir=first / "masters",
        report_dir=first / "reports",
        provenance_dir=first / "prov",
    )
    conn.close()

    # a reader who has only the export rebuilds the store from it, then re-exports
    rebuilt = duckdb.connect(":memory:")
    load_provenance(rebuilt, first / "prov")
    second = tmp_path / "second"
    export_all(
        rebuilt,
        netnew_dir=second / "netnew",
        candidates_path=second / "cand.txt",
        masters_dir=second / "masters",
        report_dir=second / "reports",
        provenance_dir=second / "prov",
    )
    rebuilt.close()

    for year in (1996, 1997, 1998, 1999, 2000, 2001):
        for kind in ("netnew", "masters"):
            a, b = first / kind / f"{year}.txt", second / kind / f"{year}.txt"
            assert a.read_bytes() == b.read_bytes(), f"{kind}/{year}.txt differs after rebuild"
    assert (first / "cand.txt").read_bytes() == (second / "cand.txt").read_bytes()
