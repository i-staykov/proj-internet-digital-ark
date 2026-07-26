"""Exports: net-new files, manifest, candidates, and merged masters."""

from pathlib import Path

import duckdb

from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.export import export_all


def _populated_db() -> duckdb.DuckDBPyConnection:
    conn = connect(":memory:")
    init_db(conn)
    prior = ensure_source(conn, "prior_task", "timestamped")
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    add_candidate(conn, "base.com", prior)
    assign_year(conn, record_evidence(conn, "base.com", prior, 1997, "prior_reused", "1997.txt"))
    add_candidate(conn, "new.com", cdx)
    assign_year(
        conn, record_evidence(conn, "new.com", cdx, 1997, "cdx_timestamp", "19970101000000")
    )
    add_candidate(conn, "cand.org", cdx)
    return conn


def test_export_all(tmp_path: Path) -> None:
    conn = _populated_db()
    stats = export_all(
        conn,
        netnew_dir=tmp_path / "netnew",
        candidates_path=tmp_path / "candidates.txt",
        masters_dir=tmp_path / "masters",
        report_dir=tmp_path / "reports",
        provenance_dir=tmp_path / "provenance",
    )

    # net-new 1997 holds only the cdx-evidenced domain
    assert (tmp_path / "netnew" / "1997.txt").read_text() == "new.com\n"
    assert stats["netnew_1997"] == 1
    # the merged master holds baseline + addition, deduped and sorted
    assert (tmp_path / "masters" / "1997.txt").read_text() == "base.com\nnew.com\n"
    assert stats["master_1997"] == 2
    # unverified candidates are exported separately
    assert (tmp_path / "candidates.txt").read_text() == "cand.org\n"
    # the manifest carries provenance for net-new pairs only
    manifest = (tmp_path / "netnew" / "evidence_manifest.csv").read_text()
    assert "new.com" in manifest and "base.com" not in manifest
    assert "ia_cdx" in manifest


def test_every_export_destination_is_redirectable(tmp_path: Path) -> None:
    conn = _populated_db()
    export_all(
        conn,
        netnew_dir=tmp_path / "netnew",
        candidates_path=tmp_path / "candidates.txt",
        masters_dir=tmp_path / "masters",
        report_dir=tmp_path / "reports",
        provenance_dir=tmp_path / "provenance",
    )

    # the contribution tables were the one destination not under the caller's
    # control, so running the tests overwrote the real ones with this two-row
    # store; a shipping artifact must not be reachable from a test run
    assert (tmp_path / "reports" / "source_contribution.csv").exists()
    assert (tmp_path / "reports" / "year_growth.csv").exists()
    assert (tmp_path / "provenance" / "evidence.parquet").exists()
    conn.close()


def test_no_export_destination_can_be_missed_by_a_test() -> None:
    """Every Path parameter of `export_all` must be redirectable, and redirected.

    Checking the files this suite happens to know about is not enough: twice now
    a new destination was added with a default pointing at the real delivery
    tree, and the tests overwrote a shipping artifact because nobody passed it.
    First the contribution tables, then the 241 MB provenance export. This
    compares the signature against what the test above actually overrides, so
    the next destination fails here instead of in the archive.
    """
    import inspect

    from ark.export import export_all

    destinations = {
        name
        for name, param in inspect.signature(export_all).parameters.items()
        if isinstance(param.default, Path)
    }
    source = inspect.getsource(test_export_all)
    missed = {name for name in destinations if f"{name}=" not in source}
    assert not missed, f"test_export_all must redirect these: {sorted(missed)}"
