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
from ark.checks import CHECKS
from ark.db import add_candidate, assign_year, ensure_source, init_db, record_evidence

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
M = "sources/mail_corpora/"
APACHE, LISTS = f"{M}build_apache_header_pool.py", f"{M}collect_apache_lists.py"
IETF, MAILLISTS = f"{M}collect_ietf_mail_archive.py", f"{M}collect_mailing_lists.py"
ENRON, MAILLIST = f"{M}build_enron_pool.py", f"{M}build_maillist_pool.py"
POLAND, CONVERT = "sources/poland/poland_pl_hostgrain.py", "engines/cdx_suffix_convert.py"
USENET_HEADER = "sources/usenet/build_usenet_header_pool.py"


@functools.cache
def script(rel: str):
    spec = importlib.util.spec_from_file_location(Path(rel).stem, SCRIPTS / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# `ark check` fails on a host record from a lane whose observation shows no host in use
SERVED = next(sql for name, _, sql in CHECKS if name == "hostname_observed_serving_web")


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
def test_funnel_one_row_per_host_year_quotes_the_lowest_under_its_own_source_once(
    tmp_path, fam, source, items, quoted, kept
):
    counts: Counter = Counter()
    rows = hn.usenet_item_rows(path := journal(tmp_path, items), counts, family=fam)
    assert [(r[0], r[2]) for r in rows] == sorted((h, y) for h, (y, _) in kept.items())
    assert {r[0]: r[4] for r in rows} == {h: url for h, (_, url) in kept.items()}
    assert {r[0]: r[3] for r in rows}[items[0][2]] == quoted
    assert tuple(items[2][2].split()[:2]) in {r[:2] for r in rows}  # filed under its registrable
    assert counts == dict(lines=5, bad_item=1, out_of_window=1, registrable_row=1, rejected_host=1)
    conn = store()
    assert hn.ingest_usenet_item_journal(conn, path, family=fam)["hostname_year_rows"] == len(kept)
    assert q(conn, SERVED) == [(0,)]
    # every pool names its first shard `shard_000.jsonl.gz`, so the pool is part of the key
    sql = "SELECT DISTINCT name, source_file FROM evidence JOIN source USING (source_id)"
    assert q(conn, sql) == [(source, "items/shard_000.jsonl.gz")]
    # a host named in a message is a link filed under its parent, and never dates that parent
    sql = "SELECT hostname, parent_domain, assigned_year, evidence_type FROM hostname_year JOIN "
    got = q(conn, sql + "evidence USING (evidence_id) ORDER BY ALL")
    assert got == [(*r[:3], "link_source") for r in rows]
    assert q(conn, "SELECT count(*) FROM domain_year") == [(0,)]
    for value, where in q(conn, "SELECT evidence_value, record_location FROM evidence"):
        assert items[int(where.removeprefix("line ")) - 1][0] in value  # journal line N is item N
    assert hn.ingest_usenet_item_journal(conn, path, family=fam)["skipped"] is True


def usenet_hosts(lines: list[str], keep_ephemeral: bool = False) -> list[str]:
    b = script(USENET_HEADER)
    stats = dict.fromkeys(b.FIELDS, 0)
    return b.hosts_of_headers([s.encode() for s in lines], stats, keep_ephemeral)


READ = {
    "apache_header": lambda lines: script(APACHE).by_hosts(script(APACHE).unfold(lines)),
    "usenet_header": lambda lines: (usenet_hosts(lines), usenet_hosts(lines, keep_ephemeral=True)),
    # field 3, the original URL: the SURT key in field 1 drops `www` and reverses the labels
    "poland_pl": lambda url: script(POLAND).host_of(url),
    "maillist": lambda lines: [s for s in lines if script(MAILLIST).BOUNDARY.match(s)],
    "host_rule": lambda hosts: [h for h in hosts if hn._VALID_HOST.match(h)],
}
TAZ, POSTED = "taz.hyperreal.org", "news2-win.server.ntlworld.com"
FOLDED = ["Received: from slarti.muc.de (192.0.2.10)", f"  by {TAZ} with SMTP; 1 Jan"]
LATE = ["Received: by wrong.example.org (x)", "Date: Wed, 01 Jan 1997 09:00:00 +0000", ""]
KEPT = [
    "pcserv.demon.co.uk", "posting.google.com", "news1.google.com", POSTED, "news.glorb.com",
    "news1.gvcl1.bc.home.com", "dialup.example.com",
]  # fmt: skip
# every sender form pipermail writes opens a message, and no body sentence does
SENDERS = [b"From " + s for s in (
    b"samsaga2@menta.net Sun Dec 17 07:39:42 2000",
    b"skip at pobox.com  Fri Jun  1 17:26:35 2001",
    b"Samuele Pedroni <pedroni@inf.ethz.ch>  Fri Jun  1 13:49:11 2001",
    b"skip@pobox.com (Skip Montanaro)  Mon Jun  4 22:03:58 2001")]  # fmt: skip
# a dial-up lease: a pool word by a digit or in a later label, a slot, a session id, an address
LEASES = [
    "1cust104.tnt8.redondo-beach.ca.da.uu.net", "man-s286.dialup.zetnet.co.uk",
    "001-067.den1.da.amisp.net", "0addba1d.news.tdin.com", "pc-192-168-0-1.isp.com",
]  # fmt: skip
# fmt: off
FIELD = [
    ("apache_header", [
        "Received: (qmail 21311 invoked by uid 6000); 1 Jan 1999 19:30:10",  # no dot, no host
        *FOLDED,
        # the sender chose the HELO name, so the `from` clause is forgeable and never read
        "Received: from blonville.caii (ecstasy.localnet [192.0.2.19]) by mx.serv.net",
        "Received: by 192.0.2.19 with SMTP", "Subject: patch by someone.example.org for review",
    ], [TAZ, "mx.serv.net"]),
    ("usenet_header", [
        "X-Trace: mail2news.demon.co.uk 894324354 19133 faqs pcserv.demon.co.uk",
        "X-Trace: posting.google.com 1340536695 5508 127.0.0.1",
        # Path is written right to left, so the injecting site is the RIGHTMOST hostname; the
        # leftmost would bank `nntp.google.com` millions of times, and dotless nodes fall out
        "Path: nntp.google.com!news1.google.com!demon!not-for-mail",
        # `.POSTED` banked 2,006 rows of fiction; `.MISMATCH` says the reverse DNS did not match
        f"Path: aioe.org!{POSTED}.POSTED!not-for-mail",
        "Path: news.glorb.com!198.186.194.249.MISMATCH!not-for-mail",
        "Message-ID: <abc@client.example.com>",  # client-stamped, never read
        "NNTP-Posting-Host:", "NNTP-Posting-Host: 192.0.2.1",
        *(f"NNTP-Posting-Host: {h}" for h in [*LEASES, *KEPT[-2:]]),
    ], (sorted(KEPT), sorted(KEPT + LEASES))),
    ("poland_pl", "http://www.zsp.busko-zdroj.com.pl:80/~ak/k.htm", "www.zsp.busko-zdroj.com.pl"),
    ("maillist", [*SENDERS, b"From RFC 2396:", b">" + SENDERS[1]], SENDERS),
    # his rule: letters, digits, interior hyphens, an alphabetic TLD, RFC 1035's lengths
    ("host_rule", ["www.demon.co.uk", "x.y-z.com", "a.io", "a" * 63 + ".com", "foo.123", "a.b",
                   "nt_box.custard.co.uk", "localhost", "-bad.com", "bad-.com", "foo..com",
                   "a" * 64 + ".com", ("a" * 60 + ".") * 5 + "x" * 60 + ".com"],
     ["www.demon.co.uk", "x.y-z.com", "a.io", "a" * 63 + ".com"]),
]


@pytest.mark.parametrize("reader,given,want", [pytest.param(*c, id=c[0]) for c in FIELD])
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
DNS = [  # (ingest, file, hosts listed, one row, files refused with the stat that says why, id)
    (hn.ingest_isc_hostnames, ("wb_nw_9607_uk.gz", ISC),
     [("dummy.custard.co.uk", "custard.co.uk", 1996), ("medusa.specialist.co.uk",
      "specialist.co.uk", 1996), ("www.demon.co.uk", "demon.co.uk", 1996)],
     ("isc survey 1996-07 host dummy.custard.co.uk", "http://nw.com/zone/9607.hosts/uk.gz",
      "line 1", "artifact_listing", hn.ISC_METHOD),
     [("wb_nw_9607.domains.gz", ISC, "not_a_host_file"),
      ("wb_nw_9507_uk.gz", ISC, "out_of_window_file")], "isc"),
    # the TARGET of an NS record, continuation lines included; the owner is the registrable lane's
    (hn.ingest_zone_hostnames, ("org.zone.gz", ZONE),
     [("a.root-servers.net", "root-servers.net", 1997), ("ns1.provider.net", "provider.net", 1997),
      ("ns2.provider.net", "provider.net", 1997)],
     ("internic org zone serial 1997041800 NS ns1.provider.net",
      hn.ZONE_CAPTURE_URLS["org.zone.gz"], "line 6", "artifact_listing", hn.ZONE_METHOD),
     [("org.zone.gz", ZONE.replace("1997041800", "2002041800"), "out_of_window_file")], "zone"),
    # the dump's header stamp dates every `*ns:`, and a glue address is dropped
    (hn.ingest_ripe_nserver_hostnames, ("ripe.db.gz", SNAPSHOT),
     [("hydra.helsinki.fi", "helsinki.fi", 1999), ("ns.reverse.example.net", "example.net", 1999),
      ("ousrvr.oulu.fi", "oulu.fi", 1999), ("ra.abo.fi", "abo.fi", 1999)],
     ("ripe_dbase:19990804 ns hydra.helsinki.fi", f"{FUNET}ripe.db.gz", "line 8",
      "artifact_listing", hn.RIPE_NS_SNAPSHOT_METHOD),
     [("x.db.gz", SNAPSHOT, "not_a_ripe_file"),
      ("ripe.db.gz", "#\n# no date\n\n" + "*ns: ns.x.fi\n" * 60, "no_header_stamp"),
      ("ripe.db.gz", SNAPSHOT.replace("990804", "030804"), "stamp_out_of_window")],
     "ripe_nserver-snapshot"),
    # an object's LATEST `changed:` dates its nserver set; one last changed in 2003 gives nothing
    (hn.ingest_ripe_nserver_hostnames, ("ripe.db.domain.gz", SPLIT),
     [("ns.gu.kiev.ua", "gu.kiev.ua", 2001), ("ns.lucky.net", "lucky.net", 2001),
      ("ns1.provider.no", "provider.no", 1998)],
     ("ripe_changed:20010716 nserver ns.lucky.net", f"{FUNET}split/ripe.db.domain.gz", "line 3",
      "artifact_listing", hn.RIPE_NS_CHANGED_METHOD), [], "ripe_nserver-split"),
]
DNS_CASES = [pytest.param(*c[:5], id=c[5]) for c in DNS]
# fmt: on


@pytest.mark.parametrize("ingest,file,listed,row,refused", DNS_CASES)
def test_field_wall_and_funnel_dns_lanes(tmp_path, ingest, file, listed, row, refused) -> None:
    """A survey line, an NS target or an `nserver:` observes a machine, not a site; a file
    outside the window or the lane writes nothing."""
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
    for name, text, key in refused:
        assert ingest(conn := store(), write(tmp_path / "refused" / name, text)).get(key) == 1
        assert q(conn, "SELECT count(*) FROM evidence") == [(0,)]


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


def test_field_maillist_header_urls_and_a_gatewayed_list_stay_out_and_gzip_is_one_stem(tmp_path):
    raw = "From skip at pobox.com  Fri Jun  1 17:26:35 2001\nDate: Fri, 01 Jun 2001 17:26:35 -0500"
    raw += "\nList-Subscribe: <http://lists.sourceforge.net/mailman/listinfo/x>\n\n"
    raw += "See http://happydoc.sf.net/ for the tool.\nFrom there it is easy.\n\n"
    raw += "From Name <a@b.org>  Sat Jun  2 09:00:00 2001\nDate: Sat, 02 Jun 2001 09:00:00 +0000\n"
    path, out = write(tmp_path / "python/doc-sig__2001-June.txt.gz", raw + "\nx\n"), io.StringIO()
    script(MAILLIST).one_file(path, out, Counter())
    item = {"item": "python/doc-sig__2001-June.txt#1", "year": 2001, "text": "happydoc.sf.net"}
    assert [json.loads(s) for s in out.getvalue().splitlines()] == [item]
    # a list gatewayed to Usenet is Usenet's lineage, so the builder and the collector skip it
    write(tmp_path / "python/python-list__2001-June.txt", raw)
    assert script(MAILLIST).month_files(tmp_path) == [path]
    assert script(MAILLIST).SKIP_LISTS == script(MAILLISTS).SKIP_LISTS


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
    # each extraction lane banks under its own source, and `ark check` passes its host records
    assert written.name == "poland_pl_pl-2001-EXTRACTION-x_hostgrain.jsonl.gz"
    usfedgov = write(tmp_path / "out/usfedgov_x.jsonl.gz", gzip.open(written, "rt").read())
    sql = "SELECT DISTINCT name, acquisition_method FROM evidence JOIN source USING (source_id)"
    for path, *lane in [(written, hn.POLAND_SOURCE, hn.POLAND_METHOD),
                        (usfedgov, hn.USFEDGOV_SOURCE, hn.USFEDGOV_METHOD)]:  # fmt: skip
        assert hn.ingest_hostname_journal(conn := store(), path)["hostname_year_rows"] == 2
        assert q(conn, sql) == [tuple(lane)] and q(conn, SERVED) == [(0,)]


MMDF, DATE = "\x01\x01\x01\x01", "Wed Oct  2 12:08:00 1996"
RELAY = [FOLDED[0], "  by cnri.reston.va.us with SMTP", "Date: Wed, 2 Oct 1996 11:05:48 -0400", ""]
SECOND = ["Received: by second.example.org (x)", "Date: Thu, 3 Oct 1996 09:00:00 -0400", ""]
MONTH = [
    # MMDF has no `From ` line, so the mbox boundary alone read 89 MB of it as silence; the
    # partition's year is a free second opinion on the message's own Date
    ([MMDF, *RELAY, "x", MMDF, MMDF, *SECOND, "x", MMDF, MMDF, *LATE, "x", MMDF], 2,
     {"messages": 3, "year_disagrees": 1, "in_window": 2}, "ietf_header-mmdf"),
    ([f"From MAILER-DAEMON {DATE}", *RELAY, "From x"], 1, {"with_hosts": 1}, "ietf_header-mbox"),
]  # fmt: skip


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


MAIL_INDEX = """
  <a href="1999-January.txt.gz">[ Gzip'd Text ]</a> <a href="2001-December.txt">[ Text ]</a>
  <a href="2004-March.txt.gz">out</a> <a href="1995-July.txt">out</a>
  <a href="1999-January/thread.html">a thread page, not an archive file</a>
"""


def test_collectors_ask_only_for_window_months_at_their_measured_pace(monkeypatch) -> None:
    a, c, m = script(LISTS), script(IETF), script(MAILLISTS)
    # the Apache API accepts a range and IGNORES it, so a month is the only form it may send
    assert (a.MONTHS[0], a.MONTHS[-1], len(a.MONTHS)) == ("1996-01", "2001-12", 72)
    assert all(c.MONTH_FILE.match(x) for x in ("1996-03", "1999-05.mail", "2001-12.mail"))
    outside = ("1995-12", "2002-01.mail", "2017-06.mail", "1999-13")
    assert not any(c.MONTH_FILE.match(x) for x in outside)
    monkeypatch.setattr(m, "fetch", lambda url: MAIL_INDEX.encode())
    assert m.month_files("https://x/", "gtk-list") == ["1999-January.txt.gz", "2001-December.txt"]
    # robots.txt asks 5 s of Apache; six parallel IETF listings drew a 429 inside a minute
    assert a.CRAWL_DELAY >= 5.0 and c.CRAWL_DELAY >= 0.75
    assert all(x.USER_AGENT.startswith("ark-research/") for x in (a, c, m))


SQUIDGUARD = "# This list was compiled in 0:00:20 on 2001.12.18 15:04:29.\n# by squidGuardRobot\n"
SQUIDGUARD += "members.tripod.com\ntripod.com\n10.1.2.3\nunder_score.tripod.com\n"
SQUIDGUARD += "pages.example.org/x\n"
D01, D02 = 1008288000, 1033171200  # tar member stamps in 2001 and 2002
CHASTITY = {
    "adult/domains": ("a.tripod.com\nb.already-his.com\nr.rolled.com\n", D01),
    "adult/urls": ("c.tripod.com/x\n", D01),
    "adult/domains.20011124.diff": ("+d.tripod.com\n-e.tripod.com\n", D01),
    "mail/domains": ("f.tripod.com\n", D01),
    "porn/domains": ("g.tripod.com\n", D02),
}


def test_blocklists_date_each_listed_host_and_split_the_hand_kept_one(tmp_path, his_files):
    """squidGuard's compile stamp dates its list: a URL's path is stripped, an address dropped. A
    chastity tar member's header dates the member, a diff keeps its additions, and the split keeps
    a host under a parent dated by a pair of ours (tripod.com) or named exactly in his files
    (already-his.com, never rolled.com, of which he holds www.rolled.com). A listed host dates
    itself, never its parent."""
    conn = store()
    source = ensure_source(conn, "squidguard_2001", "timestamped")
    add_candidate(conn, "tripod.com", source)
    v = "squidguard:adult/domains@20011218"
    assign_year(conn, record_evidence(conn, "tripod.com", source, 2001, "artifact_listing", v))
    (squid := tmp_path / "squidguard-adult-domains").write_text(SQUIDGUARD)
    with tarfile.open(tar_path := tmp_path / "chastity-list_0.5.orig.tar.gz", "w:gz") as tar:
        for name, (text, mtime) in CHASTITY.items():
            info = tarfile.TarInfo(f"chastity-list-0.5/db/{name}")
            info.size, info.mtime = len(text.encode()), mtime
            tar.addfile(info, io.BytesIO(text.encode()))
    years = q(conn, "SELECT domain, assigned_year FROM domain_year")
    stats = [hn.ingest_blocklist_hostnames(conn, path) for path in (squid, tar_path)]
    assert [s["hostname_year_rows"] for s in stats] == [2, 4]
    assert (stats[1]["split_parked"], stats[1]["out_of_window_member"]) == (1, 1)
    cols = "hostname, parent_domain, assigned_year, evidence_type, evidence_value, record_location"
    got = q(conn, f"SELECT {cols} FROM hostname_year JOIN evidence USING (evidence_id) ORDER BY 1")
    assert [r[0] for r in got] == [
        "a.tripod.com", "b.already-his.com", "c.tripod.com", "d.tripod.com", "members.tripod.com",
        "pages.example.org",
    ]  # fmt: skip
    assert ("members.tripod.com", "tripod.com", 2001, "artifact_listing",
            f"{v} host members.tripod.com", "line 3") in got  # fmt: skip
    assert ("d.tripod.com", "tripod.com", 2001, "dated_directory",
            "chastity-list:20011214 adult/domains host d.tripod.com",
            "chastity-list-0.5/db/adult/domains.20011124.diff:line 1") in got  # fmt: skip
    assert q(conn, "SELECT domain, assigned_year FROM domain_year") == years
    parents = sorted(d for (d,) in q(conn, "SELECT domain FROM domain"))
    assert parents == ["already-his.com", "example.org", "tripod.com"]
    assert all(hn.ingest_blocklist_hostnames(conn, path)["skipped"] for path in (squid, tar_path))
    assert q(conn, "SELECT record_rows FROM ingested_file ORDER BY 1") == [(2,), (4,)]


def captures(path: Path, rows: list[tuple], mode: str = "wt") -> None:
    """Capture rows `(url, timestamp[, status])`; "at" appends a member, as a live sweep grows."""
    with gzip.open(path, mode) as fh:
        for url, ts, *status in rows:
            row = {"url": url, "timestamp": ts} | ({"status": status[0]} if status else {})
            fh.write(json.dumps(row) + "\n")


def convert(tmp: Path, tag: str, out: str = "out") -> list[dict]:
    """Run the suffix converter, then every row it has written under `out`."""
    script(CONVERT).main(["--glob", str(tmp / "in/*"), "--out", str(tmp / out), "--tag", tag])
    paths = sorted((tmp / out).glob("cdx_suffix_*.jsonl.gz"))
    return [json.loads(s) for path in paths for s in gzip.open(path, "rt")]


def test_cdx_suffix_convert_dates_a_registrable_by_its_earliest_exact_2xx_or_3xx(tmp_path, capsys):
    """A www, sub or underscore capture never dates the bare name, nor an error capture gives the
    stamp. A journal that grows between runs gives, over both runs, what one full run gives, and a
    rerun on nothing new writes nothing. Bad magic and a corrupt deflate stream (`zlib.error`, not
    an OSError) are named, and a live journal keeps the rows before its missing end marker."""
    (inp := tmp_path / "in").mkdir()
    captures(grown := inp / "suffix_x_com_1.jsonl.gz", [
        ("http://x.com/b", "19980601000000", "200"), ("http://www.x.com/", "19980101000000", "200"),
        ("http://x.com/", "19980201000000", "404"), ("http://x.com/a", "19980301000000", "200"),
        ("http://nt_srv.x.com/", "19990101000000"), ("http://x.com/later", "20050101000000"),
        ("http://sub.z.com:80/a", "20000101000000"), ("http://q.com?id=1", "19990101000000"),
        ("http://x.com/moved", "20000101000000", "302"),
    ])  # fmt: skip
    (inp / "suffix_magic_1.jsonl.gz").write_bytes(b"not a gzip at all\n")
    (inp / "suffix_deflate_1.jsonl.gz").write_bytes(gzip.compress(b"")[:10] + b"\xff" * 64)
    with gzip.GzipFile(fileobj=(buf := io.BytesIO()), mode="wb") as fh:
        fh.write(b'{"url": "http://live.com/", "timestamp": "19990101000000"}\n')
        fh.flush()
        cut = buf.tell()
    (inp / "suffix_live_1.jsonl.gz").write_bytes(buf.getvalue()[:cut])
    convert(tmp_path, "one")
    out = capsys.readouterr().out
    assert "bad gzip, skipped: suffix_magic_1.jsonl.gz" in out
    assert "bad gzip, skipped: suffix_deflate_1.jsonl.gz" in out
    assert "4 journal(s) read, 0 unchanged, 2 bad" in out
    captures(grown, [("http://X.com./", "20010101000000")], mode="at")
    later = [("http://x.com:8080/", "19960101000000"), ("http://x.com/c", "19980215000000")]
    captures(inp / "suffix_y_com_2.jsonl.gz", later)
    claim: dict[str, set[int]] = {}
    for row in convert(tmp_path, "two"):
        claim.setdefault(row["domain"], set()).update(row["years"])
    assert "still bad: suffix_magic_1.jsonl.gz" in capsys.readouterr().out
    before = (state := tmp_path / "out" / script(CONVERT).STATE_NAME).stat().st_mtime_ns
    convert(tmp_path, "three")
    out = capsys.readouterr().out
    assert "0 journal(s) read, 5 unchanged, 2 bad" in out and "nothing written" in out
    assert state.stat().st_mtime_ns == before
    assert not (tmp_path / "out/cdx_suffix_three.jsonl.gz").exists()
    x = {"1996": "19960101000000", "1998": "19980215000000", "2000": "20000101000000"}
    x |= {"2001": "20010101000000"}
    fresh = convert(tmp_path, "full", "fresh")
    assert [(r["domain"], r["status"], r["stamps"]) for r in fresh] == [
        ("live.com", 200, {"1999": "19990101000000"}), ("q.com", 200, {"1999": "19990101000000"}),
        ("x.com", 200, x),
    ]  # fmt: skip
    assert claim == {r["domain"]: set(r["years"]) for r in fresh}
