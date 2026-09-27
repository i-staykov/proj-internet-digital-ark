"""Hostname lanes, source by source: the field read, the wall that keeps a name out, and the
funnel from an archived item to one `(host, year)` row. Every case id names its source."""

import functools
import gzip
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

import duckdb
import pytest

from ark import hostnames as hn
from ark.db import init_db
from ark.stats import PROVENANCE_LINEAGE

SOURCES = Path(__file__).resolve().parents[1] / "scripts/sources"
APACHE, LISTS = "mail_corpora/build_apache_header_pool.py", "mail_corpora/collect_apache_lists.py"
IETF, POLAND = "mail_corpora/collect_ietf_mail_archive.py", "poland/poland_pl_hostgrain.py"
USENET_HEADER = "usenet/build_usenet_header_pool.py"


@functools.cache
def script(rel: str):
    spec = importlib.util.spec_from_file_location(Path(rel).stem, SOURCES / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def line(item: tuple) -> str:
    return json.dumps(dict(zip(("item", "year", "text"), item, strict=True))) + "\n"


def journal(tmp_path: Path, items: list[tuple], name: str = "shard_000.jsonl.gz") -> Path:
    path = tmp_path / "items" / name
    path.parent.mkdir(exist_ok=True)
    text = "".join(line(i) for i in items)
    path.write_bytes(gzip.compress(text.encode()) if name.endswith(".gz") else text.encode())
    return path


def family(fam, source, noun, dup, reg, other, urls, id):
    """A lane's items: `dup` names one host twice in a year (the lower item is quoted), `reg` a host
    beside its registrable, `other` another lane's pointer, and the first item again in 2004."""
    (a, b, year, host), (item, ryear, rhost, registrable) = dup, reg
    items = [(a, year, host), (b, year, host), (item, ryear, f"{rhost} {registrable}")]
    items += [(other, 1999, "other.example.org"), (a, 2004, "later.example.org")]
    kept = {host: (year, urls[0]), rhost: (ryear, urls[1])}
    return pytest.param(fam, source, items, f"{noun} {year} {a} {host}", kept, id=id)


AP, MBOX = "httpd.apache.org/dev__1999-01", "https://lists.apache.org/api/mbox.lua?list="
IE, FTP = "concluded-wg-ietf-mail-archive/snmpv2/1996-10", "https://www.ietf.org/ietf-ftp/"
SIEVE, DEMON = "ietf-mail-archive/sieve/1997-03.mail", "demon.ip.support.pc.mbox.zip"
IA = "https://archive.org/download/"
# fmt: off
FAMILIES = [
    family(hn.APACHE_FAMILY, "apache_list_header_hostnames", "list header",
           (f"{AP}#1", f"{AP}#9", 1999, "taz.hyperreal.org"),
           ("tomcat.apache.org/users__2001-06#3", 2001, "mail.ibm.com", "ibm.com"),
           "gnome/gtk-list__1999-May.txt#367",
           [f"{MBOX}dev&domain=httpd.apache.org&d=1999-01",
            f"{MBOX}users&domain=tomcat.apache.org&d=2001-06"], "apache_header"),
    # the pointer keeps the month file's own name, `1996-10` early and `1997-03.mail` later:
    # a guessed suffix is a 404 for half the corpus
    family(hn.IETF_FAMILY, "ietf_list_header_hostnames", "list header",
           (f"www.ietf.org/{IE}#1", f"www.ietf.org/{IE}#7", 1996, "cnri.reston.va.us"),
           (f"www.ietf.org/{SIEVE}#3", 1997, "mail.example.org", "example.org"), f"{AP}#1",
           [f"{FTP}{IE}", f"{FTP}{SIEVE}"], "ietf_header"),
    family(hn.USENET_HEADER_FAMILY, "usenet_header_fqdn_hostnames", "usenet header",
           (f"{DEMON}#7", f"{DEMON}#91", 1998, "pcserv.demon.co.uk"),
           ("uk.comp.misc.mbox.zip#3", 2001, "news.zetnet.co.uk", "zetnet.co.uk"), f"{AP}#1",
           [f"{IA}usenet-demon/{DEMON}", f"{IA}usenet-uk/uk.comp.misc.mbox.zip"], "usenet_header"),
]
# fmt: on


@pytest.mark.parametrize("fam,source,items,quoted,kept", FAMILIES)
def test_funnel_one_row_per_host_and_year_quoting_the_lowest(
    tmp_path, fam, source, items, quoted, kept
):
    counts: Counter = Counter()
    rows = hn.usenet_item_rows(journal(tmp_path, items), counts, family=fam)
    assert [(r[0], r[2]) for r in rows] == sorted((h, y) for h, (y, _) in kept.items())
    assert {r[0]: r[4] for r in rows} == {h: url for h, (_, url) in kept.items()}
    assert {r[0]: r[3] for r in rows}[items[0][2]] == quoted
    assert (counts["bad_item"], counts["out_of_window"], counts["registrable_row"]) == (1, 1, 1)


@pytest.mark.parametrize("fam,source,items,quoted,kept", FAMILIES)
def test_funnel_ingest_lands_under_its_own_source_once(tmp_path, fam, source, items, quoted, kept):
    conn = duckdb.connect(":memory:")
    init_db(conn)
    path = journal(tmp_path, items)
    assert hn.ingest_usenet_item_journal(conn, path, family=fam)["hostname_year_rows"] == len(kept)
    sources = conn.execute("SELECT DISTINCT s.name FROM evidence e JOIN source s USING (source_id)")
    assert sources.fetchall() == [(source,)]
    assert hn.ingest_usenet_item_journal(conn, path, family=fam)["skipped"] is True
    conn.close()


@pytest.mark.parametrize(
    "source,web,lineage",
    [
        pytest.param("apache_list_header_hostnames", True, None, id="apache_header"),
        pytest.param("ietf_list_header_hostnames", True, None, id="ietf_header"),
        # lanes of one archive, or of one spool, may not corroborate each other
        pytest.param("usenet_header_fqdn_hostnames", True, "usenet", id="usenet_header"),
        pytest.param("usenet_body_url_hostnames", True, "usenet", id="usenet_header-lane"),
        pytest.param(hn.POLAND_SOURCE, True, "internet_archive", id="poland_pl"),
        pytest.param("usfedgov_extract_hostnames", True, "internet_archive", id="poland_pl-lane"),
        # the DNS lanes stay candidates: a name in a zone or a survey never served a page
        pytest.param("isc_survey_hostnames", False, None, id="isc"),
        pytest.param("ripe_nserver_hostnames", False, None, id="ripe_nserver"),
        pytest.param("internic_zone_hostnames", False, None, id="zone"),
    ],
)
def test_wall_only_web_facing_lanes_write_hostname_years(source, web, lineage) -> None:
    assert hn.writes_hostname_years(source) is web
    assert (source in hn.WEB_FACING_HOST_SOURCES) is web
    assert lineage is None or PROVENANCE_LINEAGE[source] == lineage


def usenet_hosts(line: str, keep_ephemeral: bool = False) -> list[str]:
    b = script(USENET_HEADER)
    return b.hosts_of_headers([line.encode()], dict.fromkeys(b.FIELDS, 0), keep_ephemeral)


READ = {
    "apache_header": lambda x: script(APACHE).by_hosts(
        script(APACHE).unfold(x) if isinstance(x, list) else x
    ),
    "usenet_header": usenet_hosts,
    "usenet_header-keep": lambda x: usenet_hosts(x, keep_ephemeral=True),
    "usenet_header-lease": lambda x: {script(USENET_HEADER).is_ephemeral(n) for n in x.split()},
    # field 3, the original URL: the SURT key in field 1 drops `www` and reverses the labels
    "poland_pl": lambda x: script(POLAND).host_of(x),
}
TAZ = "taz.hyperreal.org"
FOLDED = ["Received: from slarti.muc.de (192.0.2.10)", f"  by {TAZ} with SMTP; 1 Jan"]
FROM = "Received: from blonville.caii (ecstasy.localnet [192.0.2.19]) by mx.serv.net"
TRACE = "X-Trace: mail2news.demon.co.uk 894324354 19133 faqs pcserv.demon.co.uk"
POSTED, LEASE = "news2-win.server.ntlworld.com", "1cust104.tnt8.redondo-beach.ca.da.uu.net"
FIELD = {
    "apache_header": [
        # qmail's `invoked by uid` and a UUCP nodename carry no dot, so they fall out
        ("Received: (qmail 21311 invoked by uid 6000); 1 Jan 1999 19:30:10", []),
        ("Received: from en by slarti with UUCP; 01 Jan 1999 19:30:26 -0000", []),
        (FOLDED, ["taz.hyperreal.org"]),
        (
            "Received: by en1.engelschall.com (Sendmail 8.9.1) for x@apache.org",
            ["en1.engelschall.com"],
        ),
        # the sender chose the HELO name, so the `from` clause is forgeable and never read
        (FROM, ["mx.serv.net"]),
        ("Received: by 192.0.2.19 with SMTP", []),
        ("Subject: patch by someone.example.org for review", []),
    ],
    "usenet_header": [
        (TRACE, ["pcserv.demon.co.uk"]),
        ("NNTP-Posting-Host: pc-42.zetnet.co.uk", ["pc-42.zetnet.co.uk"]),
        # Path is written right to left, so the injecting site is the RIGHTMOST hostname; the
        # leftmost would bank `nntp.google.com` millions of times, and dotless nodes fall out
        ("Path: nntp.google.com!news1.google.com!demon!not-for-mail", ["news1.google.com"]),
        ("Path: nntp.google.com!feeder.news.demon.co.uk!not-for-mail", ["feeder.news.demon.co.uk"]),
        ("Message-ID: <abc@pcserv.demon.co.uk>", []),  # client-stamped, never read
        ("NNTP-Posting-Host: 192.0.2.1", []),
        ("NNTP-Posting-Host:", []),
        ("X-Trace: posting.google.com 1340536695 5508 127.0.0.1", ["posting.google.com"]),
        # `.POSTED` banked 2,006 rows of fiction; `.MISMATCH` says the reverse DNS did not match
        (f"Path: aioe.org!{POSTED}.POSTED!not-for-mail", [POSTED]),
        ("Path: news.glorb.com!198.186.194.249.MISMATCH!not-for-mail", ["news.glorb.com"]),
        (f"NNTP-Posting-Host: {LEASE}", []),
    ],
    "usenet_header-keep": [(f"NNTP-Posting-Host: {LEASE}", [LEASE])],
    "usenet_header-lease": [
        (f"{LEASE} 136.pool2.fukuoka.att.ne.jp man-s286.dialup.zetnet.co.uk", {True}),
        ("1-2-3-4.dialup.example.net 0addba1d.news.tdin.com", {True}),
        ("pcserv.demon.co.uk news.zetnet.co.uk dialup.example.com posting.google.com", {False}),
        ("news1.gvcl1.bc.home.com", {False}),
    ],
    "poland_pl": [
        ("http://www.zsp.busko-zdroj.com.pl:80/~ak/k.htm", "www.zsp.busko-zdroj.com.pl"),
        ("http://gwx.gazeta.pl:80/index.html", "gwx.gazeta.pl"),
    ],
}


# fmt: off
@pytest.mark.parametrize("reader,given,want", [
    pytest.param(r, g, w, id=f"{r}-{i}")
    for r, cases in FIELD.items() for i, (g, w) in enumerate(cases)
])
# fmt: on
def test_field_chosen(reader, given, want) -> None:
    assert READ[reader](given) == want


GW, ZSP = "http://gwx.gazeta.pl:80/", "http://www.zsp.busko-zdroj.com.pl:80/~ak/k.htm"
CDX = [
    " CDX N b a m s k r M S V g",
    f"pl,gazeta,gwx)/~p/hz11.html 19960510131727 {GW}~p/hz11.html text/html 200 X - - 3 3 a",
    f"pl,gazeta,gwx)/index.html 19960710131727 {GW}index.html text/html 200 Q - - 3 3 a",
    f"pl,com,busko-zdroj,zsp)/~ak/k.htm 20010520075947 {ZSP} text/html 200 Z - - 3 3 a",
    "pl,onet)/ 20010101000000 http://www.onet.pl:80/ text/html 404 A - - 1 1 a",
    "pl,onet)/x 20010101000000 http://www.onet.pl:80/x text/html 503 B - - 1 1 a",
    "pl,wp)/ 20030101000000 http://www.wp.pl:80/ text/html 200 C - - 1 1 a",
]


def test_wall_poland_pl_only_a_200_inside_the_window_reaches_the_journal(tmp_path, monkeypatch):
    """The 4xx and 5xx status gate: an error capture is outside the priced population, and
    of one host's captures in a year, the EARLIEST dates the pair."""
    m = script(POLAND)
    monkeypatch.setattr(m, "OUT", tmp_path / "out")
    index = tmp_path / "pl-2001-EXTRACTION-x.cdx.gz"
    index.write_bytes(gzip.compress(("\n".join(CDX) + "\n").encode()))
    size, sha = index.stat().st_size, hashlib.sha256(index.read_bytes()).hexdigest()
    # a short or altered index is refused rather than half-read into dates
    assert m.reduce_one(index, (size + 1, sha)) == m.reduce_one(index, (size, "0" * 64)) == 2
    assert not list((tmp_path / "out").glob("*.jsonl.gz"))
    assert m.reduce_one(index, (size, sha)) == 0
    [written] = (tmp_path / "out").glob("*.jsonl.gz")
    assert [json.loads(line) for line in gzip.open(written, "rt")] == [
        {"url": f"{GW}~p/hz11.html", "timestamp": "19960510131727"},
        {"url": ZSP, "timestamp": "20010520075947"},
    ]
    # the journal routes to this source, and the sibling extraction lane does not
    assert written.name == "poland_pl_pl-2001-EXTRACTION-x_hostgrain.jsonl.gz"
    assert hn.source_for(Path(written.name)) == (hn.POLAND_SOURCE, hn.POLAND_METHOD)
    sibling = hn.source_for(Path("usfedgov_USFEDGOV-EXTRACT-2001_hostgrain.jsonl.gz"))
    assert sibling[0] != hn.POLAND_SOURCE
    assert len(m.receipts()) == 19


MMDF, DATE = "\x01\x01\x01\x01", "Wed Oct  2 12:08:00 1996"
RELAY = [FOLDED[0], "  by cnri.reston.va.us with SMTP", "Date: Wed, 2 Oct 1996 11:05:48 -0400", ""]
SECOND = ["Received: by second.example.org (x)", "Date: Thu, 3 Oct 1996 09:00:00 -0400", ""]
LATE = ["Received: by wrong.example.org (x)", "Date: Wed, 01 Jan 1997 09:00:00 +0000", ""]
MONTH = [
    # MMDF has no `From ` line, so the mbox boundary alone read 89 MB of it as silence
    ([MMDF, *RELAY, "x", MMDF, MMDF, *SECOND, "x", MMDF], 2, {"messages": 2}, "ietf_header-mmdf"),
    ([f"From MAILER-DAEMON {DATE}", *RELAY, "From x"], 1, {"with_hosts": 1}, "ietf_header-mbox"),
    # the partition's year is a free second opinion on the message's own Date
    ([MMDF, *LATE, "x", MMDF], 0, {"year_disagrees": 1, "in_window": 0}, "ietf_header-year"),
]


@pytest.mark.parametrize("lines,n,stats", [pytest.param(*m[:3], id=m[3]) for m in MONTH])
def test_wall_and_funnel_ietf_header_month_files(lines, n, stats) -> None:
    c = script(IETF)
    got = c.new_stats()
    rows = list(c.rows_of(iter(lines), f"www.ietf.org/{IE}", 1996, got))
    hosts = ["cnri.reston.va.us", "second.example.org"][:n]
    want = [(f"www.ietf.org/{IE}#{i + 1}", h) for i, h in enumerate(hosts)]
    assert [(r["item"], r["text"]) for r in rows] == want
    assert {k: got[k] for k in stats} == stats


def test_wall_apache_header_a_message_its_own_date_denies_is_dropped(tmp_path) -> None:
    mbox = ["From MAILER-DAEMON Fri Jan  1 19:30:08 1999", *FOLDED[:1]]
    mbox += [f"  by {TAZ} with SMTP; 1 Jan 1999 19:30:08 -0000"]
    mbox += ["Date: Fri, 1 Jan 1999 19:58:57 +0100", "", "http://www.engelschall.com/ unread", ""]
    mbox += ["From MAILER-DAEMON Sat Jan  2 09:00:00 1999", *LATE, "a clock set a year wrong"]
    path = tmp_path / "httpd.apache.org" / "dev__1999-01.mbox.gz"
    path.parent.mkdir()
    path.write_bytes(gzip.compress(("\n".join(mbox) + "\n").encode()))
    # through the real worker, so a stats key it never seeds loses the row here too
    stats = script(APACHE).worker((0, [path], tmp_path))
    assert (stats["messages"], stats["in_window"], stats["year_disagrees"]) == (2, 1, 1)
    rows = [json.loads(s) for s in gzip.open(tmp_path / "shard_000.jsonl.gz", "rt")]
    assert rows == [{"item": f"{AP}#1", "year": 1999, "text": TAZ}]


def test_funnel_ietf_header_a_growing_plain_shard_is_read_again(tmp_path) -> None:
    """The walker once globbed `*.jsonl.gz` alone and saw none of this lane's `.jsonl` shards,
    and a done-key on the file NAME froze a shard the collector keeps appending to."""
    items = FAMILIES[1].values[2]
    shard = journal(tmp_path, items[:1], "snmpv2.jsonl")
    conn = duckdb.connect(":memory:")
    init_db(conn)
    walked = hn.ingest_usenet_item_dir(conn, shard.parent, family=hn.IETF_FAMILY)
    assert (walked["files_seen"], walked["hostname_year_rows"]) == (1, 1)
    with shard.open("a") as fh:
        fh.write(line(items[2]))
    grown = hn.ingest_usenet_item_journal(conn, shard, family=hn.IETF_FAMILY)
    assert (grown["skipped"], grown["hostname_year_rows"]) == (False, 1)
    assert conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0] == 2
    assert hn.ingest_usenet_item_journal(conn, shard, family=hn.IETF_FAMILY)["skipped"] is True
    conn.close()
    source = Path(script(IETF).__file__).read_text()
    assert 'ITEMS_DIR / (stem.rsplit("/", 2)[-2] + ".jsonl")' in source, "the shard name moved"


def test_collectors_ask_only_for_window_months_at_their_measured_pace() -> None:
    a, c = script(LISTS), script(IETF)
    # the Apache API accepts a range and IGNORES it, so a month is the only form it may send
    assert (a.MONTHS[0], a.MONTHS[-1], len(a.MONTHS)) == ("1996-01", "2001-12", 72)
    assert all(c.MONTH_FILE.match(m) for m in ("1996-03", "1999-05.mail", "2001-12.mail"))
    outside = ("1995-12", "2002-01.mail", "2017-06.mail", "1999-13")
    assert not any(c.MONTH_FILE.match(m) for m in outside)
    # robots.txt asks 5 s of Apache; six parallel IETF listings drew a 429 inside a minute
    assert a.CRAWL_DELAY >= 5.0 and c.CRAWL_DELAY >= 0.75
    assert c.USER_AGENT.startswith("ark-research/")
