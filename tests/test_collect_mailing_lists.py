"""The mailing-list collector's pure decisions: which months, which lists, which messages."""

import gzip
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "collect_mailing_lists",
    Path(__file__).resolve().parent.parent / "scripts" / "collect_mailing_lists.py",
)
assert _SPEC and _SPEC.loader
maillists = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(maillists)


INDEX = """
<html><body>
  <a href="1999-January.txt.gz">[ Gzip'd Text ]</a>
  <a href="2001-December.txt">[ Text ]</a>
  <a href="2004-March.txt.gz">out of window</a>
  <a href="1995-July.txt">also out of window</a>
  <a href="1999-January/thread.html">a thread page, not an archive file</a>
</body></html>
"""


def test_month_file_pattern_keeps_only_in_window_archives() -> None:
    """1996-2001 only, and only the per-month archive file, not its thread pages."""
    found = sorted(maillists._MONTH_FILE.findall(INDEX))
    assert found == [
        "1995-July.txt",
        "1999-January.txt.gz",
        "2001-December.txt",
        "2004-March.txt.gz",
    ]
    in_window = sorted(n for n in found if int(n[:4]) in maillists.YEARS)
    assert in_window == ["1999-January.txt.gz", "2001-December.txt"]


def test_gatewayed_lists_are_skipped() -> None:
    """python-list is bidirectionally gatewayed with comp.lang.python.

    Counting it here would let one body of observation look like two lineages,
    which is exactly what PROVENANCE_LINEAGE exists to prevent.
    """
    assert "python-list" in maillists.SKIP_LISTS
    assert "python-announce-list" in maillists.SKIP_LISTS
    assert "gtk-list" not in maillists.SKIP_LISTS


MBOX = (
    "From someone@example.com Mon Jan  4 09:00:00 1999\n"
    "Date: Mon, 4 Jan 1999 09:00:00 +0000\n"
    "Subject: one\n\nsee http://widgets.example.org/ for details\n\n"
    "From other@example.net Tue Jan  5 09:00:00 1999\n"
    "Date: Tue, 5 Jan 1999 09:00:00 +0000\n"
    "Subject: two\n\nnothing here\n"
)


def test_read_messages_splits_plain_and_gzipped_month_files(tmp_path: Path) -> None:
    plain = tmp_path / "gtk-list__1999-January.txt"
    plain.write_text(MBOX, encoding="utf-8")
    packed = tmp_path / "gtk-list__1999-January.txt.gz"
    packed.write_bytes(gzip.compress(MBOX.encode()))
    assert len(maillists.read_messages(plain)) == 2
    assert maillists.read_messages(packed) == maillists.read_messages(plain)


def test_address_pattern_refuses_a_sentence_and_reads_a_real_host() -> None:
    """The anchor is a local part, an `@` and a TLD the metric pays for."""
    assert maillists._ADDR.findall("write to bob@widgets.example.com today") == [
        "widgets.example.com"
    ]
    assert maillists._ADDR.findall("end of sentence.Next one") == []
