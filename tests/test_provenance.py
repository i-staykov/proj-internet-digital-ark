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


def test_his_own_rows_are_not_shipped_back_to_him(tmp_path) -> None:
    """The reviewer's baseline was 3 GB of a 6.9 GB archive, over his 5 GB limit.

    A `prior_reused` row says only that his own release already holds the pair, so it
    is his own file quoted back at him. Nothing this project claims rests on one:
    `every_pair_has_master_evidence` and the shipped `verify.sh` both hold without them.
    """
    conn = _store()
    prior = ensure_source(conn, "reviewer_baseline", "timestamped")
    add_candidate(conn, "his.com", prior)
    assign_year(conn, record_evidence(conn, "his.com", prior, 1997, "prior_reused", "merged1"))
    counts = write_provenance(conn, tmp_path)

    reader = duckdb.connect(":memory:")
    kinds = reader.execute(
        f"SELECT DISTINCT evidence_type FROM read_parquet('{tmp_path / 'evidence'}.parquet')"
    ).fetchall()
    assert kinds == [("cdx_timestamp",)]
    assert counts["evidence"] == 1

    # **And the assignment goes with it.** An assignment citing an evidence row that is
    # not in the archive is a reference into nothing, and the shipped verify.sh counts
    # exactly those.
    dangling = reader.execute(
        f"""
        SELECT count(*) FROM read_parquet('{tmp_path / "domain_year"}.parquet') dy
        WHERE NOT EXISTS (
            SELECT 1 FROM read_parquet('{tmp_path / "evidence"}.parquet') e
            WHERE e.evidence_id = dy.evidence_id
        )
        """
    ).fetchone()[0]
    assert dangling == 0
    assert counts["domain_year"] == 1
    reader.close()
    conn.close()


def test_an_assignment_we_can_prove_is_re_pointed_and_not_dropped(tmp_path) -> None:
    """His release was ingested first, so pairs we can prove cite his marker anyway.

    Dropping those with his evidence row left 32.4 million of our own observations with
    no assignment on the rebuilt store, which `nothing_earned_is_left_unassigned` reads
    as a domain in the candidate pool that already holds proof of a year.
    """
    conn = _store()
    prior = ensure_source(conn, "reviewer_baseline", "timestamped")
    add_candidate(conn, "both.com", prior)
    # his row lands first, so the assignment points at it
    assign_year(conn, record_evidence(conn, "both.com", prior, 1999, "prior_reused", "merged1"))
    cdx = ensure_source(conn, "ia_cdx_bulk", "timestamped")
    mine = record_evidence(conn, "both.com", cdx, 1999, "cdx_timestamp", "19990101000000")
    counts = write_provenance(conn, tmp_path)

    reader = duckdb.connect(":memory:")
    row = reader.execute(
        f"""
        SELECT evidence_id FROM read_parquet('{tmp_path / "domain_year"}.parquet')
        WHERE domain = 'both.com' AND assigned_year = 1999
        """
    ).fetchone()
    assert row == (mine,), "the assignment should cite our own observation, not his marker"
    assert counts["domain_year"] == 2
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
