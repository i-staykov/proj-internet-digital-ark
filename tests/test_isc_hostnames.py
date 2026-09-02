"""The ISC Internet Domain Survey host lists, at hostname grain.

`parse_isc_survey` collapses every `IP hostname` line to its registrable, which is why
the family read as "complete and fully held". The hostname unit the reviewer accepted
on 2026-09-01 keeps the host: the fleet's census of five 9607 files (2026-09-02) found
98.2% of them absent from both the store and his own 1996 file.
"""

import gzip
from collections import Counter
from pathlib import Path

import duckdb

from ark.db import init_db
from ark.hostnames import ISC_SOURCE_NAME, ingest_isc_hostnames, isc_survey_hosts

HOSTS = """1.0.0.2 dummy.custard.co.uk
1.125.2.7 medusa.specialist.co.uk
1.125.2.8 medusa.specialist.co.uk
1.3.3.1 specialist.co.uk
1.3.3.2 nt_box.custard.co.uk
1.3.3.3 www.demon.co.uk.
"""


def write(tmp_path: Path, text: str, name: str = "wb_nw_9607_uk.gz") -> Path:
    path = tmp_path / name
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(text)
    return path


def test_hosts_are_below_their_parent_and_odd_shapes_are_refused(tmp_path) -> None:
    counts: Counter = Counter()
    parents = isc_survey_hosts(write(tmp_path, HOSTS), counts)
    assert parents == {
        "dummy.custard.co.uk": "custard.co.uk",
        "medusa.specialist.co.uk": "specialist.co.uk",
        "www.demon.co.uk": "demon.co.uk",
    }
    assert counts["lines"] == 6
    assert counts["duplicate_line"] == 1
    assert counts["registrable_row"] == 1
    assert counts["rejected_host"] == 1


def test_ingest_dates_by_the_survey_code_and_is_idempotent(tmp_path) -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    path = write(tmp_path, HOSTS)
    stats = ingest_isc_hostnames(conn, path)
    assert stats["hostname_year_rows"] == 3
    rows = conn.execute(
        """
        SELECT hy.hostname, hy.parent_domain, hy.assigned_year, e.evidence_type,
               e.evidence_value, e.evidence_url
        FROM hostname_year hy JOIN evidence e ON e.evidence_id = hy.evidence_id
        ORDER BY hy.hostname
        """
    ).fetchall()
    assert rows[0] == (
        "dummy.custard.co.uk",
        "custard.co.uk",
        1996,
        "artifact_listing",
        "isc survey 1996-07 host dummy.custard.co.uk",
        "http://nw.com/zone/9607.hosts/uk.gz",
    )
    # each parent earns 1996 from the same observation, once
    assert conn.execute("SELECT count(*) FROM domain_year").fetchone()[0] == 3
    assert ingest_isc_hostnames(conn, path)["skipped"] is True
    assert conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0] == 3
    assert (
        conn.execute(
            "SELECT record_rows FROM ingested_file WHERE source_name = ?", [ISC_SOURCE_NAME]
        ).fetchone()[0]
        == 3
    )


def test_domains_lists_and_out_of_window_surveys_write_nothing(tmp_path) -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    assert ingest_isc_hostnames(conn, write(tmp_path, HOSTS, "wb_nw_9607.domains.gz")).get(
        "not_a_host_file"
    )
    assert ingest_isc_hostnames(conn, write(tmp_path, HOSTS, "wb_nw_9507_uk.gz")).get(
        "out_of_window_file"
    )
    assert conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0] == 0
