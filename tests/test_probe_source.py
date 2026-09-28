"""The declarative probe counts every row it drops under a reason and never guesses a column."""

import importlib.util
from collections import Counter
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "probe_source", Path(__file__).resolve().parents[1] / "scripts/pricing/probe_source.py"
)
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)

HOST = r"(?i)\b([a-z0-9][a-z0-9\-]{0,62}(?:\.[a-z0-9][a-z0-9\-]{0,62})*\.[a-z]{2,6})\b"
TABLE = {"kind": "html_table", "domain_column": 1, "date_column": 0}


def _table(*rows: tuple[str, ...]) -> str:
    cells = ("".join(f"<td>{cell}</td>" for cell in row) for row in rows)
    return "<table>" + "".join(f"<tr>{row}</tr>" for row in cells) + "</table>"


def test_a_table_row_yields_its_named_columns() -> None:
    got = list(probe.pairs_from(TABLE, _table(("1998-04-02", "example.com")), Counter()))
    assert got == [("row 0", "example.com", "1998-04-02", "1998-04-02 | example.com")]


def test_a_table_counts_every_row_it_drops_and_splits_a_cell_of_several_names() -> None:
    """The UDRP dockets put every disputed name of a case in one cell."""
    spec = {**TABLE, "domain_pattern": HOST, "header_rows": 1}
    rows = [("Date", "Domain"), ("2000-01-05", "one.com, two.net and three.org")]
    page = _table(*rows, ("1998",), ("1999", "none"))
    stats = Counter()
    got = [name for _i, name, _d, _w in probe.pairs_from(spec, page, stats)]
    assert got == ["one.com", "two.net", "three.org"]
    # the header row is skipped, not counted as seen or refused
    assert stats == {"rows_seen": 3, "refused_short_row": 1, "refused_no_hostname_in_cell": 1}


@pytest.mark.parametrize(
    ("spec", "match"),
    [({"kind": "html_table"}, "does not guess"), ({**TABLE, "table": 3}, "asks for index 3")],
    ids=["no-hostname-column-named", "table-index-out-of-range"],
)
def test_a_spec_that_would_price_the_wrong_column_refuses_to_run(spec, match) -> None:
    with pytest.raises(SystemExit, match=match):
        list(probe.pairs_from(spec, _table(("a", "b")), Counter()))


def test_out_of_window_and_undated_are_different_refusals_and_a_fixed_year_needs_no_date() -> None:
    stats = Counter()
    assert probe.year_of({}, "2004-01-01", stats) is None
    assert probe.year_of({}, "no date here", stats) is None
    assert (stats["refused_year_out_of_window"], stats["refused_no_date"]) == (1, 1)
    assert probe.year_of({"year": 1997}, "", Counter()) == 1997
    assert probe.year_of({"year": 2005}, "", Counter()) is None


def test_lines_mode_takes_group_1_where_the_date_pattern_has_one() -> None:
    page = "1996-11-30  widgets.co.uk  some description\nnothing useful here\n"
    for date, when in (
        (r"\b(\d{4})-\d{2}-\d{2}\b", "1996"),
        (r"\b\d{4}-\d{2}-\d{2}\b", "1996-11-30"),
    ):
        spec, stats = {"kind": "lines", "domain_pattern": HOST, "date_pattern": date}, Counter()
        got = [(name, w) for _i, name, w, _r in probe.pairs_from(spec, page, stats)]
        assert got == [("widgets.co.uk", when)] and probe.year_of(spec, when, Counter()) == 1996
        assert stats == {"rows_seen": 2, "refused_no_hostname_match": 1}


def test_jsonl_mode_reads_a_dotted_path_and_bad_json_is_not_a_missing_field() -> None:
    spec = {"kind": "jsonl", "domain_field": "ldhName", "date_field": "events.0.eventDate"}
    page = 'not json at all\n{"other": "x"}\n'
    page += '{"ldhName": "thing.org", "events": [{"eventDate": "1999-02-01"}]}\n'
    stats = Counter()
    got = [(name, when) for _i, name, when, _w in probe.pairs_from(spec, page, stats)]
    assert got == [("thing.org", "1999-02-01")]
    assert stats == {"rows_seen": 3, "refused_unparseable_json": 1, "refused_field_absent": 1}
    record = {"a": [{"b": 1}]}
    assert probe.dotted(record, "a.0.b") == 1
    assert [probe.dotted(record, path) for path in ("a.9.b", "a.0.missing", "a.b")] == [None] * 3
