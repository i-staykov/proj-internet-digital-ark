"""ADR-013: the annual claim is website evidence, and the method decides it."""

from __future__ import annotations

from ark.evidence_types import MASTER_TYPES, WEB_METHODS, web_evidence_sql


def test_the_allowlist_fails_closed() -> None:
    """A method nobody has classified must not reach an annual file."""
    assert "usenet_server_written_header" not in WEB_METHODS
    assert "published_registry_creation_dates" not in WEB_METHODS
    assert "isc_domain_survey" not in WEB_METHODS
    assert "registry_zone_list_wayback_capture" not in WEB_METHODS
    assert "a_method_invented_tomorrow" not in WEB_METHODS


def test_a_redirect_is_admitted_by_its_status_and_an_error_is_not() -> None:
    """Ivo's ruling, 2026-09-18. XIII's "non-error" qualifies the custodian-extract
    pattern, not the IA CDX pattern, and a TimeMap row is the IA index read through
    Memento. So a 3xx, a server answering deliberately for the exact host, is web
    presence; a 4xx or 5xx stays a candidate, because a wildcard vhost answers 404 for
    any name pointed at it.

    Driven through DuckDB rather than asserted on the string: the whole rule lives in a
    `regexp_extract` and a `LIKE`, and only the engine can say those are right.
    """
    import duckdb

    conn = duckdb.connect()
    conn.execute("CREATE TABLE evidence (acquisition_method VARCHAR, evidence_value VARCHAR)")
    rows = [
        ("nypw_timemap_non_200", "nypw timemap capture status 301 19990412235959", True),
        ("nypw_timemap_non_200", "nypw timemap capture status 302 20010704120000", True),
        ("nypw_timemap_non_200", "nypw timemap capture status 404 20010704120000", False),
        ("nypw_timemap_non_200", "nypw timemap capture status 500 20010704120000", False),
        ("nypw_timemap", "nypw timemap capture 20010704120000", True),
        ("isc_domain_survey", "nypw timemap capture status 301 20010704120000", False),
    ]
    for method, value, _ in rows:
        conn.execute("INSERT INTO evidence VALUES (?, ?)", [method, value])
    passed = {
        value
        for (value,) in conn.execute(
            f"SELECT evidence_value FROM evidence e WHERE {web_evidence_sql('e')}"
        ).fetchall()
    }
    for _, value, should_pass in rows:
        assert (value in passed) is should_pass, value
    # admitted by the predicate, deliberately NOT by the name allowlist
    assert "nypw_timemap_non_200" not in WEB_METHODS
    assert "nypw_timemap" in WEB_METHODS


def test_the_reviewers_own_baseline_is_not_our_claim() -> None:
    """`prior_task` is his merged corpus: his remediation, and never our net-new."""
    assert "prior_task" not in WEB_METHODS
    assert "prior_reused" in MASTER_TYPES


def test_the_predicate_names_the_alias_it_was_given() -> None:
    sql = web_evidence_sql("w")
    assert sql.startswith("(w.acquisition_method IN (")
    assert "'ia_cdx_domain_sweep'" in sql and "'wayback_availability'" in sql
    # one bracketed whole, so a caller may AND it into any query without parenthesising
    assert sql.endswith(")") and sql.count("(") == sql.count(")")
    # sorted, so the generated SQL does not churn between runs
    methods = sql.split("IN (", 1)[1].split(")", 1)[0].split(", ")
    assert methods == sorted(methods)
