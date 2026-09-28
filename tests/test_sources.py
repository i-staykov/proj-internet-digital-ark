"""Bulk source parsers and the collectors that feed them: what each reads from its source, what it
refuses and says why, and the promotion that re-files a mention without altering it."""

import gzip
import importlib.util
import json
from collections import Counter
from email.header import Header
from pathlib import Path

import pytest
from his_release import WEB_METHOD, capture

from ark import held
from ark import sources as src
from ark.canonical import to_registrable
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.sources import SOURCES
from ark.usenet import bare_domains_in_body, body_of, domains_in_message, message_year, parse_usenet


def _script(rel: str):
    path = Path(__file__).resolve().parent.parent / "scripts" / rel
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


whois = _script("sources/usenet/collect_usenet_whois.py")
texts = _script("pricing/probe_texts_corpus.py")
attrition = _script("sources/directories/collect_attrition.py")
maillists = _script("sources/mail_corpora/collect_mailing_lists.py")
udrp = _script("sources/directories/collect_udrp_proceedings.py")
pandora = _script("sources/directories/seed_pandora_titles.py")
promo = _script("engines/build_promotion_journals.py")
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
    records, stats = _parse(src.parse_afnic_fr, tmp_path, "afnic.csv", _lines(AFNIC_ROWS))
    assert {(r.raw, r.year) for r in records} == (
        {("keep.fr", y) for y in (1998, 1999, 2000, 2001)}
        | {("wd.fr", y) for y in (1997, 1998, 1999)}
        | {("old.fr", y) for y in range(1996, 2002)}
    )
    # every record carries its auditable registration interval
    assert all(r.evidence_value.startswith("registered ") for r in records)
    assert (stats["no_creation_date"], stats["out_of_window"]) == (1, 2)


def test_ukwa_source_and_target_read_their_own_column_in_every_shard(tmp_path: Path) -> None:
    """The file is internally sorted shards, so an out-of-window year is not the end."""
    rows = ["1995|bssv01.lancs.ac.uk|www.env.uea.ac.uk\t2", "1998|a.co.uk|x.com\t1"]
    rows += ["2002|c.co.uk|z.com\t1", "malformed line without pipes", "1996|e.co.uk|v.de\t1"]
    sources, stats = _parse(src.parse_ukwa_link_source, tmp_path, "hl.tsv", _lines(rows))
    targets, _ = _parse(src.parse_ukwa_link_target, tmp_path, "hl.tsv", _lines(rows))
    assert [(r.raw, r.year, r.evidence_value) for r in sources] == [
        ("a.co.uk", 1998, "host_link_graph:1998"),
        ("e.co.uk", 1996, "host_link_graph:1996"),
    ]
    assert [(r.raw, r.year) for r in targets] == [("x.com", 1998), ("v.de", 1996)]
    assert (stats["lines"], stats["out_of_window"], stats["malformed"]) == (5, 2, 1)
    # a truncated gzip yields its intact prefix and records the truncation
    blob = gzip.compress(_lines([f"199{y}|h{y}.co.uk|t.com\t1" for y in range(6, 10)]).encode())
    (cut := tmp_path / "host-linkage.tsv.gz").write_bytes(blob[: len(blob) - 20])
    assert len(list(src.parse_ukwa_link_source(cut, stats := Counter()))) >= 1
    assert stats["truncated_tail"] == 1


# fmt: off
CDX_SNAPSHOT = [  # (domain, status, years, what else the row keeps)
    ("hit.com", 200, [1997], {}), ("none.com", 200, [], {}), ("err.com", 503, [], {}),
    ("out.com", 200, [2005], {}), ("big.com", 200, [1998], {"truncated": True}),
    ("conv.com", 200, [1998], {"stamps": {"1998": "19981205115848"}}),
    ("Host.com", 200, [1997, 1999],
     {"hosts": {"www.host.com": "19970101000000", "host.com": "19990301000000"}}),
    ("bad.com", 200, [2000], {"stamps": {"2000": "2000"}}),
    ("off.com", 200, [2001], {"stamps": {"2001": "19991231"}}),
]
# fmt: on


def test_cdx_snapshot_yields_a_record_per_returned_year_naming_its_capture(tmp_path) -> None:
    """One record per year returned, no inference of adjacent years; a per-year stamp or the
    domain's own `hosts` entry names the capture, and nothing else does."""
    rows = [{"domain": d, "status": s, "years": y} | kept for d, s, y, kept in CDX_SNAPSHOT]
    records, stats = _parse(src.parse_cdx_snapshot, tmp_path, "cdx_1.jsonl", _jsonl(rows))
    assert [(r.raw, r.year, r.evidence_value) for r in records] == [
        ("hit.com", 1997, "cdx capture 1997"),
        ("big.com", 1998, "cdx capture 1998"),
        ("conv.com", 1998, "cdx capture 19981205115848 conv.com"),
        ("Host.com", 1997, "cdx capture 1997"),
        ("Host.com", 1999, "cdx capture 19990301000000 host.com"),
        ("bad.com", 2000, "cdx capture 2000"),
        ("off.com", 2001, "cdx capture 2001"),
    ]
    urls = [r.evidence_url.removeprefix("https://web.archive.org/web/") for r in records]
    assert urls[1:5] == [
        "1998/big.com",
        "19981205115848/http://conv.com/",
        "1997/Host.com",
        "19990301000000/http://host.com/",
    ]
    assert (stats["journal_lines"], stats["query_failed"], stats["exact_capture"]) == (9, 1, 2)
    assert (stats["no_capture_in_window"], stats["truncated_response"]) == (2, 1)


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
    directory, dir_stats = _parse(src.parse_expansion_directory, tmp_path, name, text)
    links, link_stats = _parse(src.parse_expansion_links, tmp_path, name, text)
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


# fmt: off
NYPW = [  # (timestamp, url, status) in the eight-field NYPW first-capture format
    ("19970326221054", "http://0-0-0checkmate.com:80/", "200"),
    ("20070717010807", "http://late.com/", "404"),
    ("19980101000000", "http://redirect.com/", "302"),
    ("20010101000000", "http://gone.com/", "404"), ("19990101000000", "http://nothing.com/", "-"),
    ("20010305101500", "http://hmcfunding.com:80/", "500"),
]
# fmt: on


def test_nypw_keeps_in_window_200s_and_nonok_takes_exactly_what_the_200_parser_drops(tmp_path):
    """The timestamp is field 2 and the URL field 3, and a row evidences its own year alone; the
    200 and non-200 specs partition the in-window rows, and a `-` status is no answer."""
    text = "".join(f"https://e/ com,example)/ {t} {u} text/html {s} D 1\n" for t, u, s in NYPW)
    ok, ok_stats = _parse(SOURCES["nypw_firstcdx"].parse, tmp_path, "nypw.txt", text)
    nonok, stats = _parse(SOURCES["nypw_timemaps_nonok"].parse, tmp_path, "nypw.txt", text)
    assert [(r.raw, r.year) for r in ok] == [("http://0-0-0checkmate.com:80/", 1997)]
    assert [(r.raw, r.year) for r in nonok] == [
        ("http://redirect.com/", 1998),
        ("http://gone.com/", 2001),
        ("http://hmcfunding.com:80/", 2001),
    ]
    assert (ok_stats["out_of_window"], ok_stats["non_200"]) == (1, 4)
    assert (stats["out_of_window"], stats["ok_lane"], stats["no_response"]) == (1, 1, 1)
    # the status the server answered with is part of the evidence
    assert nonok[2].evidence_value == "nypw timemap capture status 500 20010305101500"
    assert nonok[2].evidence_url == (
        "https://web.archive.org/web/20010305101500/http://hmcfunding.com:80/"
    )


@pytest.mark.parametrize(
    ("raw", "year"),
    [(Header("Tue, 18 Jun 1996 12:00:00 GMT"), 1996), ("1997/06/18", 1997), ("not a date", None)],
    ids=["rfc822-in-an-rfc2047-header", "giganews-slash", "garbage"],
)
def test_usenet_reads_every_date_header_form(raw, year) -> None:
    assert message_year(raw) == year


def test_usenet_separates_out_of_window_from_unreadable_dates(tmp_path: Path) -> None:
    post = "From x\nDate: {}\nMessage-ID: <{}@h>\nFrom: p@vendor.com\n\nhttp://{}.com/\n"
    text = "".join(post.format(*row) for row in [("2008/01/01", "a", "a"), ("garbled", "b", "b")])
    text += post.format("1998/01/01", "c", "c")
    records, stats = _parse(parse_usenet, tmp_path, "g.mbox", text)
    assert (stats["out_of_window"], stats["unreadable_date"]) == (1, 1)
    assert {r.year for r in records} == {1998}


# fmt: off
MESSAGE_DOMAINS = {
    "body-urls-and-sender": (
        "Check out http://www.example.com/new, https://other.co.uk/x, http://groups.google.com/x",
        "Someone <person@vendor.net>", ["example.com", "other.co.uk", "vendor.net"]),
    "scheme-less-www": ("Try WWW.UPPER.COM for prices", "", ["upper.com"]),
    "bare-host-is-its-own-source": ("I work at bigcorp.com these days", "", []),
    "www-inside-an-address": ("mail me at bob@www.baz.net", "", []),
    "infrastructure-sender": ("", "a@deja.com", []),
}


@pytest.mark.parametrize(("body", "sender", "expected"), list(MESSAGE_DOMAINS.values()),
                         ids=list(MESSAGE_DOMAINS))
# fmt: on
def test_usenet_message_domains(body, sender, expected) -> None:
    """URLs, `www.` hosts and the sender's domain are read; a bare host and plumbing are not."""
    assert sorted(domains_in_message(body, sender)) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [("mail bob@foo.com", {"foo.com"}), ("the sentence end.Company said so", set())],
    ids=["address", "sentence-punctuation"],
)
def test_printed_text_domains(text, expected) -> None:
    """Printed copy reads a name in an address and refuses one cut out of a longer word."""
    assert texts.domains_in(text) == expected


NEWS_HEADERS = b"From: a@b.com\r\nNewsgroups: alt.isd.net\r\n"
NEWS_HEADERS += b"Path: news.relay.org!feeder!not-for-mail\r\n\r\nthe site is realsite.com\r\n"
# fmt: off
BARE = {
    "bare-host": ("BigCorp.com, mirror ftp.example.org/pub", {"bigcorp.com", "example.org"}),
    "url-or-address": ("see http://foo.com/x or mail bob@foo.com", set()),
    "cut-out-of-a-longer-token": ("the sentence end.Company said so, john.com@example.org", set()),
    "file-name": ("open the readme.txt file", set()),
    "version-number": ("upgraded to 4.0.2.au", set()),
    "multi-label-suffix": ("order from shop.com.au today", {"shop.com.au"}),
    "infrastructure": ("archived at groups.google.com and archive.org", set()),
    # `Path:`, `Xref:` and `Newsgroups:` are dotted by construction, so only the body is read
    "body-only": (body_of(NEWS_HEADERS), {"realsite.com"}),
}
# fmt: on


@pytest.mark.parametrize(("text", "expected"), list(BARE.values()), ids=list(BARE))
def test_bare_usenet_host(text, expected) -> None:
    """The bare-host path reads names in prose; URLs and addresses belong to the other paths."""
    assert set(bare_domains_in_body(text)) == expected


IEDR_PAGE = _lines([
    '<html><body>', '<p>[ <a href="0-9-doms.html">0-9</a> | <a href="a-doms.html">A</a> ]</p>',
    "aardvark.ie<br>", "a-and-d.ie<br>", "WWW.Mixed-Case.IE<br>", "sub.deeper.ie<br>",
    "domainregistry.ie<br>", '<p><font size="1">This page was <b>updated automatically</b>',
    " at 14:51 GMT on Friday, 21 December 2001</font></p>", "</body></html>",
])  # fmt: skip
IEDR_LISTS_PAGE = _lines([
    "<html><body>", "<p>[ 0-9 | A | B ]</p>", "oldname.ie<br>", "another.ie<br>",
    "<p>Last updated 27 Nov 1999</p>", "</body></html>",
])  # fmt: skip


def test_iedr_page_dates_every_registrable_name_on_it(tmp_path: Path) -> None:
    """The footer date is read with tags stripped, since it spans a `<b>`, and the earlier lists
    tree's wording is read too."""
    records, stats = _parse(src.parse_iedr_register, tmp_path, "a-doms.html", IEDR_PAGE)
    assert {r.year for r in records} == {2001}
    assert "iedr register listing" in records[0].evidence_value
    # a www- or subdomain-prefixed form is the same registration, counted once, and the
    # registry's own host is not a registration it found
    names = sorted(r.raw for r in records)
    assert names == ["a-and-d.ie", "aardvark.ie", "deeper.ie", "mixed-case.ie"]
    assert stats["registry_own_host"] >= 1
    name = "19991128191652_a-doms.html"
    records, stats = _parse(src.parse_iedr_register, tmp_path, name, IEDR_LISTS_PAGE)
    assert {(r.raw, r.year) for r in records} == {("oldname.ie", 1999), ("another.ie", 1999)}
    assert stats["no_footer_date"] == 0


ZONE = _lines([
    "ORG.\tIN\tSOA\tA.ROOT-SERVERS.NET.\thostmaster.INTERNIC.NET. (", "\t\t\t\t1997041800\t;serial",
    "\t\t\t\t10800  ;refresh every 3 hours", "\t\t\t\t)", "ORG.  518400 IN NS A.ROOT-SERVERS.NET.",
    "A.ROOT-SERVERS.NET.  518400  A  198.41.0.4", "EXAMPLE.ORG.  172800  NS  NS1.PROVIDER.NET.",
    "  172800  NS  NS2.PROVIDER.NET.", "SUB.DEEPER.ORG.  172800  NS  NS1.PROVIDER.NET.",
    "OTHER.ORG.  172800  NS  NS.OTHER.ORG.", ";End of file.",
])  # fmt: skip


def test_internic_delegation_is_the_owner_dated_by_the_serial_inside_the_file(tmp_path) -> None:
    """A deeper owner is skipped, not truncated; the apex and a continuation line are counted,
    and a renamed file still dates itself by its SOA serial."""
    records, stats = _parse(_zone, tmp_path, "something-else.gz", ZONE)
    assert {r.raw for r in records} == {"example.org", "other.org"}
    assert (stats["deeper_than_one_label"], stats["apex_delegation"]) == (1, 1)
    assert stats["owner_outside_zone"] >= 1
    assert {r.year for r in records} == {1997}
    assert all("serial 1997041800" in r.evidence_value for r in records)


def test_internic_reports_reverse_dns_and_the_canonicaliser_refuses_it(tmp_path: Path) -> None:
    """The parser reports what the zone delegates; the funnel decides what is storable."""
    arpa = ZONE.replace("ORG", "ARPA").replace("EXAMPLE.ARPA.", "IN-ADDR.ARPA.")
    records, _ = _parse(_zone, tmp_path, "arpa.zone.gz", arpa)
    assert "in-addr.arpa" in {r.raw for r in records}
    assert to_registrable("in-addr.arpa") is None
    assert to_registrable("206.in-addr.arpa") is None


CDX_LINES = [
    " CDX N b a m s c k r V v D d g M n",
    "at,vetcontrol)/ 19981212033831 http://www.vetcontrol.at:80/ text/html 200 A - - 9 f.arc.gz",
    "com,example)/ 19970601120000 http://example.com:80/ text/html 200 B - - 9 f.arc.gz",
    "com,example)/r 19970601120001 http://example.com:80/r text/html 302 C - - 9 f.arc.gz",
    "com,late)/ 20030101000000 http://late.com/ text/html 200 D - - 9 f.arc.gz",
    "broken line without enough fields",
    "com,short)/ 1998 http://short.com/ text/html 200 E - - 9 f.arc.gz",
]

CDXJ_LINES = [
    'com,example)/ 19961013223438 {"url": "http://www.example.com:80/", "status": "200"}',
    '1,208,96,204)/ 19961013223438 {"url": "http://204.96.208.1:80/", "status": "200"}',
    'org,foo)/x 19961014000000 {"url": "http://foo.org/x", "status": "404"}',
    'com,late)/ 20080101000000 {"url": "http://late.com/", "status": "200"}',
    "garbage line without json",
]

# fmt: off
ODP_RDF = [
    "<RDF>", "<!-- Generated at 2000-08-07 08:00:40 GMT on  -->", '<Topic r:id="Top/Arts">',
    "  <catid>2</catid>", '  <link r:resource="http://www.example.com/"/>',
    '  <link r:resource="http://sub.example.org:80/path"/>',
    '  <narrow r:resource="Top/Arts/Music"/>',  # internal topic ref, not a URL
    "</Topic>", '<ExternalPage about="https://www.another.net/home">', "  <title>Another</title>",
    "</ExternalPage>", "</RDF>",
]
# fmt: on


def _scout_record(oai_id: str, year: str, urls: list[str], extra: str = "") -> str:
    ids = "".join(f"<dc:identifier>{u}</dc:identifier>" for u in urls)
    return (
        f"<record><header><identifier>{oai_id}</identifier>"
        "<datestamp>2003-04-02</datestamp></header><metadata><oai_dc:dc>"
        f"<dc:date>{year}</dc:date><dc:description>d</dc:description>{extra}{ids}"
        "</oai_dc:dc></metadata></record>"
    )


SCOUT = "<OAI-PMH><ListRecords>" + "".join([
    _scout_record("oai:scout:1", "1998", ["http://www.example.com/"]),
    _scout_record("oai:scout:2", "1989", ["http://old.example.org/"]),
    _scout_record("oai:scout:3", "2000", ["http://a.net/", "https://b.org/x"]),
    _scout_record("oai:scout:4", "1997", [], extra="<dc:identifier>id-999</dc:identifier>"),
]) + "</ListRecords></OAI-PMH>"  # fmt: skip


GEOINDEX_ROWS = [
    "19990412183021/http://www.example.co.uk/index.html\tOX11 0QX",
    "20010101000000/http://sub.host.ac.uk/a/b\tSW1A 1AA",
]
# junk stamps are in the real file, so the window filter rejects them
GEOINDEX_ROWS += [f"{stamp}/http://www.x.co.uk/\tE1 6AN" for stamp in ("19800101000000",
                  "19941231235959", "20051231235959", "notatimestamp")]  # fmt: skip


CREATION_ROWS = [
    "domain;tld;dnssec;registrar;created_at;records_ns;records_ds;records_dnskey;analyzed_at",
    "stdominic.net;net;f;Reg A;1999-09-01;{ns1.x.};{};{};2024-10-12",
    "oncall.org;org;f;Reg B;1997-11-26;{ns1.y.};{};{};2024-10-12",
    "blueadvise.com;com;f;GoDaddy;2021-09-13;{ns1.z.};{};{};2024-10-12",  # after the window
    "ancient.com;com;f;Reg C;1994-02-02;{ns1.w.};{};{};2024-10-12",  # before it
    "nodate.nl;nl;t;unknown;;{een.dnssrv.nl.};{};{};2024-11-07",  # no creation date
    "short;row",
]


RDAP = [{"domain": "in.com", "status": 200, "creation_year": 1998, "response": {}}]
RDAP += [{"domain": f"{y}.com", "creation_year": y} for y in (1996, 2001, 1995, 2002)]
RDAP += [{"domain": "gone.com", "status": 404, "creation_year": None}, {"creation_year": 1997}]
DYC = ["petrosys.com.au\t1997\t155", "petrosys.com.au\t1998\t75", "21.com\t2003\t246"]
DYC += ["other\t2001\t8"]  # not a hostname, canonicalisation drops it later
DYC += ["example.com\t1995\t3", "missing-a-column\t1999", "bad-year\tnineteen\t5"]
DYC += ["good.com\t1999\tmany"]  # the count is provenance, so it never gates a row
REGISTRY = [
    {"host": "Example.dk", "year": 2001, "text": "DK Zonen header 20010413"},
    {"host": "other.dk", "year": 2000, "text": "DK Zonen header 20001231"},
    {"host": "late.dk", "year": 2001, "text": "DK Zonen header 20020105"},
    {"host": "undated.dk", "year": 2001, "text": "no stamp"},
    {"host": "old.dk", "year": 1995, "text": "DK Zonen header 19950101"},
    {"year": 2001, "text": "DK Zonen header 20010101"},
]
WHOIS_ROW = {"domain": "example.com", "year": 1998, "created": "1998-12-19"}
WHOIS_ROWS = [WHOIS_ROW | {"group": "microsoft.public.win2000.dns", "message_id": "<abc@x>"}]
WHOIS_ROWS += [WHOIS_ROW | {"created": "1997-12-19"}, {"domain": "other.com", "year": 2004}]
WAYBACK = "https://web.archive.org/web/"
# fmt: off
PARSED = {  # (parser, file, text, rows yielded, the first row's URL, stats)
    # the short line and the 4-digit timestamp line are malformed
    "early_web": (src.parse_early_web_cdx, "s.cdx.gz", _lines(CDX_LINES),
                  [("http://www.vetcontrol.at:80/", 1998, "19981212033831"),
                   ("http://example.com:80/", 1997, "19970601120000")],
                  f"{WAYBACK}19981212033831/http://www.vetcontrol.at:80/",
                  {"lines": 7, "header_lines": 1, "non_200": 1, "out_of_window": 1,
                   "malformed": 2}),
    # the parser does not canonicalize, so the bare-IP capture is yielded for the loader to drop
    "arquivo": (src.parse_arquivo_cdxj, "Roteiro.cdxj", _lines(CDXJ_LINES),
                [("http://www.example.com:80/", 1996, "19961013223438"),
                 ("http://204.96.208.1:80/", 1996, "19961013223438")],
                "https://arquivo.pt/wayback/19961013223438/http://www.example.com:80/",
                {"lines": 5, "non_200": 1, "out_of_window": 1, "malformed": 1}),
    # survey date 9607 is 1996, and the last whitespace token is the host
    "isc": (src.parse_isc_survey, "wb_nw_9607.domains.gz",
            _lines(["banc-agricol.ad", "1.2.3.4 test.eowyn.fr.eu.org", "", "ad"]),
            [(h, 1996, "1996-07") for h in ("banc-agricol.ad", "test.eowyn.fr.eu.org", "ad")],
            None, {"lines": 4}),
    # an out-of-window survey is skipped whole, not read line by line
    "isc-pre-window": (src.parse_isc_survey, "wb_nw_9507.domains.gz", "x.com\n", [], None,
                       {"out_of_window_file": 1, "lines": 0}),
    # the generation stamp fixes the year, and the internal topic ref is excluded
    "odp": (src.parse_odp, "c2000.rdf", _lines(ODP_RDF),
            [(u, 2000, "odp 2000-08-07") for u in ("http://www.example.com/",
             "http://sub.example.org:80/path", "https://www.another.net/home")], None, {}),
    # the OAI record id is the auditable evidence reference
    "internet_scout": (src.parse_internet_scout, "scout_oai.xml", SCOUT,
                       [("http://www.example.com/", 1998, "oai:scout:1"),
                        ("http://a.net/", 2000, "oai:scout:3"),
                        ("https://b.org/x", 2000, "oai:scout:3")],
                       None, {"out_of_window": 1, "no_url": 1}),
    # the year is read from the capture stamp kept verbatim, never supplied alongside it
    "ukwa_geoindex": (src.parse_ukwa_geoindex, "geo.tsv.gz", _lines(GEOINDEX_ROWS),
                      [("http://www.example.co.uk/index.html", 1999, "19990412183021"),
                       ("http://sub.host.ac.uk/a/b", 2001, "20010101000000")],
                      f"{WAYBACK}19990412183021/http://www.example.co.uk/index.html",
                      {"out_of_window": 3, "malformed": 1}),
    # a creation date attests its own year and no later one, and nothing outside the window
    "rdap": (src.parse_rdap_snapshot, "rdap_1.jsonl.gz", _jsonl(RDAP) + "\n{not json\n",
             [("in.com", 1998, "rdap creation 1998"), ("1996.com", 1996, "rdap creation 1996"),
              ("2001.com", 2001, "rdap creation 2001")], "https://rdap.org/domain/in.com",
             {"journal_lines": 8, "outside_window": 2, "not_dated": 1, "unparseable_line": 1,
              "no_domain": 1}),
    # an entry the harvest could not date is counted, never dated by assumption
    "ncsa": (src.parse_ncsa_whats_new, "ncsa.tsv",
             "example.com\t1996-01-01\nother.org\t1996-07-15\nundated.net\t\n",
             [("example.com", 1996, "ncsa whats-new entry 1996-01-01"),
              ("other.org", 1996, "ncsa whats-new entry 1996-07-15")], None, {"no_date": 1}),
    # the Wayback calendar for that host and year makes an approval request checkable
    "domain_year_captures": (src.parse_domain_year_captures, "dyc.txt", _lines(DYC),
                             [("petrosys.com.au", 1997, "ia_captures:1997:155"),
                              ("petrosys.com.au", 1998, "ia_captures:1998:75"),
                              ("other", 2001, "ia_captures:2001:8"),
                              ("good.com", 1999, "ia_captures:1999:?")],
                             f"{WAYBACK}1997*/http://petrosys.com.au/",
                             {"out_of_window": 2, "malformed": 2}),
    # a creation date dates its own year only, with ICANN's lookup for the exact name; the
    # header is a row whose date does not parse, counted beside `nodate.nl`
    "domain_creation": (src.parse_domain_creation_csv, "d.csv", _lines(CREATION_ROWS),
                        [("stdominic.net", 1999, "registry created 1999-09-01"),
                         ("oncall.org", 1997, "registry created 1997-11-26")],
                        "https://lookup.icann.org/en/lookup?q=stdominic.net",
                        {"out_of_window": 2, "no_creation_date": 2, "malformed": 1}),
    # a registry item is filed at the year its stamp names, or not at all
    "registry_items": (src.parse_registry_items, "i.jsonl", _jsonl(REGISTRY) + "\n",
                       [("example.dk", 2001, "20010413: DK Zonen header 20010413"),
                        ("other.dk", 2000, "20001231: DK Zonen header 20001231")], None,
                       {"journal_lines": 6, "stamp_does_not_name_the_year": 2, "malformed": 2}),
    # `ark check` reads the first four-digit run, so a year in the group name must not lead
    "usenet_whois": (src._parse_usenet_whois_journal, "uw.jsonl.gz", _jsonl(WHOIS_ROWS),
                     [("example.com", 1998,
                       "record created 1998-12-19 pasted in microsoft.public.win2000.dns <abc@x>")],
                     None, {"created_year_mismatch": 1, "malformed": 1}),
    "iedr-out-of-window": (src.parse_iedr_register, "l-doms.html",
                           IEDR_PAGE.replace("21 December 2001", "28 March 2002"), [], None,
                           {"out_of_window_page": 1}),
    "iedr-no-date-line": (src.parse_iedr_register, "a-doms.html",
                          "<html><body>orphan.ie<br></body></html>", [], None,
                          {"no_footer_date": 1}),
    # pending applications and the registry's own prose pages list no registration
    "iedr-stalled": (src.parse_iedr_register, "19991128233948_stalled.html", IEDR_LISTS_PAGE, [],
                     None, {"not_a_register_page": 1}),
    "internic-out-of-window": (_zone, "org.zone.gz", ZONE.replace("1997041800", "1993041800"), [],
                               None, {"out_of_window_file": 1}),
    "internic-no-serial": (_zone, "org.zone.gz", ZONE.replace("\t\t\t\t1997041800\t;serial\n", ""),
                           [], None, {"no_soa_serial": 1}),
    "ripe-no-stamp": (src.parse_ripe_dbase_1999, "ns.db",
                      "#\n# no date here\n\n" + "*dn: EXAMPLE.FI\n" * 60, [], None,
                      {"no_header_stamp": 1}),
    "ripe-out-of-window": (src.parse_ripe_dbase_1999, "y2003.db",
                           "#\n# 030804 00:07:01\n\n*dn: EXAMPLE.FI\n", [], None,
                           {"stamp_out_of_window": 1}),
}


@pytest.mark.parametrize(("parser", "name", "text", "rows", "url", "counted"),
                         list(PARSED.values()), ids=list(PARSED))
# fmt: on
def test_a_parser_dates_each_row_by_its_own_stamp_and_counts_why_the_rest_are_refused(
    tmp_path: Path, parser, name, text, rows, url, counted
) -> None:
    """A row or file that cannot be dated in window is refused whole and counted, never guessed;
    a dated row carries the value and URL an auditor checks it by."""
    records, stats = _parse(parser, tmp_path, name, text)
    assert [(r.raw, r.year, r.evidence_value) for r in records] == rows
    assert url is None or records[0].evidence_url == url
    assert {key: stats[key] for key in counted} == counted


# fmt: off
WHOIS_BLOCK = "\n" + _lines([
    "   Registrant:", "   The OpenSSL Project", "", "      Domain Name: OPENSSL.ORG", "",
    "      Administrative Contact:", "         Someone  someone@openssl.org",
    "      Technical Contact:", "         Someone  someone@openssl.org", "",
    "      Record last updated on 12-Jan-2001.", "      Record expires on 18-Dec-2002.",
    "      Record created on 19-Dec-1998.", "", "      Domain servers in listed order:",
    "      NS1.EXAMPLE.NET", "      NS2.EXAMPLE.NET", "", "      Domain Name: ENGELSCHALL.COM", "",
    "      Administrative Contact:", "         Someone  rse@engelschall.com", "",
    "      Record created on 30-Jun-1996."])
# fmt: on
WHOIS_PAIRS = [("openssl.org", 1998), ("engelschall.com", 1996)]
# the same block as a mail client rewrote it, leading runs become `&nbsp;`
WHOIS_ESCAPED = "\n".join(
    "&nbsp;" * (len(line) - len(line.lstrip(" "))) + line.lstrip(" ")
    for line in WHOIS_BLOCK.split("\n")
)
WHOIS_FILLER = "\n".join(f"   line {i}" for i in range(whois.MAX_BACK + 5)) + "\n"
NAME, CREATED = "      Domain Name: {}\n", "      Record created on 04-Jul-{}.\n"
# fmt: off
CREATIONS = {
    "own-name": (WHOIS_BLOCK, WHOIS_PAIRS),
    # the escaped copy must not bind 1998 to the name that follows it
    "escaped-copy": (WHOIS_BLOCK + WHOIS_ESCAPED, WHOIS_PAIRS + WHOIS_PAIRS),
    "far-below-its-name": (NAME.format("EXAMPLE.COM") + WHOIS_FILLER + CREATED.format(1997), []),
    "out-of-window-and-unregistrable": (NAME.format("EXAMPLE.COM") + CREATED.format(2004)
                                        + NAME.format("DOMAIN.BILLING") + CREATED.format(1997), []),
    "nominet-next-line": (
        "    Domain Name:\n        example.co.uk\n\n    Registered on: 01-Feb-1999\n",
        [("example.co.uk", 1999)]),
}
# fmt: on


@pytest.mark.parametrize(("text", "expected"), list(CREATIONS.values()), ids=list(CREATIONS))
def test_a_pasted_whois_creation_line_binds_to_its_own_name(text, expected) -> None:
    """A creation line dates the nearest name above it, in window and registrable, or none."""
    assert [(d, y) for d, _c, y, _b in whois.creations_in(text)] == expected


# The RIPE NCC permission: derive (domain, year) pairs and publish no personal data. Contact
# details sit inline in the domain objects, so every leak case fails on a widened pattern.
# fmt: off
RIPE_SNAPSHOT = _lines([
    "#", "# 990804 00:07:01", "#", "# Restricted rights.", "",
    "*dn: OULU.FI", "*de: Oulu University", "*ac: KR101", "*ch: lk-kr@finou.oulu.fi 19910916",
    "*so: RIPE", "", "*dn: TuKKK.FI", "*de: Rehtorinpellonkatu 3, SF-20500 TURKU, Finland",
    "*ac: +358 21 6383105", "*ac: mniemi@abo.fi", "*tc: hostmaster@utu.fi", "*so: RIPE", "",
    "*dn: 231.130.IN-ADDR.ARPA", "*de: reverse zone", "*so: RIPE", "",
    "*in: 193.166.0.0 - 193.166.255.255", "*na: FUNET", "*ch: ripe-dbm@ripe.net 19990711"])
RIPE_CHANGED = _lines([
    "#", "# 990804 00:07:01", "#", "", "*dn: OULU.FI", "*de: Oulu University",
    "*ch: lk-kr@finou.oulu.fi 19910916", "*ch: dfk@cwi.nl 19970930",
    "*ch: ripe-dbm@ripe.net 19990711", "*so: RIPE", "", "*dn: TuKKK.FI",
    "*ch: mniemi@abo.fi 19980825", "*ch: mniemi@abo.fi 19981103", "*so: RIPE", "",
    "*dn: 231.130.IN-ADDR.ARPA", "*ch: hostmaster@example.net 19980101", "*so: RIPE"])
RIPE_SPLIT = _lines([
    "#", "#       Restricted rights.", "#", "", "domain:       hasselblad.gm",
    "descr:        Victor Hasselblad AB", "nserver:      ns.domain.se",
    "changed:      ovema@a.sol.no 19971128", "source:       RIPE", "", "domain:       example.bg",
    "changed:      hostmaster@example.bg 20001114", "changed:      hostmaster@example.bg 20010302",
    "changed:      hostmaster@example.bg 20030506", "source:       RIPE", "",
    "domain:       200.193.193.in-addr.arpa", "changed:      mx@lucky.net 20010716",
    "source:       RIPE"])
RIPE_LEAKS = {  # (parser, text, never emitted, pairs emitted, stats)
    # the snapshot's header stamp dates every domain object
    "snapshot": (src.parse_ripe_dbase_1999, RIPE_SNAPSHOT,
                 "@ +358 Rehtorinpellonkatu TURKU abo.fi utu.fi ripe-dbm",
                 [("OULU.FI", 1999), ("TuKKK.FI", 1999)],
                 {"header_year": 1999, "reverse_zone_skipped": 1}),
    # `changed:` reaches the years the snapshot cannot: 1991 is before the window, and the
    # second 1998 line on TuKKK adds nothing
    "changed": (src.parse_ripe_dbase_changed, RIPE_CHANGED, "@ finou cwi.nl ripe-dbm abo.fi mniemi",
                [("OULU.FI", 1997), ("OULU.FI", 1999), ("TuKKK.FI", 1998)],
                {"changed_out_of_window": 1, "same_year_repeat": 1, "reverse_zone_skipped": 1}),
    # the split edition's long keys reach 2000 and 2001; 2003 is after the window
    "split": (src.parse_ripe_dbase_split_2004, RIPE_SPLIT, "@ ovema a.sol.no lucky.net hostmaster",
              [("example.bg", 2000), ("example.bg", 2001), ("hasselblad.gm", 1997)],
              {"changed_out_of_window": 1, "reverse_zone_skipped": 1}),
}


@pytest.mark.parametrize(("parser", "text", "forbidden", "pairs", "counted"),
                         list(RIPE_LEAKS.values()), ids=list(RIPE_LEAKS))
# fmt: on
def test_ripe_emits_no_personal_data(tmp_path: Path, parser, text, forbidden, pairs, counted):
    """Every emitted value is a bare hostname and a date: no address, phone or contact line."""
    records, stats = _parse(parser, tmp_path, "ripe.db", text)
    emitted = " ".join(r.raw for r in records) + " ".join(r.evidence_value for r in records)
    for needle in forbidden.split():
        assert needle not in emitted, f"parser leaked {needle!r}"
    assert sorted((r.raw, r.year) for r in records) == pairs
    assert {key: stats[key] for key in counted} == counted
    # `ark check` compares the year inside the value against the assigned year
    assert all(str(r.year) in r.evidence_value for r in records)


ATTRITION = [
    '[99.11.30] Li [potus] <a href="1999/11/30/www.coronus.com/">Coronus</a>'
    ' (<a href="http://www.coronus.com">www.coronus.com</a>)',
    "[01.05.02] NT [x] Something ( www.example.com )",
    '[99.08.23] Li [x] <a href="1998/08/23/www.prim-nov.si/">Org</a> ( www.prim-nov.si )',
    '[99.08.09] Li [x] <a href="1999/08/08/www.phonefun.com/">Org</a> ( www.phonefun.com )',
    "[00.01.02] NT [x] Org ( www.example.com )",
    '[<a href="/news">Attrition News</a>]--[<a href="stats.html">Stats</a>]',
    "[99.11.30] Li [somebody] An organisation with no site listed",
]


def test_attrition_rows_need_the_two_witnesses_to_agree_on_the_year(tmp_path) -> None:
    """The index date and the mirror path must agree on the year; a day slip is kept, and only
    index pages are read, not the breakouts that reslice them."""
    (page := tmp_path / "1999-11.html").write_text(_lines(ATTRITION))
    stats: Counter = Counter()
    assert attrition.rows_in(page, stats) == [
        ("www.coronus.com", 1999, 11, 30, "1999/11/30/www.coronus.com"),
        ("www.example.com", 2001, 5, 2, None),
        ("www.phonefun.com", 1999, 8, 9, "1999/08/08/www.phonefun.com"),
        ("www.example.com", 2000, 1, 2, None),
    ]
    assert stats == Counter(rows=6, date_confirmed_twice=1, date_single_witness=2,
                            dropped_year_disagreement=1, kept_day_disagreement=1,
                            dated_1_or_2_january=1, row_without_host=1)  # fmt: skip
    assert all(attrition.INDEX.match(name) for name in ("1999-11.html", "1998.html"))
    assert not any(attrition.INDEX.match(name) for name in ("com.html", "ytcracker.html"))


MBOX = (
    "From someone@example.com Mon Jan  4 09:00:00 1999\nDate: Mon, 4 Jan 1999 09:00:00 +0000\n"
    "Subject: one\n\nsee http://widgets.example.org/ for details\n\n"
    "From other@example.net Tue Jan  5 09:00:00 1999\nDate: Tue, 5 Jan 1999 09:00:00 +0000\n"
    "Subject: two\n\nnothing here\n"
)


def test_mailing_list_messages_split_alike_plain_or_gzipped_and_an_address_names_a_host(tmp_path):
    (plain := tmp_path / "gtk-list__1999-January.txt").write_text(MBOX)
    (packed := tmp_path / "gtk-list__1999-January.txt.gz").write_bytes(gzip.compress(MBOX.encode()))
    assert len(maillists.read_messages(plain)) == 2
    assert maillists.read_messages(packed) == maillists.read_messages(plain)
    assert maillists._ADDR.findall("mail bob@widgets.example.com today") == ["widgets.example.com"]
    assert maillists._ADDR.findall("mail x@end.Company said") == []


# fmt: off
UDRP = [  # (commenced, decided, proceeding, names)
    ("2000-12-20", "2001-03-04", "WIPO D2000-0001", "musicweb.com"),
    ("2001-05-15", "-", "WIPO D2000-1762", "late.com"),
    ("2000-01-11", "-", "NAF FA0092016", "one.com, www.two.co.uk and one.com again"),
    ("2004-05-06", "2004-07-01", "WIPO D2004-0001", "later.com"),
    ("2000-06-01", "-", "", "orphan.com"),
]
# fmt: on


def test_udrp_records_carry_an_auditable_case_and_the_commencement_year() -> None:
    """No corroboration split sits behind this source, so every record it emits is master: the
    commencement year dates it, and the case number, not the year, names the decision page."""
    heads = ("Date Commenced", "Date Decided", "Proceeding Number", "Domain Name(s)", "Case Type")
    table = [[f"<th>{h}</th>" for h in (*heads, "Status")]]
    table += [[f"<td>{c}</td>" for c in (*row, "UDRP (1)", "Name transfer(21)")] for row in UDRP]
    page = "<table>" + "".join(f"<tr>{''.join(cells)}</tr>" for cells in table) + "</table>"
    stats: Counter = Counter()
    got = sorted(udrp.records_in(page, stats), key=lambda record: record["domain"])
    wipo = "https://www.wipo.int/amc/en/domains/decisions/html/2000/d2000-"
    assert [tuple(r.values()) for r in got] == [
        ("late.com", 2001, "WIPO D2000-1762", "2001-05-15", f"{wipo}1762.html"),
        ("musicweb.com", 2000, "WIPO D2000-0001", "2000-12-20", f"{wipo}0001.html"),
        ("one.com", 2000, "NAF FA0092016", "2000-01-11", udrp.LIST_URL),
        ("two.co.uk", 2000, "NAF FA0092016", "2000-01-11", udrp.LIST_URL),
    ]
    assert list(got[0]) == ["domain", "year", "proceeding", "commenced", "url"]
    assert (stats["out_of_window"], stats["no_proceeding_number"]) == (1, 1)


PANDORA = (
    "tep_id,name,gathered_url,surt\n"
    '/tep/1,"A title",http://www.acoss.org.au/some/path.pdf,"au,org,acoss)/some/path.pdf"\n'
    '/tep/2,"Another",http://lawlink.nsw.gov.au/x,"au,gov,nsw,lawlink)/x"\n'
    '/tep/3,"Same domain again",http://www.acoss.org.au/other,"au,org,acoss)/other"\n'
)


def test_pandora_titles_give_deduped_registrable_domains_bom_or_not(tmp_path) -> None:
    """`lawlink.nsw.gov.au` gives `nsw.gov.au`: the pinned suffix list has `gov.au` only. A file
    without the URL column is refused, and a row without a URL is counted."""
    for encoding in ("utf-8", "utf-8-sig"):
        (path := tmp_path / "titles.csv").write_text(PANDORA, encoding=encoding)
        domains, stats = pandora.registrable_domains(path)
        assert domains == {"acoss.org.au", "nsw.gov.au"}
        assert stats == {"rows": 3, "with_url": 3, "unparsed": 0}
    (wrong := tmp_path / "wrong.csv").write_text("tep_id,name\n/tep/1,A title\n")
    with pytest.raises(SystemExit, match="gathered_url"):
        pandora.registrable_domains(wrong)
    (gaps := tmp_path / "gaps.csv").write_text(PANDORA.splitlines()[0] + '\n/tep/9,"No url",,"x"\n')
    assert pandora.registrable_domains(gaps) == (set(), {"rows": 1, "with_url": 0, "unparsed": 0})


def test_a_promoted_line_parses_back_to_its_evidence_value_under_a_master_sibling(tmp_path):
    """Promotion re-files an observation and must not alter one: through each target's real
    loader, which must be the parser its mention source reads with, the written line gives back
    the stored value, or the Message-ID in the shipped corpus stops naming its post."""
    value = "comp.lang.python usenet post <3358fb02.28570944@news.alt.net>"
    line = promo.journal_line("brownschool.com", 1997, value, "https://e/1")
    (path := tmp_path / "promoted.jsonl.gz").write_bytes(gzip.compress(_jsonl([line]).encode()))
    for mention_source, ingest_key in promo.PROMOTION.items():
        spec = SOURCES[ingest_key]
        assert spec.evidence_type != "link_target", f"{ingest_key} is still candidate-only"
        mention = next(s for s in SOURCES.values() if s.source_name == mention_source)
        assert mention.parse is spec.parse, f"{mention_source} and {ingest_key} parse apart"
        records = [(r.raw, r.year, r.evidence_value) for r in spec.parse(path, Counter())]
        assert records == [("brownschool.com", 1997, value)]
    # the parser defaults an absent group to `usenet`; guessing one would fabricate a newsgroup
    got = promo.journal_line("foo.com", 1999, "solitary", None)
    assert got == {"domain": "foo.com", "year": 1999, "message_id": "solitary"}


def test_a_pair_held_by_us_or_by_his_exact_name_is_not_promoted(his_files) -> None:
    """Held is our assignment or the exact name in his file for that year, and only an
    assignment of ours corroborates a mention."""
    init_db(conn := connect(":memory:"))
    mention = ensure_source(conn, "usenet_mention", "candidate_only")
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    # his 1997 file holds already-his.com, his 1999 file only www.rolled.com; no assignment of
    # ours corroborates undated.com, and dated.com is ours already
    mentions = [("fresh.com", 1998), ("already-his.com", 1997), ("rolled.com", 1999)]
    mentions += [("undated.com", 1998), ("dated.com", 1998)]
    for name, year in mentions:
        add_candidate(conn, name, cdx)
        record_evidence(conn, name, mention, year, "link_target", f"alt.test <{name}>", "u")
    ours = [("fresh.com", 2000), ("already-his.com", 2000), ("rolled.com", 2000)]
    for name, year in [*ours, ("dated.com", 1998)]:
        value = capture(name, year)
        eid = record_evidence(conn, name, cdx, year, "cdx_timestamp", value, None, WEB_METHOD)
        assign_year(conn, eid)
    rows = promo.select(conn, "usenet_mention", held.load())
    assert sorted((d, y) for d, y, _v, _u in rows) == [("fresh.com", 1998), ("rolled.com", 1999)]
