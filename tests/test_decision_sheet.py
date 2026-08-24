"""The decision sheet must show measured pending sources and nothing else."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "decision_sheet", ROOT / "scripts" / "decision_sheet.py"
)
decision_sheet = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(decision_sheet)

parse = decision_sheet.parse
render = decision_sheet.render


def test_only_pending_entries_with_a_measured_line_appear():
    doc = """
### banked_thing / cdx_timestamp
- measured: 900 net-new post-split EE
- what dates one item: a capture stamp

Decision: master

### unmeasured / artifact_listing
- what dates one item: a serial
- potential: 88

Decision: pending

### measured_pending / artifact_listing
- measured: 1,234.5 net-new post-split EE, 2026-08-24
- what dates one item: the zone's own SOA serial

Decision: pending
"""
    rows = parse(doc)
    assert [r["source"] for r in rows] == ["measured_pending"]
    assert rows[0]["ee"] == 1234.5
    assert rows[0]["standard"] == "the zone's own SOA serial"


def test_rows_sort_by_equivalent_english_descending():
    doc = """
### small / artifact_listing
- measured: 10 EE
- what dates one item: x

Decision: pending

### big / cdx_timestamp
- measured: 5,000 EE
- what dates one item: y

Decision: pending
"""
    assert [r["source"] for r in parse(doc)] == ["big", "small"]


def test_a_class_that_cannot_date_a_year_is_marked_not_blocking():
    doc = """
### pool_only / link_target
- measured: 40 EE
- what dates one item: nothing

Decision: pending
"""
    out = render(parse(doc))
    assert "not blocking" in out
    # It cannot date a year, so it must not be counted in the waiting total.
    assert "**1 rows, 0 equivalent-English waiting on a word.**" in out


def test_a_missing_standard_is_named_rather_than_left_blank():
    doc = """
### no_standard / artifact_listing
- measured: 7 EE

Decision: pending
"""
    assert parse(doc)[0]["standard"] == "NOT STATED"


def test_an_empty_sheet_says_so():
    assert "Nothing measured is waiting" in render([])


def test_a_wrapped_standard_is_joined_rather_than_truncated():
    doc = """
### wrapped / artifact_listing
- measured: 100 EE
- what dates one item: the page's own line, `updated automatically at 14:51 GMT on
  Friday, 21 December 2001`, written by the registry
- potential: 90

Decision: pending
"""
    standard = parse(doc)[0]["standard"]
    assert standard.endswith("written by the registry")
    assert "\n" not in standard
