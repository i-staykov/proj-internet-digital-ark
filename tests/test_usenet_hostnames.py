"""Hosts typed as body URLs in dated Usenet posts, at hostname grain.

Approved master 2026-09-04 after thirteen pools were read whole. The two things that can
go wrong here are both extraction failures that already happened once on this corpus: a
host taken from a header rather than the body (14.02% of one pool's hosts, `Organization:`
alone 12.65%), and a post boundary the reader does not recognise, which appends one post's
headers to the previous post's body. Both are upstream of these journals, so what this
tests is the funnel: the item pointer, the window, the registrable rule and idempotence.
"""

import gzip
import json
from collections import Counter
from pathlib import Path

import duckdb

from ark.db import init_db
from ark.hostnames import (
    USENET_SOURCE,
    ingest_usenet_item_journal,
    usenet_item_rows,
)

ITEMS = [
    # two hosts in one post, both below their parent
    {"item": "uk.comp.sys.mbox.zip#12", "year": 1997, "text": "www.demon.co.uk pages.demon.co.uk"},
    # a later item names the same host and year; the lower item is the one quoted
    {"item": "uk.comp.sys.mbox.zip#99", "year": 1997, "text": "www.demon.co.uk"},
    # its own registrable, so it belongs to domain_year and not here
    {"item": "uk.comp.sys.mbox.zip#13", "year": 1997, "text": "demon.co.uk"},
    # outside 1996-2001
    {"item": "uk.comp.sys.mbox.zip#14", "year": 2004, "text": "www.later.co.uk"},
    # an underscore is not an RFC 1123 hostname
    {"item": "uk.comp.sys.mbox.zip#15", "year": 1998, "text": "nt_box.custard.co.uk"},
    # a pool holding another hierarchy's groups: the archive identifier follows the group
    {"item": "microsoft.public.mbox.zip#7", "year": 1999, "text": "support.microsoft.com"},
    # not an item pointer at all
    {"item": "somewhere", "year": 1999, "text": "www.nowhere.com"},
]


def write(tmp_path: Path, rows: list[dict], name: str = "shard_000.jsonl.gz") -> Path:
    pool = tmp_path / "usenet_uk_items"
    pool.mkdir(exist_ok=True)
    path = pool / name
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


def test_the_funnel_keeps_sub_registrable_hosts_and_quotes_the_lowest_item(tmp_path) -> None:
    counts: Counter = Counter()
    rows = usenet_item_rows(write(tmp_path, ITEMS), counts)
    assert [(r[0], r[2]) for r in rows] == [
        ("pages.demon.co.uk", 1997),
        ("support.microsoft.com", 1999),
        ("www.demon.co.uk", 1997),
    ]
    quoted = {r[0]: r[3] for r in rows}
    # #12 sorts below #99 as a string, and the choice has to be deterministic or the
    # evidence changes every time the same shard is re-read
    assert quoted["www.demon.co.uk"] == ("usenet post 1997 uk.comp.sys.mbox.zip#12 www.demon.co.uk")
    urls = {r[0]: r[4] for r in rows}
    # the identifier comes from the group's first label, not from the pool directory: the
    # `usenet_new` and `usenet_bulk` pools hold twelve hierarchies between them, and all
    # 24 identifiers this derives were probed against archive.org/metadata on 2026-09-04
    assert urls["support.microsoft.com"] == (
        "https://archive.org/download/usenet-microsoft/microsoft.public.mbox.zip"
    )
    assert urls["www.demon.co.uk"] == (
        "https://archive.org/download/usenet-uk/uk.comp.sys.mbox.zip"
    )
    assert counts["out_of_window"] == 1
    assert counts["bad_item"] == 1
    assert counts["registrable_row"] == 1
    assert counts["rejected_host"] == 1


def test_ingest_writes_the_parent_year_too_and_is_idempotent(tmp_path) -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    path = write(tmp_path, ITEMS)
    stats = ingest_usenet_item_journal(conn, path)
    assert stats["hostname_year_candidates"] == 3
    # `www.demon.co.uk` is `www.<parent registrable>`, which the ingest refuses for every
    # lane (C-55) and `hostname_is_not_the_parent_www` enforces. Section XI of his
    # 2026-09-04 brief permits it; that is #101 and it is a backfill, since the evidence
    # row below is written whether the hostname record is or not.
    assert stats["hostname_year_rows"] == 2
    held = conn.execute("SELECT hostname FROM hostname_year ORDER BY hostname").fetchall()
    assert held == [("pages.demon.co.uk",), ("support.microsoft.com",)]
    assert (
        conn.execute(
            "SELECT count(*) FROM evidence WHERE evidence_value LIKE '%www.demon.co.uk'"
        ).fetchone()[0]
        == 1
    )
    # A post naming `pages.demon.co.uk` names demon.co.uk in the same breath, and
    # `nothing_earned_is_left_unassigned` requires the parent's year to exist for every
    # master-eligible evidence row.
    parents = conn.execute(
        "SELECT DISTINCT domain, assigned_year FROM domain_year ORDER BY domain"
    ).fetchall()
    assert parents == [("demon.co.uk", 1997), ("microsoft.com", 1999)]
    rows = conn.execute(
        "SELECT evidence_type, evidence_value FROM evidence WHERE domain = 'microsoft.com'"
    ).fetchall()
    assert rows == [
        ("link_source", "usenet post 1999 microsoft.public.mbox.zip#7 support.microsoft.com")
    ]

    # The pool is part of the idempotence key, because every pool names its first shard
    # `shard_000.jsonl.gz` and a bare filename would mark twelve of the thirteen as done.
    again = ingest_usenet_item_journal(conn, path)
    assert again["skipped"] is True
    assert conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0] == 2
    key = conn.execute(
        "SELECT file_name FROM ingested_file WHERE source_name = ?", [USENET_SOURCE]
    ).fetchone()[0]
    assert key == "usenet_uk_items/shard_000.jsonl.gz"
    conn.close()


def test_the_host_regex_is_his_structural_rule() -> None:
    """His words: "dot-separated labels, use letters, digits, and interior hyphens only, and
    end in an alphabetic TLD label."

    The last clause was missing until 2026-09-04 and cost nothing measurable, because
    `to_registrable` consults the public suffix list and a sweep of all 929,964 shipped lines
    found zero violations. It is asserted here because "no violations today" and "cannot
    violate" are different properties, and a new source only meets the second one.
    """
    from ark.hostnames import _VALID_HOST

    for host in ("www.demon.co.uk", "pages.demon.co.uk", "x.y-z.com", "a.b", "x.in-addr.arpa"):
        assert _VALID_HOST.match(host), host
    for host in (
        "foo.123",  # a numeric last label is not an alphabetic TLD
        "1.2.3.4",  # nor is an address
        "nt_box.custard.co.uk",  # underscores are not RFC 1123
        "localhost",  # no dot, so no labels to separate
        "-bad.com",
        "bad-.com",  # hyphens are interior only
        "foo..com",  # an empty label
    ):
        assert not _VALID_HOST.match(host), host
