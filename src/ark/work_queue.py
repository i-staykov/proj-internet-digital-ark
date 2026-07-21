"""SQLite-backed work queue: the crawler's crash-safe journal.

Every fetch task is a row moving through pending -> in_flight -> done/failed.
Each transition is committed immediately, so a restart resumes exactly where
the previous run stopped. Retry policy lives with the caller, not here.
"""

import sqlite3
from collections.abc import Iterable
from pathlib import Path

DEFAULT_QUEUE_PATH = Path("data/queue.sqlite")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fetch_state (
    task_type     TEXT NOT NULL,
    key           TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'in_flight', 'done', 'failed')),
    attempts      INTEGER NOT NULL DEFAULT 0,
    http_status   INTEGER,
    next_retry_at TEXT,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (task_type, key)
);
CREATE INDEX IF NOT EXISTS idx_fetch_state_ready
    ON fetch_state (task_type, status, next_retry_at);
"""


def connect_queue(path: Path | str = DEFAULT_QUEUE_PATH) -> sqlite3.Connection:
    """Open the queue database in WAL mode, creating folder and schema if needed."""
    path = Path(path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    # autocommit mode: each statement is its own durable transaction
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    # with WAL (write-ahead logging) this syncs at checkpoints instead of every commit
    # queue rows are cheap to redo, so the power-loss window is an acceptable trade
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(_SCHEMA)
    return conn


def enqueue(conn: sqlite3.Connection, task_type: str, keys: Iterable[str]) -> int:
    """Add work items; existing keys are left untouched. Returns rows added."""
    cur = conn.executemany(
        "INSERT OR IGNORE INTO fetch_state (task_type, key) VALUES (?, ?)",
        ((task_type, key) for key in keys),
    )
    return cur.rowcount


def claim(conn: sqlite3.Connection, task_type: str, limit: int = 100) -> list[str]:
    """Atomically move up to `limit` ready items to in_flight and return their keys."""
    rows = conn.execute(
        """
        UPDATE fetch_state
        SET status = 'in_flight', attempts = attempts + 1, updated_at = datetime('now')
        WHERE (task_type, key) IN (
            SELECT task_type, key FROM fetch_state
            WHERE task_type = ? AND status = 'pending'
              AND (next_retry_at IS NULL OR next_retry_at <= datetime('now'))
            LIMIT ?
        )
        RETURNING key
        """,
        (task_type, limit),
    ).fetchall()
    return [row["key"] for row in rows]


def mark_done(conn: sqlite3.Connection, task_type: str, key: str) -> None:
    conn.execute(
        "UPDATE fetch_state SET status = 'done', updated_at = datetime('now') "
        "WHERE task_type = ? AND key = ?",
        (task_type, key),
    )


def mark_failed(
    conn: sqlite3.Connection,
    task_type: str,
    key: str,
    http_status: int | None = None,
    retry_after_s: float | None = None,
) -> None:
    """Record a failure. With a retry delay the item returns to pending; without one it is final."""
    if retry_after_s is None:
        conn.execute(
            "UPDATE fetch_state SET status = 'failed', http_status = ?, "
            "updated_at = datetime('now') WHERE task_type = ? AND key = ?",
            (http_status, task_type, key),
        )
    else:
        conn.execute(
            "UPDATE fetch_state SET status = 'pending', http_status = ?, "
            "next_retry_at = datetime('now', ? || ' seconds'), "
            "updated_at = datetime('now') WHERE task_type = ? AND key = ?",
            (http_status, f"+{retry_after_s}", task_type, key),
        )


def reset_in_flight(conn: sqlite3.Connection) -> int:
    """Return crash leftovers to pending. Run once at startup. Returns rows reset."""
    cur = conn.execute(
        "UPDATE fetch_state SET status = 'pending', updated_at = datetime('now') "
        "WHERE status = 'in_flight'"
    )
    return cur.rowcount


def counts(conn: sqlite3.Connection, task_type: str) -> dict[str, int]:
    rows = conn.execute(
        "SELECT status, count(*) AS n FROM fetch_state WHERE task_type = ? GROUP BY status",
        (task_type,),
    ).fetchall()
    return {row["status"]: row["n"] for row in rows}
