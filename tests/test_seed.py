"""Seeding: canonicalize, dedup against store and batch, queue only the unknown."""

from pathlib import Path

import duckdb

from ark.db import add_candidate, connect, ensure_source, init_db
from ark.seed import seed_from_file
from ark.work_queue import connect_queue, counts


def _stores() -> tuple[duckdb.DuckDBPyConnection, object]:
    conn = connect(":memory:")
    init_db(conn)
    return conn, connect_queue(":memory:")


def test_seed_funnel(tmp_path: Path) -> None:
    conn, queue_conn = _stores()
    # known.com is already in the store, like a baseline domain
    sid = ensure_source(conn, "prior_task", "timestamped")
    add_candidate(conn, "known.com", sid)

    fixture = tmp_path / "seeds.txt"
    fixture.write_text(
        "fresh.org\nwww.fresh.org\nknown.com\n$garbage$\nother.net\n", encoding="utf-8"
    )
    stats = seed_from_file(conn, queue_conn, fixture)

    assert stats["lines"] == 5
    assert stats["invalid"] == 1
    assert stats["already_known"] == 1
    # fresh.org and its www variant collapse into one new candidate
    assert stats["new_candidates"] == 2
    assert stats["enqueued"] == 2
    assert counts(queue_conn, "cdx_verify") == {"pending": 2}
    # candidates are registered but unverified: no year rows
    assert conn.execute("SELECT count(*) FROM domain_year").fetchone()[0] == 0


def test_seed_limit(tmp_path: Path) -> None:
    conn, queue_conn = _stores()
    fixture = tmp_path / "seeds.txt"
    fixture.write_text("a.com\nb.com\nc.com\n", encoding="utf-8")
    stats = seed_from_file(conn, queue_conn, fixture, limit=2)
    assert stats["lines"] == 2
    assert stats["new_candidates"] == 2
