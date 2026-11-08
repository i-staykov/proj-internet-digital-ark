"""The hostname lanes `just bank` folds (`ark ingest-usenet-hostnames`, `-usenet-header-`,
`-maillist-`, `-enron-`, `cdx_suffix_convert.py`), the header lane's field read
(`build_usenet_header_pool.py`) and the RIPE NCC promise its decided block cites: the wall that
keeps a name out, and the funnel from an archived item to one `(host, year)` row."""

import functools
import gzip
import io
import json
from collections import Counter
from pathlib import Path

import duckdb
import pytest
from conftest import script

from ark import hostnames as hn
from ark.checks import CHECKS
from ark.db import init_db

CONVERT = "engines/cdx_suffix_convert.py"
USENET_HEADER = "sources/usenet/build_usenet_header_pool.py"


script = functools.cache(script)

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


AP, DEMON = "httpd.apache.org/dev__1999-01", "demon.ip.support.pc.mbox.zip"
IA, UK = "https://archive.org/download/", "uk.comp.sys.mbox.zip"
GTK, BLAIR = "gnome/gtk-list__1999-May.txt", "maildir/blair-l/personnel___promotions"
# fmt: off
FAMILIES = [
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
    "usenet_header": lambda lines: (usenet_hosts(lines), usenet_hosts(lines, keep_ephemeral=True)),
    "host_rule": lambda hosts: [h for h in hosts if hn._VALID_HOST.match(h)],
}
POSTED = "news2-win.server.ntlworld.com"
KEPT = [
    "pcserv.demon.co.uk", "posting.google.com", "news1.google.com", POSTED, "news.glorb.com",
    "news1.gvcl1.bc.home.com", "dialup.example.com",
]  # fmt: skip
# a dial-up lease: a pool word by a digit or in a later label, a slot, a session id, an address
LEASES = [
    "1cust104.tnt8.redondo-beach.ca.da.uu.net", "man-s286.dialup.zetnet.co.uk",
    "001-067.den1.da.amisp.net", "0addba1d.news.tdin.com", "pc-192-168-0-1.isp.com",
]  # fmt: skip
# fmt: off
FIELD = [
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
# fmt: on


def test_wall_ripe_nserver_emits_no_personal_data(tmp_path) -> None:
    rows = hn.ripe_snapshot_nservers(write(tmp_path / "ripe.db.gz", SNAPSHOT), Counter())
    rows += hn.ripe_changed_nservers(write(tmp_path / "ripe.db.domain.gz", SPLIT), Counter())
    emitted = " ".join(f"{h} {p} {v}" for h, p, _, v in rows)
    for bait in ("@", "+358", "Rehtorinpellonkatu", "TURKU", "KR101", "utu.fi", "lk-kr", "LNN1"):
        assert bait not in emitted, f"reader leaked {bait!r}"


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
