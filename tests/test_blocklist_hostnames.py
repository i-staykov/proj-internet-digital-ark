"""The hosts two banked blocklists name, kept at hostname grain.

`parse_squidguard_blacklist` and `parse_chastity_split` collapse `x.tripod.com/y` to
`tripod.com`. The hostname unit the reviewer accepted on 2026-09-01 keeps the host:
7,653 (hostname, 2001) records absent from both the store and his own 2001 file,
3,410.4 EE, measured 2026-09-02 on the live store. Same bytes, same stamps.
"""

import io
import tarfile
from collections import Counter
from pathlib import Path

import duckdb

from ark.db import init_db
from ark.hostnames import (
    CHASTITY_HOST_SOURCE,
    SQUIDGUARD_HOST_SOURCE,
    _list_hosts,
    ingest_blocklist_hostnames,
)

SQUIDGUARD = """# This list was compiled in 0:00:20 on 2001.12.18 15:04:29.
# by squidGuardRobot-2.3.4
members.tripod.com
tripod.com
10.1.2.3
under_score.tripod.com
pages.example.org/deep/path
"""
DEC_14_2001 = 1008288000


def chastity_tarball(tmp_path: Path, mtime: int = DEC_14_2001) -> Path:
    path = tmp_path / "chastity-list_0.5.orig.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        for name, text in {
            "chastity-list-0.5/db/adult/domains": "a.tripod.com\nb.novel.com\n",
            "chastity-list-0.5/db/adult/urls": "c.tripod.com/x\n",
            "chastity-list-0.5/db/adult/domains.20011124.diff": "+d.tripod.com\n-e.tripod.com\n",
            "chastity-list-0.5/db/mail/domains": "f.tripod.com\n",
        }.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size, info.mtime = len(data), mtime
            tar.addfile(info, io.BytesIO(data))
    return path


def test_list_hosts_keeps_sub_hosts_only() -> None:
    counts: Counter = Counter()
    hosts = _list_hosts(SQUIDGUARD, is_diff=False, counts=counts)
    assert hosts == {"members.tripod.com": "tripod.com", "pages.example.org": "example.org"}
    assert counts["registrable_row"] == 1
    assert counts["ip_or_empty"] == 1
    assert counts["rejected_host"] == 1
    # a diff keeps additions and drops removals
    assert _list_hosts("+x.tripod.com\n-y.tripod.com\n", True, counts) == {
        "x.tripod.com": "tripod.com"
    }


def test_squidguard_rows_are_dated_by_the_compile_stamp_and_idempotent(tmp_path) -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    path = tmp_path / "squidguard-adult-domains"
    path.write_text(SQUIDGUARD)
    stats = ingest_blocklist_hostnames(conn, path)
    assert stats["hostname_year_rows"] == 2
    assert stats["parent_year_rows"] == 2
    row = conn.execute(
        """
        SELECT hy.parent_domain, hy.assigned_year, e.evidence_type, e.evidence_value
        FROM hostname_year hy JOIN evidence e ON e.evidence_id = hy.evidence_id
        WHERE hy.hostname = 'members.tripod.com'
        """
    ).fetchone()
    assert row == (
        "tripod.com",
        2001,
        "artifact_listing",
        "squidguard:adult/domains@20011218 host members.tripod.com",
    )
    assert ingest_blocklist_hostnames(conn, path)["skipped"] is True
    assert conn.execute(
        "SELECT record_rows FROM ingested_file WHERE source_name = ?", [SQUIDGUARD_HOST_SOURCE]
    ).fetchone() == (2,)


def test_chastity_reads_the_tar_member_header_and_takes_the_split(tmp_path) -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    squid = tmp_path / "squidguard-adult-domains"
    squid.write_text(SQUIDGUARD)
    ingest_blocklist_hostnames(conn, squid)  # tripod.com now carries 2001
    stats = ingest_blocklist_hostnames(conn, chastity_tarball(tmp_path))
    # a, c and d under the corroborated tripod.com; b.novel.com parked; mail skipped
    assert stats["hostname_year_rows"] == 3
    assert stats["split_parked"] == 1
    assert stats["mail_list_skipped"] == 1
    value = conn.execute(
        "SELECT e.evidence_type, e.evidence_value FROM hostname_year hy "
        "JOIN evidence e ON e.evidence_id = hy.evidence_id WHERE hy.hostname = 'd.tripod.com'"
    ).fetchone()
    assert value == ("dated_directory", "chastity-list:20011214 adult/domains host d.tripod.com")
    assert conn.execute("SELECT count(*) FROM domain WHERE domain = 'novel.com'").fetchone() == (0,)
    assert conn.execute(
        "SELECT count(*) FROM ingested_file WHERE source_name = ?", [CHASTITY_HOST_SOURCE]
    ).fetchone() == (1,)


def test_a_member_stamped_outside_the_window_writes_nothing(tmp_path) -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    stats = ingest_blocklist_hostnames(conn, chastity_tarball(tmp_path, mtime=1033171200))
    assert stats["out_of_window_member"] == 3  # the mail list is skipped first
    assert stats["hostname_year_rows"] == 0
