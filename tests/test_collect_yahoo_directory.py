"""The Yahoo directory walk's two pure decisions: which capture, which branches."""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "collect_yahoo_directory",
    Path(__file__).resolve().parent.parent / "scripts" / "collect_yahoo_directory.py",
)
assert _SPEC and _SPEC.loader
yahoo = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(yahoo)


def test_captured_stamp_reads_the_date_off_the_landed_url() -> None:
    """The whole saving of this route is that the redirect carries the real date."""
    landed = "https://web.archive.org/web/19961128071244id_/http://www.yahoo.com/Government/"
    assert yahoo.captured_stamp(landed) == "19961128071244"


def test_captured_stamp_is_empty_when_nothing_was_captured() -> None:
    assert yahoo.captured_stamp("https://web.archive.org/web/http://www.yahoo.com/") == ""


PAGE = """
<html><body>
  <a href="/Government/Agencies/">a catalogue branch</a>
  <a href="http://www.yahoo.com/Science/Energy/">another, absolute</a>
  <a href="/bin/search?p=x">the CGI tree, not a branch</a>
  <a href="/Business/?mode=list">a query string, so the search form</a>
  <a href="/Arts/Design_Arts/index.html">a document, not a directory</a>
  <a href="http://www.example.com/">an outbound site, not a branch</a>
  <a href="/homet/">the front page's own furniture</a>
</body>
"""


def test_child_paths_takes_directory_branches_only() -> None:
    found = yahoo.child_paths(PAGE, "http://www.yahoo.com/")
    assert found == [
        "http://www.yahoo.com/Government/Agencies/",
        "http://www.yahoo.com/Science/Energy/",
    ]


def test_child_paths_normalises_mirror_hosts_onto_one_name() -> None:
    """Captures are served from www1..www10, and those are one page, not ten."""
    page = '<a href="http://www7.yahoo.com/Business/Companies/">x</a>'
    assert yahoo.child_paths(page, "http://www7.yahoo.com/Business/") == [
        "http://www.yahoo.com/Business/Companies/"
    ]
