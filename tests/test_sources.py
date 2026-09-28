"""Bulk source parsers: field handling, filters, per-file stats, registration."""

import gzip
import importlib.util
import json
from collections import Counter
from email.header import Header
from pathlib import Path

import pytest

from ark.canonical import to_registrable
from ark.sources import (
    SOURCES,
    _parse_usenet_whois_journal,
    attested_years,
    parse_afnic_fr,
    parse_arquivo_cdxj,
    parse_cdx_snapshot,
    parse_domain_creation_csv,
    parse_domain_year_captures,
    parse_early_web_cdx,
    parse_expansion_directory,
    parse_expansion_links,
    parse_iedr_register,
    parse_internet_scout,
    parse_isc_survey,
    parse_ncsa_whats_new,
    parse_odp,
    parse_rdap_snapshot,
    parse_registry_items,
    parse_ripe_dbase_1999,
    parse_ripe_dbase_changed,
    parse_ripe_dbase_split_2004,
    parse_ukwa_geoindex,
    parse_ukwa_link_source,
    parse_ukwa_link_target,
)
from ark.usenet import (
    bare_domains_in_body,
    body_of,
    domains_in_message,
    is_moderated_announce,
    message_year,
    parse_usenet,
)


def _script(name: str, rel: str):
    path = Path(__file__).resolve().parent.parent / "scripts" / rel
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


whois = _script("collect_usenet_whois", "sources/usenet/collect_usenet_whois.py")
texts = _script("probe_texts_corpus", "pricing/probe_texts_corpus.py")
_zone = SOURCES["internic_zone"].parse


def _parse(parser, tmp_path: Path, name: str, text: str):
    """Write `text` to `name`, gzipped when it ends `.gz`, and return the records and stats."""
    path = tmp_path / name
    if name.endswith(".gz"):
        path.write_bytes(gzip.compress(text.encode("utf-8")))
    else:
        path.write_text(text, encoding="utf-8")
    stats: Counter = Counter()
    return list(parser(path, stats)), stats


def _lines(rows: list[str]) -> str:
    return "\n".join(rows) + "\n"


def _jsonl(rows: list[dict]) -> str:
    return "".join(json.dumps(r) + "\n" for r in rows)


REGISTERED = {
    "early_web": ("cdx_timestamp", False),
    "isc_survey": ("artifact_listing", False),
    "arquivo_roteiro": ("cdx_timestamp", False),
    "arquivo_ia": ("cdx_timestamp", False),
    "afnic_fr": ("whois_creation", False),
    "odp": ("artifact_listing", False),
    "internet_scout": ("dated_directory", False),
    "ukwa_link_source": ("link_source", False),
    # its rows keep no host, so they cannot identify the name they would date
    "ukwa_link_target": ("link_target", True),
    "ukwa_link_target_bare": ("artifact_listing", False),
    "rdap_snapshot": ("whois_creation", False),
    "cdx_snapshot": ("cdx_timestamp", False),
    "expansion_directory": ("dated_directory", False),
    "expansion_links": ("link_target", True),
    "usenet_dated": ("dated_directory", False),
    "usenet_candidates": ("link_target", True),
    "usenet_whois_dated": ("whois_creation", False),
    "usenet_whois_candidates": ("link_target", True),
    "domain_creation_bulk": ("whois_creation", False),
    "internic_zone": ("artifact_listing", False),
    "dk_hostmaster_dk_zonen_domains_txt_wayback_2001": ("artifact_listing", False),
    "ukwa_geoindex": ("cdx_timestamp", False),
}


@pytest.mark.parametrize(("key", "registered"), list(REGISTERED.items()), ids=list(REGISTERED))
def test_each_source_is_registered_at_its_evidence_class(key, registered) -> None:
    """A source's class and candidate flag decide whether its rows can date a year."""
    assert (SOURCES[key].evidence_type, SOURCES[key].is_candidate_only) == registered


def test_each_source_files_under_its_own_name_and_method() -> None:
    """A parser shared between specs still files each under its own source name."""
    assert SOURCES["arquivo_ia"].parse is SOURCES["arquivo_roteiro"].parse is parse_arquivo_cdxj
    assert SOURCES["arquivo_ia"].source_name == "arquivo_ia"
    dated, candidates = SOURCES["usenet_whois_dated"], SOURCES["usenet_whois_candidates"]
    assert dated.parse is candidates.parse is _parse_usenet_whois_journal
    assert dated.source_name != candidates.source_name
    dk = SOURCES["dk_hostmaster_dk_zonen_domains_txt_wayback_2001"]
    assert dk.parse is parse_registry_items
    assert SOURCES["rdap_snapshot"].source_name == "rdap_snapshot"
    assert SOURCES["rdap_snapshot"].acquisition_method == "rdap_journal_file"
    assert SOURCES["cdx_snapshot"].source_name == "ia_cdx_bulk"
    assert SOURCES["cdx_snapshot"].acquisition_method == "ia_cdx_collapsed_query"
    assert SOURCES["domain_creation_bulk"].source_name == "domain_creation_bulk"
    assert SOURCES["ukwa_geoindex"].acquisition_method == "bl_geoindex_extract"


CDX_LINES = [
    " CDX N b a m s c k r V v D d g M n",
    "at,vetcontrol)/ 19981212033831 http://www.vetcontrol.at:80/ text/html 200 A - - 9 f.arc.gz",
    "com,example)/ 19970601120000 http://example.com:80/ text/html 200 B - - 9 f.arc.gz",
    "com,example)/r 19970601120001 http://example.com:80/r text/html 302 C - - 9 f.arc.gz",
    "com,late)/ 20030101000000 http://late.com/ text/html 200 D - - 9 f.arc.gz",
    "broken line without enough fields",
    "com,short)/ 1998 http://short.com/ text/html 200 E - - 9 f.arc.gz",
]


@pytest.mark.parametrize("name", ["sample.cdx.gz", "sample.cdx"], ids=["gzip", "plain"])
def test_early_web_filters_and_yields(tmp_path: Path, name: str) -> None:
    records, stats = _parse(parse_early_web_cdx, tmp_path, name, _lines(CDX_LINES))
    assert [(r.raw, r.year, r.evidence_value) for r in records] == [
        ("http://www.vetcontrol.at:80/", 1998, "19981212033831"),
        ("http://example.com:80/", 1997, "19970601120000"),
    ]
    assert records[0].evidence_url == (
        "https://web.archive.org/web/19981212033831/http://www.vetcontrol.at:80/"
    )
    assert (stats["lines"], stats["header_lines"], stats["non_200"]) == (7, 1, 1)
    assert stats["out_of_window"] == 1
    # both the short line and the 4-digit timestamp line are malformed
    assert stats["malformed"] == 2


def test_isc_reads_domains_and_host_lists(tmp_path: Path) -> None:
    rows = ["banc-agricol.ad", "1.2.3.4 test.eowyn.fr.eu.org", "", "ad"]
    records, stats = _parse(parse_isc_survey, tmp_path, "wb_nw_9607.domains.gz", _lines(rows))
    # survey date 9607 is 1996; the last whitespace token is the host
    assert [(r.raw, r.year, r.evidence_value) for r in records] == [
        ("banc-agricol.ad", 1996, "1996-07"),
        ("test.eowyn.fr.eu.org", 1996, "1996-07"),
        ("ad", 1996, "1996-07"),
    ]
    assert stats["lines"] == 4


CDXJ_LINES = [
    'com,example)/ 19961013223438 {"url": "http://www.example.com:80/", "status": "200"}',
    '1,208,96,204)/ 19961013223438 {"url": "http://204.96.208.1:80/", "status": "200"}',
    'org,foo)/x 19961014000000 {"url": "http://foo.org/x", "status": "404"}',
    'com,late)/ 20080101000000 {"url": "http://late.com/", "status": "200"}',
    "garbage line without json",
]


def test_arquivo_cdxj_filters_and_yields(tmp_path: Path) -> None:
    records, stats = _parse(parse_arquivo_cdxj, tmp_path, "Roteiro.cdxj", _lines(CDXJ_LINES))
    # the parser does not canonicalize, so the bare-IP capture is yielded for the loader to drop
    assert [(r.raw, r.year, r.evidence_value) for r in records] == [
        ("http://www.example.com:80/", 1996, "19961013223438"),
        ("http://204.96.208.1:80/", 1996, "19961013223438"),
    ]
    assert records[0].evidence_url == (
        "https://arquivo.pt/wayback/19961013223438/http://www.example.com:80/"
    )
    assert (stats["non_200"], stats["out_of_window"], stats["malformed"]) == (1, 1, 1)
    assert stats["lines"] == 5


AFNIC_ROWS = [
    '"Nom de domaine";"Pays BE";"Departement BE";"Ville BE";"Nom BE";"Sous domaine";'
    '"Type du titulaire";"Pays titulaire";"Departement titulaire";"Domaine IDN";'
    '"Date de création";"Date de retrait du WHOIS"',
    "keep.fr;FR;75;PARIS;REG;fr;;;;0;15-03-1998;",  # created 1998, still active
    "wd.fr;FR;75;PARIS;REG;fr;;;;0;01-01-1997;10-06-1999",  # withdrawn 1999
    "old.fr;FR;75;PARIS;REG;fr;;;;0;20-05-1994;",  # created pre-window, active
    "future.fr;FR;75;PARIS;REG;fr;;;;0;10-10-2012;",  # created after window
    "predrop.fr;FR;75;PARIS;REG;fr;;;;0;01-01-1993;15-02-1995",  # withdrawn pre-window
    "nodate.fr;FR;75;PARIS;REG;fr;;;;0;;",  # no creation date
]


def test_afnic_emits_every_in_window_registered_year(tmp_path: Path) -> None:
    records, stats = _parse(parse_afnic_fr, tmp_path, "afnic.csv", _lines(AFNIC_ROWS))
    assert {(r.raw, r.year) for r in records} == (
        {("keep.fr", y) for y in (1998, 1999, 2000, 2001)}
        | {("wd.fr", y) for y in (1997, 1998, 1999)}
        | {("old.fr", y) for y in range(1996, 2002)}
    )
    # every record carries its auditable registration interval, no year outside window
    assert all(r.evidence_value.startswith("registered ") for r in records)
    assert all(1996 <= r.year <= 2001 for r in records)
    assert stats["no_creation_date"] == 1  # nodate.fr
    assert stats["out_of_window"] == 2  # future.fr and predrop.fr


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
    records, _ = _parse(parse_odp, tmp_path, "c2000.rdf", _lines(ODP_RDF))
    # the generation stamp fixes the year; the internal topic ref is excluded
    assert {(r.raw, r.year) for r in records} == {
        ("http://www.example.com/", 2000),
        ("http://sub.example.org:80/path", 2000),
        ("https://www.another.net/home", 2000),
    }
    assert {r.evidence_value for r in records} == {"odp 2000-08-07"}


def _scout_record(oai_id: str, year: str, urls: list[str], extra: str = "") -> str:
    ids = "".join(f"<dc:identifier>{u}</dc:identifier>" for u in urls)
    return (
        f"<record><header><identifier>{oai_id}</identifier>"
        "<datestamp>2003-04-02</datestamp></header><metadata><oai_dc:dc>"
        f"<dc:date>{year}</dc:date><dc:description>d</dc:description>{extra}{ids}"
        "</oai_dc:dc></metadata></record>"
    )


def test_internet_scout_extracts_in_window_reviewed_sites(tmp_path: Path) -> None:
    xml = (
        "<OAI-PMH><ListRecords>"
        + _scout_record("oai:scout:1", "1998", ["http://www.example.com/"])
        + _scout_record("oai:scout:2", "1989", ["http://old.example.org/"])
        + _scout_record("oai:scout:3", "2000", ["http://a.net/", "https://b.org/x"])
        + _scout_record("oai:scout:4", "1997", [], extra="<dc:identifier>id-999</dc:identifier>")
        + "</ListRecords></OAI-PMH>"
    )
    records, stats = _parse(parse_internet_scout, tmp_path, "scout_oai.xml", xml)
    assert {(r.raw, r.year) for r in records} == {
        ("http://www.example.com/", 1998),
        ("http://a.net/", 2000),
        ("https://b.org/x", 2000),
    }
    # the OAI record id is the auditable evidence reference
    assert {r.raw: r.evidence_value for r in records}["http://www.example.com/"] == "oai:scout:1"
    assert stats["out_of_window"] == 1  # the 1989 record
    assert stats["no_url"] == 1  # record 4 has only a non-URL identifier


UKWA_LINES = [
    "1995|bssv01.lancs.ac.uk|www.env.uea.ac.uk\t2",
    "1996|acorn.educ.nottingham.ac.uk|www.planete.net\t2",
    "1998|albert.hep.ph.ic.ac.uk|www.clrc.ac.uk\t1",
    "2001|foo.co.uk|bar.com\t5",
    "malformed line without pipes",
]


def test_ukwa_link_source_takes_source_host_in_window(tmp_path: Path) -> None:
    records, stats = _parse(parse_ukwa_link_source, tmp_path, "hl.tsv.gz", _lines(UKWA_LINES))
    assert [(r.raw, r.year, r.evidence_value) for r in records] == [
        ("acorn.educ.nottingham.ac.uk", 1996, "host_link_graph:1996"),
        ("albert.hep.ph.ic.ac.uk", 1998, "host_link_graph:1998"),
        ("foo.co.uk", 2001, "host_link_graph:2001"),
    ]
    assert (stats["out_of_window"], stats["malformed"]) == (1, 1)


def test_ukwa_reads_every_shard_and_not_just_the_first(tmp_path: Path) -> None:
    """The file is internally sorted shards, so an out-of-window year is not the end."""
    rows = ["2000|a.co.uk|x.com\t1", "2001|b.co.uk|y.com\t1", "2002|c.co.uk|z.com\t1"]
    rows += ["2010|d.co.uk|w.com\t1"]
    # the second shard starts over
    rows += ["1996|e.co.uk|v.com\t1", "2001|f.co.uk|u.com\t1", "2004|g.co.uk|t.com\t1"]
    records, stats = _parse(parse_ukwa_link_source, tmp_path, "hl.tsv.gz", _lines(rows))
    assert [(r.raw, r.year) for r in records] == [
        ("a.co.uk", 2000),
        ("b.co.uk", 2001),
        ("e.co.uk", 1996),
        ("f.co.uk", 2001),
    ]
    assert stats["out_of_window"] == 3


def test_ukwa_tolerates_truncated_gzip(tmp_path: Path) -> None:
    rows = "\n".join(f"199{y}|host{y}.co.uk|t.com\t1" for y in range(6, 10)) + "\n"
    blob = gzip.compress(rows.encode("utf-8"))
    fixture = tmp_path / "host-linkage.tsv.gz"
    fixture.write_bytes(blob[: len(blob) - 20])
    stats: Counter = Counter()
    # must not raise; yields the intact prefix and records the truncation
    assert len(list(parse_ukwa_link_source(fixture, stats))) >= 1
    assert stats["truncated_tail"] == 1


def test_ukwa_source_and_target_read_different_columns(tmp_path: Path) -> None:
    rows = ["1998|source-a.co.uk|target-a.com\t3", "1999|source-b.co.uk|target-b.de\t1"]
    text = _lines([*rows, "2003|late.co.uk|late-target.com\t9"])
    sources, src_stats = _parse(parse_ukwa_link_source, tmp_path, "hl.tsv", text)
    targets, tgt_stats = _parse(parse_ukwa_link_target, tmp_path, "hl.tsv", text)
    assert [(r.raw, r.year) for r in sources] == [
        ("source-a.co.uk", 1998),
        ("source-b.co.uk", 1999),
    ]
    assert [(r.raw, r.year) for r in targets] == [("target-a.com", 1998), ("target-b.de", 1999)]
    assert src_stats["lines"] == 3 and tgt_stats["lines"] == 3


GEOINDEX_ROWS = [
    "19990412183021/http://www.example.co.uk/index.html\tOX11 0QX",
    "20010101000000/http://sub.host.ac.uk/a/b\tSW1A 1AA",
    # junk stamps are in the real file, so the window filter rejects them
    "19800101000000/http://www.old.co.uk/\tE1 6AN",
    "19941231235959/http://www.early.co.uk/\tE1 6AN",
    "20051231235959/http://www.late.co.uk/\tE1 6AN",
    "notatimestamp/http://www.bad.co.uk/\tE1 6AN",
]


def test_ukwa_geoindex_dates_in_window_rows_by_their_own_stamp(tmp_path: Path) -> None:
    """The year is read from the capture stamp kept verbatim, never supplied alongside it."""
    records, stats = _parse(parse_ukwa_geoindex, tmp_path, "geo.tsv.gz", _lines(GEOINDEX_ROWS))
    assert [r.year for r in records] == [1999, 2001]
    assert (stats["out_of_window"], stats["malformed"]) == (3, 1)
    assert records[0].evidence_value == "19990412183021"
    assert records[0].evidence_value.startswith(str(records[0].year))
    assert "19990412183021" in records[0].evidence_url


@pytest.mark.parametrize(
    ("year", "attested"),
    [(1998, (1998,)), (1996, (1996,)), (2001, (2001,)), (1995, ()), (1970, ()), (2004, ())],
    ids=["1998", "window-start", "window-end", "before", "long-before", "after"],
)
def test_attested_years_is_the_creation_year_alone(year, attested) -> None:
    """A creation date attests its own year and no later one, and nothing outside the window."""
    assert attested_years(year) == attested


def test_rdap_snapshot_yields_only_the_creation_year(tmp_path: Path) -> None:
    rows = [
        {"domain": "in.com", "status": 200, "creation_year": 1998, "response": {}},
        {"domain": "early.com", "status": 200, "creation_year": 1995, "response": {}},
        {"domain": "late.com", "status": 200, "creation_year": 2004, "response": {}},
        {"domain": "gone.com", "status": 404, "creation_year": None, "response": None},
    ]
    records, stats = _parse(parse_rdap_snapshot, tmp_path, "rdap_1.jsonl", _jsonl(rows))
    assert [(r.raw, r.year) for r in records] == [("in.com", 1998)]
    assert records[0].evidence_value == "rdap creation 1998"
    assert records[0].evidence_url == "https://rdap.org/domain/in.com"
    assert (stats["journal_lines"], stats["outside_window"], stats["not_dated"]) == (4, 2, 1)


def test_rdap_snapshot_reads_gzip_and_skips_junk_lines(tmp_path: Path) -> None:
    ok, nameless = json.dumps({"domain": "ok.fr", "creation_year": 2000}), '{"creation_year": 1997}'
    text = f"{ok}\n\n{{not json\n{nameless}\n"
    records, stats = _parse(parse_rdap_snapshot, tmp_path, "rdap_2.jsonl.gz", text)
    assert [(r.raw, r.year) for r in records] == [("ok.fr", 2000)]
    assert (stats["unparseable_line"], stats["no_domain"]) == (1, 1)


def test_cdx_snapshot_yields_a_record_per_returned_year(tmp_path: Path) -> None:
    rows = [
        {"domain": "hit.com", "status": 200, "years": [1997, 1999], "truncated": False},
        {"domain": "none.com", "status": 200, "years": [], "truncated": False},
        {"domain": "err.com", "status": 503, "years": [], "truncated": False},
        {"domain": "out.com", "status": 200, "years": [2005], "truncated": False},
        {"domain": "big.com", "status": 200, "years": [1998], "truncated": True},
    ]
    records, stats = _parse(parse_cdx_snapshot, tmp_path, "cdx_1.jsonl", _jsonl(rows))
    # one record per year actually returned, no inference of adjacent years
    assert [(r.raw, r.year) for r in records] == [
        ("hit.com", 1997),
        ("hit.com", 1999),
        ("big.com", 1998),
    ]
    assert records[0].evidence_value == "cdx capture 1997"
    assert (stats["journal_lines"], stats["query_failed"]) == (5, 1)
    assert stats["no_capture_in_window"] == 2  # none.com and the out-of-window one
    assert stats["truncated_response"] == 1


def test_cdx_snapshot_names_the_exact_capture_when_the_record_keeps_its_stamp(tmp_path) -> None:
    """A per-year stamp or the domain's own `hosts` entry names the capture; nothing else does."""
    hosts = {"www.host.com": "19970101000000", "host.com": "19990301000000"}
    stamps = {"1998": "19981205115848"}
    rows = [
        {"domain": "conv.com", "status": 200, "years": [1997, 1998], "stamps": stamps},
        {"domain": "Host.com", "status": 200, "years": [1997, 1999], "hosts": hosts},
        {"domain": "bad.com", "status": 200, "years": [2000], "stamps": {"2000": "2000"}},
        {"domain": "off.com", "status": 200, "years": [2001], "stamps": {"2001": "19991231"}},
    ]
    records, stats = _parse(parse_cdx_snapshot, tmp_path, "cdx_2.jsonl", _jsonl(rows))
    assert [(r.raw, r.year, r.evidence_value) for r in records] == [
        ("conv.com", 1997, "cdx capture 1997"),
        ("conv.com", 1998, "cdx capture 19981205115848 conv.com"),
        ("Host.com", 1997, "cdx capture 1997"),
        ("Host.com", 1999, "cdx capture 19990301000000 host.com"),
        ("bad.com", 2000, "cdx capture 2000"),
        ("off.com", 2001, "cdx capture 2001"),
    ]
    assert [r.evidence_url.removeprefix("https://web.archive.org/web/") for r in records] == [
        "1997/conv.com",
        "19981205115848/http://conv.com/",
        "1997/Host.com",
        "19990301000000/http://host.com/",
        "2000/bad.com",
        "2001/off.com",
    ]
    assert all(r.evidence_url.startswith("https://web.archive.org/web/") for r in records)
    assert stats["exact_capture"] == 2


def _page(url: str, status: int, timestamp: str | None, curated: bool, domains: list[str]):
    row = {"domain": url, "page_url": url, "status": status, "timestamp": timestamp}
    row |= {"year": int(timestamp[:4]) if timestamp else None}
    return row | {"curated": curated, "domains": domains}


EXPANSION_RECORDS = [
    _page("http://dir.example/", 200, "19980101000000", True, ["listed-a.com", "listed-b.org"]),
    _page("http://blog.example/", 200, "19990101000000", False, ["linked-c.net"]),
    _page("http://dead.example/", 503, None, True, []),
]


def test_expansion_sources_split_the_same_journal_by_curation(tmp_path: Path) -> None:
    name, text = "expand_1.jsonl", _jsonl(EXPANSION_RECORDS)
    directory, dir_stats = _parse(parse_expansion_directory, tmp_path, name, text)
    links, link_stats = _parse(parse_expansion_links, tmp_path, name, text)
    # a curated page's entries date its capture year; an ordinary page's links are candidates
    assert [(r.raw, r.year) for r in directory] == [("listed-a.com", 1998), ("listed-b.org", 1998)]
    assert [(r.raw, r.year) for r in links] == [("linked-c.net", 1999)]
    # each half counts the other half and the failed fetch, so nothing is silent
    assert dir_stats["other_half"] == 1 and dir_stats["fetch_failed"] == 1
    assert link_stats["other_half"] == 1 and link_stats["fetch_failed"] == 1
    # the evidence records the page it came from
    assert directory[0].evidence_value == "linked from http://dir.example/ captured 19980101000000"
    assert directory[0].evidence_url == (
        "https://web.archive.org/web/19980101000000/http://dir.example/"
    )


def test_ncsa_whats_new_dates_each_entry_by_its_issue(tmp_path: Path) -> None:
    text = "example.com\t1996-01-01\nother.org\t1996-07-15\nundated.net\t\n"
    records, stats = _parse(parse_ncsa_whats_new, tmp_path, "ncsa.tsv", text)
    assert [(r.raw, r.year) for r in records] == [("example.com", 1996), ("other.org", 1996)]
    # an entry the harvest could not date is counted, never dated by assumption
    assert stats["no_date"] == 1
    assert records[0].evidence_value == "ncsa whats-new entry 1996-01-01"


def _nypw(*rows: tuple[str, str, str]) -> str:
    """Lines in the eight-field NYPW first-capture format: (timestamp, url, status)."""
    return "".join(
        f"https://example/ com,example)/ {ts} {url} text/html {status} DIGEST123 1097\n"
        for ts, url, status in rows
    )


def test_nypw_reads_its_own_columns_and_keeps_in_window_200s(tmp_path: Path) -> None:
    """The timestamp is field 2 and the URL field 3, and a row evidences its own year alone."""
    text = _nypw(
        ("19970326221054", "http://0-0-0checkmate.com:80/", "200"),
        ("20070717010807", "http://late.com/", "200"),
        ("19980101000000", "http://redirect.com/", "302"),
        ("19980101000000", "http://good.com/", "200"),
    )
    records, stats = _parse(SOURCES["nypw_firstcdx"].parse, tmp_path, "nypw.txt", text)
    assert [(r.raw, r.year) for r in records] == [
        ("http://0-0-0checkmate.com:80/", 1997),
        ("http://good.com/", 1998),
    ]
    assert (stats["out_of_window"], stats["non_200"]) == (1, 1)


def test_nypw_nonok_takes_exactly_the_lane_the_200_parser_drops(tmp_path: Path) -> None:
    """The 200 and non-200 specs partition the in-window rows; a `-` status is no answer."""
    text = _nypw(
        ("20070717010807", "http://late.com/", "404"),
        ("19980101000000", "http://redirect.com/", "302"),
        ("20010101000000", "http://gone.com/", "404"),
        ("19980101000000", "http://good.com/", "200"),
        ("19990101000000", "http://nothing.com/", "-"),
        ("20010305101500", "http://hmcfunding.com:80/", "500"),
    )
    records, stats = _parse(SOURCES["nypw_timemaps_nonok"].parse, tmp_path, "nypw.txt", text)
    assert [(r.raw, r.year) for r in records] == [
        ("http://redirect.com/", 1998),
        ("http://gone.com/", 2001),
        ("http://hmcfunding.com:80/", 2001),
    ]
    assert (stats["out_of_window"], stats["ok_lane"], stats["no_response"]) == (1, 1, 1)
    # the status the server answered with is part of the evidence
    assert records[2].evidence_value == "nypw timemap capture status 500 20010305101500"
    assert records[2].evidence_url == (
        "https://web.archive.org/web/20010305101500/http://hmcfunding.com:80/"
    )


DATES = {
    "rfc822": ("Tue, 18 Jun 1996 12:00:00 GMT", 1996),
    "giganews-slash": ("1997/06/18", 1997),
    "iso": ("1998-06-18", 1998),
    "out-of-window-still-read": ("2010/06/18", 2010),
    "garbage": ("not a date", None),
    "empty": ("", None),
    "header-rfc822": (Header("Tue, 18 Jun 1996 12:00:00 GMT"), 1996),
    "header-slash": (Header("1997/06/18"), 1997),
    "header-garbage": (Header("not a date"), None),
}


@pytest.mark.parametrize(("raw", "year"), list(DATES.values()), ids=list(DATES))
def test_usenet_reads_every_date_header_form(raw, year) -> None:
    """A Date reads as RFC 822, a bare YYYY/MM/DD or ISO date, as a string or an RFC 2047 Header."""
    assert message_year(raw) == year


def test_usenet_separates_out_of_window_from_unreadable_dates(tmp_path: Path) -> None:
    post = "From x\nDate: {}\nMessage-ID: <{}@h>\nFrom: p@vendor.com\n\nhttp://{}.com/\n"
    text = "".join(post.format(*row) for row in [("2008/01/01", "a", "a"), ("garbled", "b", "b")])
    text += post.format("1998/01/01", "c", "c")
    records, stats = _parse(parse_usenet, tmp_path, "g.mbox", text)
    assert (stats["out_of_window"], stats["unreadable_date"]) == (1, 1)
    assert {r.year for r in records} == {1998}


MESSAGE_DOMAINS = {
    "body-urls-and-sender": (
        "Check out http://www.example.com/new and https://other.co.uk/x",
        "Someone <person@vendor.net>",
        ["example.com", "other.co.uk", "vendor.net"],
    ),
    "scheme-less-www": (
        "Try www.warehouse.co.uk for prices, or WWW.UPPER.COM",
        "",
        ["upper.com", "warehouse.co.uk"],
    ),
    "bare-host-in-prose": ("I work at bigcorp.com these days", "", []),
    "bare-path-is-its-own-source": ("we launched bigcorp.com last week", "", []),
    "www-inside-an-address": ("mail me at bob@www.baz.net", "", []),
    "both-spellings-once": ("http://www.foo.com/x and later just www.foo.com", "", ["foo.com"]),
    "infrastructure": ("see http://groups.google.com/x", "a@deja.com", []),
}


@pytest.mark.parametrize(
    ("body", "sender", "expected"), list(MESSAGE_DOMAINS.values()), ids=list(MESSAGE_DOMAINS)
)
def test_usenet_message_domains(body, sender, expected) -> None:
    """URLs, `www.` hosts and the sender's domain are read; a bare host and plumbing are not."""
    assert sorted(domains_in_message(body, sender)) == expected


def test_usenet_journal_records_the_message_id_as_evidence(tmp_path: Path) -> None:
    row = {"domain": "example.com", "year": 1997, "message_id": "<abc@host>", "group": "g"}
    records, _ = _parse(SOURCES["usenet_dated"].parse, tmp_path, "ud.jsonl.gz", _jsonl([row]))
    assert [r.year for r in records] == [1997]
    assert "<abc@host>" in records[0].evidence_value


def test_moderated_announce_follows_usenet_naming_convention() -> None:
    """A group with an announce or moderated component, or on the named list, is moderated."""
    assert is_moderated_announce("comp.os.linux.announce")
    assert is_moderated_announce("misc.business.moderated")
    assert is_moderated_announce("comp.internet.net-happenings")
    # the marker is not always last
    assert is_moderated_announce("news.announce.conferences")
    assert is_moderated_announce("news.announce.newgroups")
    assert not is_moderated_announce("alt.internet.commerce")
    assert not is_moderated_announce("biz.marketplace")


PRINTED = {
    "bare-two-label": ("visit foo.com today", {"foo.com"}),
    "url": ("http://foo.com/pricing", {"foo.com"}),
    "address": ("mail bob@foo.com", {"foo.com"}),
    "www": ("see www.foo.com", {"foo.com"}),
    "bare-in-prose": ("I work at bigcorp.com these days", {"bigcorp.com"}),
    "sentence-punctuation": ("the sentence end.Company said so", set()),
    "file-name": ("open the readme.txt file", set()),
    "html-file": ("index.html", set()),
    "abbreviation": ("U.S. Government offices", set()),
    "deep-host": ("a.b.c.foo.com", {"foo.com"}),
    "one-name-per-host": ("www.bbc.co.uk and bbc.co.uk", {"bbc.co.uk"}),
}


@pytest.mark.parametrize(("text", "expected"), list(PRINTED.values()), ids=list(PRINTED))
def test_printed_text_domains(text, expected) -> None:
    """Printed copy reads a bare name as an address, refuses punctuation and file names."""
    assert texts.domains_in(text) == expected


NEWS_HEADERS = b"From: a@b.com\r\nNewsgroups: alt.isd.net\r\n"
NEWS_HEADERS += b"Path: news.relay.org!feeder!not-for-mail\r\n\r\nthe site is realsite.com\r\n"
BARE = {
    "bare-host": ("we launched bigcorp.com last week", {"bigcorp.com"}),
    "upper-case": ("prices at WAREHOUSE.CO.UK", {"warehouse.co.uk"}),
    "host-with-path": ("mirror at ftp.example.org/pub", {"example.org"}),
    "url": ("see http://foo.com/x", set()),
    "address": ("mail bob@foo.com", set()),
    "inside-a-url-path": ("http://host.net/path/other.com/", set()),
    "sentence-punctuation": ("the sentence end.Company said so", set()),
    "file-name": ("open the readme.txt file", set()),
    "html-file": ("index.html", set()),
    "version-number": ("upgraded to 4.0.2.au", set()),
    "multi-label-suffix": ("order from shop.com.au today", {"shop.com.au"}),
    "deep-host": ("a.b.c.foo.com", {"foo.com"}),
    "full-stop": ("Visit foo.com. The site is new.", {"foo.com"}),
    "domain-shaped-local-part": ("john.com@example.org wrote", set()),
    "infrastructure": ("archived at groups.google.com and archive.org", set()),
    # `Path:`, `Xref:` and `Newsgroups:` are dotted by construction, so only the body is read
    "body-only": (body_of(NEWS_HEADERS), {"realsite.com"}),
}


@pytest.mark.parametrize(("text", "expected"), list(BARE.values()), ids=list(BARE))
def test_bare_usenet_host(text, expected) -> None:
    """The bare-host path reads names in prose; URLs and addresses belong to the other paths."""
    assert set(bare_domains_in_body(text)) == expected


def test_domain_year_captures_keeps_only_in_window_rows(tmp_path: Path) -> None:
    rows = ["petrosys.com.au\t1997\t155", "petrosys.com.au\t1998\t75", "21.com\t2003\t246"]
    rows += ["other\t2001\t8"]  # not a hostname, canonicalisation drops it later
    rows += ["example.com\t1995\t3", "missing-a-column\t1999", "bad-year\tnineteen\t5"]
    rows += ["good.com\t1999\tmany"]  # the count is provenance, so it never gates a row
    records, stats = _parse(parse_domain_year_captures, tmp_path, "dyc.txt", _lines(rows))
    assert [(r.raw, r.year, r.evidence_value) for r in records] == [
        ("petrosys.com.au", 1997, "ia_captures:1997:155"),
        ("petrosys.com.au", 1998, "ia_captures:1998:75"),
        ("other", 2001, "ia_captures:2001:8"),
        ("good.com", 1999, "ia_captures:1999:?"),
    ]
    assert (stats["out_of_window"], stats["malformed"]) == (2, 2)
    # the Wayback calendar for that host and year makes an approval request checkable
    assert records[0].evidence_url == "https://web.archive.org/web/1997*/http://petrosys.com.au/"


CREATION_ROWS = [
    "domain;tld;dnssec;registrar;created_at;records_ns;records_ds;records_dnskey;analyzed_at",
    "stdominic.net;net;f;Reg A;1999-09-01;{ns1.x.};{};{};2024-10-12",
    "oncall.org;org;f;Reg B;1997-11-26;{ns1.y.};{};{};2024-10-12",
    "blueadvise.com;com;f;GoDaddy;2021-09-13;{ns1.z.};{};{};2024-10-12",  # after the window
    "ancient.com;com;f;Reg C;1994-02-02;{ns1.w.};{};{};2024-10-12",  # before it
    "nodate.nl;nl;t;unknown;;{een.dnssrv.nl.};{};{};2024-11-07",  # no creation date
    "short;row",
]


def test_creation_csv_dates_each_domain_by_its_creation_year_alone(tmp_path: Path) -> None:
    """A creation date dates its own year only, with ICANN's lookup for the exact name."""
    records, stats = _parse(parse_domain_creation_csv, tmp_path, "d.csv", _lines(CREATION_ROWS))
    assert [(r.raw, r.year, r.evidence_value) for r in records] == [
        ("stdominic.net", 1999, "registry created 1999-09-01"),
        ("oncall.org", 1997, "registry created 1997-11-26"),
    ]
    assert records[0].evidence_url == "https://lookup.icann.org/en/lookup?q=stdominic.net"
    assert stats["out_of_window"] == 2
    # the header is a row whose date does not parse, counted beside `nodate.nl`
    assert stats["no_creation_date"] == 2
    assert stats["malformed"] == 1


IEDR_PAGE = """<html><body>
<p>[ <a href="0-9-doms.html">0-9</a> | <a href="a-doms.html">A</a> ]</p>
aardvark.ie<br>
a-and-d.ie<br>
WWW.Mixed-Case.IE<br>
sub.deeper.ie<br>
domainregistry.ie<br>
<p><font size="1">This page was <b>updated automatically</b>
 at 14:51 GMT on Friday, 21 December 2001</font></p>
</body></html>
"""
IEDR_LISTS_PAGE = """<html><body>
<p>[ 0-9 | A | B ]</p>
oldname.ie<br>
another.ie<br>
<p>Last updated 27 Nov 1999</p>
</body></html>
"""


def test_iedr_page_dates_every_registrable_name_on_it(tmp_path: Path) -> None:
    """The footer date is read with tags stripped, since it spans a `<b>`."""
    records, stats = _parse(parse_iedr_register, tmp_path, "a-doms.html", IEDR_PAGE)
    assert {r.year for r in records} == {2001}
    assert "iedr register listing" in records[0].evidence_value
    assert stats["no_footer_date"] == 0
    names = {r.raw for r in records}
    # a www- or subdomain-prefixed form is the same registration, counted once
    assert {"aardvark.ie", "a-and-d.ie", "mixed-case.ie", "deeper.ie"} <= names
    assert len(names) == len(records)
    # the registry's own host is not a registration it found
    assert "domainregistry.ie" not in names
    assert stats["registry_own_host"] >= 1


def test_iedr_earlier_lists_tree_wording_is_also_read(tmp_path: Path) -> None:
    name = "19991128191652_a-doms.html"
    records, stats = _parse(parse_iedr_register, tmp_path, name, IEDR_LISTS_PAGE)
    assert {r.year for r in records} == {1999}
    assert {r.raw for r in records} == {"oldname.ie", "another.ie"}
    assert stats["no_footer_date"] == 0


ZONE = """ORG.\tIN\tSOA\tA.ROOT-SERVERS.NET.\thostmaster.INTERNIC.NET. (
\t\t\t\t1997041800\t;serial
\t\t\t\t10800  ;refresh every 3 hours
\t\t\t\t)
ORG.                      518400 IN  NS    A.ROOT-SERVERS.NET.
A.ROOT-SERVERS.NET.       518400     A     198.41.0.4
EXAMPLE.ORG.              172800     NS    NS1.PROVIDER.NET.
                          172800     NS    NS2.PROVIDER.NET.
SUB.DEEPER.ORG.           172800     NS    NS1.PROVIDER.NET.
OTHER.ORG.                172800     NS    NS.OTHER.ORG.
;End of file.
"""


def test_internic_delegation_is_the_owner_and_never_the_nameserver(tmp_path: Path) -> None:
    """A deeper owner is skipped, not truncated; the apex and a continuation line are counted."""
    records, stats = _parse(_zone, tmp_path, "org.zone.gz", ZONE)
    names = {r.raw for r in records}
    assert names == {"example.org", "other.org"}
    assert not any("provider.net" in n for n in names)
    assert {"a.root-servers.net", "deeper.org", "org"}.isdisjoint(names)
    assert (stats["deeper_than_one_label"], stats["apex_delegation"]) == (1, 1)
    assert stats["owner_outside_zone"] >= 1


def test_internic_year_comes_from_the_serial_inside_the_file(tmp_path: Path) -> None:
    """A renamed file still dates itself by its SOA serial."""
    records, _ = _parse(_zone, tmp_path, "something-else.gz", ZONE)
    assert records
    assert {r.year for r in records} == {1997}
    assert all("serial 1997041800" in r.evidence_value for r in records)


def test_internic_reports_reverse_dns_and_the_canonicaliser_refuses_it(tmp_path: Path) -> None:
    """The parser reports what the zone delegates; the funnel decides what is storable."""
    arpa = ZONE.replace("ORG", "ARPA").replace("EXAMPLE.ARPA.", "IN-ADDR.ARPA.")
    records, _ = _parse(_zone, tmp_path, "arpa.zone.gz", arpa)
    assert "in-addr.arpa" in {r.raw for r in records}
    assert to_registrable("in-addr.arpa") is None
    assert to_registrable("206.in-addr.arpa") is None


def test_registry_item_is_filed_at_the_year_its_stamp_names(tmp_path: Path) -> None:
    rows = [
        {"host": "Example.dk", "year": 2001, "text": "DK Zonen header 20010413"},
        {"host": "other.dk", "year": 2000, "text": "DK Zonen header 20001231"},
    ]
    records, stats = _parse(parse_registry_items, tmp_path, "i.jsonl", _jsonl(rows) + "\n")
    assert [(r.raw, r.year) for r in records] == [("example.dk", 2001), ("other.dk", 2000)]
    assert records[0].evidence_value.startswith("20010413: ")
    assert stats["journal_lines"] == 2


WHOIS_BLOCK = """
   Registrant:
   The OpenSSL Project

      Domain Name: OPENSSL.ORG

      Administrative Contact:
         Someone  someone@openssl.org
      Technical Contact:
         Someone  someone@openssl.org

      Record last updated on 12-Jan-2001.
      Record expires on 18-Dec-2002.
      Record created on 19-Dec-1998.

      Domain servers in listed order:
      NS1.EXAMPLE.NET
      NS2.EXAMPLE.NET

      Domain Name: ENGELSCHALL.COM

      Administrative Contact:
         Someone  rse@engelschall.com

      Record created on 30-Jun-1996.
"""
WHOIS_PAIRS = [("openssl.org", 1998), ("engelschall.com", 1996)]
# the same block as a mail client rewrote it, leading runs become `&nbsp;`
WHOIS_ESCAPED = "\n".join(
    "&nbsp;" * (len(line) - len(line.lstrip(" "))) + line.lstrip(" ")
    for line in WHOIS_BLOCK.split("\n")
)
WHOIS_FILLER = "\n".join(f"   line {i}" for i in range(whois.MAX_BACK + 5))
CREATIONS = {
    "own-name": (WHOIS_BLOCK, WHOIS_PAIRS),
    # the escaped copy must not bind 1998 to the name that follows it
    "escaped-copy": (WHOIS_BLOCK + WHOIS_ESCAPED, WHOIS_PAIRS + WHOIS_PAIRS),
    "far-below-its-name": (
        f"      Domain Name: EXAMPLE.COM\n{WHOIS_FILLER}\n      Record created on 04-Jul-1997.\n",
        [],
    ),
    "out-of-window-and-unregistrable": (
        "      Domain Name: EXAMPLE.COM\n      Record created on 04-Jul-2004.\n"
        "      Domain Name: DOMAIN.BILLING\n      Record created on 04-Jul-1997.\n",
        [],
    ),
    "nominet-next-line": (
        "    Domain Name:\n        example.co.uk\n\n    Registered on: 01-Feb-1999\n",
        [("example.co.uk", 1999)],
    ),
}


@pytest.mark.parametrize(("text", "expected"), list(CREATIONS.values()), ids=list(CREATIONS))
def test_a_pasted_whois_creation_line_binds_to_its_own_name(text, expected) -> None:
    """A creation line dates the nearest name above it, in window and registrable, or none."""
    assert [(d, y) for d, _c, y, _b in whois.creations_in(text)] == expected


def test_usenet_whois_evidence_value_leads_with_the_registry_stamp(tmp_path: Path) -> None:
    """`ark check` reads the first four-digit run, so a year in the group name must not lead."""
    row = {"domain": "example.com", "year": 1998, "created": "1998-12-19"}
    row |= {"group": "microsoft.public.win2000.dns", "message_id": "<abc@example>"}
    records, _ = _parse(_parse_usenet_whois_journal, tmp_path, "uw.jsonl.gz", _jsonl([row]))
    assert [r.year for r in records] == [1998]
    assert records[0].evidence_value.startswith("record created 1998-12-19 ")


# The RIPE NCC permission: derive (domain, year) pairs and publish no personal data. Contact
# details sit inline in the domain objects, so every leak case fails on a widened pattern.
RIPE_SNAPSHOT = """#
# 990804 00:07:01
#
# Restricted rights.

*dn: OULU.FI
*de: Oulu University
*ac: KR101
*ch: lk-kr@finou.oulu.fi 19910916
*so: RIPE

*dn: TuKKK.FI
*de: Rehtorinpellonkatu 3, SF-20500 TURKU, Finland
*ac: +358 21 6383105
*ac: mniemi@abo.fi
*tc: hostmaster@utu.fi
*so: RIPE

*dn: 231.130.IN-ADDR.ARPA
*de: reverse zone
*so: RIPE

*in: 193.166.0.0 - 193.166.255.255
*na: FUNET
*ch: ripe-dbm@ripe.net 19990711
"""
RIPE_CHANGED = """#
# 990804 00:07:01
#

*dn: OULU.FI
*de: Oulu University
*ch: lk-kr@finou.oulu.fi 19910916
*ch: dfk@cwi.nl 19970930
*ch: ripe-dbm@ripe.net 19990711
*so: RIPE

*dn: TuKKK.FI
*ch: mniemi@abo.fi 19980825
*ch: mniemi@abo.fi 19981103
*so: RIPE

*dn: 231.130.IN-ADDR.ARPA
*ch: hostmaster@example.net 19980101
*so: RIPE
"""
RIPE_SPLIT = """#
#       Restricted rights.
#

domain:       hasselblad.gm
descr:        Victor Hasselblad AB
nserver:      ns.domain.se
changed:      ovema@a.sol.no 19971128
source:       RIPE

domain:       example.bg
changed:      hostmaster@example.bg 20001114
changed:      hostmaster@example.bg 20010302
changed:      hostmaster@example.bg 20030506
source:       RIPE

domain:       200.193.193.in-addr.arpa
changed:      mx@lucky.net 20010716
source:       RIPE
"""
RIPE_LEAKS = {
    "snapshot": (
        parse_ripe_dbase_1999,
        RIPE_SNAPSHOT,
        "@ +358 Rehtorinpellonkatu TURKU abo.fi utu.fi ripe-dbm",
    ),
    "changed": (parse_ripe_dbase_changed, RIPE_CHANGED, "@ finou cwi.nl ripe-dbm abo.fi mniemi"),
    "split": (parse_ripe_dbase_split_2004, RIPE_SPLIT, "@ ovema a.sol.no lucky.net hostmaster"),
}


@pytest.mark.parametrize(
    ("parser", "text", "forbidden"), list(RIPE_LEAKS.values()), ids=list(RIPE_LEAKS)
)
def test_ripe_emits_no_personal_data(tmp_path: Path, parser, text, forbidden) -> None:
    """Every emitted value is a bare hostname and a date: no address, phone or contact line."""
    records, _ = _parse(parser, tmp_path, "ripe.db", text)
    assert records
    emitted = " ".join(r.raw for r in records) + " ".join(r.evidence_value for r in records)
    for needle in forbidden.split():
        assert needle not in emitted, f"parser leaked {needle!r}"
    for record in records:
        assert " " not in record.raw and "," not in record.raw


def test_ripe_snapshot_reads_domain_objects_and_dates_them_1999(tmp_path: Path) -> None:
    records, stats = _parse(parse_ripe_dbase_1999, tmp_path, "ripe.db", RIPE_SNAPSHOT)
    assert [r.raw for r in records] == ["OULU.FI", "TuKKK.FI"]
    assert {r.year for r in records} == {1999}
    assert (stats["header_year"], stats["reverse_zone_skipped"]) == (1999, 1)


def test_ripe_changed_reaches_the_years_the_snapshot_cannot(tmp_path: Path) -> None:
    records, stats = _parse(parse_ripe_dbase_changed, tmp_path, "ripe.db", RIPE_CHANGED)
    assert sorted((r.raw, r.year) for r in records) == [
        ("OULU.FI", 1997),
        ("OULU.FI", 1999),
        ("TuKKK.FI", 1998),
    ]
    # 1991 is before the window; the second 1998 line on TuKKK adds nothing
    assert (stats["changed_out_of_window"], stats["same_year_repeat"]) == (1, 1)
    assert stats["reverse_zone_skipped"] == 1
    # `ark check` compares the year inside the value against the assigned year
    assert all(str(r.year) in r.evidence_value for r in records)


def test_ripe_split_reads_the_long_keys_and_reaches_2000_and_2001(tmp_path: Path) -> None:
    records, stats = _parse(parse_ripe_dbase_split_2004, tmp_path, "ripe.db", RIPE_SPLIT)
    assert sorted((r.raw, r.year) for r in records) == [
        ("example.bg", 2000),
        ("example.bg", 2001),
        ("hasselblad.gm", 1997),
    ]
    # 2003 is after the window and the reverse zone never becomes current
    assert (stats["changed_out_of_window"], stats["reverse_zone_skipped"]) == (1, 1)


REGISTRY_REFUSED = [
    {"host": "late.dk", "year": 2001, "text": "DK Zonen header 20020105"},
    {"host": "undated.dk", "year": 2001, "text": "no stamp"},
    {"host": "old.dk", "year": 1995, "text": "DK Zonen header 19950101"},
    {"year": 2001, "text": "DK Zonen header 20010101"},
]
WHOIS_REFUSED = [
    {"domain": "example.com", "year": 1998, "created": "1997-12-19", "group": "g"},
    {"domain": "other.com", "year": 2004, "created": "2004-01-01", "group": "g"},
]
IEDR_LATE = IEDR_PAGE.replace("21 December 2001", "28 March 2002")
IEDR_UNDATED = "<html><body>orphan.ie<br></body></html>"
ZONE_1993 = ZONE.replace("1997041800", "1993041800")
ZONE_NO_SERIAL = "\n".join(line for line in ZONE.splitlines() if ";serial" not in line)
RIPE_UNSTAMPED = "#\n# no date here\n\n" + "*dn: EXAMPLE.FI\n" * 60
RIPE_2003 = "#\n# 030804 00:07:01\n\n*dn: EXAMPLE.FI\n"
ISC_UNREAD = {"out_of_window_file": 1, "lines": 0}  # skipped whole, not read line by line
REFUSED = {
    "isc-pre-window": (parse_isc_survey, "wb_nw_9507.domains.gz", "x.com\n", ISC_UNREAD),
    "iedr-out-of-window": (parse_iedr_register, "l-doms.html", IEDR_LATE, "out_of_window_page"),
    "iedr-no-date-line": (parse_iedr_register, "a-doms.html", IEDR_UNDATED, "no_footer_date"),
    "internic-out-of-window": (_zone, "org.zone.gz", ZONE_1993, "out_of_window_file"),
    "internic-no-serial": (_zone, "org.zone.gz", ZONE_NO_SERIAL, "no_soa_serial"),
    "ripe-no-stamp": (parse_ripe_dbase_1999, "ns.db", RIPE_UNSTAMPED, "no_header_stamp"),
    "ripe-out-of-window": (parse_ripe_dbase_1999, "y2003.db", RIPE_2003, "stamp_out_of_window"),
    "registry-stamp-names-another-year": (
        parse_registry_items,
        "i.jsonl",
        _jsonl(REGISTRY_REFUSED),
        {"stamp_does_not_name_the_year": 2, "malformed": 2},
    ),
    "usenet-whois-stamp-disagrees": (
        _parse_usenet_whois_journal,
        "uw.jsonl.gz",
        _jsonl(WHOIS_REFUSED),
        {"created_year_mismatch": 1, "malformed": 1},
    ),
}
# pending applications and the registry's own prose pages list no registration
for page in ("19991128233948_stalled", "19991129020519_weekly", "19991128213509_dom-list"):
    case = (parse_iedr_register, f"{page}.html", IEDR_LISTS_PAGE, "not_a_register_page")
    REFUSED[f"iedr-{page[15:]}"] = case


@pytest.mark.parametrize(
    ("parser", "name", "text", "counted"), list(REFUSED.values()), ids=list(REFUSED)
)
def test_an_undatable_file_or_row_yields_nothing_and_says_why(
    tmp_path: Path, parser, name, text, counted
) -> None:
    """A file or row that cannot be dated in window is refused whole, never guessed."""
    records, stats = _parse(parser, tmp_path, name, text)
    assert records == []
    counted = {counted: 1} if isinstance(counted, str) else counted
    assert {key: stats[key] for key in counted} == counted
