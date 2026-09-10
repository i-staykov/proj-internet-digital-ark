"""Relay hosts from the `Received: ... by <host>` clause of dated IETF list messages.

C-83's class at a second host, so the field, the wall and the parser are all the Apache
lane's and are tested there. What is new and tested here is the item pointer, which carries
the month file's own name because this archive spells the same month `1996-03` in the early
years and `1999-05.mail` from 1998 on, and the MMDF boundary, without which the concluded
working groups read as zero messages rather than as an error.
"""

import gzip
import importlib.util
import json
from collections import Counter
from pathlib import Path

import duckdb

from ark.db import init_db
from ark.hostnames import (
    IETF_FAMILY,
    WEB_FACING_HOST_SOURCES,
    ingest_usenet_item_journal,
    usenet_item_rows,
    writes_hostname_years,
)

ITEMS = [
    {
        "item": "www.ietf.org/concluded-wg-ietf-mail-archive/snmpv2/1996-10#1",
        "year": 1996,
        "text": "cnri.reston.va.us",
    },
    # a later message names the same host and year; the lower item is the one quoted
    {
        "item": "www.ietf.org/concluded-wg-ietf-mail-archive/snmpv2/1996-10#7",
        "year": 1996,
        "text": "cnri.reston.va.us",
    },
    {
        "item": "www.ietf.org/ietf-mail-archive/sieve/1997-03.mail#3",
        "year": 1997,
        "text": "mail.example.org example.org",
    },
    # an Apache item pointer is not an IETF one, whatever else it carries
    {"item": "httpd.apache.org/dev__1999-01#1", "year": 1999, "text": "taz.hyperreal.org"},
    {
        "item": "www.ietf.org/concluded-wg-ietf-mail-archive/snmpv2/1996-10#4",
        "year": 2004,
        "text": "later.example.org",
    },
]


def write(tmp_path: Path, rows: list[dict]) -> Path:
    pool = tmp_path / "ietf_header_items"
    pool.mkdir(exist_ok=True)
    path = pool / "shard_000.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


def test_the_item_pointer_keeps_the_file_name_and_resolves_to_it(tmp_path) -> None:
    """Both spellings and both trees, because a guessed suffix is a 404 for half the corpus."""
    counts: Counter = Counter()
    rows = usenet_item_rows(write(tmp_path, ITEMS), counts, family=IETF_FAMILY)
    assert [(r[0], r[2]) for r in rows] == [
        ("cnri.reston.va.us", 1996),
        ("mail.example.org", 1997),
    ]
    quoted = {r[0]: r[3] for r in rows}
    assert quoted["cnri.reston.va.us"] == (
        "list header 1996 "
        "www.ietf.org/concluded-wg-ietf-mail-archive/snmpv2/1996-10#1 cnri.reston.va.us"
    )
    urls = {r[0]: r[4] for r in rows}
    assert urls["cnri.reston.va.us"] == (
        "https://www.ietf.org/ietf-ftp/concluded-wg-ietf-mail-archive/snmpv2/1996-10"
    )
    assert urls["mail.example.org"] == (
        "https://www.ietf.org/ietf-ftp/ietf-mail-archive/sieve/1997-03.mail"
    )
    assert counts["bad_item"] == 1
    assert counts["out_of_window"] == 1
    assert counts["registrable_row"] == 1


def test_the_lane_writes_hostname_years_under_the_same_widening() -> None:
    assert writes_hostname_years("ietf_list_header_hostnames")
    assert "ietf_list_header_hostnames" in WEB_FACING_HOST_SOURCES


def test_ingest_lands_under_its_own_source_and_is_idempotent(tmp_path) -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    path = write(tmp_path, ITEMS)
    stats = ingest_usenet_item_journal(conn, path, family=IETF_FAMILY)
    assert stats["hostname_year_rows"] == 2
    sources = conn.execute(
        "SELECT DISTINCT s.name FROM evidence e JOIN source s USING (source_id)"
    ).fetchall()
    assert sources == [("ietf_list_header_hostnames",)]
    again = ingest_usenet_item_journal(conn, path, family=IETF_FAMILY)
    assert again["skipped"] is True
    conn.close()


def _collector():
    spec = importlib.util.spec_from_file_location(
        "collect_ietf_mail_archive",
        Path(__file__).resolve().parents[1]
        / "scripts/sources/mail_corpora/collect_ietf_mail_archive.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MMDF = "\x01\x01\x01\x01"


def test_an_mmdf_month_reads_as_messages_and_not_as_silence() -> None:
    """`822ext/1996-08` holds 52 messages and the mbox boundary alone returns 0 of them.

    There is no `From ` line anywhere in an MMDF file, so nothing errors: the parser simply
    never opens a header block. That is 89 MB of the partition read as empty, and it is the
    boundary defect `docs/lore/traps.md` already paid for once.
    """
    c = _collector()
    lines = [
        MMDF,
        "Received: from relay.example.net (192.0.2.4)",
        "  by cnri.reston.va.us with SMTP; 2 Oct 1996 12:08 EDT",
        "Date: Wed, 2 Oct 1996 11:05:48 -0400",
        "",
        "the body is never read",
        MMDF,
        MMDF,
        "Received: by second.example.org (Sendmail)",
        "Date: Thu, 3 Oct 1996 09:00:00 -0400",
        "",
        "another message",
        MMDF,
    ]
    stats = c.new_stats()
    stem = "www.ietf.org/concluded-wg-ietf-mail-archive/822ext/1996-10"
    rows = list(c.rows_of(iter(lines), stem, 1996, stats))
    assert stats["messages"] == 2
    assert [r["text"] for r in rows] == ["cnri.reston.va.us", "second.example.org"]
    assert rows[0]["item"] == stem + "#1"
    assert rows[1]["item"] == stem + "#2"


def test_an_mbox_month_still_reads_through_the_apache_boundary() -> None:
    c = _collector()
    lines = [
        "From MAILER-DAEMON Wed Oct  2 12:08:00 1996",
        "Received: from relay.example.net (192.0.2.4)",
        "  by cnri.reston.va.us with SMTP; 2 Oct 1996 12:08 EDT",
        "Date: Wed, 2 Oct 1996 11:05:48 -0400",
        "",
        "body text mentioning From nothing in particular",
    ]
    stats = c.new_stats()
    stem = "www.ietf.org/ietf-mail-archive/sieve/1997-03.mail"
    rows = list(c.rows_of(iter(lines), stem, 1996, stats))
    assert [r["text"] for r in rows] == ["cnri.reston.va.us"]
    assert stats["with_hosts"] == 1


def test_a_message_filed_under_a_year_its_own_date_denies_is_dropped() -> None:
    """The partition is a free second opinion, and it dropped 5.5% of the fleet's sample."""
    c = _collector()
    lines = [
        MMDF,
        "Received: by wrong.example.org (Sendmail)",
        "Date: Wed, 01 Jan 1997 09:00:00 +0000",
        "",
        "a sender clock set to the wrong year",
        MMDF,
    ]
    stats = c.new_stats()
    stem = "www.ietf.org/concluded-wg-ietf-mail-archive/snmpv2/1996-10"
    assert list(c.rows_of(iter(lines), stem, 1996, stats)) == []
    assert stats["year_disagrees"] == 1
    assert stats["in_window"] == 0


def test_a_rounded_listing_size_is_read_as_bytes_and_not_as_its_first_digits() -> None:
    """`40K` parsed by a leading `\\d+` is 40, and the plan then ranks the corpus backwards."""
    c = _collector()
    assert c.sized("3034") == 3034
    assert c.sized("40K") == 40 * 1024
    assert c.sized("1.2M") == int(1.2 * 1024**2)
    row = '<a href="1997-01.mail">1997-01.mail</a>       02-Sep-2009 20:30     40K'
    assert c.FILE_ROW.findall(row) == [("1997-01.mail", "40K")]


def test_only_in_window_month_files_are_planned() -> None:
    """The archive runs to the present day; the plan may only name 1996 to 2001."""
    c = _collector()
    assert c.MONTH_FILE.match("1996-03")
    assert c.MONTH_FILE.match("1999-05.mail")
    assert c.MONTH_FILE.match("2001-12.mail")
    for outside in ("1995-12", "2002-01.mail", "2017-06.mail", "index.html", "1999-13"):
        assert not c.MONTH_FILE.match(outside), outside


def test_the_measured_crawl_delay_is_not_quietly_retuned() -> None:
    """Six parallel listings drew a 429 inside a minute; one connection with a pause did not."""
    c = _collector()
    assert c.CRAWL_DELAY >= 0.75
    assert c.USER_AGENT.startswith("ark-research/")
