"""The declarative probe: what it extracts, and what it refuses to guess.

Loaded by path, like the other script tests: `scripts/` is not a package.

**Why the refusals carry the weight here.** A probe's whole output is one number, the
yield, and a probe that silently drops rows reports a bad extraction as a bad source.
That failure is invisible downstream, so these tests pin that every drop is counted
under a reason, and that a spec which does not say which column holds the hostname
fails loudly instead of guessing (ADR-004).

Nothing here reaches the network: `pairs_from` and `year_of` take the page as text.
"""

import importlib.util
from collections import Counter
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "probe_source", Path(__file__).resolve().parents[1] / "scripts" / "probe_source.py"
)
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)

HOST = r"(?i)\b([a-z0-9][a-z0-9\-]{0,62}(?:\.[a-z0-9][a-z0-9\-]{0,62})*\.[a-z]{2,6})\b"


def _table(*rows: str) -> str:
    return "<table>" + "".join(rows) + "</table>"


def _row(*cells: str) -> str:
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


def test_a_table_row_yields_its_named_columns() -> None:
    spec = {"kind": "html_table", "domain_column": 1, "date_column": 0}
    page = _table(_row("1998-04-02", "example.com"))
    got = list(probe.pairs_from(spec, page, Counter()))
    assert got == [("row 0", "example.com", "1998-04-02", "1998-04-02 | example.com")]


def test_a_spec_that_does_not_name_the_hostname_column_refuses_to_run() -> None:
    """The failure mode this prevents is pricing the wrong column and believing it."""
    with pytest.raises(SystemExit, match="does not guess"):
        list(probe.pairs_from({"kind": "html_table"}, _table(_row("a", "b")), Counter()))


def test_a_cell_listing_several_names_yields_all_of_them() -> None:
    """The UDRP dockets put every disputed name of a case in one cell, so a cell taken
    whole would refuse those rows and price the source too low."""
    spec = {"kind": "html_table", "domain_column": 1, "date_column": 0, "domain_pattern": HOST}
    page = _table(_row("2000-01-05", "one.com, two.net and three.org"))
    names = [name for _i, name, _d, _w in probe.pairs_from(spec, page, Counter())]
    assert names == ["one.com", "two.net", "three.org"]


def test_a_short_row_is_refused_under_its_own_reason() -> None:
    stats = Counter()
    spec = {"kind": "html_table", "domain_column": 3, "date_column": 0}
    assert list(probe.pairs_from(spec, _table(_row("1998-01-01", "x")), stats)) == []
    assert stats["refused_short_row"] == 1
    assert stats["rows_seen"] == 1


def test_header_rows_are_skipped_without_being_counted_as_refusals() -> None:
    stats = Counter()
    spec = {"kind": "html_table", "domain_column": 1, "date_column": 0, "header_rows": 1}
    page = _table(_row("Date", "Domain"), _row("1997-06-01", "kept.com"))
    got = list(probe.pairs_from(spec, page, stats))
    assert [name for _i, name, _d, _w in got] == ["kept.com"]
    assert stats["rows_seen"] == 1
    assert not [key for key in stats if key.startswith("refused_")]


def test_the_table_index_is_checked_rather_than_silently_falling_back() -> None:
    spec = {"kind": "html_table", "domain_column": 0, "table": 3}
    with pytest.raises(SystemExit, match="asks for index 3"):
        list(probe.pairs_from(spec, _table(_row("a")), Counter()))


def test_out_of_window_and_undated_are_different_refusals() -> None:
    """They say different things about a source: one is a date column that works and a
    corpus that is too late, the other is a date column that is not being read."""
    stats = Counter()
    assert probe.year_of({}, "2004-01-01", stats) is None
    assert probe.year_of({}, "no date here", stats) is None
    assert stats["refused_year_out_of_window"] == 1
    assert stats["refused_no_date"] == 1


def test_a_fixed_year_needs_no_date_column() -> None:
    """A page that is itself one year, for example a 1997 annual directory."""
    assert probe.year_of({"year": 1997}, "", Counter()) == 1997
    assert probe.year_of({"year": 2005}, "", Counter()) is None


def test_lines_mode_finds_a_hostname_and_a_date_on_the_same_line() -> None:
    """Group 1 wins where a pattern has one, which is what lets a spec point at the
    year inside a longer date; the whole match is used where it has none. Either way
    the year that comes out is the same, which is all the date text is read for."""
    page = "1996-11-30  widgets.co.uk  some description\nnothing useful here\n"
    grouped = {"kind": "lines", "domain_pattern": HOST, "date_pattern": r"\b(\d{4})-\d{2}-\d{2}\b"}
    whole = {"kind": "lines", "domain_pattern": HOST, "date_pattern": r"\b\d{4}-\d{2}-\d{2}\b"}
    assert [(n, w) for _i, n, w, _r in probe.pairs_from(grouped, page, Counter())] == [
        ("widgets.co.uk", "1996")
    ]
    assert [(n, w) for _i, n, w, _r in probe.pairs_from(whole, page, Counter())] == [
        ("widgets.co.uk", "1996-11-30")
    ]
    for spec in (grouped, whole):
        _i, _n, when, _r = next(iter(probe.pairs_from(spec, page, Counter())))
        assert probe.year_of(spec, when, Counter()) == 1996


def test_lines_mode_counts_a_line_with_no_hostname() -> None:
    stats = Counter()
    spec = {"kind": "lines", "domain_pattern": HOST}
    list(probe.pairs_from(spec, "nothing useful here\n", stats))
    assert stats["refused_no_hostname_match"] == 1


def test_jsonl_mode_reads_a_dotted_field_path() -> None:
    spec = {"kind": "jsonl", "domain_field": "ldhName", "date_field": "events.0.eventDate"}
    page = '{"ldhName": "thing.org", "events": [{"eventDate": "1999-02-01"}]}\n'
    got = list(probe.pairs_from(spec, page, Counter()))
    assert [(name, when) for _i, name, when, _w in got] == [("thing.org", "1999-02-01")]


def test_a_dotted_path_that_misses_returns_none_rather_than_raising() -> None:
    record = {"a": [{"b": 1}]}
    assert probe.dotted(record, "a.0.b") == 1
    assert probe.dotted(record, "a.9.b") is None
    assert probe.dotted(record, "a.0.missing") is None
    assert probe.dotted(record, "a.b") is None


def test_jsonl_mode_separates_bad_json_from_a_missing_field() -> None:
    stats = Counter()
    spec = {"kind": "jsonl", "domain_field": "ldhName"}
    page = 'not json at all\n{"other": "x"}\n'
    assert list(probe.pairs_from(spec, page, stats)) == []
    assert stats["refused_unparseable_json"] == 1
    assert stats["refused_field_absent"] == 1
