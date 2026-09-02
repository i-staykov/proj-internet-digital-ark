"""The nameservers RIPE `domain:` objects point at, at hostname grain.

Both banked RIPE lanes read the delegated name and the audit trail and skip `*ns:`.
Under the hostname unit that column is a corpus of its own (measured 2026-09-02:
38,189 records from the 1999 snapshot, 11,895 from the 2004 split edition). The
permission Ivo holds from the RIPE NCC constrains the code, so the leak tests here
mirror the ones on `parse_ripe_dbase_1999`: nothing but a nameserver hostname and a
date may leave these readers.
"""

import gzip
from collections import Counter
from pathlib import Path

import duckdb

from ark.db import init_db
from ark.hostnames import (
    RIPE_NS_SOURCE,
    ingest_ripe_nserver_hostnames,
    ripe_changed_nservers,
    ripe_snapshot_nservers,
)

SNAPSHOT = """#
# 990804 00:07:01
#
# Restricted rights.

*dn: OULU.FI
*de: Oulu University
*ac: KR101
*ns: ousrvr.oulu.fi
*ns: hydra.helsinki.fi 128.214.4.29
*ch: lk-kr@finou.oulu.fi 19910916
*so: RIPE

*dn: TuKKK.FI
*de: Rehtorinpellonkatu 3, SF-20500 TURKU, Finland
*ac: +358 21 6383105
*ac: mniemi@abo.fi
*tc: hostmaster@utu.fi
*ns: ra.abo.fi
*ns: abo.fi
*ns: under_score.abo.fi
*so: RIPE

*dn: 231.130.IN-ADDR.ARPA
*ns: ns.reverse.example.net
*so: RIPE
"""

SPLIT = """#
# Copyright (c) by RIPE NCC

domain:       200.193.193.in-addr.arpa
descr:        Splitblock
admin-c:      LNN1-RIPE
nserver:      ns.lucky.net
nserver:      ns.gu.kiev.ua
changed:      mx@lucky.net 19990716
changed:      mx@lucky.net 20010716
source:       RIPE

domain:       example.gm
nserver:      ns1.provider.no
changed:      hostmaster@provider.no 20031104
source:       RIPE

domain:       other.gm
nserver:      ns1.provider.no
nserver:      provider.no
changed:      hostmaster@provider.no 19981104
source:       RIPE
"""


def write(tmp_path: Path, text: str, name: str) -> Path:
    path = tmp_path / name
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(text)
    return path


def test_snapshot_reads_only_ns_values_dated_by_the_header(tmp_path: Path) -> None:
    counts: Counter = Counter()
    rows = ripe_snapshot_nservers(write(tmp_path, SNAPSHOT, "ripe.db.gz"), counts)
    assert [(h, p, y) for h, p, y, _ in rows] == [
        ("hydra.helsinki.fi", "helsinki.fi", 1999),
        ("ns.reverse.example.net", "example.net", 1999),
        ("ousrvr.oulu.fi", "oulu.fi", 1999),
        ("ra.abo.fi", "abo.fi", 1999),
    ]
    assert rows[0][3] == "ripe_dbase:19990804 ns hydra.helsinki.fi"
    # glue address dropped, bare registrable counted not kept, underscore refused
    assert counts["glue_or_empty"] == 1
    assert counts["registrable_row"] == 1
    assert counts["rejected_host"] == 1
    assert counts["ns_lines"] == 6


def test_snapshot_emits_no_personal_data(tmp_path: Path) -> None:
    counts: Counter = Counter()
    rows = ripe_snapshot_nservers(write(tmp_path, SNAPSHOT, "ripe.db.gz"), counts)
    emitted = " ".join(f"{h} {p} {v}" for h, p, _, v in rows)
    for forbidden in ("@", "+358", "Rehtorinpellonkatu", "TURKU", "KR101", "utu.fi", "lk-kr"):
        assert forbidden not in emitted, f"reader leaked {forbidden!r}"


def test_snapshot_without_a_stamp_or_out_of_window_writes_nothing(tmp_path: Path) -> None:
    counts: Counter = Counter()
    nostamp = "#\n# no date\n\n" + "*ns: ns.example.fi\n" * 60
    assert ripe_snapshot_nservers(write(tmp_path, nostamp, "ripe.db.gz"), counts) == []
    assert counts["no_header_stamp"] == 1
    counts = Counter()
    late = SNAPSHOT.replace("990804", "030804")
    assert ripe_snapshot_nservers(write(tmp_path, late, "ripe.db.gz"), counts) == []
    assert counts["stamp_out_of_window"] == 1


def test_split_dates_the_nserver_set_by_the_latest_changed_line(tmp_path: Path) -> None:
    counts: Counter = Counter()
    rows = ripe_changed_nservers(write(tmp_path, SPLIT, "ripe.db.domain.gz"), counts)
    assert [(h, p, y) for h, p, y, _ in rows] == [
        ("ns.gu.kiev.ua", "gu.kiev.ua", 2001),
        ("ns.lucky.net", "lucky.net", 2001),
        ("ns1.provider.no", "provider.no", 1998),
    ]
    assert rows[1][3] == "ripe_changed:20010716 nserver ns.lucky.net"
    # the object last changed in 2003 contributes nothing; its host is in window elsewhere
    assert counts["object_out_of_window"] == 1
    assert counts["objects_in_window"] == 2
    assert counts["registrable_row"] == 1
    assert "@" not in " ".join(v for *_, v in rows)


def test_ingest_writes_rows_for_both_editions_and_is_idempotent(tmp_path: Path) -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    snapshot = write(tmp_path, SNAPSHOT, "ripe.db.gz")
    split = write(tmp_path, SPLIT, "ripe.db.domain.gz")
    # An `nserver:` attribute observes a nameserver, not a site, so since 2026-09-02
    # the lane writes evidence and the parent's year but no hostname record.
    assert ingest_ripe_nserver_hostnames(conn, snapshot)["hostname_year_candidates"] == 4
    assert ingest_ripe_nserver_hostnames(conn, split)["hostname_year_candidates"] == 3
    assert conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0] == 0
    rows = conn.execute(
        """
        SELECT e.domain, e.evidence_year, e.evidence_type, e.acquisition_method, e.evidence_url
        FROM evidence e WHERE e.evidence_value LIKE '%ns.lucky.net%'
        """
    ).fetchall()
    assert rows == [
        (
            "lucky.net",
            2001,
            "artifact_listing",
            "ripe_changed_nserver",
            "https://ftp.funet.fi/pub/netinfo/RIPE/dbase/split/ripe.db.domain.gz",
        )
    ]
    # every parent earns its year from the same row, once per (parent, year)
    assert conn.execute("SELECT count(*) FROM domain_year").fetchone()[0] == 7
    assert ingest_ripe_nserver_hostnames(conn, snapshot)["skipped"] is True
    assert conn.execute("SELECT count(*) FROM evidence").fetchone()[0] == 7
    assert (
        conn.execute(
            "SELECT sum(record_rows) FROM ingested_file WHERE source_name = ?", [RIPE_NS_SOURCE]
        ).fetchone()[0]
        == 0
    )


def test_a_file_with_another_name_is_refused(tmp_path: Path) -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    stats = ingest_ripe_nserver_hostnames(conn, write(tmp_path, SNAPSHOT, "other.db.gz"))
    assert stats.get("not_a_ripe_file") == 1
