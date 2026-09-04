"""The capture-journal hostname lane, and what survives of the 2026-09-02 purpose rules.

One of the two still stands: a record needs an observation of the host serving web content,
so the DNS lanes date the parent only. The other is gone. `www.<parent>` was refused as the
parent's own site until 2026-09-04, when ADR-009 admitted it on his section XI and on a count
of his own benchmark, where 1,221,065 names have both forms in the same year file.

What replaced it is the weaker and more useful invariant: a `www.<parent>` record must point at
evidence naming that exact host, so admitting the shape never became asserting it.
"""

import gzip
import json
from pathlib import Path

import duckdb

from ark.checks import collect_checks
from ark.db import init_db
from ark.hostnames import WEB_FACING_HOST_SOURCES, ingest_hostname_journal, writes_hostname_years

CAPTURES = [
    ("http://www.example.com/", "19980301000000"),
    ("http://shop.example.com/x", "19980415120000"),
    ("http://example.com/", "19980102000000"),
    ("http://www.example.com/a", "19990101000000"),
]


def write(tmp_path: Path, rows: list[tuple[str, str]], name: str = "sweep_test.jsonl.gz") -> Path:
    path = tmp_path / name
    with gzip.open(path, "wt") as fh:
        for url, ts in rows:
            fh.write(json.dumps({"url": url, "timestamp": ts}) + "\n")
    return path


def test_www_of_the_parent_is_a_record_and_still_dates_the_registrable(tmp_path) -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    stats = ingest_hostname_journal(conn, write(tmp_path, CAPTURES))
    # three (host, year) candidates below the registrable, all three now records
    assert stats["hostname_year_candidates"] == 3
    assert stats["hostname_year_rows"] == 3
    assert sorted(conn.execute("SELECT hostname, assigned_year FROM hostname_year").fetchall()) == [
        ("shop.example.com", 1998),
        ("www.example.com", 1998),
        ("www.example.com", 1999),
    ]
    # the www captures still date example.com in both years
    assert sorted(conn.execute("SELECT assigned_year FROM domain_year").fetchall()) == [
        (1998,),
        (1999,),
    ]
    results = {r["name"]: r for r in collect_checks(conn, Path("no-such-export"))}
    assert results["a_www_record_has_its_own_evidence"]["ok"]
    assert results["hostname_observed_serving_web"]["ok"]


def test_a_forced_dns_row_and_a_www_row_without_its_own_evidence_are_both_caught() -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    conn.execute("INSERT INTO source (name, kind) VALUES ('isc_survey_hostnames', 'timestamped')")
    conn.execute("INSERT INTO domain (domain, tld, discovered_source) VALUES ('x.com', 'com', 1)")
    conn.execute(
        "INSERT INTO evidence (domain, source_id, evidence_year, evidence_type, evidence_value) "
        "VALUES ('x.com', 1, 1997, 'artifact_listing', 'isc survey 1997-01 host www.x.com')"
    )
    eid = conn.execute("SELECT evidence_id FROM evidence").fetchone()[0]
    conn.execute(
        "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) "
        "VALUES ('www.x.com', 'x.com', 1997, ?)",
        [eid],
    )
    results = {r["name"]: r for r in collect_checks(conn, Path("no-such-export"))}
    # the ISC lane is still not web-facing, so the row is refused on that ground
    assert results["hostname_observed_serving_web"]["offending"] == 1
    # and the value DOES name www.x.com, so the new invariant is satisfied: admitting the
    # shape is not the same as letting a parent's capture stand in for it
    assert results["a_www_record_has_its_own_evidence"]["offending"] == 0
    # a row whose evidence names only the parent is what that invariant is for
    conn.execute(
        "INSERT INTO evidence (domain, source_id, evidence_year, evidence_type, evidence_value) "
        "VALUES ('x.com', 1, 1998, 'artifact_listing', 'isc survey 1998-01 host x.com')"
    )
    bare = conn.execute("SELECT max(evidence_id) FROM evidence").fetchone()[0]
    conn.execute(
        "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) "
        "VALUES ('www.x.com', 'x.com', 1998, ?)",
        [bare],
    )
    results = {r["name"]: r for r in collect_checks(conn, Path("no-such-export"))}
    assert results["a_www_record_has_its_own_evidence"]["offending"] == 1


def test_dns_lanes_are_not_web_facing() -> None:
    for name in ("isc_survey_hostnames", "ripe_nserver_hostnames", "internic_zone_hostnames"):
        assert name not in WEB_FACING_HOST_SOURCES
        assert not writes_hostname_years(name)
    assert writes_hostname_years("ia_cdx_hostnames")


def test_a_journal_that_has_GROWN_is_read_again(tmp_path) -> None:
    """The sweep appends to its journal under the final name, for hours.

    Ledgering by name alone marked a live journal done at whatever length it had: on
    2026-09-04 the first pass read `suffix_co_uk_...` at 391,684 rows and the second pass
    skipped all 500 files, so every row written afterwards would never have been read. The
    `.part`-then-rename convention does not cover an append-style collector; skipping on
    content does, for every lane at once.
    """
    conn = duckdb.connect(":memory:")
    init_db(conn)
    path = write(tmp_path, CAPTURES[:2])
    first = ingest_hostname_journal(conn, path)
    assert first["skipped"] is False
    before = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]

    # unchanged: skipped
    assert ingest_hostname_journal(conn, path)["skipped"] is True

    # grown: read again, and only the new rows land, because the insert ignores duplicates
    write(tmp_path, CAPTURES)
    again = ingest_hostname_journal(conn, path)
    assert again["skipped"] is False
    after = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]
    assert after > before
    # one ledger row, updated to the new digest, with the rows of both passes summed
    ledger = conn.execute("SELECT count(*), sum(record_rows) FROM ingested_file").fetchone()
    assert ledger[0] == 1
    assert ledger[1] == first["hostname_year_rows"] + again["hostname_year_rows"]
    conn.close()
