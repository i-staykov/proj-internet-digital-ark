"""`trace.py`, the tool the reviewer runs blind, driven the way he runs it.

`write_provenance` copies `src/ark/provenance_trace.py` into the export folder as
`trace.py`, and the reviewer runs that copy from there with no project around it.
So each test runs the copied file as `__main__` from its shipped location rather
than importing the module, and reads what it printed.
"""

import runpy
import sys
from pathlib import Path

import pytest

from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.provenance import write_provenance

CAPTURE_URL = "https://web.archive.org/web/19980101000000/http://example.com/"


@pytest.fixture
def export(tmp_path: Path) -> Path:
    """A provenance folder holding one dated domain and one bare candidate."""
    conn = connect(":memory:")
    init_db(conn)
    cdx = ensure_source(conn, "ia_cdx_bulk", "timestamped")
    add_candidate(conn, "example.com", cdx)
    proof = record_evidence(
        conn, "example.com", cdx, 1998, "cdx_timestamp", "19980101000000", url=CAPTURE_URL
    )
    assign_year(conn, proof)
    add_candidate(conn, "candidate.org", cdx)
    write_provenance(conn, tmp_path)
    conn.close()
    return tmp_path


def _run(export: Path, monkeypatch, capsys, *args: str) -> str:
    monkeypatch.setattr(sys, "argv", ["trace.py", *args])
    runpy.run_path(str(export / "trace.py"), run_name="__main__")
    return capsys.readouterr().out


def test_a_year_traces_to_the_observation_behind_it(export, monkeypatch, capsys) -> None:
    # typed carelessly on purpose: `main` is what normalises the name
    out = _run(export, monkeypatch, capsys, " Example.COM ", "1998")
    assert out.startswith("example.com\n")
    assert "  1998\n" in out
    observation = next(line for line in out.splitlines() if "cdx_timestamp" in line)
    assert "ia_cdx_bulk" in observation and "19980101000000" in observation
    assert CAPTURE_URL in out


def test_no_arguments_summarises_the_export_and_offers_a_real_query(
    export, monkeypatch, capsys
) -> None:
    out = _run(export, monkeypatch, capsys)
    assert out.startswith("Provenance export loaded.")
    # every shipped table, the optional one included: it once went unlisted while
    # its file sat beside the others, and the reviewer was told five tables of six
    for table in (
        "source",
        "domain",
        "evidence",
        "domain_year",
        "ingested_file",
        "domain_language",
    ):
        assert f"  {table:<16}" in out, table
    assert out.rstrip().endswith("python trace.py example.com 1998")


def test_a_candidate_and_a_stranger_are_told_apart(export, monkeypatch, capsys) -> None:
    assert "no year assigned" in _run(export, monkeypatch, capsys, "candidate.org")
    assert "not in the dataset" in _run(export, monkeypatch, capsys, "nobody.net", "1998")
