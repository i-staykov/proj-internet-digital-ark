"""Early Web CDX parser: field handling, filters, per-file stats."""

import gzip
from collections import Counter
from pathlib import Path

from ark.sources import SOURCES, parse_arquivo_cdxj, parse_early_web_cdx, parse_isc_survey

CDX_LINES = [
    " CDX N b a m s c k r V v D d g M n",
    "at,vetcontrol)/ 19981212033831 http://www.vetcontrol.at:80/ text/html 200 A - - 9 f.arc.gz",
    "com,example)/ 19970601120000 http://example.com:80/ text/html 200 B - - 9 f.arc.gz",
    "com,example)/r 19970601120001 http://example.com:80/r text/html 302 C - - 9 f.arc.gz",
    "com,late)/ 20030101000000 http://late.com/ text/html 200 D - - 9 f.arc.gz",
    "broken line without enough fields",
    "com,short)/ 1998 http://short.com/ text/html 200 E - - 9 f.arc.gz",
]


def _write_gzip_fixture(path: Path) -> None:
    path.write_bytes(gzip.compress(("\n".join(CDX_LINES) + "\n").encode("utf-8")))


def test_parser_filters_and_yields(tmp_path: Path) -> None:
    fixture = tmp_path / "sample.cdx.gz"
    _write_gzip_fixture(fixture)
    stats: Counter = Counter()

    records = list(parse_early_web_cdx(fixture, stats))

    assert [(r.raw, r.year, r.evidence_value) for r in records] == [
        ("http://www.vetcontrol.at:80/", 1998, "19981212033831"),
        ("http://example.com:80/", 1997, "19970601120000"),
    ]
    assert records[0].evidence_url == (
        "https://web.archive.org/web/19981212033831/http://www.vetcontrol.at:80/"
    )
    assert stats["lines"] == 7
    assert stats["header_lines"] == 1
    assert stats["non_200"] == 1
    assert stats["out_of_window"] == 1
    # both the short line and the 4-digit timestamp line are malformed
    assert stats["malformed"] == 2


def test_parser_reads_plain_text_too(tmp_path: Path) -> None:
    fixture = tmp_path / "sample.cdx"
    fixture.write_text(CDX_LINES[1] + "\n", encoding="utf-8")
    stats: Counter = Counter()

    records = list(parse_early_web_cdx(fixture, stats))

    assert len(records) == 1
    assert records[0].year == 1998


def test_early_web_is_registered_as_master_cdx_source() -> None:
    spec = SOURCES["early_web"]
    assert spec.evidence_type == "cdx_timestamp"
    assert spec.is_candidate_only is False


ISC_LINES = ["banc-agricol.ad", "1.2.3.4 test.eowyn.fr.eu.org", "", "ad"]


def test_isc_reads_domains_and_host_lists(tmp_path: Path) -> None:
    fixture = tmp_path / "wb_nw_9607.domains.gz"
    fixture.write_bytes(gzip.compress(("\n".join(ISC_LINES) + "\n").encode("utf-8")))
    stats: Counter = Counter()

    records = list(parse_isc_survey(fixture, stats))

    # survey date 9607 -> 1996; the last whitespace token is the host
    assert [(r.raw, r.year, r.evidence_value) for r in records] == [
        ("banc-agricol.ad", 1996, "1996-07"),
        ("test.eowyn.fr.eu.org", 1996, "1996-07"),
        ("ad", 1996, "1996-07"),
    ]
    assert stats["lines"] == 4


def test_isc_skips_pre_window_survey_file(tmp_path: Path) -> None:
    # the Jul 1995 survey is before our window and must be skipped whole
    fixture = tmp_path / "wb_nw_9507.domains.gz"
    fixture.write_bytes(gzip.compress(b"foo.com\n"))
    stats: Counter = Counter()

    records = list(parse_isc_survey(fixture, stats))

    assert records == []
    assert stats["out_of_window_file"] == 1
    assert stats["lines"] == 0


def test_isc_is_registered_as_artifact_master() -> None:
    spec = SOURCES["isc_survey"]
    assert spec.evidence_type == "artifact_listing"
    assert spec.is_candidate_only is False


CDXJ_LINES = [
    'com,example)/ 19961013223438 {"url": "http://www.example.com:80/", "status": "200"}',
    '1,208,96,204)/ 19961013223438 {"url": "http://204.96.208.1:80/", "status": "200"}',
    'org,foo)/x 19961014000000 {"url": "http://foo.org/x", "status": "404"}',
    'com,late)/ 20080101000000 {"url": "http://late.com/", "status": "200"}',
    "garbage line without json",
]


def test_arquivo_cdxj_filters_and_yields(tmp_path: Path) -> None:
    fixture = tmp_path / "Roteiro.cdxj"
    fixture.write_text("\n".join(CDXJ_LINES) + "\n", encoding="utf-8")
    stats: Counter = Counter()

    records = list(parse_arquivo_cdxj(fixture, stats))

    # the raw url comes from the JSON; the parser does not canonicalize, so the
    # bare-IP capture is still yielded (the loader's canonicalizer drops it)
    assert [(r.raw, r.year, r.evidence_value) for r in records] == [
        ("http://www.example.com:80/", 1996, "19961013223438"),
        ("http://204.96.208.1:80/", 1996, "19961013223438"),
    ]
    assert records[0].evidence_url == (
        "https://arquivo.pt/wayback/19961013223438/http://www.example.com:80/"
    )
    assert stats["non_200"] == 1
    assert stats["out_of_window"] == 1
    assert stats["malformed"] == 1
    assert stats["lines"] == 5


def test_arquivo_is_registered_as_cdx_master() -> None:
    spec = SOURCES["arquivo_roteiro"]
    assert spec.evidence_type == "cdx_timestamp"
    assert spec.is_candidate_only is False
