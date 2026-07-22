"""Scoreboard queries: net-new pairs and domains vs the baseline."""

import duckdb

from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.stats import collect_stats, format_stats


def _populated_db() -> duckdb.DuckDBPyConnection:
    conn = connect(":memory:")
    init_db(conn)
    prior = ensure_source(conn, "prior_task", "timestamped")
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")

    # baseline-only domain
    add_candidate(conn, "base.com", prior)
    assign_year(conn, record_evidence(conn, "base.com", prior, 1997, "prior_reused", "1997.txt"))
    # genuinely net-new domain
    add_candidate(conn, "new.com", cdx)
    assign_year(
        conn, record_evidence(conn, "new.com", cdx, 1998, "cdx_timestamp", "19980101000000")
    )
    # baseline domain gaining a new year: net-new pair, not a net-new domain
    add_candidate(conn, "mixed.com", prior)
    assign_year(conn, record_evidence(conn, "mixed.com", prior, 1996, "prior_reused", "1996.txt"))
    assign_year(
        conn, record_evidence(conn, "mixed.com", cdx, 1999, "cdx_timestamp", "19990101000000")
    )
    # unverified candidate
    add_candidate(conn, "cand.org", cdx)
    return conn


def test_collect_stats_counts() -> None:
    stats = collect_stats(_populated_db())
    assert stats["netnew_domains"] == 1
    assert stats["netnew_pairs_total"] == 2
    assert stats["netnew_pairs_by_year"] == {1998: 1, 1999: 1}
    assert stats["baseline_domains"] == 2
    assert stats["total_domains"] == 4
    assert stats["total_pairs"] == 4
    assert stats["candidate_pool"] == 1


def test_format_stats_renders() -> None:
    out = format_stats(collect_stats(_populated_db()))
    assert "net-new domains" in out
    assert "1998: 1" in out
