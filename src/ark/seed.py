"""Load candidate domains from a seed file and queue the ones still unproven.

Seeding never verifies anything: it canonicalizes, registers candidates, and
enqueues work. Verification happens in its own stage so each can be rerun and
resumed independently.

What counts as "nothing left to do" is a confirmed year, not mere presence in the
store. A domain can already be on file with no year assigned at all, which is
precisely what a candidate is: reached by a candidate-only source, or dated
outside 1996-2001, or queried and unanswered. Skipping those would leave them
permanently unqueued while `ark export` still lists them as candidates, so the
classification below distinguishes three states rather than one.
"""

import sqlite3
from pathlib import Path

import duckdb
from loguru import logger

from ark.canonical import to_registrable
from ark.db import add_candidates, ensure_source
from ark.metrics import record_metrics
from ark.work_queue import enqueue

CDX_TASK = "cdx_verify"

# One pass over the store instead of a query per line: at 600k-domain seed files
# the per-row round trips dominate, and the classification is a set operation.
_CLASSIFY_SQL = """
SELECT d.domain,
       EXISTS (SELECT 1 FROM domain_year dy WHERE dy.domain = d.domain) AS has_year,
       EXISTS (
         SELECT 1 FROM evidence e
         WHERE e.domain = d.domain AND e.evidence_type = 'prior_reused'
       ) AS in_baseline
FROM (SELECT unnest($domains) AS domain) d
WHERE EXISTS (SELECT 1 FROM domain s WHERE s.domain = d.domain)
"""


def seed_from_file(
    conn: duckdb.DuckDBPyConnection,
    queue_conn: sqlite3.Connection,
    path: Path,
    limit: int | None = None,
) -> dict[str, int]:
    """Canonicalize up to `limit` lines, register candidates, queue what is unproven."""
    source_id = ensure_source(conn, path.stem, "candidate_only")
    stats = {
        "lines": 0,
        "invalid": 0,
        # already carries a confirmed year, so there is nothing to verify
        "already_confirmed_baseline": 0,
        "already_confirmed_own_evidence": 0,
        # on file but with no confirmed year: still a candidate, still queued
        "already_candidate": 0,
        "new_candidates": 0,
    }

    seen: set[str] = set()
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
            seen.add(domain)

    if not seen:
        logger.info(f"{path.name}: {stats}")
        record_metrics(conn, "seed", path.stem, stats)
        return stats

    known = {
        domain: (has_year, in_baseline)
        for domain, has_year, in_baseline in conn.execute(
            _CLASSIFY_SQL, {"domains": sorted(seen)}
        ).fetchall()
    }

    unproven: set[str] = set()
    fresh: list[str] = []
    for domain in sorted(seen):
        state = known.get(domain)
        if state is None:
            fresh.append(domain)
            stats["new_candidates"] += 1
            unproven.add(domain)
            continue
        has_year, in_baseline = state
        if has_year:
            key = "already_confirmed_baseline" if in_baseline else "already_confirmed_own_evidence"
            stats[key] += 1
            continue
        # on file, no confirmed year: a candidate that was never queued
        stats["already_candidate"] += 1
        unproven.add(domain)

    # One statement rather than one per name. A row-at-a-time loop over 29,432
    # PANDORA names held the store's only write lock for more than twenty minutes,
    # which blocks every reader as well as every other writer.
    add_candidates(conn, fresh, source_id)
    stats["enqueued"] = enqueue(queue_conn, CDX_TASK, sorted(unproven))
    logger.info(f"{path.name}: {stats}")
    record_metrics(conn, "seed", path.stem, stats)
    return stats
