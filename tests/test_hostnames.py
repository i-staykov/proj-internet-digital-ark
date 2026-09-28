"""Hostname lanes, source by source: the field read, the wall that keeps a name out, and the
funnel from an archived item to one `(host, year)` row. Every case id names its source."""

import functools
import gzip
import hashlib
import importlib.util
import io
import json
import tarfile
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
ENRON, MAILLIST = "mail_corpora/build_enron_pool.py", "mail_corpora/build_maillist_pool.py"


@functools.cache
def script(rel: str):
    spec = importlib.util.spec_from_file_location(Path(rel).stem, SOURCES / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def store() -> duckdb.DuckDBPyConnection:
    init_db(conn := duckdb.connect(":memory:"))
    return conn


def q(conn, sql: str) -> list:
    return conn.execute(sql).fetchall()


def line(item: tuple) -> str:
    return json.dumps(dict(zip(("item", "year", "text"), item, strict=True))) + "\n"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(gzip.compress(text.encode()) if path.suffix == ".gz" else text.encode())
    return path


def journal(tmp_path: Path, items: list[tuple], name: str = "shard_000.jsonl.gz") -> Path:
    return write(tmp_path / "items" / name, "".join(line(i) for i in items))


def family(fam, source, noun, dup, reg, other, urls, id):
    """A lane's items: `dup` names one host twice in a year (the lower item is quoted), `reg` a host
    beside its registrable and a name off his rule, `other` another lane's pointer, and 2004."""
    (a, b, year, host), (item, ryear, rhost, registrable) = dup, reg
    items = [(a, year, host), (b, year, host), (item, ryear, f"{rhost} {registrable} x_{rhost}")]
    items += [(other, 1999, "other.example.org"), (a, 2004, "later.example.org")]
    kept = {host: (year, urls[0]), rhost: (ryear, urls[1])}
    return pytest.param(fam, source, items, f"{noun} {year} {a} {host}", kept, id=id)


AP, MBOX = "httpd.apache.org/dev__1999-01", "https://lists.apache.org/api/mbox.lua?list="
IE, FTP = "concluded-wg-ietf-mail-archive/snmpv2/1996-10", "https://www.ietf.org/ietf-ftp/"
SIEVE, DEMON = "ietf-mail-archive/sieve/1997-03.mail", "demon.ip.support.pc.mbox.zip"
IA, UK = "https://archive.org/download/", "uk.comp.sys.mbox.zip"
GTK, BLAIR = "gnome/gtk-list__1999-May.txt", "maildir/blair-l/personnel___promotions"
# fmt: off
FAMILIES = [
    family(hn.APACHE_FAMILY, "apache_list_header_hostnames", "list header",
           (f"{AP}#1", f"{AP}#9", 1999, "taz.hyperreal.org"),
           ("tomcat.apache.org/users__2001-06#3", 2001, "mail.ibm.com", "ibm.com"), f"{GTK}#367",
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
    # `#12` sorts below `#99`; the identifier follows the group, not the pool; `www.` is a record
    family(hn.USENET_FAMILY, "usenet_body_url_hostnames", "usenet post",
           (f"{UK}#12", f"{UK}#99", 1997, "www.demon.co.uk"),
           ("microsoft.public.mbox.zip#7", 1999, "support.microsoft.com", "microsoft.com"),
           "somewhere", [f"{IA}usenet-uk/{UK}", f"{IA}usenet-microsoft/microsoft.public.mbox.zip"],
           "usenet"),
    # the pointer resolves to the archive host that serves it, which differs per list host
    family(hn.MAILLIST_FAMILY, "maillist_body_url_hostnames", "list message",
           (f"{GTK}#367", f"{GTK}#400", 1999, "gimp.cs.stevens-tech.edu"),
           ("python/doc-sig__2001-June.txt#7", 2001, "happydoc.sf.net", "sf.net"), f"{UK}#12",
           ["https://mail.gnome.org/archives/gtk-list/1999-May.txt.gz",
            "https://mail.python.org/pipermail/doc-sig/2001-June.txt"], "maillist"),
    # the item is the tar member, and every item resolves to the one release CMU serves
    family(hn.ENRON_FAMILY, "enron_body_url_hostnames", "enron message",
           (f"{BLAIR}/1.", f"{BLAIR}/7.", 2001, "oasis.caiso.com"),
           ("maildir/kaminski-v/all_documents/12.", 2000, "risk.enron.com", "enron.com"),
           f"{UK}#12", [hn.ENRON_ARCHIVE] * 2, "enron"),
]
# fmt: on


@pytest.mark.parametrize("fam,source,items,quoted,kept", FAMILIES)
def test_funnel_one_row_per_host_year_quotes_the_lowest(tmp_path, fam, source, items, quoted, kept):
    counts: Counter = Counter()
    rows = hn.usenet_item_rows(journal(tmp_path, items), counts, family=fam)
    assert [(r[0], r[2]) for r in rows] == sorted((h, y) for h, (y, _) in kept.items())
    assert {r[0]: r[4] for r in rows} == {h: url for h, (_, url) in kept.items()}
    assert {r[0]: r[3] for r in rows}[items[0][2]] == quoted
    assert tuple(items[2][2].split()[:2]) in {r[:2] for r in rows}  # filed under its registrable
    assert counts == dict(lines=5, bad_item=1, out_of_window=1, registrable_row=1, rejected_host=1)


@pytest.mark.parametrize("fam,source,items,quoted,kept", FAMILIES)
def test_funnel_ingest_lands_under_its_own_source_once(tmp_path, fam, source, items, quoted, kept):
    conn, path = store(), journal(tmp_path, items)
    assert hn.ingest_usenet_item_journal(conn, path, family=fam)["hostname_year_rows"] == len(kept)
    # every pool names its first shard `shard_000.jsonl.gz`, so the pool is part of the key
    sql = "SELECT DISTINCT name, source_file FROM evidence JOIN source USING (source_id)"
    assert q(conn, sql) == [(source, "items/shard_000.jsonl.gz")]
    # a host named in a message is a link filed under its parent, and never dates that parent
    want = [(*r[:3], "link_source") for r in hn.usenet_item_rows(path, Counter(), family=fam)]
    sql = "SELECT hostname, parent_domain, assigned_year, evidence_type FROM hostname_year JOIN "
    assert q(conn, sql + "evidence USING (evidence_id) ORDER BY ALL") == want
    assert q(conn, "SELECT count(*) FROM domain_year") == [(0,)]
    for value, where in q(conn, "SELECT evidence_value, record_location FROM evidence"):
        assert items[int(where.removeprefix("line ")) - 1][0] in value  # journal line N is item N
    assert hn.ingest_usenet_item_journal(conn, path, family=fam)["skipped"] is True


# fmt: off
@pytest.mark.parametrize("source,web,lineage", [pytest.param(*c[:3], id=c[3]) for c in [
    ("apache_list_header_hostnames", True, None, "apache_header"),
    ("ietf_list_header_hostnames", True, None, "ietf_header"),
    # lanes of one archive, or of one spool, may not corroborate each other
    ("usenet_header_fqdn_hostnames", True, "usenet", "usenet_header"),
    ("usenet_body_url_hostnames", True, "usenet", "usenet"),
    (hn.POLAND_SOURCE, True, "internet_archive", "poland_pl"),
    ("usfedgov_extract_hostnames", True, "internet_archive", "poland_pl-lane"),
    # the DNS lanes stay candidates: a name in a zone or a survey never served a page
    ("isc_survey_hostnames", False, None, "isc"),
    ("ripe_nserver_hostnames", False, None, "ripe_nserver"),
    ("internic_zone_hostnames", False, None, "zone"),
]])
# fmt: on
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
    "maillist-boundary": lambda x: bool(script(MAILLIST).BOUNDARY.match(x)),
    "host_rule": lambda x: bool(hn._VALID_HOST.match(x)),
}
TAZ = "taz.hyperreal.org"
FOLDED = ["Received: from slarti.muc.de (192.0.2.10)", f"  by {TAZ} with SMTP; 1 Jan"]
FROM = "Received: from blonville.caii (ecstasy.localnet [192.0.2.19]) by mx.serv.net"
TRACE = "X-Trace: mail2news.demon.co.uk 894324354 19133 faqs pcserv.demon.co.uk"
POSTED, LEASE = "news2-win.server.ntlworld.com", "1cust104.tnt8.redondo-beach.ca.da.uu.net"
# fmt: off
FIELD = {
    "apache_header": [
        # qmail's `invoked by uid` and a UUCP nodename carry no dot, so they fall out
        ("Received: (qmail 21311 invoked by uid 6000); 1 Jan 1999 19:30:10", []),
        ("Received: from en by slarti with UUCP; 01 Jan 1999 19:30:26 -0000", []),
        (FOLDED, ["taz.hyperreal.org"]),
        ("Received: by en1.engelschall.com (Sendmail 8.9.1) for x@apache.org",
         ["en1.engelschall.com"]),
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
    # every sender form pipermail writes opens a message, and no body sentence does
    "maillist-boundary": [(b"From " + s, True) for s in (
        b"samsaga2@menta.net Sun Dec 17 07:39:42 2000",
        b"skip at pobox.com  Fri Jun  1 17:26:35 2001",
        b"Samuele Pedroni <pedroni@inf.ethz.ch>  Fri Jun  1 13:49:11 2001",
        b"skip@pobox.com (Skip Montanaro)  Mon Jun  4 22:03:58 2001")] + [(s, False) for s in (
        b"From RFC 2396:", b"From now on please do all bugfixes in gnome-1-4-branch, all cool",
        b">From skip at pobox.com  Fri Jun  1 17:26:35 2001")],
    # his rule: letters, digits, interior hyphens, an alphabetic TLD, RFC 1035's lengths
    "host_rule": [(h, True) for h in ("www.demon.co.uk", "x.y-z.com", "a.io", "x.in-addr.arpa",
                                      "a" * 63 + ".com")] + [(h, False) for h in (
        "foo.123", "1.2.3.4", "a.b", "nt_box.custard.co.uk", "localhost", "-bad.com", "bad-.com",
        "foo..com", "a" * 64 + ".com", ("a" * 60 + ".") * 5 + "x" * 60 + ".com")],
}


@pytest.mark.parametrize("reader,given,want", [
    pytest.param(r, g, w, id=f"{r}-{i}")
    for r, cases in FIELD.items() for i, (g, w) in enumerate(cases)
])
# fmt: on
def test_field_chosen(reader, given, want) -> None:
    assert READ[reader](given) == want


# fmt: off
# fixture addresses sit on `hygiene.KNOWN_ADDRESSES`
ISC = "".join(f"{a} {h}\n" for a, h in [
    ("1.0.0.2", "dummy.custard.co.uk"), ("1.125.2.7", "medusa.specialist.co.uk"),
    ("1.125.2.8", "medusa.specialist.co.uk"), ("1.3.3.1", "specialist.co.uk"),
    ("1.3.3.2", "nt_box.custard.co.uk"), ("1.3.3.3", "www.demon.co.uk.")])
ZONE = "\n".join([
    "ORG.\tIN\tSOA\tA.ROOT-SERVERS.NET.\thostmaster.INTERNIC.NET. (", "\t\t1997041800\t;serial",
    ")", "ORG.  518400 IN NS A.ROOT-SERVERS.NET.", "A.ROOT-SERVERS.NET.  518400 A 198.41.0.4",
    "EXAMPLE.ORG.  172800 NS NS1.PROVIDER.NET.", "  172800 NS NS2.PROVIDER.NET.",
    "OTHER.ORG.  172800 NS OTHER.ORG.", "BARE.ORG.  172800 NS PROVIDER.NET.",
    "ODD.ORG.  172800 NS UNDER_SCORE.PROVIDER.NET.", ""])
# every field but `*ns:` is bait: the RIPE NCC permission lets a nameserver and a date leave
SNAPSHOT = "\n".join([
    "#", "# 990804 00:07:01", "#", "", "*dn: OULU.FI", "*ac: KR101", "*ns: ousrvr.oulu.fi",
    "*ns: hydra.helsinki.fi 128.214.4.29", "*ch: lk-kr@finou.oulu.fi 19910916", "",
    "*dn: TuKKK.FI", "*de: Rehtorinpellonkatu 3, SF-20500 TURKU, Finland", "*ac: +358 21 6383105",
    "*tc: hostmaster@utu.fi", "*ns: ra.abo.fi", "*ns: abo.fi", "*ns: under_score.abo.fi", "",
    "*dn: 231.130.IN-ADDR.ARPA", "*ns: ns.reverse.example.net", ""])
SPLIT = "\n".join([
    "domain: 200.193.193.in-addr.arpa", "admin-c: LNN1-RIPE", "nserver: ns.lucky.net",
    "nserver: ns.gu.kiev.ua", "changed: mx@lucky.net 19990716", "changed: mx@lucky.net 20010716",
    "", "domain: example.gm", "nserver: ns1.provider.no", "changed: hm@provider.no 20031104", "",
    "domain: other.gm", "nserver: ns1.provider.no", "nserver: provider.no",
    "changed: hostmaster@provider.no 19981104", ""])
FUNET = "https://ftp.funet.fi/pub/netinfo/RIPE/dbase/"
# fmt: on


def test_wall_ripe_nserver_emits_no_personal_data(tmp_path) -> None:
    rows = hn.ripe_snapshot_nservers(write(tmp_path / "ripe.db.gz", SNAPSHOT), Counter())
    rows += hn.ripe_changed_nservers(write(tmp_path / "ripe.db.domain.gz", SPLIT), Counter())
    emitted = " ".join(f"{h} {p} {v}" for h, p, _, v in rows)
    for bait in ("@", "+358", "Rehtorinpellonkatu", "TURKU", "KR101", "utu.fi", "lk-kr", "LNN1"):
        assert bait not in emitted, f"reader leaked {bait!r}"


# fmt: off
DNS = [  # (ingest, file, hosts listed, one row, id)
    (hn.ingest_isc_hostnames, ("wb_nw_9607_uk.gz", ISC),
     [("dummy.custard.co.uk", "custard.co.uk", 1996), ("medusa.specialist.co.uk",
      "specialist.co.uk", 1996), ("www.demon.co.uk", "demon.co.uk", 1996)],
     ("isc survey 1996-07 host dummy.custard.co.uk", "http://nw.com/zone/9607.hosts/uk.gz",
      "line 1", "artifact_listing", hn.ISC_METHOD), "isc"),
    # the TARGET of an NS record, continuation lines included; the owner is the registrable lane's
    (hn.ingest_zone_hostnames, ("org.zone.gz", ZONE),
     [("a.root-servers.net", "root-servers.net", 1997), ("ns1.provider.net", "provider.net", 1997),
      ("ns2.provider.net", "provider.net", 1997)],
     ("internic org zone serial 1997041800 NS ns1.provider.net",
      hn.ZONE_CAPTURE_URLS["org.zone.gz"], "line 6", "artifact_listing", hn.ZONE_METHOD), "zone"),
    # the dump's header stamp dates every `*ns:`, and a glue address is dropped
    (hn.ingest_ripe_nserver_hostnames, ("ripe.db.gz", SNAPSHOT),
     [("hydra.helsinki.fi", "helsinki.fi", 1999), ("ns.reverse.example.net", "example.net", 1999),
      ("ousrvr.oulu.fi", "oulu.fi", 1999), ("ra.abo.fi", "abo.fi", 1999)],
     ("ripe_dbase:19990804 ns hydra.helsinki.fi", f"{FUNET}ripe.db.gz", "line 8",
      "artifact_listing", hn.RIPE_NS_SNAPSHOT_METHOD), "ripe_nserver-snapshot"),
    # an object's LATEST `changed:` dates its nserver set; one last changed in 2003 gives nothing
    (hn.ingest_ripe_nserver_hostnames, ("ripe.db.domain.gz", SPLIT),
     [("ns.gu.kiev.ua", "gu.kiev.ua", 2001), ("ns.lucky.net", "lucky.net", 2001),
      ("ns1.provider.no", "provider.no", 1998)],
     ("ripe_changed:20010716 nserver ns.lucky.net", f"{FUNET}split/ripe.db.domain.gz", "line 3",
      "artifact_listing", hn.RIPE_NS_CHANGED_METHOD), "ripe_nserver-split"),
]


@pytest.mark.parametrize("ingest,file,listed,row", [pytest.param(*c[:4], id=c[4]) for c in DNS])
# fmt: on
def test_field_wall_and_funnel_dns_lanes(tmp_path, ingest, file, listed, row) -> None:
    """A survey line, an NS target or an `nserver:` observes a machine, not a site."""
    conn, path = store(), write(tmp_path / file[0], file[1])
    assert ingest(conn, path)["hostname_year_rows"] == 0
    cols = "evidence_value, domain, evidence_year, evidence_url, record_location, evidence_type"
    got = q(conn, f"SELECT {cols}, acquisition_method FROM evidence")
    assert sorted((v.rsplit(" ", 1)[1], d, y) for v, d, y, *_ in got) == listed
    assert row in [(r[0], *r[3:]) for r in got]
    for value, _, _, _, where, *_ in got:  # a row names the line it was read from
        assert value.rsplit(" ", 1)[1] in file[1].splitlines()[int(where[5:]) - 1].lower(), value
    assert ingest(conn, path)["skipped"] is True
    sql = "SELECT (SELECT count(*) FROM hostname_year) + (SELECT count(*) FROM domain_year), "
    sql += "(SELECT count(*) FROM evidence), (SELECT sum(record_rows) FROM ingested_file)"
    assert q(conn, sql) == [(0, len(listed), 0)]


# fmt: off
REFUSED = [  # (ingest, file, the stat that refuses it, id)
    (hn.ingest_isc_hostnames, ("wb_nw_9607.domains.gz", ISC), "not_a_host_file", "isc-domains"),
    (hn.ingest_isc_hostnames, ("wb_nw_9507_uk.gz", ISC), "out_of_window_file", "isc-1995"),
    (hn.ingest_zone_hostnames, ("org.zone.gz", ZONE.replace("1997041800", "2002041800")),
     "out_of_window_file", "zone-2002"),
    (hn.ingest_ripe_nserver_hostnames, ("x.db.gz", SNAPSHOT), "not_a_ripe_file", "ripe_nserver"),
    (hn.ingest_ripe_nserver_hostnames, ("ripe.db.gz", "#\n# no date\n\n" + "*ns: ns.x.fi\n" * 60),
     "no_header_stamp", "ripe_nserver-no_stamp"),
    (hn.ingest_ripe_nserver_hostnames, ("ripe.db.gz", SNAPSHOT.replace("990804", "030804")),
     "stamp_out_of_window", "ripe_nserver-2003"),
]
# fmt: on


@pytest.mark.parametrize("ingest,file,key", [pytest.param(*c[:3], id=c[3]) for c in REFUSED])
def test_wall_a_file_outside_the_window_or_the_lane_writes_nothing(tmp_path, ingest, file, key):
    assert ingest(conn := store(), write(tmp_path / file[0], file[1])).get(key) == 1
    sql = "SELECT (SELECT count(*) FROM evidence) + (SELECT count(*) FROM hostname_year)"
    assert q(conn, sql) == [(0,)]


def test_field_enron_the_builder_streams_the_tarball_and_reads_dated_bodies_only(tmp_path):
    # fmt: off
    members = {
        f"{BLAIR}/1.": b"Message-ID: <1.JavaMail@thyme>\r\nDate: Fri, 14 Sep 2001 14:05:43 -0700"
        b"\r\n\r\nFiled at http://oasis.caiso.com/x/ and see FTP://Data.Example.COM:21/x\r\n",
        # a URL in a header was not typed by the sender
        "maildir/kaminski-v/sent/2.": b"Date: Mon, 03 Jan 2000 09:00:00 -0800\nX-Folder: "
        b"http://in.header.example.org/\n\nnothing typed here\n",
        "maildir/blair-l/inbox/3.": b"Date: Tue, 05 Mar 2002 09:00:00 -0800\n\nhttp://late.example.org/",
        "maildir/blair-l/inbox/4.": b"Subject: no date\n\nhttp://undated.example.org/\n",
        "README": b"not a message"}
    # fmt: on
    with tarfile.open(path := tmp_path / "enron.tar.gz", "w:gz") as tar:
        for name, raw in members.items():
            (info := tarfile.TarInfo(name)).size = len(raw)
            tar.addfile(info, io.BytesIO(raw))
    script(ENRON).build(path, tmp_path / "items")
    rows = [json.loads(s) for s in gzip.open(tmp_path / "items/shard_000.jsonl.gz", "rt")]
    text = "oasis.caiso.com data.example.com"
    assert rows == [{"item": f"{BLAIR}/1.", "year": 2001, "text": text}]


def test_field_maillist_header_urls_stay_out_and_the_item_stem_ignores_gzip(tmp_path) -> None:
    raw = "From skip at pobox.com  Fri Jun  1 17:26:35 2001\nDate: Fri, 01 Jun 2001 17:26:35 -0500"
    raw += "\nList-Subscribe: <http://lists.sourceforge.net/mailman/listinfo/x>\n\n"
    raw += "See http://happydoc.sf.net/ for the tool.\nFrom there it is easy.\n\n"
    raw += "From Name <a@b.org>  Sat Jun  2 09:00:00 2001\nDate: Sat, 02 Jun 2001 09:00:00 +0000\n"
    path, out = write(tmp_path / "python/doc-sig__2001-June.txt.gz", raw + "\nx\n"), io.StringIO()
    script(MAILLIST).one_file(path, out, Counter())
    item = {"item": "python/doc-sig__2001-June.txt#1", "year": 2001, "text": "happydoc.sf.net"}
    assert [json.loads(s) for s in out.getvalue().splitlines()] == [item]


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
    index = write(tmp_path / "pl-2001-EXTRACTION-x.cdx.gz", "\n".join(CDX) + "\n")
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
    got = (c := script(IETF)).new_stats()
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
    path = write(tmp_path / "httpd.apache.org" / "dev__1999-01.mbox.gz", "\n".join(mbox) + "\n")
    # through the real worker, so a stats key it never seeds loses the row here too
    stats = script(APACHE).worker((0, [path], tmp_path))
    assert (stats["messages"], stats["in_window"], stats["year_disagrees"]) == (2, 1, 1)
    rows = [json.loads(s) for s in gzip.open(tmp_path / "shard_000.jsonl.gz", "rt")]
    assert rows == [{"item": f"{AP}#1", "year": 1999, "text": TAZ}]


def test_funnel_ietf_header_a_growing_plain_shard_is_read_again(tmp_path) -> None:
    conn, shard = store(), journal(tmp_path, (items := FAMILIES[1].values[2])[:1], "snmpv2.jsonl")
    walked = hn.ingest_usenet_item_dir(conn, shard.parent, family=hn.IETF_FAMILY)
    assert (walked["files_seen"], walked["hostname_year_rows"]) == (1, 1)
    with shard.open("a") as fh:
        fh.write(line(items[2]))
    grown = hn.ingest_usenet_item_journal(conn, shard, family=hn.IETF_FAMILY)
    assert (grown["skipped"], grown["hostname_year_rows"]) == (False, 1)
    assert q(conn, "SELECT count(*) FROM hostname_year") == [(2,)]
    assert hn.ingest_usenet_item_journal(conn, shard, family=hn.IETF_FAMILY)["skipped"] is True


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
