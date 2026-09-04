"""Hosts typed as body URLs in dated mailing-list messages, at hostname grain.

Admitted 2026-09-04 under the standing rule as the mailing-list twin of the Usenet lane. The
funnel is shared; what is new is the item pointer, `<host>/<list>__<YYYY-Month>.txt#<n>`, and
the archive URL it resolves to, which differs per host: gnome serves gzipped month files and
python serves them plain. The builder's message boundary is tested against the three sender
forms pipermail writes and against a body sentence that begins `From `.
"""

import gzip
import importlib.util
import json
from collections import Counter
from pathlib import Path

import duckdb

from ark.db import init_db
from ark.hostnames import (
    MAILLIST_FAMILY,
    ingest_usenet_item_journal,
    usenet_item_rows,
)

ITEMS = [
    {"item": "gnome/gtk-list__1999-May.txt#367", "year": 1999, "text": "gimp.cs.stevens-tech.edu"},
    # a later message names the same host and year; the lower item is the one quoted
    {"item": "gnome/gtk-list__1999-May.txt#400", "year": 1999, "text": "gimp.cs.stevens-tech.edu"},
    {"item": "python/doc-sig__2001-June.txt#7", "year": 2001, "text": "happydoc.sf.net sf.net"},
    # a Usenet item pointer is not a mailing-list one
    {"item": "uk.comp.sys.mbox.zip#12", "year": 1997, "text": "pages.demon.co.uk"},
    {"item": "gnome/gtk-list__2004-May.txt#1", "year": 2004, "text": "later.example.org"},
]


def write(tmp_path: Path, rows: list[dict]) -> Path:
    pool = tmp_path / "maillists_items"
    pool.mkdir(exist_ok=True)
    path = pool / "shard_000.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


def test_the_item_pointer_resolves_to_the_archive_host_that_serves_it(tmp_path) -> None:
    counts: Counter = Counter()
    rows = usenet_item_rows(write(tmp_path, ITEMS), counts, family=MAILLIST_FAMILY)
    assert [(r[0], r[2]) for r in rows] == [
        ("gimp.cs.stevens-tech.edu", 1999),
        ("happydoc.sf.net", 2001),
    ]
    quoted = {r[0]: r[3] for r in rows}
    assert quoted["gimp.cs.stevens-tech.edu"] == (
        "list message 1999 gnome/gtk-list__1999-May.txt#367 gimp.cs.stevens-tech.edu"
    )
    urls = {r[0]: r[4] for r in rows}
    assert urls["gimp.cs.stevens-tech.edu"] == (
        "https://mail.gnome.org/archives/gtk-list/1999-May.txt.gz"
    )
    assert urls["happydoc.sf.net"] == "https://mail.python.org/pipermail/doc-sig/2001-June.txt"
    assert counts["bad_item"] == 1
    assert counts["out_of_window"] == 1
    assert counts["registrable_row"] == 1


def test_ingest_lands_under_its_own_source_and_is_idempotent(tmp_path) -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    path = write(tmp_path, ITEMS)
    stats = ingest_usenet_item_journal(conn, path, family=MAILLIST_FAMILY)
    assert stats["hostname_year_rows"] == 2
    sources = conn.execute(
        "SELECT DISTINCT s.name FROM evidence e JOIN source s USING (source_id)"
    ).fetchall()
    assert sources == [("maillist_body_url_hostnames",)]
    parents = conn.execute("SELECT domain, assigned_year FROM domain_year ORDER BY 1").fetchall()
    assert parents == [("sf.net", 2001), ("stevens-tech.edu", 1999)]
    again = ingest_usenet_item_journal(conn, path, family=MAILLIST_FAMILY)
    assert again["skipped"] is True
    key = conn.execute(
        "SELECT file_name FROM ingested_file WHERE source_name = 'maillist_body_url_hostnames'"
    ).fetchone()[0]
    assert key == "maillists_items/shard_000.jsonl.gz"
    conn.close()


def _builder():
    spec = importlib.util.spec_from_file_location(
        "build_maillist_pool",
        Path(__file__).resolve().parents[1] / "scripts/sources/mail_corpora/build_maillist_pool.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_boundary_takes_every_pipermail_sender_form_and_no_body_sentence() -> None:
    b = _builder()
    for line in (
        b"From samsaga2@menta.net Sun Dec 17 07:39:42 2000",
        b"From skip at pobox.com  Fri Jun  1 17:26:35 2001",
        b"From Samuele Pedroni <pedroni@inf.ethz.ch>  Fri Jun  1 13:49:11 2001",
        b"From skip@pobox.com (Skip Montanaro)  Mon Jun  4 22:03:58 2001",
    ):
        assert b.BOUNDARY.match(line), line
    for line in (
        b"From RFC 2396:",
        b"From now on please do all bugfixes in gnome-1-4-branch, all cool",
        b">From skip at pobox.com  Fri Jun  1 17:26:35 2001",
    ):
        assert not b.BOUNDARY.match(line), line


def test_header_urls_stay_out_and_the_item_stem_ignores_gzip(tmp_path) -> None:
    b = _builder()
    raw = (
        b"From skip at pobox.com  Fri Jun  1 17:26:35 2001\n"
        b"Date: Fri, 01 Jun 2001 17:26:35 -0500\n"
        b"List-Subscribe: <http://lists.sourceforge.net/mailman/listinfo/x>\n"
        b"\n"
        b"See http://happydoc.sf.net/ for the tool.\n"
        b"From there it is easy.\n"
        b"\n"
        b"From Name <a@b.org>  Sat Jun  2 09:00:00 2001\n"
        b"Date: Sat, 02 Jun 2001 09:00:00 +0000\n"
        b"\n"
        b"no url here\n"
    )
    folder = tmp_path / "python"
    folder.mkdir()
    path = folder / "doc-sig__2001-June.txt.gz"
    with gzip.open(path, "wb") as fh:
        fh.write(raw)
    out: list[str] = []

    class Sink:
        def write(self, s: str) -> None:
            out.append(s)

    stats = {"posts": 0, "in_window": 0, "with_urls": 0, "files": 0, "bytes": 0}
    b.one_file(path, Sink(), stats)
    assert stats == {"posts": 2, "in_window": 2, "with_urls": 1, "files": 1, "bytes": 0}
    row = json.loads(out[0])
    assert row == {
        "item": "python/doc-sig__2001-June.txt#1",
        "year": 2001,
        "text": "happydoc.sf.net",
    }
