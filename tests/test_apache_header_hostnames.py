"""Relay hosts from the `Received: ... by <host>` clause of dated Apache list messages.

Approved 2026-09-09 (C-83) for the `by` clause alone. The funnel is the body-URL family's;
what is new is the field read, the item pointer `<list domain>/<list>__<YYYY-MM>#<n>`, and
the API URL it resolves to. The builder is tested against the four `Received:` shapes that
actually occur in `httpd/dev` 1999-01, because three of them defeat a naive `by (\\S+)`.
"""

import gzip
import importlib.util
import json
from collections import Counter
from pathlib import Path

import duckdb

from ark.db import init_db
from ark.hostnames import (
    APACHE_FAMILY,
    WEB_FACING_HOST_SOURCES,
    ingest_usenet_item_journal,
    usenet_item_rows,
    writes_hostname_years,
)

ITEMS = [
    {"item": "httpd.apache.org/dev__1999-01#1", "year": 1999, "text": "taz.hyperreal.org"},
    # a later message names the same host and year; the lower item is the one quoted
    {"item": "httpd.apache.org/dev__1999-01#9", "year": 1999, "text": "taz.hyperreal.org"},
    {"item": "tomcat.apache.org/users__2001-06#3", "year": 2001, "text": "mail.ibm.com ibm.com"},
    # a mailing-list item pointer from the pipermail lane is not an Apache one
    {"item": "gnome/gtk-list__1999-May.txt#367", "year": 1999, "text": "gimp.example.org"},
    {"item": "httpd.apache.org/dev__1999-01#4", "year": 2004, "text": "later.example.org"},
]


def write(tmp_path: Path, rows: list[dict]) -> Path:
    pool = tmp_path / "apache_header_items"
    pool.mkdir(exist_ok=True)
    path = pool / "shard_000.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


def test_the_item_pointer_resolves_to_the_mbox_export_of_that_list_month(tmp_path) -> None:
    counts: Counter = Counter()
    rows = usenet_item_rows(write(tmp_path, ITEMS), counts, family=APACHE_FAMILY)
    assert [(r[0], r[2]) for r in rows] == [
        ("mail.ibm.com", 2001),
        ("taz.hyperreal.org", 1999),
    ]
    quoted = {r[0]: r[3] for r in rows}
    assert quoted["taz.hyperreal.org"] == (
        "list header 1999 httpd.apache.org/dev__1999-01#1 taz.hyperreal.org"
    )
    urls = {r[0]: r[4] for r in rows}
    assert urls["taz.hyperreal.org"] == (
        "https://lists.apache.org/api/mbox.lua?list=dev&domain=httpd.apache.org&d=1999-01"
    )
    assert urls["mail.ibm.com"] == (
        "https://lists.apache.org/api/mbox.lua?list=users&domain=tomcat.apache.org&d=2001-06"
    )
    assert counts["bad_item"] == 1
    assert counts["out_of_window"] == 1
    assert counts["registrable_row"] == 1


def test_the_lane_writes_hostname_years_and_is_the_only_non_web_one() -> None:
    """C-83 widened the wall to "in use"; the DNS lanes it did NOT widen stay out."""
    assert writes_hostname_years("apache_list_header_hostnames")
    assert "apache_list_header_hostnames" in WEB_FACING_HOST_SOURCES
    for name in ("isc_survey_hostnames", "ripe_nserver_hostnames", "internic_zone_hostnames"):
        assert not writes_hostname_years(name)


def test_ingest_lands_under_its_own_source_and_is_idempotent(tmp_path) -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    path = write(tmp_path, ITEMS)
    stats = ingest_usenet_item_journal(conn, path, family=APACHE_FAMILY)
    assert stats["hostname_year_rows"] == 2
    sources = conn.execute(
        "SELECT DISTINCT s.name FROM evidence e JOIN source s USING (source_id)"
    ).fetchall()
    assert sources == [("apache_list_header_hostnames",)]
    again = ingest_usenet_item_journal(conn, path, family=APACHE_FAMILY)
    assert again["skipped"] is True
    conn.close()


def _builder():
    spec = importlib.util.spec_from_file_location(
        "build_apache_header_pool",
        Path(__file__).resolve().parents[1]
        / "scripts/sources/mail_corpora/build_apache_header_pool.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_four_real_received_shapes() -> None:
    """All four are in `httpd/dev` 1999-01, and three defeat a naive `by (\\S+)`."""
    b = _builder()
    # qmail writes `invoked by uid 6000`, and a UUCP hop writes a bare nodename. Neither
    # token carries a dot, so requiring one is what keeps them out.
    assert b.by_hosts("Received: (qmail 21311 invoked by uid 6000); 1 Jan 1999 19:30:10") == []
    assert b.by_hosts("Received: from en by slarti with UUCP; 01 Jan 1999 19:30:26 -0000") == []
    # The expensive one: the `by` clause is on a folded continuation line.
    folded = b.unfold(
        [
            "Received: from slarti.muc.de (192.0.2.10)",
            "  by taz.hyperreal.org with SMTP; 1 Jan 1999 19:30:08 -0000",
        ]
    )
    assert b.by_hosts(folded) == ["taz.hyperreal.org"]
    # And a `by` with no `from` clause at all.
    assert b.by_hosts("Received: by en1.engelschall.com (Sendmail 8.9.1) for x@apache.org") == [
        "en1.engelschall.com"
    ]


def test_the_from_clause_and_ip_literals_are_never_read() -> None:
    """The sender chose the HELO name, so it is forgeable and outside the approval."""
    b = _builder()
    line = "Received: from blonville.caii (ecstasy.localnet [192.0.2.19]) by mx.serv.net"
    assert b.by_hosts(line) == ["mx.serv.net"]
    assert b.by_hosts("Received: by 192.0.2.19 with SMTP") == []
    # A non-Received header that happens to contain the word `by` is not a hop.
    assert b.by_hosts("Subject: patch by someone.example.org for review") == []


def test_a_message_filed_under_a_year_its_own_date_denies_is_dropped(tmp_path) -> None:
    """The partition is a free second opinion; the GNOME lane measured this at 1 in 64."""
    b = _builder()
    raw = (
        b"From MAILER-DAEMON Fri Jan  1 19:30:08 1999\n"
        b"Received: from slarti.muc.de (192.0.2.10)\n"
        b"  by taz.hyperreal.org with SMTP; 1 Jan 1999 19:30:08 -0000\n"
        b"Date: Fri, 1 Jan 1999 19:58:57 +0100\n"
        b"\n"
        b"body mentions http://www.engelschall.com/ and is never read\n"
        b"\n"
        b"From MAILER-DAEMON Sat Jan  2 09:00:00 1999\n"
        b"Received: by wrong.example.org (Sendmail)\n"
        b"Date: Wed, 01 Jan 1997 09:00:00 +0000\n"
        b"\n"
        b"a sender clock set to the wrong year\n"
    )
    folder = tmp_path / "httpd.apache.org"
    folder.mkdir()
    path = folder / "dev__1999-01.mbox.gz"
    with gzip.open(path, "wb") as fh:
        fh.write(raw)
    out: list[str] = []

    class Sink:
        def write(self, s: str) -> None:
            out.append(s)

    stats = dict.fromkeys(
        (
            "files",
            "messages",
            "in_window",
            "with_hosts",
            "no_by_host",
            "undated",
            "out_of_window",
            "year_disagrees",
            "bad_name",
        ),
        0,
    )
    b.one_file(path, Sink(), stats)
    assert stats["messages"] == 2
    assert stats["in_window"] == 1
    assert stats["year_disagrees"] == 1
    assert len(out) == 1
    assert json.loads(out[0]) == {
        "item": "httpd.apache.org/dev__1999-01#1",
        "year": 1999,
        "text": "taz.hyperreal.org",
    }


def _collector():
    spec = importlib.util.spec_from_file_location(
        "collect_apache_lists",
        Path(__file__).resolve().parents[1]
        / "scripts/sources/mail_corpora/collect_apache_lists.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_plan_round_trips_and_the_harvest_reads_what_expand_writes(tmp_path) -> None:
    """`--expand` rewrites the plan `--discover` wrote and `--harvest` reads it back.

    The three passes share one four-column TSV, so a format drift between them would show up
    as a harvest that fetches nothing rather than as an error. This pins the contract.
    """
    c = _collector()
    c.PLAN = tmp_path / "plan.tsv"
    rows = {
        ("httpd.apache.org", "dev", "1999-01"): 782,
        ("tomcat.apache.org", "users", "2001-06"): 3313,
    }
    c._write_plan(rows)
    assert sorted(c._planned_rows()) == [
        ("httpd.apache.org", "dev", "1999-01", 782),
        ("tomcat.apache.org", "users", "2001-06", 3313),
    ]


def test_the_month_form_is_the_only_one_the_collector_can_send() -> None:
    """A range is accepted and IGNORED by this API, so no code path may build one."""
    c = _collector()
    assert c.MONTHS[0] == "1996-01"
    assert c.MONTHS[-1] == "2001-12"
    assert len(c.MONTHS) == 72
    assert all(len(m) == 7 and m[4] == "-" for m in c.MONTHS)
    # robots.txt says Crawl-delay: 5, and the collector must not be quietly retuned below it.
    assert c.CRAWL_DELAY >= 5.0
