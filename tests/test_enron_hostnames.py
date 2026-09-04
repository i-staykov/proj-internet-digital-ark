"""Hosts typed as body URLs in dated Enron messages, at hostname grain.

Admitted 2026-09-04 under the standing rule as the third member of the body-URL family. The
funnel is shared with the Usenet and mailing-list lanes; what is new is the item pointer, the
message's own path inside the CMU tarball, and the builder, which streams the tarball and cuts
each member at its first blank line rather than matching a boundary.
"""

import gzip
import importlib.util
import io
import json
import tarfile
from collections import Counter
from pathlib import Path

import duckdb

from ark.db import init_db
from ark.hostnames import (
    ENRON_ARCHIVE,
    ENRON_FAMILY,
    ingest_usenet_item_journal,
    usenet_item_rows,
)

ITEMS = [
    {"item": "maildir/blair-l/personnel___promotions/1.", "year": 2001, "text": "oasis.caiso.com"},
    # a later member names the same host and year; the lower item is the one quoted
    {"item": "maildir/blair-l/personnel___promotions/7.", "year": 2001, "text": "oasis.caiso.com"},
    {
        "item": "maildir/kaminski-v/all_documents/12.",
        "year": 2000,
        "text": "risk.enron.com enron.com",
    },
    # a Usenet item pointer is not an Enron one
    {"item": "uk.comp.sys.mbox.zip#12", "year": 1997, "text": "pages.demon.co.uk"},
    {"item": "maildir/blair-l/inbox/3.", "year": 2002, "text": "later.example.org"},
]


def write(tmp_path: Path, rows: list[dict]) -> Path:
    pool = tmp_path / "enron_items"
    pool.mkdir(exist_ok=True)
    path = pool / "shard_000.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


def test_the_item_pointer_is_the_tar_member_and_resolves_to_the_release(tmp_path) -> None:
    counts: Counter = Counter()
    rows = usenet_item_rows(write(tmp_path, ITEMS), counts, family=ENRON_FAMILY)
    assert [(r[0], r[2]) for r in rows] == [
        ("oasis.caiso.com", 2001),
        ("risk.enron.com", 2000),
    ]
    quoted = {r[0]: r[3] for r in rows}
    assert quoted["oasis.caiso.com"] == (
        "enron message 2001 maildir/blair-l/personnel___promotions/1. oasis.caiso.com"
    )
    assert {r[4] for r in rows} == {ENRON_ARCHIVE}
    assert counts["bad_item"] == 1
    assert counts["out_of_window"] == 1
    assert counts["registrable_row"] == 1


def test_ingest_lands_under_its_own_source_and_is_idempotent(tmp_path) -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    path = write(tmp_path, ITEMS)
    stats = ingest_usenet_item_journal(conn, path, family=ENRON_FAMILY)
    assert stats["hostname_year_rows"] == 2
    sources = conn.execute(
        "SELECT DISTINCT s.name FROM evidence e JOIN source s USING (source_id)"
    ).fetchall()
    assert sources == [("enron_body_url_hostnames",)]
    parents = conn.execute("SELECT domain, assigned_year FROM domain_year ORDER BY 1").fetchall()
    assert parents == [("caiso.com", 2001), ("enron.com", 2000)]
    again = ingest_usenet_item_journal(conn, path, family=ENRON_FAMILY)
    assert again["skipped"] is True
    key = conn.execute(
        "SELECT file_name FROM ingested_file WHERE source_name = 'enron_body_url_hostnames'"
    ).fetchone()[0]
    assert key == "enron_items/shard_000.jsonl.gz"
    conn.close()


def _builder():
    spec = importlib.util.spec_from_file_location(
        "build_enron_pool",
        Path(__file__).resolve().parents[1] / "scripts/sources/mail_corpora/build_enron_pool.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tarball(tmp_path: Path, members: dict[str, bytes]) -> Path:
    path = tmp_path / "enron.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        for name, raw in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            tar.addfile(info, io.BytesIO(raw))
    return path


def test_the_builder_streams_the_tarball_and_reads_bodies_only(tmp_path) -> None:
    b = _builder()
    dated = (
        b"Message-ID: <1.JavaMail.evans@thyme>\r\n"
        b"Date: Fri, 14 Sep 2001 14:05:43 -0700 (PDT)\r\n"
        b"X-Origin: Blair-L\r\n"
        b"\r\n"
        b"Filed at http://oasis.caiso.com/electric/ and see FTP://Data.Example.COM:21/x\r\n"
    )
    header_url_only = (
        b"Date: Mon, 03 Jan 2000 09:00:00 -0800 (PST)\n"
        b"X-Folder: \\John\\Sent http://in.header.example.org/\n"
        b"\n"
        b"nothing typed here\n"
    )
    late = b"Date: Tue, 05 Mar 2002 09:00:00 -0800 (PST)\n\nhttp://too.late.example.org/\n"
    undated = b"Subject: no date\n\nhttp://undated.example.org/\n"
    path = _tarball(
        tmp_path,
        {
            "maildir/blair-l/personnel___promotions/1.": dated,
            "maildir/kaminski-v/sent/2.": header_url_only,
            "maildir/blair-l/inbox/3.": late,
            "maildir/blair-l/inbox/4.": undated,
            "README": b"not a message",
        },
    )
    stats = b.build(path, tmp_path / "items")
    assert {k: stats[k] for k in ("posts", "in_window", "with_urls")} == {
        "posts": 4,
        "in_window": 2,
        "with_urls": 1,
    }
    with gzip.open(tmp_path / "items" / "shard_000.jsonl.gz", "rt") as fh:
        rows = [json.loads(line) for line in fh]
    assert rows == [
        {
            "item": "maildir/blair-l/personnel___promotions/1.",
            "year": 2001,
            "text": "oasis.caiso.com data.example.com",
        }
    ]
