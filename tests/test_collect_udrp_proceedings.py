"""The UDRP proceedings reader, and the rules that make it master evidence.

Loaded by path, like the other script tests: `scripts/` is not a package.

This source takes **no corroboration split** (ADR-002), so unlike a Usenet or OCR
extractor there is no wall behind its pattern: anything it emits becomes a master
claim. The tests therefore pin what it refuses as tightly as what it accepts.
"""

import importlib.util
from collections import Counter
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "collect_udrp_proceedings",
    Path(__file__).resolve().parents[1] / "scripts" / "collect_udrp_proceedings.py",
)
udrp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(udrp)


def _page(*rows: str) -> str:
    head = (
        "<table><tr><th>Date Commenced</th><th>Date Decided</th>"
        "<th>Proceeding Number</th><th>Domain Name(s)</th>"
        "<th>Case Type</th><th>Status</th></tr>"
    )
    return head + "".join(rows) + "</table>"


def _row(commenced: str, decided: str, number: str, domains: str) -> str:
    return (
        f"<tr><td>{commenced}</td><td>{decided}</td><td>{number}</td>"
        f"<td>{domains}</td><td>UDRP (1)</td><td>Name transfer(21)</td></tr>"
    )


def test_reads_the_commencement_year_and_the_domain_column() -> None:
    stats: Counter = Counter()
    page = _page(_row("2000-01-03", "2000-02-21", "WIPO D2000-0001", "musicweb.com"))
    got = list(udrp.records_in(page, stats))
    assert got == [
        {
            "domain": "musicweb.com",
            "year": 2000,
            "proceeding": "WIPO D2000-0001",
            "commenced": "2000-01-03",
            "url": udrp.LIST_URL,
        }
    ]


def test_the_year_comes_from_commencement_not_from_the_decision() -> None:
    """A case commenced in 2000 and decided in 2001 evidences 2000.

    The domain certainly existed when the complaint was filed, so the earlier date
    is the safer claim, and `evidence_year_matches_its_value` requires the value to
    name the year it is filed under.
    """
    stats: Counter = Counter()
    page = _page(_row("2000-12-20", "2001-03-04", "NAF FA0092015", "buyerschoice.com"))
    (record,) = list(udrp.records_in(page, stats))
    assert record["year"] == 2000
    assert record["commenced"].startswith("2000")


def test_out_of_window_rows_are_counted_and_dropped() -> None:
    stats: Counter = Counter()
    page = _page(
        _row("2004-05-06", "2004-07-01", "WIPO D2004-0001", "later.com"),
        _row("1999-12-09", "2000-01-18", "WIPO D1999-0001", "worldwrestlingfederation.com"),
    )
    got = list(udrp.records_in(page, stats))
    assert [r["domain"] for r in got] == ["worldwrestlingfederation.com"]
    assert stats["out_of_window"] == 1


def test_several_disputed_names_in_one_cell_all_count() -> None:
    stats: Counter = Counter()
    page = _page(_row("2000-06-01", "-", "WIPO D2000-0500", "one.com, two.net and three.org"))
    got = sorted(r["domain"] for r in udrp.records_in(page, stats))
    assert got == ["one.com", "three.org", "two.net"]


def test_a_row_with_no_proceeding_number_is_refused() -> None:
    """The number is what makes a row auditable, so a row without one is dropped
    rather than filed under a URL a reviewer cannot resolve."""
    stats: Counter = Counter()
    page = _page(_row("2000-06-01", "-", "", "orphan.com"))
    assert list(udrp.records_in(page, stats)) == []
    assert stats["no_proceeding_number"] == 1


def test_hostnames_are_collapsed_to_registered_domains() -> None:
    """III.8: the output unit is the registered domain, not the hostname."""
    stats: Counter = Counter()
    page = _page(_row("2001-02-02", "-", "WIPO D2001-0002", "www.example.co.uk"))
    (record,) = list(udrp.records_in(page, stats))
    assert record["domain"] == "example.co.uk"


def test_the_same_domain_twice_in_one_cell_yields_one_record() -> None:
    stats: Counter = Counter()
    page = _page(_row("2000-03-03", "-", "WIPO D2000-0300", "dup.com and dup.com again"))
    assert len(list(udrp.records_in(page, stats))) == 1


def test_a_header_row_produces_nothing() -> None:
    stats: Counter = Counter()
    assert list(udrp.records_in(_page(), stats)) == []
    assert stats["rows_with_a_date"] == 0


def test_the_journal_carries_the_date_and_number_the_parser_needs() -> None:
    """`sources.parse_udrp_proceedings` builds the evidence value from these two
    fields and puts the date first, so the first four-digit run in the value is the
    year the row is filed under. A NAF number like `FA0092016` offers `0092` and a
    `D2000-` case commenced in 2001 offers 2000, so either one leading would fail
    `evidence_year_matches_its_value`."""
    stats: Counter = Counter()
    page = _page(_row("2001-05-15", "-", "WIPO D2000-1762", "late.com"))
    (record,) = list(udrp.records_in(page, stats))
    assert record["commenced"] == "2001-05-15"
    assert record["proceeding"] == "WIPO D2000-1762"
    assert record["year"] == 2001
