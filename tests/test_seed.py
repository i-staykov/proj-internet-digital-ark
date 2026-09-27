"""Seeding: canonicalize, dedup against store and batch, queue only the unknown."""

from pathlib import Path

import duckdb
from his_release import HIS_YEARS, stage, text

from ark import held
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.seed import seed_from_file
from ark.work_queue import connect_queue, counts


def _stores() -> tuple[duckdb.DuckDBPyConnection, object]:
    conn = connect(":memory:")
    init_db(conn)
    return conn, connect_queue(":memory:")


def test_seed_funnel(tmp_path: Path, his_files: Path) -> None:
    conn, queue_conn = _stores()
    # on file but with no confirmed year: this is a candidate, not settled work
    sid = ensure_source(conn, "wayback_cdx", "timestamped")
    add_candidate(conn, "known.com", sid)

    fixture = tmp_path / "seeds.txt"
    fixture.write_text(
        "fresh.org\nwww.fresh.org\nknown.com\n$garbage$\nother.net\n", encoding="utf-8"
    )
    stats = seed_from_file(conn, queue_conn, fixture)

    assert stats["lines"] == 5
    assert stats["invalid"] == 1
    # already on file, but unproven, so it is queued rather than dismissed
    assert stats["already_candidate"] == 1
    assert stats["already_confirmed_baseline"] == 0
    # fresh.org and its www variant collapse into one new candidate
    assert stats["new_candidates"] == 2
    assert stats["enqueued"] == 3
    assert counts(queue_conn, "cdx_verify") == {"pending": 3}
    # candidates are registered but unverified: no year rows
    assert conn.execute("SELECT count(*) FROM domain_year").fetchone()[0] == 0


def test_seed_skips_only_domains_with_a_confirmed_year(tmp_path: Path, his_files: Path) -> None:
    conn, queue_conn = _stores()
    sid = ensure_source(conn, "wayback_cdx", "timestamped")
    # one domain confirmed by collected evidence
    add_candidate(conn, "ours.com", sid)
    assign_year(
        conn, record_evidence(conn, "ours.com", sid, 1997, "cdx_timestamp", "19970101000000")
    )
    # and one his 1997 file holds, which the store need not: his file alone settles it
    stage(his_files.parent, {"1997.txt": text(sorted(HIS_YEARS[1997] + ["base.com"]))})
    held.prepare(his_files)

    fixture = tmp_path / "seeds.txt"
    fixture.write_text("base.com\nours.com\nnew.com\n", encoding="utf-8")
    stats = seed_from_file(conn, queue_conn, fixture)

    # the two confirmed ones are counted apart, and neither is re-queued
    assert stats["already_confirmed_baseline"] == 1
    assert stats["already_confirmed_own_evidence"] == 1
    assert stats["already_candidate"] == 0
    assert stats["new_candidates"] == 1
    assert stats["enqueued"] == 1


def test_his_www_form_confirms_no_bare_name(tmp_path: Path, his_files: Path) -> None:
    """His 1999 file holds www.rolled.com. The exact name rolled.com is not his, and no year of
    ours dates it, so it is queued."""
    conn, queue_conn = _stores()

    fixture = tmp_path / "seeds.txt"
    fixture.write_text("rolled.com\n", encoding="utf-8")
    stats = seed_from_file(conn, queue_conn, fixture)

    assert stats["already_confirmed_baseline"] == 0
    assert stats["new_candidates"] == 1
    assert stats["enqueued"] == 1


def test_seed_limit(tmp_path: Path, his_files: Path) -> None:
    conn, queue_conn = _stores()
    fixture = tmp_path / "seeds.txt"
    fixture.write_text("a.com\nb.com\nc.com\n", encoding="utf-8")
    stats = seed_from_file(conn, queue_conn, fixture, limit=2)
    assert stats["lines"] == 2
    assert stats["new_candidates"] == 2
