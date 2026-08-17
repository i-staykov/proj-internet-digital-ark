"""The residual auditor: the two checks that have to fire on a real defect.

Loaded by path, like the other script tests: `scripts/` is not a package.

The pair of checks is the point. `unread` catches a glob matching files the
ledger has never read, which is the 496-shard case worth 14,956 equivalent-English.
`glob_too_narrow` catches the opposite, a file the ledger holds that the documented
glob cannot reach, which loses nothing now and makes `just reproduce` rebuild a
store missing it later. A tool that found only one of the two would read as clean
in exactly the case that has already happened twice.
"""

import importlib.util
from pathlib import Path

import duckdb

from ark.db import connect, init_db

_SPEC = importlib.util.spec_from_file_location(
    "audit_residual",
    Path(__file__).resolve().parents[1] / "scripts" / "audit_residual.py",
)
audit_residual = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(audit_residual)


def _ledger(**by_source: set[str]) -> dict[str, set[str]]:
    return dict(by_source)


def _fake_source_tree(tmp_path: Path, monkeypatch, ingest_line: str, files: list[str]) -> None:
    """A justfile with one ingest line, and a data tree it points at."""
    for name in files:
        target = tmp_path / "data" / "raw" / "demo" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x")
    justfile = tmp_path / "justfile"
    justfile.write_text(f"demo:\n    {ingest_line}\n")
    monkeypatch.setattr(audit_residual, "ROOT", tmp_path)
    monkeypatch.setattr(audit_residual, "JUSTFILE", justfile)
    monkeypatch.setattr(audit_residual, "RAW", tmp_path / "data" / "raw")


def test_unread_reports_files_a_documented_glob_matches(tmp_path, monkeypatch, capsys) -> None:
    """The 496-shard shape: the glob is right and no ingest ever ran it."""
    _fake_source_tree(
        tmp_path,
        monkeypatch,
        "uv run ark ingest isc_survey data/raw/demo/*.gz",
        ["a.gz", "b.gz", "c.gz"],
    )
    found = audit_residual.check_unread(_ledger(isc_survey={"a.gz"}), verbose=True)
    out = capsys.readouterr().out
    assert found == 2
    assert "b.gz" in out and "c.gz" in out
    assert "a.gz" not in out


def test_unread_is_silent_when_the_ledger_holds_everything(tmp_path, monkeypatch, capsys) -> None:
    _fake_source_tree(
        tmp_path, monkeypatch, "uv run ark ingest isc_survey data/raw/demo/*.gz", ["a.gz", "b.gz"]
    )
    found = audit_residual.check_unread(_ledger(isc_survey={"a.gz", "b.gz"}), verbose=False)
    assert found == 0
    assert "nothing" in capsys.readouterr().out


def test_glob_too_narrow_reports_an_ingested_file_the_glob_cannot_reach(
    tmp_path, monkeypatch, capsys
) -> None:
    """The 2026-07-26 shape: `*.domains.gz` missed a file that was ingested."""
    _fake_source_tree(
        tmp_path,
        monkeypatch,
        "uv run ark ingest isc_survey data/raw/demo/*.domains.gz",
        ["x.domains.gz", "wb_nw_9607_org.gz"],
    )
    found = audit_residual.check_glob_too_narrow(
        _ledger(isc_survey={"x.domains.gz", "wb_nw_9607_org.gz"}), verbose=True
    )
    out = capsys.readouterr().out
    assert found == 1
    assert "wb_nw_9607_org.gz" in out


def test_a_commented_out_ingest_line_is_not_read_as_documented(
    tmp_path, monkeypatch, capsys
) -> None:
    """`arquivo_ia`'s input was deleted at 47 GB and its line commented out, so a
    commented line must not be reported as an unread source."""
    _fake_source_tree(
        tmp_path,
        monkeypatch,
        "# uv run ark ingest isc_survey data/raw/demo/*.gz",
        ["a.gz", "b.gz"],
    )
    assert audit_residual.check_unread(_ledger(), verbose=False) == 0
    assert "nothing" in capsys.readouterr().out


def test_a_writer_that_outlasts_our_patience_gets_an_explanation_not_a_traceback(
    tmp_path: Path, monkeypatch
) -> None:
    """Found by running the tool while `ark seed` held the lock for 20 minutes.

    A read-only reporting tool that ends in a DuckDB traceback reads as a broken
    tool rather than as a busy store, and the first version gave up after 117
    seconds for the same reason.
    """
    import duckdb as _duckdb

    def always_locked(*_args, **_kwargs):
        raise _duckdb.IOException(
            'IO Error: Could not set lock on file "x": Conflicting lock is held in '
            "/usr/bin/python3.12 (PID 73793) by user someone."
        )

    monkeypatch.setattr(audit_residual.duckdb, "connect", always_locked)
    try:
        audit_residual.read_only_store(tmp_path / "store.duckdb", patience_s=0)
    except SystemExit as exc:
        assert "PID 73793" in str(exc)
        assert "waits for the writer" in str(exc)
    else:
        raise AssertionError("a permanently locked store must exit with an explanation")


def test_a_non_lock_error_is_not_swallowed(tmp_path: Path, monkeypatch) -> None:
    """Waiting is right for a lock and wrong for a missing or corrupt file."""
    import duckdb as _duckdb

    def broken(*_args, **_kwargs):
        raise _duckdb.IOException("IO Error: file is not a valid DuckDB database")

    monkeypatch.setattr(audit_residual.duckdb, "connect", broken)
    try:
        audit_residual.read_only_store(tmp_path / "store.duckdb", patience_s=60)
    except SystemExit:
        raise AssertionError("a corrupt store must not be reported as a busy one") from None
    except _duckdb.IOException as exc:
        assert "valid DuckDB database" in str(exc)


def test_stale_derived_skips_a_store_with_no_baseline() -> None:
    """No baseline evidence means nothing to be stale against, which is a skip
    rather than a pass: a check that examined nothing must not read like one that
    found nothing wrong."""
    conn: duckdb.DuckDBPyConnection = connect(":memory:")
    init_db(conn)
    assert audit_residual.baseline_loaded_at(conn) is None
    assert audit_residual.check_stale_derived(conn) == 0
