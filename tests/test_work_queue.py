"""Work queue lifecycle: enqueue, claim, done/failed, retry gating, crash recovery."""

from ark.work_queue import (
    claim,
    connect_queue,
    counts,
    enqueue,
    mark_done,
    mark_failed,
    reset_in_flight,
)

TASK = "cdx_verify"


def _queue():
    return connect_queue(":memory:")


def test_enqueue_is_idempotent() -> None:
    conn = _queue()
    assert enqueue(conn, TASK, ["a.com", "b.com"]) == 2
    assert enqueue(conn, TASK, ["a.com", "c.com"]) == 1
    assert counts(conn, TASK) == {"pending": 3}


def test_claim_then_done_lifecycle() -> None:
    conn = _queue()
    enqueue(conn, TASK, ["a.com", "b.com"])
    claimed = claim(conn, TASK, limit=1)
    assert len(claimed) == 1
    assert counts(conn, TASK) == {"pending": 1, "in_flight": 1}
    mark_done(conn, TASK, claimed[0])
    assert counts(conn, TASK) == {"pending": 1, "done": 1}
    # a finished key cannot be re-enqueued back to pending
    enqueue(conn, TASK, claimed)
    assert counts(conn, TASK) == {"pending": 1, "done": 1}


def test_failed_with_retry_waits_for_its_retry_time() -> None:
    conn = _queue()
    enqueue(conn, TASK, ["a.com"])
    (key,) = claim(conn, TASK)
    mark_failed(conn, TASK, key, http_status=429, retry_after_s=3600)
    # pending again, but not ready until the hour passed
    assert counts(conn, TASK) == {"pending": 1}
    assert claim(conn, TASK) == []


def test_failed_without_retry_is_final() -> None:
    conn = _queue()
    enqueue(conn, TASK, ["a.com"])
    (key,) = claim(conn, TASK)
    mark_failed(conn, TASK, key, http_status=404)
    assert counts(conn, TASK) == {"failed": 1}
    assert claim(conn, TASK) == []


def test_reset_in_flight_recovers_crash_leftovers() -> None:
    conn = _queue()
    enqueue(conn, TASK, ["a.com", "b.com"])
    claim(conn, TASK)
    assert reset_in_flight(conn) == 2
    assert counts(conn, TASK) == {"pending": 2}
    # attempts survive the reset, so retry counting still works
    (key,) = claim(conn, TASK, limit=1)
    row = conn.execute(
        "SELECT attempts FROM fetch_state WHERE task_type = ? AND key = ?", (TASK, key)
    ).fetchone()
    assert row["attempts"] == 2
