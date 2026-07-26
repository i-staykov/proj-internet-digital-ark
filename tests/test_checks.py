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


def test_detects_evidence_year_disagreeing_with_its_value() -> None:
    conn = _clean_store()
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    add_candidate(conn, "mislabelled.com", cdx)
    # the timestamp says 1997 but the row is filed under 1999
    assign_year(
        conn,
        record_evidence(conn, "mislabelled.com", cdx, 1999, "cdx_timestamp", "19970101000000"),
    )
    results = _results_by_name(conn)
    assert results["evidence_year_matches_its_value"]["ok"] is False
    assert results["evidence_year_matches_its_value"]["offending"] == 1


def test_registration_spans_are_exempt_from_the_year_match() -> None:
    conn = _clean_store()
    # AFNIC states a span, so its value names two years and neither need equal
    # the year it evidences; that is the documented mechanism, not a defect
    afnic = ensure_source(conn, "afnic_fr", "timestamped")
    add_candidate(conn, "span.fr", afnic)
    for year in (1999, 2000, 2001):
        assign_year(
            conn,
            record_evidence(
                conn, "span.fr", afnic, year, "whois_creation", "registered 16-03-1998..active"
            ),
        )
    results = _results_by_name(conn)
    assert results["evidence_year_matches_its_value"]["ok"] is True

    # the same shape from any other source is NOT exempt
    rdap = ensure_source(conn, "rdap", "timestamped")
    add_candidate(conn, "notexempt.com", rdap)
    assign_year(
        conn,
        record_evidence(conn, "notexempt.com", rdap, 2001, "whois_creation", "rdap creation 1998"),
    )
    assert _results_by_name(conn)["evidence_year_matches_its_value"]["ok"] is False


def test_detects_an_addition_that_is_also_baseline() -> None:
    conn = _clean_store()
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    prior = ensure_source(conn, "prior_task", "timestamped")
    add_candidate(conn, "both.com", cdx)
    # assigned from our own evidence, so it counts as an addition ...
    assign_year(
        conn, record_evidence(conn, "both.com", cdx, 1998, "cdx_timestamp", "19980202000000")
    )
    # ... while the baseline also had it, which would inflate net-new
    record_evidence(conn, "both.com", prior, 1998, "prior_reused", "1998.txt")
    results = _results_by_name(conn)
    assert results["additions_not_double_counted"]["ok"] is False
    assert results["additions_not_double_counted"]["offending"] == 1


def test_detects_master_evidence_left_unassigned() -> None:
    conn = _clean_store()
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    add_candidate(conn, "orphan.com", cdx)
    # evidence recorded but assign_year never called: the domain would sit in the
    # candidate pool while already holding proof of 1996
    record_evidence(conn, "orphan.com", cdx, 1996, "cdx_timestamp", "19960303000000")
    results = _results_by_name(conn)
    assert results["nothing_earned_is_left_unassigned"]["ok"] is False
    assert results["nothing_earned_is_left_unassigned"]["offending"] == 1
