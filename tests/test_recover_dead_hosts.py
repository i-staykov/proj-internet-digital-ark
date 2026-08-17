"""A dead host's pages and its files are different questions, and only one was asked.

`reprobe_closed.py` re-asks whether a host answers. That is the wrong question for a
source closed on availability, and 2026-08-16 proved it twice: `nw.com` had been
recorded as unrecoverable while `zone/9701.domains.gz` sat intact in the Wayback
Machine, worth 76,324 net-new pairs; and `cybermetrics.wlv.ac.uk` does not resolve at
all while its entire `/database/` tree survives, including a 166 MB zip.

These tests pin the filter that separates a data file from a page, because its two
failure modes are opposite and both are expensive. Too strict and it hides the file
that matters, which is what "Wayback skips large binaries" would have done. Too loose
and it reports every HTML page on a dead host as a recovery.
"""

import importlib.util
from pathlib import Path

_HERE = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "recover_dead_hosts", _HERE / "scripts" / "recover_dead_hosts.py"
)
recover = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(recover)


def _row(url, size, mime="application/octet-stream", ts="20070810124544"):
    return [url, ts, mime, str(size), "200"]


def test_a_large_archive_is_reported() -> None:
    rows = [_row("http://cybermetrics.wlv.ac.uk/database/uk_2002.zip", 166_593_268)]
    assert recover.interesting(rows)[0][3].endswith("uk_2002.zip")


def test_a_self_extracting_exe_is_reported() -> None:
    """Excluding .exe would have hidden the largest files on the first host tried.

    A 1990s research host shipped its datasets as self-extracting archives, so the
    generous suffix list is deliberate rather than sloppy.
    """
    rows = [_row("http://cybermetrics.wlv.ac.uk/database/uk_unis_2000.exe", 45_486_540)]
    assert len(recover.interesting(rows)) == 1


def test_pages_are_not_reported_however_large() -> None:
    rows = [
        _row("http://dead.example/index.html", 5_000_000, "text/html"),
        _row("http://dead.example/logo.png", 900_000, "image/png"),
        _row("http://dead.example/app.js", 800_000, "application/javascript"),
    ]
    assert recover.interesting(rows) == []


def test_the_159_byte_stub_shape_is_far_below_the_floor() -> None:
    """The stub that fooled a checker for weeks must not read as a recovered file."""
    rows = [
        _row("http://www.webarchive.org.uk/datasets/ukwa.ds.2/cdx/1996.cdx.gz", 159, "text/html")
    ]
    assert recover.interesting(rows) == []


def test_results_come_back_largest_first() -> None:
    """The reader wants the prize, not the README that happens to sort first."""
    rows = [
        _row("http://dead.example/small.zip", 30_000),
        _row("http://dead.example/huge.zip", 90_000_000),
        _row("http://dead.example/medium.zip", 2_000_000),
    ]
    sizes = [size for size, _ts, _mime, _url in recover.interesting(rows)]
    assert sizes == sorted(sizes, reverse=True)


def test_an_unparseable_length_is_skipped_rather_than_raising() -> None:
    """A CDX line with a dash for length is normal and must not end the sweep."""
    rows = [_row("http://dead.example/x.zip", "-"), _row("http://dead.example/y.zip", 50_000)]
    assert [u for _s, _t, _m, u in recover.interesting(rows)] == ["http://dead.example/y.zip"]


def test_papers_and_fonts_are_not_data() -> None:
    """The first whole-register sweep returned 89 hits and most were a reading list.

    Conference PDFs on Yahoo Webscope, PostScript papers from a 1999 caching
    workshop, and Bootstrap glyph fonts on an Icelandic archive. All are served as
    octet-stream, so the mime check alone lets them through.
    """
    rows = [
        _row("http://webscope.sandbox.yahoo.com/files/YmirV.pdf", 5_251_465),
        _row("http://www.ircache.net/Cache/Workshop99/Papers/rochat-final.ps.gz", 251_434),
        _row("https://vefsafn.is/is/x/glyphicons-halflings-regular.ttf", 24_547),
        _row("https://vefsafn.is/is/x/glyphicons-halflings-regular.woff", 23_909),
    ]
    assert recover.interesting(rows) == []


def test_a_real_tsv_still_survives_the_tightening() -> None:
    """The one genuine hit of that sweep must not be filtered out with the noise."""
    rows = [
        _row(
            "http://data.webarchive.org.uk/opendata/ukwa.ds.1/classification/classification.tsv",
            637_342,
        )
    ]
    assert len(recover.interesting(rows)) == 1
