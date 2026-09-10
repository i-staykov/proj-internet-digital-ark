"""Server-written header hostnames from dated Usenet posts.

Approved master-eligible by Ivo on 2026-09-10, reopening a 2026-09-08 rejection whose
grounds were a size that turned out to be wrong. The funnel is the body-URL family's; what
is new is the three fields read and the two markers a news server appends to a `Path`
element, both of which banked fiction before they were pinned here.
"""

import gzip
import importlib.util
import json
from collections import Counter
from pathlib import Path

import duckdb

from ark.db import init_db
from ark.hostnames import (
    USENET_HEADER_FAMILY,
    WEB_FACING_HOST_SOURCES,
    ingest_usenet_item_journal,
    usenet_item_rows,
    writes_hostname_years,
)
from ark.stats import PROVENANCE_LINEAGE

ITEMS = [
    {"item": "demon.ip.support.pc.mbox.zip#7", "year": 1998, "text": "pcserv.demon.co.uk"},
    # the same host and year later in the same group; the lower item is the one quoted
    {"item": "demon.ip.support.pc.mbox.zip#91", "year": 1998, "text": "pcserv.demon.co.uk"},
    {"item": "uk.comp.misc.mbox.zip#3", "year": 2001, "text": "news.zetnet.co.uk zetnet.co.uk"},
    # an Apache item pointer is not a Usenet one
    {"item": "httpd.apache.org/dev__1999-01#1", "year": 1999, "text": "taz.hyperreal.org"},
    {"item": "uk.comp.misc.mbox.zip#8", "year": 2005, "text": "later.example.org"},
]


def write(tmp_path: Path, rows: list[dict]) -> Path:
    pool = tmp_path / "usenet_header_items"
    pool.mkdir(exist_ok=True)
    path = pool / "shard_000.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


def test_the_item_pointer_resolves_to_the_archive_that_still_serves_the_group(tmp_path) -> None:
    counts: Counter = Counter()
    rows = usenet_item_rows(write(tmp_path, ITEMS), counts, family=USENET_HEADER_FAMILY)
    assert [(r[0], r[2]) for r in rows] == [
        ("news.zetnet.co.uk", 2001),
        ("pcserv.demon.co.uk", 1998),
    ]
    quoted = {r[0]: r[3] for r in rows}
    assert quoted["pcserv.demon.co.uk"] == (
        "usenet header 1998 demon.ip.support.pc.mbox.zip#7 pcserv.demon.co.uk"
    )
    urls = {r[0]: r[4] for r in rows}
    assert (
        urls["pcserv.demon.co.uk"]
        == "https://archive.org/download/usenet-demon/demon.ip.support.pc.mbox.zip"
    )
    assert (
        urls["news.zetnet.co.uk"] == "https://archive.org/download/usenet-uk/uk.comp.misc.mbox.zip"
    )
    assert counts["bad_item"] == 1
    assert counts["out_of_window"] == 1
    # `zetnet.co.uk` is its own registrable and belongs to domain_year, not here
    assert counts["registrable_row"] == 1


def test_the_lane_writes_hostname_years_under_c83s_widened_wall() -> None:
    assert writes_hostname_years("usenet_header_fqdn_hostnames")
    assert "usenet_header_fqdn_hostnames" in WEB_FACING_HOST_SOURCES


def test_the_two_usenet_lanes_share_one_provenance_lineage() -> None:
    """They read the same spool, so filing them apart would let it corroborate itself."""
    assert PROVENANCE_LINEAGE["usenet_header_fqdn_hostnames"] == "usenet"
    assert PROVENANCE_LINEAGE["usenet_body_url_hostnames"] == "usenet"


def test_ingest_lands_under_its_own_source_and_is_idempotent(tmp_path) -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    path = write(tmp_path, ITEMS)
    stats = ingest_usenet_item_journal(conn, path, family=USENET_HEADER_FAMILY)
    assert stats["hostname_year_rows"] == 2
    sources = conn.execute(
        "SELECT DISTINCT s.name FROM evidence e JOIN source s USING (source_id)"
    ).fetchall()
    assert sources == [("usenet_header_fqdn_hostnames",)]
    again = ingest_usenet_item_journal(conn, path, family=USENET_HEADER_FAMILY)
    assert again["skipped"] is True
    conn.close()


def _builder():
    spec = importlib.util.spec_from_file_location(
        "build_usenet_header_pool",
        Path(__file__).resolve().parents[1] / "scripts/sources/usenet/build_usenet_header_pool.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _hosts(lines: list[str], keep_ephemeral: bool = False) -> list[str]:
    b = _builder()
    stats = dict.fromkeys(b.FIELDS, 0)
    return b.hosts_of_headers([line.encode() for line in lines], stats, keep_ephemeral)


def test_the_three_fields_read_and_the_one_that_is_not() -> None:
    assert _hosts(["X-Trace: mail2news.demon.co.uk 894324354 19133 faqs pcserv.demon.co.uk"]) == [
        "pcserv.demon.co.uk"
    ]
    assert _hosts(["NNTP-Posting-Host: pc-42.zetnet.co.uk"]) == ["pc-42.zetnet.co.uk"]
    # The final hop is the RIGHTMOST element that is a HOSTNAME, because Path is written
    # right to left: the rightmost site injected the article and the leftmost archived it.
    # Taking the leftmost would bank `nntp.google.com` several million times over. Bare
    # nodenames (`demon`) and the `not-for-mail` sentinel carry no dot and fall out, so the
    # rightmost hostname here is the second element and not the fourth.
    assert _hosts(["Path: nntp.google.com!news1.google.com!demon!not-for-mail"]) == [
        "news1.google.com"
    ]
    assert _hosts(["Path: nntp.google.com!feeder.news.demon.co.uk!not-for-mail"]) == [
        "feeder.news.demon.co.uk"
    ]
    # the Message-ID host is client-stamped and has no ruling, so it is never read
    assert _hosts(["Message-ID: <abc@pcserv.demon.co.uk>"]) == []


def test_a_posting_host_that_is_an_ip_dates_nothing() -> None:
    # RFC 5737 TEST-NET-1 stands in for the real dotted quad these headers carry, so the
    # fixture asserts the shape without writing down somebody's address.
    assert _hosts(["NNTP-Posting-Host: 192.0.2.1"]) == []
    assert _hosts(["NNTP-Posting-Host:"]) == []
    assert _hosts(["X-Trace: posting.google.com 1340536695 5508 127.0.0.1"]) == [
        "posting.google.com"
    ]


def test_the_markers_a_server_appends_to_a_path_element() -> None:
    """Left in, `.POSTED` banked 2,006 rows of fiction in a 35 MB test."""
    assert _hosts(["Path: aioe.org!news2-win.server.ntlworld.com.POSTED!not-for-mail"]) == [
        "news2-win.server.ntlworld.com"
    ]
    # `.MISMATCH` is the server saying the reverse DNS did NOT match, so the element goes
    assert _hosts(["Path: news.glorb.com!198.186.194.249.MISMATCH!not-for-mail"]) == [
        "news.glorb.com"
    ]


def test_a_dial_up_lease_is_not_a_host() -> None:
    b = _builder()
    for lease in (
        "1cust104.tnt8.redondo-beach.ca.da.uu.net",
        "136.pool2.fukuoka.att.ne.jp",
        "man-s286.dialup.zetnet.co.uk",
        "1-2-3-4.dialup.example.net",
        "0addba1d.news.tdin.com",
    ):
        assert b.is_ephemeral(lease), lease
    for machine in (
        "pcserv.demon.co.uk",
        "news.zetnet.co.uk",
        "dialup.example.com",
        "news1.gvcl1.bc.home.com",
        "posting.google.com",
    ):
        assert not b.is_ephemeral(machine), machine


def test_keep_ephemeral_turns_the_filter_off_for_a_measured_comparison() -> None:
    line = ["NNTP-Posting-Host: 1cust104.tnt8.redondo-beach.ca.da.uu.net"]
    assert _hosts(line) == []
    assert _hosts(line, keep_ephemeral=True) == ["1cust104.tnt8.redondo-beach.ca.da.uu.net"]
