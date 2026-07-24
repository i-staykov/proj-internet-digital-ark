"""Bulk source parsers: field handling, filters, per-file stats, registration."""

import gzip
from collections import Counter
from pathlib import Path

from ark.sources import (
    SOURCES,
    parse_afnic_fr,
    parse_arquivo_cdxj,
    parse_early_web_cdx,
    parse_internet_scout,
    parse_isc_survey,
    parse_odp,
    parse_ukwa_link_source,
)

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


def test_arquivo_ia_shares_the_roteiro_parser_under_its_own_source_name() -> None:
    spec = SOURCES["arquivo_ia"]
    assert spec.source_name == "arquivo_ia"
    assert spec.evidence_type == "cdx_timestamp"
    assert spec.is_candidate_only is False
    # same tested CDXJ parser, so no new parsing logic to trust
    assert spec.parse is SOURCES["arquivo_roteiro"].parse


# name;PaysBE;DeptBE;VilleBE;NomBE;Sousdomaine;Type;PaysTit;DeptTit;IDN;Creation;Retrait
AFNIC_HEADER = (
    '"Nom de domaine";"Pays BE";"Departement BE";"Ville BE";"Nom BE";'
    '"Sous domaine";"Type du titulaire";"Pays titulaire";"Departement titulaire";'
    '"Domaine IDN";"Date de création";"Date de retrait du WHOIS"'
)
AFNIC_ROWS = [
    "keep.fr;FR;75;PARIS;REG;fr;;;;0;15-03-1998;",  # created 1998, still active -> 1998-2001
    "wd.fr;FR;75;PARIS;REG;fr;;;;0;01-01-1997;10-06-1999",  # withdrawn 1999 -> 1997-1999
    "old.fr;FR;75;PARIS;REG;fr;;;;0;20-05-1994;",  # created pre-window, active -> 1996-2001
    "future.fr;FR;75;PARIS;REG;fr;;;;0;10-10-2012;",  # created after window -> nothing
    "predrop.fr;FR;75;PARIS;REG;fr;;;;0;01-01-1993;15-02-1995",  # withdrawn pre-window -> nothing
    "nodate.fr;FR;75;PARIS;REG;fr;;;;0;;",  # no creation date -> skipped
]


def test_afnic_emits_every_in_window_registered_year(tmp_path: Path) -> None:
    fixture = tmp_path / "afnic.csv"
    fixture.write_text("\n".join([AFNIC_HEADER, *AFNIC_ROWS]) + "\n", encoding="utf-8")
    stats: Counter = Counter()
    records = list(parse_afnic_fr(fixture, stats))

    pairs = {(r.raw, r.year) for r in records}
    assert pairs == (
        {("keep.fr", y) for y in (1998, 1999, 2000, 2001)}  # created 1998, still active
        | {("wd.fr", y) for y in (1997, 1998, 1999)}  # withdrawn mid-1999
        | {("old.fr", y) for y in range(1996, 2002)}  # created pre-window, active
    )
    # every record carries its auditable registration interval, no year outside window
    assert all(r.evidence_value.startswith("registered ") for r in records)
    assert all(1996 <= r.year <= 2001 for r in records)
    assert stats["no_creation_date"] == 1  # nodate.fr
    assert stats["out_of_window"] == 2  # future.fr + predrop.fr


def test_afnic_is_registered_as_whois_creation_master() -> None:
    spec = SOURCES["afnic_fr"]
    assert spec.evidence_type == "whois_creation"
    assert spec.is_candidate_only is False


ODP_RDF = [
    "<RDF>",
    "<!-- Generated at 2000-08-07 08:00:40 GMT on  -->",
    '<Topic r:id="Top/Arts">',
    "  <catid>2</catid>",
    '  <link r:resource="http://www.example.com/"/>',
    '  <link r:resource="http://sub.example.org:80/path"/>',
    '  <narrow r:resource="Top/Arts/Music"/>',  # internal topic ref, not a URL
    "</Topic>",
    '<ExternalPage about="https://www.another.net/home">',
    "  <title>Another</title>",
    "</ExternalPage>",
    "</RDF>",
]


def test_odp_extracts_dated_external_sites_only(tmp_path: Path) -> None:
    fixture = tmp_path / "c2000.rdf"  # plain (no .gz) -> read as text
    fixture.write_text("\n".join(ODP_RDF) + "\n", encoding="utf-8")
    stats: Counter = Counter()
    records = list(parse_odp(fixture, stats))

    # the generation stamp fixes the year; the internal topic ref is excluded
    assert {(r.raw, r.year) for r in records} == {
        ("http://www.example.com/", 2000),
        ("http://sub.example.org:80/path", 2000),
        ("https://www.another.net/home", 2000),
    }
    # every row is stamped with the dump date for provenance
    assert {r.evidence_value for r in records} == {"odp 2000-08-07"}


def test_odp_is_registered_as_artifact_listing_master() -> None:
    spec = SOURCES["odp"]
    assert spec.evidence_type == "artifact_listing"
    assert spec.is_candidate_only is False


def _scout_record(oai_id: str, year: str, urls: list[str], extra: str = "") -> str:
    ids = "".join(f"<dc:identifier>{u}</dc:identifier>" for u in urls)
    return (
        f"<record><header><identifier>{oai_id}</identifier>"
        "<datestamp>2003-04-02</datestamp></header><metadata><oai_dc:dc>"
        f"<dc:date>{year}</dc:date><dc:description>d</dc:description>{extra}{ids}"
        "</oai_dc:dc></metadata></record>"
    )


def test_internet_scout_extracts_in_window_reviewed_sites(tmp_path: Path) -> None:
    fixture = tmp_path / "scout_oai.xml"
    fixture.write_text(
        "<OAI-PMH><ListRecords>"
        + _scout_record("oai:scout:1", "1998", ["http://www.example.com/"])
        + _scout_record("oai:scout:2", "1989", ["http://old.example.org/"])  # out of window
        + _scout_record("oai:scout:3", "2000", ["http://a.net/", "https://b.org/x"])
        + _scout_record(
            "oai:scout:4", "1997", [], extra="<dc:identifier>internal-id-999</dc:identifier>"
        )
        + "</ListRecords></OAI-PMH>",
        encoding="utf-8",
    )
    stats: Counter = Counter()
    records = list(parse_internet_scout(fixture, stats))

    assert {(r.raw, r.year) for r in records} == {
        ("http://www.example.com/", 1998),
        ("http://a.net/", 2000),
        ("https://b.org/x", 2000),
    }
    # the OAI record id is the auditable evidence reference
    assert (
        next(r.evidence_value for r in records if r.raw == "http://www.example.com/")
        == "oai:scout:1"
    )
    assert stats["out_of_window"] == 1  # the 1989 record
    assert stats["no_url"] == 1  # record 4 has only a non-URL identifier


def test_internet_scout_is_registered_as_dated_directory_master() -> None:
    spec = SOURCES["internet_scout"]
    assert spec.evidence_type == "dated_directory"
    assert spec.is_candidate_only is False


UKWA_LINES = [
    "1995|bssv01.lancs.ac.uk|www.env.uea.ac.uk\t2",
    "1996|acorn.educ.nottingham.ac.uk|www.planete.net\t2",
    "1998|albert.hep.ph.ic.ac.uk|www.clrc.ac.uk\t1",
    "2001|foo.co.uk|bar.com\t5",
    "malformed line without pipes",
]


def test_ukwa_link_source_takes_source_host_in_window(tmp_path: Path) -> None:
    fixture = tmp_path / "host-linkage.tsv.gz"
    fixture.write_bytes(gzip.compress(("\n".join(UKWA_LINES) + "\n").encode("utf-8")))
    stats: Counter = Counter()

    records = list(parse_ukwa_link_source(fixture, stats))

    # only the source host, only in-window years; the 1995 row is dropped
    assert [(r.raw, r.year, r.evidence_value) for r in records] == [
        ("acorn.educ.nottingham.ac.uk", 1996, "host_link_graph:1996"),
        ("albert.hep.ph.ic.ac.uk", 1998, "host_link_graph:1998"),
        ("foo.co.uk", 2001, "host_link_graph:2001"),
    ]
    assert stats["out_of_window"] == 1
    assert stats["malformed"] == 1


def test_ukwa_stops_after_the_window(tmp_path: Path) -> None:
    # the graph is year-sorted; the parser breaks at the first post-2001 row
    # (skipping the huge out-of-window tail and the truncated download end)
    rows = [
        "2000|a.co.uk|x.com\t1",
        "2001|b.co.uk|y.com\t1",
        "2002|c.co.uk|z.com\t1",
        "2005|d.co.uk|w.com\t1",
    ]
    fixture = tmp_path / "host-linkage.tsv.gz"
    fixture.write_bytes(gzip.compress(("\n".join(rows) + "\n").encode("utf-8")))
    stats: Counter = Counter()

    records = list(parse_ukwa_link_source(fixture, stats))

    assert [(r.raw, r.year) for r in records] == [("a.co.uk", 2000), ("b.co.uk", 2001)]


def test_ukwa_tolerates_truncated_gzip(tmp_path: Path) -> None:
    rows = "\n".join(f"199{y}|host{y}.co.uk|t.com\t1" for y in range(6, 10)) + "\n"
    blob = gzip.compress(rows.encode("utf-8"))
    # lop off the gzip tail so decompression raises partway through
    fixture = tmp_path / "host-linkage.tsv.gz"
    fixture.write_bytes(blob[: len(blob) - 20])
    stats: Counter = Counter()

    # must not raise; yields the intact prefix and records the truncation
    records = list(parse_ukwa_link_source(fixture, stats))

    assert len(records) >= 1
    assert stats["truncated_tail"] == 1


def test_ukwa_link_source_is_master() -> None:
    spec = SOURCES["ukwa_link_source"]
    assert spec.evidence_type == "link_source"
    assert spec.is_candidate_only is False
