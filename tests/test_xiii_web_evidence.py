"""The annual claim is website evidence: the method decides it, and an error capture never does."""

from __future__ import annotations

from ark.evidence_types import MASTER_TYPES, WEB_METHODS, web_evidence_sql


def test_the_allowlist_fails_closed() -> None:
    """A method nobody has classified must not reach an annual file."""
    assert "usenet_server_written_header" not in WEB_METHODS
    assert "published_registry_creation_dates" not in WEB_METHODS
    assert "isc_domain_survey" not in WEB_METHODS
    assert "registry_zone_list_wayback_capture" not in WEB_METHODS
    assert "a_method_invented_tomorrow" not in WEB_METHODS
    # a per-year capture count cannot show that the host answered without an error
    assert "ia_domain_year_census" not in WEB_METHODS


def test_a_redirect_is_admitted_by_its_status_and_an_error_is_not() -> None:
    """A capture enters the masters only when the exact host answered 2xx or 3xx. A 3xx is
    a server answering deliberately for that host; a 4xx or 5xx stays a candidate whatever
    its method, because a wildcard vhost answers 404 for any name pointed at it.

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
        ("nypw_timemap_hostgrain", "cdx capture 20010704120000 a.example.com", True),
        ("nypw_timemap_hostgrain", "cdx capture 20010704120000 status 404 a.example.com", False),
        ("bulk_cdx_file", "cdx capture 20010704120000 status 503 b.example.com", False),
        ("early_web_hostgrain", "cdx capture 19990101000000 status 302 c.example.com", True),
        ("ia_domain_year_census", "ia domain year census 2001 captures 12", False),
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


def test_the_three_judged_methods_stay_where_ivo_put_them() -> None:
    """Ruled 2026-09-18, after reading the 38 exclusions that can back a year.

    The other 35 are registry, zone, WHOIS, RDAP, ISC DNS, mail and Usenet, which XIII
    names by hand as candidate-only. These three needed a judgement.
    """
    # a custodian's dated per-host mirror of the page the host served
    assert "attrition_defacement_mirror_index" in WEB_METHODS
    # an exact-host IA CDX first capture, admitted so it matches its own hostgrain sibling
    assert "nypw_first_capture_index" in WEB_METHODS
    assert "nypw_firstcdx_hostgrain" in WEB_METHODS
    # a third-party textual mention, which XIII names as candidate-only however dated it is
    assert "ncsa_whats_new_pages" not in WEB_METHODS
    # registry data does not become a web capture by being captured from the web
    assert "registry_zone_list_wayback_capture" not in WEB_METHODS
    assert "registry_listing_capture" not in WEB_METHODS
