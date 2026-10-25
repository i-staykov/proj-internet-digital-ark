"""The shipped saturation ledger, byte for byte the register, and the unparsed pool."""

import os
import sys
from pathlib import Path

import pytest
from conftest import script

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"


ledger = script("round/saturation_ledger.py", "saturation_ledger")


REGISTER = FIXTURES / "register"
SOURCES, CLOSED = ((REGISTER / name).read_text() for name in ("sources.md", "sources-closed.md"))


def is_the_expected_ledger(tmp_path: Path, sources: str = SOURCES, closed: str = CLOSED) -> bool:
    """The exporter over two register pages. The fixture is stored with LF so git cannot
    rewrite it; the CSV module writes CRLF, the artifact's real shape."""
    (tmp_path / "sources.md").write_text(sources)  # the `reference` column names the page
    (tmp_path / "sources-closed.md").write_text(closed)
    out = tmp_path / "ledger.csv"
    argv = ["saturation_ledger.py", "--out", str(out), "--sources", str(tmp_path / "sources.md")]
    argv += ["--closed", str(tmp_path / "sources-closed.md"), "--contribution", str(tmp_path / "x")]
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(sys, "argv", argv)
        assert ledger.main() == 0
    return out.read_bytes() == (REGISTER / "expected_ledger.csv").read_bytes().replace(
        b"\n", b"\r\n"
    )


def _reorder(page: str, order: list[int]) -> str:
    lines = []
    for line in page.splitlines():
        cells = line.strip().strip("|").split("|")
        if line.startswith("|") and len(cells) == len(order):
            line = "|" + "|".join(cells[i] for i in order) + "|"
        lines.append(line)
    return "\n".join(lines) + "\n"


def test_the_ledger_is_byte_for_byte_what_the_register_says_in_any_column_order(tmp_path):
    """Cells are found by header name, so a shuffled page, or a column the exporter has never
    heard of prepended where a positional reader goes wrong, gives the same bytes."""
    assert is_the_expected_ledger(tmp_path)
    shuffled = _reorder(SOURCES, [10, 6, 0, 9, 3, 1, 7, 2, 8, 4, 5])
    assert shuffled != SOURCES, "the fixture was not actually reordered"
    assert is_the_expected_ledger(tmp_path, shuffled, _reorder(CLOSED, [4, 2, 0, 3, 1]))
    grown = []
    for line in SOURCES.splitlines():
        if line.startswith("|"):
            body = line.strip().strip("|")
            added = "---" if not set(line) - set("|-: ") else "top"
            line = f"| {'priority' if body.split('|')[0].strip() == 'source' else added} |{body}|"
        grown.append(line)
    assert is_the_expected_ledger(tmp_path, "\n".join(grown) + "\n")


def test_a_missing_column_is_named_and_a_closed_rows_verdict_is_its_reasons_closed_word():
    page = "| source | version or date | net-new EE (date) | quality issues |\n|---|---|---|---|\n"
    found = r"source_link.*Headers found: source, version or date, net-new EE \(date\), quality"
    with pytest.raises(ValueError, match=found):
        ledger.rows_from_register(page + "| a | 2026-09-01 | 12 EE | none |\n")
    text = CLOSED + (
        "| not_a_source | 2026-09-01 | 0 EE | REJECTED. FIND, not a source. |  |\n"
        "| aged_out | 2026-09-19, retired | 0 EE | RETIRED: never priced; retired unmeasured |  |\n"
    )
    _, rejected, retired = ledger.rows_from_register(text, "docs/registers/sources-closed.md")
    assert rejected["status"] == "rejected" and not rejected["decision"].startswith("retain")
    assert (retired["status"], retired["decision"]) == ("retired", "retired unmeasured")


def test_the_unparsed_pool_reads_no_walk_journal(tmp_path, monkeypatch):
    import gzip

    pool = script("round/unparsed_pool.py", "unparsed_pool")
    for name, url in (
        ("sweep_a.jsonl.gz", "http://bad_one.com/"),
        ("walk_a.jsonl.gz", "http://bad_two.com/"),
    ):
        (tmp_path / name).write_bytes(gzip.compress(f'{{"url": "{url}"}}\n'.encode()))
    out = tmp_path / "pool.txt"
    monkeypatch.setattr(
        sys, "argv", ["unparsed_pool.py", "--dirs", str(tmp_path), "--out", str(out)]
    )
    assert pool.main() == 0 and out.read_text().splitlines()[1:] == ["bad_one.com\tnot_rfc1123"]
    # incremental: a journal newer than the file is read alone and merged in, as a full scan would
    (tmp_path / "sweep_a.jsonl.gz").write_bytes(b"")  # a full scan would lose bad_one.com
    (tmp_path / "sweep_b.jsonl.gz").write_bytes(gzip.compress(b'{"url": "http://bad_3.com/"}\n'))
    os.utime(tmp_path / "sweep_a.jsonl.gz", (0, 0))
    os.utime(out, (1, 1))
    monkeypatch.setattr(sys, "argv", [*sys.argv, "--incremental"])
    assert pool.main() == 0
    assert out.read_text().splitlines()[1:] == [f"bad_{n}.com\tnot_rfc1123" for n in ("3", "one")]
