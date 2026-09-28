"""The residual auditor: `unread` and `glob_too_narrow` must each fire on a real defect."""

import importlib.util
import os
from pathlib import Path

import duckdb
import pytest

from ark.db import add_candidate, connect, ensure_source, init_db

_SPEC = importlib.util.spec_from_file_location(
    "audit_residual", Path(__file__).resolve().parents[1] / "scripts/harness/audit_residual.py"
)
audit_residual = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(audit_residual)
INGEST = "uv run ark ingest isc_survey data/raw/demo/*.gz"


def _tree(tmp_path: Path, monkeypatch, ingest_line: str, files: list[str]) -> None:
    """A justfile with one ingest line, and a data tree it points at."""
    for name in files:
        target = tmp_path / "data" / "raw" / "demo" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x")
    (tmp_path / "justfile").write_text(f"demo:\n    {ingest_line}\n")
    monkeypatch.setattr(audit_residual, "ROOT", tmp_path)
    monkeypatch.setattr(audit_residual, "JUSTFILE", tmp_path / "justfile")
    monkeypatch.setattr(audit_residual, "RAW", tmp_path / "data" / "raw")


@pytest.mark.parametrize(
    ("line", "ledger", "found", "shown"),
    [
        pytest.param(INGEST, {"a.gz"}, 2, ["b.gz", "c.gz"], id="reports_files_a_glob_matches"),
        pytest.param(INGEST, {"a.gz", "b.gz", "c.gz"}, 0, ["nothing"], id="silent_when_all_held"),
        pytest.param("# " + INGEST, set(), 0, ["nothing"], id="commented_ingest_is_undocumented"),
    ],
)
def test_unread(tmp_path, monkeypatch, capsys, line, ledger, found, shown) -> None:
    _tree(tmp_path, monkeypatch, line, ["a.gz", "b.gz", "c.gz"])
    assert audit_residual.check_unread({"isc_survey": ledger}, verbose=True) == found
    out = capsys.readouterr().out
    assert all(s in out for s in shown)
    assert "a.gz" not in out


def test_glob_too_narrow_reports_an_ingested_file_the_glob_cannot_reach(
    tmp_path, monkeypatch, capsys
) -> None:
    held = ["x.domains.gz", "wb_nw_9607_org.gz"]
    _tree(tmp_path, monkeypatch, "uv run ark ingest isc_survey data/raw/demo/*.domains.gz", held)
    assert audit_residual.check_glob_too_narrow({"isc_survey": set(held)}, verbose=True) == 1
    assert "wb_nw_9607_org.gz" in capsys.readouterr().out


def test_a_locked_store_exits_with_an_explanation_and_a_corrupt_one_raises(
    tmp_path: Path, monkeypatch
) -> None:
    def fail(message: str):
        def connect_(*_args, **_kwargs):
            raise duckdb.IOException(message)

        return connect_

    lock = 'IO Error: Could not set lock on file "x": Conflicting lock is held in py (PID 73793)'
    monkeypatch.setattr(audit_residual.duckdb, "connect", fail(lock))
    with pytest.raises(SystemExit, match="PID 73793") as exc:
        audit_residual.read_only_store(tmp_path / "store.duckdb", patience_s=0)
    assert "waits for the writer" in str(exc.value)
    monkeypatch.setattr(audit_residual.duckdb, "connect", fail("not a valid DuckDB database"))
    with pytest.raises(duckdb.IOException, match="valid DuckDB database"):
        audit_residual.read_only_store(tmp_path / "store.duckdb", patience_s=60)


def test_stale_derived_judges_every_list_in_a_store_with_no_rows_of_his(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    conn = connect(":memory:")
    init_db(conn)
    add_candidate(conn, "fresh.com", ensure_source(conn, "demo", "candidate_only"))
    rel = audit_residual.DERIVED[0][0]
    queue = tmp_path / rel
    queue.parent.mkdir(parents=True)
    queue.write_text("a.com\n")
    os.utime(queue, (0, 0))
    monkeypatch.setattr(audit_residual, "ROOT", tmp_path)
    assert audit_residual.check_stale_derived(conn) == 1
    out = capsys.readouterr().out
    assert f"[STALE] {rel}" in out and "newest candidates" in out
