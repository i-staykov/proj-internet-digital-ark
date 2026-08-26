"""The BL geoindex parser, and the approval gate that still stands in front of it.

A parser is not a permission. `ukwa_geoindex` is registered so that approving the
class is one command rather than a day's work, and these tests exist to prove that
registering it did not quietly grant it anything.
"""

import gzip
from collections import Counter

from ark.sources import SOURCES, parse_ukwa_geoindex

ROWS = [
    "19990412183021/http://www.example.co.uk/index.html\tOX11 0QX",
    "20010101000000/http://sub.host.ac.uk/a/b\tSW1A 1AA",
    # Junk stamps really are in this file, so the window filter has to reject them
    # rather than the ordering being trusted.
    "19800101000000/http://www.old.co.uk/\tE1 6AN",
    "19941231235959/http://www.early.co.uk/\tE1 6AN",
    "20051231235959/http://www.late.co.uk/\tE1 6AN",
    "notatimestamp/http://www.bad.co.uk/\tE1 6AN",
]


def _write(tmp_path):
    path = tmp_path / "geoindex_inwindow.tsv.gz"
    with gzip.open(path, "wt") as fh:
        fh.write("\n".join(ROWS) + "\n")
    return path


def test_only_in_window_rows_are_yielded(tmp_path) -> None:
    stats: Counter = Counter()
    records = list(parse_ukwa_geoindex(_write(tmp_path), stats))
    assert [r.year for r in records] == [1999, 2001]
    assert stats["out_of_window"] == 3
    assert stats["malformed"] == 1


def test_the_capture_timestamp_is_the_evidence_value(tmp_path) -> None:
    """A capture in 1999 evidences 1999 and nothing else, so the stamp is kept
    verbatim and the year is read from it rather than supplied alongside."""
    stats: Counter = Counter()
    records = list(parse_ukwa_geoindex(_write(tmp_path), stats))
    assert records[0].evidence_value == "19990412183021"
    assert records[0].evidence_value.startswith(str(records[0].year))
    assert "19990412183021" in records[0].evidence_url


def test_the_spec_is_registered_as_a_self_dating_capture_type() -> None:
    spec = SOURCES["ukwa_geoindex"]
    assert spec.evidence_type == "cdx_timestamp"
    assert spec.acquisition_method == "bl_geoindex_extract"


def test_registering_the_parser_did_not_grant_the_class_anything() -> None:
    """The gate is the `Decision:` line, not the presence of code. If this ever
    fails, a parser has been read as an approval, which is the one thing ADR-003
    exists to prevent."""
    from pathlib import Path

    approvals = Path(__file__).resolve().parents[1] / "docs" / "approved-sources-list.md"
    text = approvals.read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if "| ukwa_geoindex |" in line)
    assert row.rstrip().endswith("| pending |"), (
        "ukwa_geoindex is no longer pending; if that was deliberate this test should "
        "be updated in the same commit as the Decision line"
    )
