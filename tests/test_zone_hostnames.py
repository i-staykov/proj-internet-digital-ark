"""The nameserver TARGETS of an InterNIC zone, at hostname grain.

`parse_internic_zone` keeps the owner of an NS record and discards the target, because
at registrable grain the target is the operator we already hold. The hostname unit the
reviewer accepted on 2026-09-01 makes the discarded column a corpus of its own: the
1997 zones name 21,498 proper hostnames and 19,211 of them were absent at 1997 from
both the store and the reviewer's own 1997 file (measured 2026-09-02, 11,860.7 EE).
"""

import gzip
from collections import Counter
from pathlib import Path

import duckdb

from ark.db import init_db
from ark.hostnames import ZONE_SOURCE_NAME, ingest_zone_hostnames, zone_ns_targets

ZONE = """ORG.\tIN\tSOA\tA.ROOT-SERVERS.NET.\thostmaster.INTERNIC.NET. (
\t\t\t\t1997041800\t;serial
\t\t\t\t10800  ;refresh every 3 hours
\t\t\t\t)
ORG.                      518400 IN  NS    A.ROOT-SERVERS.NET.
A.ROOT-SERVERS.NET.       518400     A     198.41.0.4
EXAMPLE.ORG.              172800     NS    NS1.PROVIDER.NET.
                          172800     NS    NS2.PROVIDER.NET.
OTHER.ORG.                172800     NS    OTHER.ORG.
BARE.ORG.                 172800     NS    PROVIDER.NET.
ODD.ORG.                  172800     NS    UNDER_SCORE.PROVIDER.NET.
;End of file.
"""


def write(tmp_path: Path, text: str, name: str = "org.zone.gz") -> Path:
    path = tmp_path / name
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(text)
    return path


def test_targets_are_hostnames_below_their_parent_and_continuation_lines_count(tmp_path) -> None:
    counts: Counter = Counter()
    parents = zone_ns_targets(write(tmp_path, ZONE), counts)
    assert parents == {
        "a.root-servers.net": "root-servers.net",
        "ns1.provider.net": "provider.net",
        "ns2.provider.net": "provider.net",
    }
    # a target that is its own registrable belongs to domain_year, an underscore is refused
    assert counts["registrable_row"] == 2
    assert counts["rejected_host"] == 1
    assert counts["ns_records"] == 6


def test_ingest_writes_hostname_rows_dated_by_the_serial_and_is_idempotent(tmp_path) -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    path = write(tmp_path, ZONE)
    stats = ingest_zone_hostnames(conn, path)
    assert stats["hostname_year_rows"] == 3
    rows = conn.execute(
        """
        SELECT hy.hostname, hy.parent_domain, hy.assigned_year, e.evidence_type, e.evidence_value
        FROM hostname_year hy JOIN evidence e ON e.evidence_id = hy.evidence_id
        ORDER BY hy.hostname
        """
    ).fetchall()
    assert rows[1] == (
        "ns1.provider.net",
        "provider.net",
        1997,
        "artifact_listing",
        "internic org zone serial 1997041800 NS ns1.provider.net",
    )
    # the parent earns 1997 from the same observation, once per parent
    assert conn.execute("SELECT count(*) FROM domain_year").fetchone()[0] == 2
    assert ingest_zone_hostnames(conn, path)["skipped"] is True
    assert conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0] == 3
    assert (
        conn.execute(
            "SELECT record_rows FROM ingested_file WHERE source_name = ?", [ZONE_SOURCE_NAME]
        ).fetchone()[0]
        == 3
    )


def test_a_zone_dated_outside_the_window_writes_nothing(tmp_path) -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    stats = ingest_zone_hostnames(conn, write(tmp_path, ZONE.replace("1997041800", "2002041800")))
    assert stats.get("out_of_window_file") == 1
    assert conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0] == 0
