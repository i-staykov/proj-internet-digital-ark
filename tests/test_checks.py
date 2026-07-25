"""Integrity checks: a clean store passes; a planted violation is caught."""

import duckdb

from ark.checks import collect_checks
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence


def _clean_store() -> duckdb.DuckDBPyConnection:
    conn = connect(":memory:")
    init_db(conn)
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    art = ensure_source(conn, "isc_survey", "timestamped")
    add_candidate(conn, "example.com", cdx)
    assign_year(
        conn, record_evidence(conn, "example.com", cdx, 1998, "cdx_timestamp", "19980101000000")
    )
    add_candidate(conn, "sub.co.uk", art)
    assign_year(conn, record_evidence(conn, "sub.co.uk", art, 2000, "artifact_listing", "isc-2000"))
    return conn


def _results_by_name(conn: duckdb.DuckDBPyConnection) -> dict[str, dict]:
    return {r["name"]: r for r in collect_checks(conn)}


def test_clean_store_passes_all_checks() -> None:
    results = collect_checks(_clean_store())
    assert results, "expected at least one check"
    assert all(r["ok"] for r in results), [r["name"] for r in results if not r["ok"]]


def test_detects_candidate_backed_assignment() -> None:
    conn = _clean_store()
    # a candidate-only (link_target) evidence row, then a domain_year that
    # references it directly, bypassing assign_year's guard
    add_candidate(conn, "leak.net", ensure_source(conn, "ukwa_link", "candidate_only"))
    link = ensure_source(conn, "ukwa_link", "candidate_only")
    ev = record_evidence(conn, "leak.net", link, 1999, "link_target", "graph-row")
    conn.execute(
        "INSERT INTO domain_year (domain, assigned_year, evidence_id) VALUES (?, ?, ?)",
        ["leak.net", 1999, ev],
    )
    results = _results_by_name(conn)
    assert results["no_candidate_leakage"]["ok"] is False
    assert results["no_candidate_leakage"]["offending"] == 1
    # and the pair has no master-eligible evidence either
    assert results["every_pair_has_master_evidence"]["ok"] is False
