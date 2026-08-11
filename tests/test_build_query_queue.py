"""The queue builder's round-window query.

Loaded by path, like the other script tests: `scripts/` is not a package.

This exists because the query was once written `TIMESTAMPTZ ?`, which DuckDB's
parser rejects, and nothing ran it until a queue was needed. The builder is the
only consumer, so a parse error there disables `just query-queue` and
`just query-queue-preview` together and leaves the shards on disk as the newest
ones anybody can have.
"""

import importlib.util
from pathlib import Path

import duckdb

from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence

_SPEC = importlib.util.spec_from_file_location(
    "build_query_queue",
    Path(__file__).resolve().parents[1] / "scripts" / "build_query_queue.py",
)
build_query_queue = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(build_query_queue)


def _store() -> duckdb.DuckDBPyConnection:
    """One baseline pair and two net-new pairs, stamped either side of a window."""
    conn = connect(":memory:")
    init_db(conn)
    prior = ensure_source(conn, "prior_task", "timestamped")
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")

    add_candidate(conn, "base.com", prior)
    assign_year(conn, record_evidence(conn, "base.com", prior, 1997, "prior_reused", "1997.txt"))
    add_candidate(conn, "early.net", cdx)
    assign_year(
        conn, record_evidence(conn, "early.net", cdx, 1998, "cdx_timestamp", "19980101000000")
    )
    add_candidate(conn, "inside.uk", cdx)
    assign_year(
        conn, record_evidence(conn, "inside.uk", cdx, 1999, "cdx_timestamp", "19990101000000")
    )

    # Stamped rather than left on now(), so the assertions do not move with the
    # wall clock.
    stamps = {
        "base.com": "2026-08-10 09:00:00+00",
        "early.net": "2026-08-01 09:00:00+00",
        "inside.uk": "2026-08-10 09:00:00+00",
    }
    for domain, stamp in stamps.items():
        conn.execute(
            "UPDATE domain_year SET verified_at = CAST(? AS TIMESTAMPTZ) WHERE domain = ?",
            [stamp, domain],
        )
    return conn


def test_round_window_query_parses_and_runs() -> None:
    """A bound parameter for the window, which is what the parser refused."""
    rows = build_query_queue.round_netnew_by_tld(_store(), "2026-08-05 00:00:00+00")
    assert dict(rows) == {"uk": 1}


def test_baseline_pairs_are_excluded_and_the_window_is_honoured() -> None:
    conn = _store()
    # widened past every stamp: the baseline pair still does not count, because
    # the round measures what the reviewer has not already credited
    assert dict(build_query_queue.round_netnew_by_tld(conn, "2026-07-01 00:00:00+00")) == {
        "net": 1,
        "uk": 1,
    }
    # a window ahead of every stamp counts nothing at all
    assert build_query_queue.round_netnew_by_tld(conn, "2026-09-01 00:00:00+00") == []
