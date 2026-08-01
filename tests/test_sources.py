"""Bulk source parsers: field handling, filters, per-file stats, registration."""

import gzip
import json
from collections import Counter
from pathlib import Path

from ark.sources import (
    SOURCES,
    parse_afnic_fr,
    parse_arquivo_cdxj,
    parse_cdx_snapshot,
    parse_early_web_cdx,
    parse_expansion_directory,
    parse_expansion_links,
    parse_internet_scout,
    parse_isc_survey,
    parse_odp,
    parse_rdap_snapshot,
    parse_ukwa_link_source,
    parse_ukwa_link_target,
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


_JOURNAL_NAME = "rdap_20260725T120000Z.jsonl"


def _journal(tmp_path: Path, records: list[dict], name: str = _JOURNAL_NAME) -> Path:
    path = tmp_path / name
    body = "".join(json.dumps(r) + "\n" for r in records)
    if name.endswith(".gz"):
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            fh.write(body)
    else:
        path.write_text(body, encoding="utf-8")
    return path


def test_rdap_snapshot_yields_only_the_creation_year(tmp_path) -> None:
    path = _journal(
        tmp_path,
        [
            {"domain": "in.com", "status": 200, "creation_year": 1998, "response": {}},
            {"domain": "early.com", "status": 200, "creation_year": 1995, "response": {}},
            {"domain": "late.com", "status": 200, "creation_year": 2004, "response": {}},
            {"domain": "gone.com", "status": 404, "creation_year": None, "response": None},
        ],
    )
    stats: Counter = Counter()
    records = list(parse_rdap_snapshot(path, stats))
    # one record, for the creation year alone; out-of-window years attest nothing
    assert [(r.raw, r.year) for r in records] == [("in.com", 1998)]
    assert records[0].evidence_value == "rdap creation 1998"
    assert records[0].evidence_url == "https://rdap.org/domain/in.com"
    assert stats["journal_lines"] == 4
    assert stats["outside_window"] == 2
    assert stats["not_dated"] == 1


def test_rdap_snapshot_reads_gzip_and_skips_junk_lines(tmp_path) -> None:
    path = tmp_path / "rdap_20260725T130000Z.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({"domain": "ok.fr", "creation_year": 2000}) + "\n")
        fh.write("\n")
        fh.write("{not json\n")
        fh.write(json.dumps({"creation_year": 1997}) + "\n")  # no domain
    stats: Counter = Counter()
    records = list(parse_rdap_snapshot(path, stats))
    assert [(r.raw, r.year) for r in records] == [("ok.fr", 2000)]
    assert stats["unparseable_line"] == 1
    assert stats["no_domain"] == 1


def test_rdap_snapshot_is_registered_apart_from_the_legacy_source() -> None:
    spec = SOURCES["rdap_snapshot"]
    assert spec.source_name == "rdap_snapshot"
    assert spec.evidence_type == "whois_creation"
    assert spec.acquisition_method == "rdap_journal_file"
    assert spec.is_candidate_only is False


def test_cdx_snapshot_yields_a_record_per_returned_year(tmp_path) -> None:
    path = _journal(
        tmp_path,
        [
            {"domain": "hit.com", "status": 200, "years": [1997, 1999], "truncated": False},
            {"domain": "none.com", "status": 200, "years": [], "truncated": False},
            {"domain": "err.com", "status": 503, "years": [], "truncated": False},
            {"domain": "out.com", "status": 200, "years": [2005], "truncated": False},
        ],
        name="cdx_20260725T120000Z.jsonl",
    )
    stats: Counter = Counter()
    records = list(parse_cdx_snapshot(path, stats))

    # one record per year actually returned, no inference of adjacent years
    assert [(r.raw, r.year) for r in records] == [("hit.com", 1997), ("hit.com", 1999)]
    assert records[0].evidence_value == "cdx capture 1997"
    assert stats["journal_lines"] == 4
    assert stats["query_failed"] == 1
    assert stats["no_capture_in_window"] == 2  # none.com and the out-of-window one


def test_cdx_snapshot_counts_truncated_responses(tmp_path) -> None:
    path = _journal(
        tmp_path,
        [{"domain": "big.com", "status": 200, "years": [1998], "truncated": True}],
        name="cdx_20260725T130000Z.jsonl",
    )
    stats: Counter = Counter()
    assert len(list(parse_cdx_snapshot(path, stats))) == 1
    assert stats["truncated_response"] == 1


def test_cdx_snapshot_is_registered_as_a_cdx_master_source() -> None:
    spec = SOURCES["cdx_snapshot"]
    assert spec.source_name == "ia_cdx_bulk"
    assert spec.evidence_type == "cdx_timestamp"
    assert spec.acquisition_method == "ia_cdx_collapsed_query"
    assert spec.is_candidate_only is False


UKWA_ROWS = [
    "1998|source-a.co.uk|target-a.com\t3",
    "1999|source-b.co.uk|target-b.de\t1",
    "2003|late.co.uk|late-target.com\t9",
]


def test_ukwa_source_and_target_read_different_columns(tmp_path: Path) -> None:
    fixture = tmp_path / "host-linkage.tsv"
    fixture.write_text("\n".join(UKWA_ROWS) + "\n", encoding="utf-8")

    src_stats: Counter = Counter()
    sources = [(r.raw, r.year) for r in parse_ukwa_link_source(fixture, src_stats)]
    tgt_stats: Counter = Counter()
    targets = [(r.raw, r.year) for r in parse_ukwa_link_target(fixture, tgt_stats)]

    assert sources == [("source-a.co.uk", 1998), ("source-b.co.uk", 1999)]
    assert targets == [("target-a.com", 1998), ("target-b.de", 1999)]
    # the scan stops at the first out-of-window year rather than reading on
    assert src_stats["lines"] == 3 and tgt_stats["lines"] == 3


def test_ukwa_target_is_registered_as_candidate_only() -> None:
    spec = SOURCES["ukwa_link_target"]
    assert spec.evidence_type == "link_target"
    # this is the whole point: being linked to can never assign a year
    assert spec.is_candidate_only is True
    assert SOURCES["ukwa_link_source"].is_candidate_only is False


EXPANSION_RECORDS = [
    {
        "domain": "http://dir.example/",
        "page_url": "http://dir.example/",
        "status": 200,
        "timestamp": "19980101000000",
        "year": 1998,
        "curated": True,
        "domains": ["listed-a.com", "listed-b.org"],
    },
    {
        "domain": "http://blog.example/",
        "page_url": "http://blog.example/",
        "status": 200,
        "timestamp": "19990101000000",
        "year": 1999,
        "curated": False,
        "domains": ["linked-c.net"],
    },
    {
        "domain": "http://dead.example/",
        "page_url": "http://dead.example/",
        "status": 503,
        "timestamp": None,
        "year": None,
        "curated": True,
        "domains": [],
    },
]


def test_expansion_sources_split_the_same_journal_by_curation(tmp_path) -> None:
    path = _journal(tmp_path, EXPANSION_RECORDS, name="expand_20260726T000000Z.jsonl")

    dir_stats: Counter = Counter()
    directory = [(r.raw, r.year) for r in parse_expansion_directory(path, dir_stats)]
    link_stats: Counter = Counter()
    links = [(r.raw, r.year) for r in parse_expansion_links(path, link_stats)]

    # a curated page's entries are master evidence for its capture year
    assert directory == [("listed-a.com", 1998), ("listed-b.org", 1998)]
    # an ordinary page's outbound links are candidates only
    assert links == [("linked-c.net", 1999)]
    # each half counts the other half and the failed fetch, so nothing is silent
    assert dir_stats["other_half"] == 1 and dir_stats["fetch_failed"] == 1
    assert link_stats["other_half"] == 1 and link_stats["fetch_failed"] == 1


def test_expansion_evidence_records_the_page_it_came_from(tmp_path) -> None:
    path = _journal(tmp_path, EXPANSION_RECORDS[:1], name="expand_20260726T010000Z.jsonl")
    records = list(parse_expansion_directory(path, Counter()))
    assert records[0].evidence_value == "linked from http://dir.example/ captured 19980101000000"
    assert records[0].evidence_url == (
        "https://web.archive.org/web/19980101000000/http://dir.example/"
    )


def test_expansion_specs_carry_the_right_dispositions() -> None:
    assert SOURCES["expansion_links"].is_candidate_only is True
    assert SOURCES["expansion_directory"].is_candidate_only is False
    assert SOURCES["expansion_directory"].evidence_type == "dated_directory"


def test_ncsa_whats_new_dates_each_entry_by_its_issue(tmp_path) -> None:
    from ark.sources import parse_ncsa_whats_new

    path = tmp_path / "ncsa.tsv"
    path.write_text("example.com\t1996-01-01\nother.org\t1996-07-15\nundated.net\t\n")
    stats: Counter = Counter()
    records = list(parse_ncsa_whats_new(path, stats))

    assert [(r.raw, r.year) for r in records] == [("example.com", 1996), ("other.org", 1996)]
    # an entry the harvest could not date is counted, never dated by assumption
    assert stats["no_date"] == 1
    assert records[0].evidence_value == "ncsa whats-new entry 1996-01-01"


# --- NYPW first-capture index ------------------------------------------------


def _nypw_line(timestamp: str, original: str, status: str = "200") -> str:
    """One line in the eight-field NYPW first-capture format."""
    return (
        f"https://example/ com,example)/ {timestamp} {original} text/html {status} DIGEST123 1097\n"
    )


def test_nypw_reads_timestamp_and_url_from_their_own_columns(tmp_path):
    """The format is not classic CDX: the timestamp is field 2 and the URL
    field 3, where early_web has them at 1 and 2. Reading the wrong column
    silently yields a SURT as a domain and no year at all."""
    path = tmp_path / "nypw.txt"
    path.write_text(_nypw_line("19970326221054", "http://0-0-0checkmate.com:80/"))
    stats = Counter()
    records = list(SOURCES["nypw_firstcdx"].parse(path, stats))
    assert len(records) == 1
    assert records[0].year == 1997
    assert records[0].raw == "http://0-0-0checkmate.com:80/"


def test_nypw_drops_out_of_window_and_non_200(tmp_path):
    path = tmp_path / "nypw.txt"
    path.write_text(
        _nypw_line("20070717010807", "http://late.com/")
        + _nypw_line("19980101000000", "http://redirect.com/", status="302")
        + _nypw_line("19980101000000", "http://good.com/")
    )
    stats = Counter()
    records = list(SOURCES["nypw_firstcdx"].parse(path, stats))
    assert [r.raw for r in records] == ["http://good.com/"]
    assert stats["out_of_window"] == 1
    assert stats["non_200"] == 1


def test_nypw_evidences_only_the_year_it_names(tmp_path):
    """A first-capture row says the URL was archived in that year and nothing
    about any later one, which is III.7 applied to this source."""
    path = tmp_path / "nypw.txt"
    path.write_text(_nypw_line("19990601120000", "http://once.com/"))
    records = list(SOURCES["nypw_firstcdx"].parse(path, Counter()))
    assert [r.year for r in records] == [1999]


# --- Usenet announcement archives --------------------------------------------


def test_usenet_reads_the_giganews_iso_date_format(tmp_path):
    """Most posts carry an RFC 822 date, but the Giganews donation rewrote a
    large share as a bare YYYY/MM/DD, which parsedate_to_datetime rejects. In
    comp.infosystems.www.announce that is 21,346 of 23,282 messages, so a parser
    that only understands RFC 822 silently discards 92% of the archive."""
    from ark.usenet import message_year

    assert message_year("Tue, 18 Jun 1996 12:00:00 GMT") == 1996
    assert message_year("1997/06/18") == 1997
    assert message_year("1998-06-18") == 1998
    assert message_year("2010/06/18") == 2010  # readable, filtered later by window
    assert message_year("not a date") is None
    assert message_year("") is None


def test_usenet_separates_out_of_window_from_unreadable_dates(tmp_path):
    """One counter for both hides which problem a barren source has. An archive
    that is entirely out of window should be dropped; one whose dates cannot be
    parsed means the parser is wrong. alt.www.webmaster is 170 MB and 100%
    out of window, while comp.infosystems.www.announce looked 92% undated until
    the Giganews date format was handled."""
    from ark.usenet import parse_usenet

    path = tmp_path / "g.mbox"
    path.write_text(
        "From x\nDate: 2008/01/01\nMessage-ID: <a@h>\nFrom: p@vendor.com\n\nhttp://a.com/\n"
        "From x\nDate: garbled nonsense\nMessage-ID: <b@h>\nFrom: p@vendor.com\n\nhttp://b.com/\n"
        "From x\nDate: 1998/01/01\nMessage-ID: <c@h>\nFrom: p@vendor.com\n\nhttp://c.com/\n"
    )
    stats = Counter()
    records = list(parse_usenet(path, stats))
    assert stats["out_of_window"] == 1
    assert stats["unreadable_date"] == 1
    assert {r.year for r in records} == {1998}


def test_usenet_extracts_body_urls_and_the_sender_domain(tmp_path):
    """The From: domain counts because in vendor and announcement posts the
    sender is very often the site itself, and it is the one string a mail system
    validated rather than a human typed into a message body."""
    from ark.usenet import domains_in_message

    found = domains_in_message(
        "Check out http://www.example.com/new and https://other.co.uk/x",
        "Someone <person@vendor.net>",
    )
    assert set(found) == {"example.com", "other.co.uk", "vendor.net"}


def test_usenet_drops_infrastructure_hosts():
    """Archive and Usenet plumbing is not a website anyone announced."""
    from ark.usenet import domains_in_message

    found = domains_in_message("see http://groups.google.com/x", "a@deja.com")
    assert found == []


def test_usenet_journal_records_the_message_id_as_evidence(tmp_path):
    """The Message-ID is globally unique by design, so it names the exact post a
    year assignment came from and a reviewer can go and read it."""
    import gzip
    import json

    path = tmp_path / "usenet_dated.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "domain": "example.com",
                    "year": 1997,
                    "message_id": "<abc@host>",
                    "group": "comp.infosystems.www.announce",
                }
            )
            + "\n"
        )
    records = list(SOURCES["usenet_dated"].parse(path, Counter()))
    assert len(records) == 1
    assert records[0].year == 1997
    assert "<abc@host>" in records[0].evidence_value


def test_usenet_dated_is_master_and_mentions_are_candidate_only():
    """The split is the whole safety argument: a corroborated domain can carry
    the post date, an uncorroborated name cannot assign a year at all."""
    assert SOURCES["usenet_dated"].evidence_type == "dated_directory"
    assert not SOURCES["usenet_dated"].is_candidate_only
    assert SOURCES["usenet_candidates"].is_candidate_only
