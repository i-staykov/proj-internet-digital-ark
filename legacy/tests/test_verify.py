"""Verification: fake fetcher, real store and queue, no network."""

import duckdb

from ark.db import add_candidate, connect, ensure_source, init_db
from ark.seed import CDX_TASK
from ark.verify import verify_batch
from ark.work_queue import connect_queue, counts, enqueue


def _stores() -> tuple[duckdb.DuckDBPyConnection, object]:
    conn = connect(":memory:")
    init_db(conn)
    return conn, connect_queue(":memory:")


def _seed(conn, queue_conn, domains: list[str]) -> None:
    sid = ensure_source(conn, "test_seed", "candidate_only")
    for domain in domains:
        add_candidate(conn, domain, sid)
    enqueue(queue_conn, CDX_TASK, domains)


def test_verify_assigns_years_from_captures() -> None:
    conn, queue_conn = _stores()
    _seed(conn, queue_conn, ["old.com", "gone.com"])

    def fake_fetcher(domain: str, year: int):
        # old.com was captured in 1998 and 2001; gone.com never
        if domain == "old.com" and year in (1998, 2001):
            return f"{year}0315120000", "http://old.com/"
        return None

    stats = verify_batch(conn, queue_conn, fetcher=fake_fetcher)

    assert stats == {"claimed": 2, "with_evidence": 1, "years_assigned": 2, "failed": 0}
    rows = conn.execute(
        "SELECT domain, assigned_year FROM domain_year ORDER BY assigned_year"
    ).fetchall()
    assert rows == [("old.com", 1998), ("old.com", 2001)]
    assert counts(queue_conn, CDX_TASK) == {"done": 2}


def test_verify_failure_goes_back_to_queue() -> None:
    conn, queue_conn = _stores()
    _seed(conn, queue_conn, ["flaky.com"])

    def broken_fetcher(domain: str, year: int):
        raise ConnectionError("simulated 429")

    stats = verify_batch(conn, queue_conn, fetcher=broken_fetcher)

    assert stats["failed"] == 1
    # failed with a retry delay: pending again, but not claimable yet
    assert counts(queue_conn, CDX_TASK) == {"pending": 1}
    assert conn.execute("SELECT count(*) FROM domain_year").fetchone()[0] == 0


def test_verify_is_resumable() -> None:
    conn, queue_conn = _stores()
    _seed(conn, queue_conn, ["a.com", "b.com"])

    def fetcher(domain: str, year: int):
        return None

    verify_batch(conn, queue_conn, batch_size=1, fetcher=fetcher)
    assert counts(queue_conn, CDX_TASK) == {"done": 1, "pending": 1}
    verify_batch(conn, queue_conn, batch_size=1, fetcher=fetcher)
    assert counts(queue_conn, CDX_TASK) == {"done": 2}
