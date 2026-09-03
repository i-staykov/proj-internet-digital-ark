"""The shipped saturation ledger, on a two-page register small enough to read.

The ledger is a SHIPPED artifact built from prose, so the risk is silent: a column
added to the register shifts every cell after it and the CSV still looks fine. These
tests pin the bytes for one row of each shape the register carries, then reorder the
register's columns and demand the same bytes back.

Loaded by path, like the other script tests: `scripts/` is not a package.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/register"

_SPEC = importlib.util.spec_from_file_location(
    "saturation_ledger", ROOT / "scripts/round/saturation_ledger.py"
)
ledger = importlib.util.module_from_spec(_SPEC)
sys.modules["saturation_ledger"] = ledger
_SPEC.loader.exec_module(ledger)


def _build(tmp_path: Path, sources: str | None = None, closed: str | None = None) -> bytes:
    """Run the exporter over the fixture pages, or over replacements for them."""
    pages = {"sources.md": sources, "sources-closed.md": closed}
    paths = {}
    for name, text in pages.items():
        if text is None:
            paths[name] = FIXTURES / name
            continue
        # Same filename, because the `reference` column names the page it read.
        written = tmp_path / name
        written.write_text(text, encoding="utf-8")
        paths[name] = written
    out = tmp_path / "ledger.csv"
    argv = [
        "saturation_ledger.py",
        "--out",
        str(out),
        "--sources",
        str(paths["sources.md"]),
        "--closed",
        str(paths["sources-closed.md"]),
        "--contribution",
        str(tmp_path / "no-contribution.csv"),
    ]
    saved, sys.argv = sys.argv, argv
    try:
        assert ledger.main() == 0
    finally:
        sys.argv = saved
    return out.read_bytes()


def _expected() -> bytes:
    """The fixture is stored with LF so git's newline handling cannot rewrite it.

    The CSV module writes CRLF, which is the artifact's real shape, and no field in
    the fixture holds a newline of its own, so the substitution is exact.
    """
    return (FIXTURES / "expected_ledger.csv").read_bytes().replace(b"\n", b"\r\n")


def _reorder(page: str, order: list[int]) -> str:
    """Rewrite a register page with its columns in a different order."""
    lines = []
    for line in page.splitlines():
        cells = line.strip().strip("|").split("|")
        if line.startswith("|") and len(cells) == len(order):
            line = "|" + "|".join(cells[i] for i in order) + "|"
        lines.append(line)
    return "\n".join(lines) + "\n"


def test_the_ledger_is_byte_for_byte_what_the_register_says(tmp_path: Path) -> None:
    """Every cell shape in one assertion: filled, `n/a`, detail-only, closed page."""
    assert _build(tmp_path) == _expected()


def test_reordering_the_register_columns_changes_nothing(tmp_path: Path) -> None:
    """Cells are found by header name, so the page's column order is not load-bearing."""
    sources = (FIXTURES / "sources.md").read_text(encoding="utf-8")
    closed = (FIXTURES / "sources-closed.md").read_text(encoding="utf-8")
    # `source` off the front on both pages, and the eleven columns shuffled.
    shuffled = _reorder(sources, [10, 6, 0, 9, 3, 1, 7, 2, 8, 4, 5])
    assert shuffled != sources, "the fixture was not actually reordered"
    assert _build(tmp_path, sources=shuffled, closed=_reorder(closed, [4, 2, 0, 3, 1])) == (
        _expected()
    )


def test_an_added_column_does_not_shift_a_cell(tmp_path: Path) -> None:
    """A column the exporter has never heard of leaves the named ones where they are.

    Prepended, because that is the position a positional reader gets wrong: the source
    name came out of the first cell until this ticket.
    """
    sources = (FIXTURES / "sources.md").read_text(encoding="utf-8")
    grown = []
    for line in sources.splitlines():
        if line.startswith("|"):
            body = line.strip().strip("|")
            if not set(line) - set("|-: "):
                added = "---"
            elif body.split("|")[0].strip() == "source":
                added = "priority"
            else:
                added = "top"
            line = f"| {added} |{body}|"
        grown.append(line)
    assert _build(tmp_path, sources="\n".join(grown) + "\n") == _expected()


def test_a_missing_required_column_names_the_headers_it_found() -> None:
    """The failure is loud, because a quiet one ships a wrong ledger."""
    page = (
        "# Sources\n\n"
        "| source | version or date | net-new EE (date) | quality issues |\n"
        "|---|---|---|---|\n"
        "| a_family | 2026-09-01 | 12 EE (2026-09-01) | none |\n"
    )
    with pytest.raises(ValueError) as caught:
        ledger.rows_from_register(page, "docs/sources.md")
    message = str(caught.value)
    assert "source_link" in message
    assert "Headers found: source, version or date, net-new EE (date), quality issues" in message


def test_retrieval_method_is_populated_from_the_register_column() -> None:
    """E4.3's added column: his own schema word, which the CSV used to drop."""
    text = (FIXTURES / "sources.md").read_text(encoding="utf-8")
    rows = {row["source_family"]: row for row in ledger.rows_from_register(text)}
    assert rows["every_cell_filled"]["retrieval_method"] == "ftp listing"
    assert rows["blocked_by_robots"]["retrieval_method"] == "robots refusal"
    # `n/a` in the register means the entry does not say, and is kept as it stands.
    assert rows["says_nothing"]["retrieval_method"] == "n/a"


def test_the_closed_page_reads_its_five_columns_and_leaves_the_rest_empty() -> None:
    """No retrieval, coverage, overlap or effort column exists there, so those are empty."""
    text = (FIXTURES / "sources-closed.md").read_text(encoding="utf-8")
    (row,) = ledger.rows_from_register(text, "docs/sources-closed.md")
    assert row["source_family"] == "closed_on_measurement"
    assert row["coverage_ee"] == "4.44"
    assert row["source_link"] == "https://example.org/irr-dump.txt"
    empty = ("coverage_period", "retrieval_method", "baseline_overlap", "effort")
    assert [row[field] for field in empty] == ["", "", "", ""]
