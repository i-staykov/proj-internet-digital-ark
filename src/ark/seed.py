"""Load candidate domains from a seed file and queue the unknown ones.

Seeding never verifies anything: it canonicalizes, registers candidates,
and enqueues work. Verification happens in its own stage so each can be
rerun and resumed independently.
"""

import sqlite3
from pathlib import Path

import duckdb
from loguru import logger

from ark.canonical import to_registrable
from ark.db import add_candidate, ensure_source
from ark.metrics import record_metrics
from ark.work_queue import enqueue

CDX_TASK = "cdx_verify"


def seed_from_file(
    conn: duckdb.DuckDBPyConnection,
    queue_conn: sqlite3.Connection,
    path: Path,
    limit: int | None = None,
) -> dict[str, int]:
    """Canonicalize up to `limit` lines and queue domains the store has never seen."""
    source_id = ensure_source(conn, path.stem, "candidate_only")
    stats = {"lines": 0, "invalid": 0, "already_known": 0, "new_candidates": 0}
    batch: set[str] = set()
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if limit is not None and stats["lines"] >= limit:
                break
            raw = line.strip()
            if not raw:
                continue
            stats["lines"] += 1
            domain = to_registrable(raw)
            if domain is None:
                stats["invalid"] += 1
                continue
            if domain in batch:
                continue
            known = conn.execute("SELECT 1 FROM domain WHERE domain = ?", [domain]).fetchone()
            if known:
                stats["already_known"] += 1
                continue
            add_candidate(conn, domain, source_id)
            batch.add(domain)
    stats["new_candidates"] = len(batch)
    stats["enqueued"] = enqueue(queue_conn, CDX_TASK, sorted(batch))
    logger.info(f"{path.name}: {stats}")
    record_metrics(conn, "seed", path.stem, stats)
    return stats
