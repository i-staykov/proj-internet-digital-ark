"""The annual claim is website evidence: the method decides it, an error capture never does, and
a record's row captures exactly the name it dates."""

from __future__ import annotations

import duckdb
import pytest

from ark.evidence_types import (
    MASTER_TYPES,
    WEB_METHODS,
    qualifies_sql,
    web_evidence_exists,
    web_evidence_sql,
)

WAYBACK = "https://web.archive.org/web"
MIRROR = "https://github.com/attrition-org/web-hack-mirror/blob/main/mirror"
T1, T2 = "19990412235959", "20010704120000"
SITE = "http://example.com/"


def wayback(stamp: str, original: str) -> str:
    return f"{WAYBACK}/{stamp}/{original}"


def mirror(host: str) -> str:
    return f"{MIRROR}/1999/05/01/{host}/"


def _evidence(rows: list[tuple[str | None, ...]]) -> duckdb.DuckDBPyConnection:
    """An `evidence` table with the columns the screen reads, one row per
    `(domain, acquisition_method, evidence_value, evidence_url)`."""
    conn = duckdb.connect()
    conn.execute(
        "CREATE TABLE evidence (evidence_id INTEGER, domain VARCHAR, "
        "acquisition_method VARCHAR, evidence_value VARCHAR, evidence_url VARCHAR)"
    )
    conn.executemany(
        "INSERT INTO evidence VALUES (?, ?, ?, ?, ?)",
        [(n, *row) for n, row in enumerate(rows, start=1)],
    )
    return conn


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
    `regexp_extract` and a `SIMILAR TO`, and only the engine can say those are right.
    """
    rows = [
        ("nypw_timemap_non_200", "nypw timemap capture status 301 19990412235959", True),
        ("nypw_timemap_non_200", "nypw timemap capture status 302 20010704120000", True),
        ("nypw_timemap_non_200", "nypw timemap capture status 206 20010704120000", True),
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
    conn = _evidence([("example.com", method, value, None) for method, value, _ in rows])
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
    """His release is his, never our net-new: the store holds no row of his, so neither his
    source nor his type can date a year, and the schema refuses his type outright."""
    assert "prior_task" not in WEB_METHODS
    assert "prior_reused" not in MASTER_TYPES


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


# One row per value format a web method writes, each dating `example.com`: naming exactly that
# name passes, naming another host fails, and naming none fails.
FORMATS = [
    # a capture names its host last, with the status of a non-200 before it
    ("ia_cdx_domain_sweep", f"cdx capture {T1} example.com", None, True),
    ("ia_cdx_domain_sweep", f"cdx capture {T1} www.example.com", None, False),
    ("early_web_hostgrain", f"cdx capture {T1} status 302 example.com", None, True),
    ("nypw_timemap_hostgrain", f"cdx capture {T1} status 404 example.com", None, False),
    # a link graph names its target last; its source form names none
    ("ukwa_host_link_graph", "host_link_graph:1999 example.com", None, True),
    ("ukwa_host_link_graph", "host_link_graph:1999 other.com", None, False),
    ("ukwa_host_link_graph", "host_link_graph:1999", None, False),
    # a bare stamp takes its URL's host, without case, port, user or trailing dot, and only
    # when the URL carries the same stamp
    ("bulk_cdx_file", T1, wayback(T1, "http://Example.COM:80/"), True),
    ("arquivo_cdxj", T1, f"https://arquivo.pt/wayback/{T1}/http://u@example.com./x", True),
    ("bl_geoindex_extract", T1, wayback(T1, "http://www.example.com/"), False),
    ("bulk_cdx_file", T1, wayback(T2, SITE), False),
    ("bulk_cdx_file", T1, None, False),
    # a TimeMap stamp the same way, a 3xx admitted and a 4xx refused
    ("nypw_first_capture_index", f"nypw first capture {T1}", wayback(T1, SITE), True),
    ("nypw_timemap", f"nypw timemap capture {T1}", wayback(T1, "http://other.com/"), False),
    ("nypw_timemap_non_200", f"nypw timemap capture status 301 {T1}", wayback(T1, SITE), True),
    ("nypw_timemap_non_200", f"nypw timemap capture status 404 {T1}", wayback(T1, SITE), False),
    # a defacement mirror names its host in its path
    ("attrition_defacement_mirror_index", "attrition", mirror("example.com"), True),
    ("attrition_defacement_mirror_index", "attrition", mirror("www.example.com"), False),
    # a year alone names no host, whatever web method wrote it
    ("ia_cdx_collapsed_query", "cdx capture 1999", None, False),
    ("bulk_cdx_file", "cdx capture 2001", None, False),
    # a format nobody taught the screen fails closed, even beside a URL naming the host
    ("wayback_availability", "available 19990101", wayback(T1, SITE), False),
    # the exact host is not enough under a method that is not web
    ("internic_zone_ns_target", f"cdx capture {T1} example.com", None, False),
]


def test_a_record_ships_only_on_a_capture_of_exactly_its_own_name() -> None:
    """A capture of `www.` or of any other host beneath a name dates that host, not the name.
    Driven through DuckDB, and never unknown: every row is true or false, so `NOT (...)` in a
    caller keeps every row that fails."""
    conn = _evidence([("example.com", *row[:3]) for row in FORMATS])
    got = conn.execute(
        f"SELECT {qualifies_sql('e', 'e.domain')} FROM evidence e ORDER BY evidence_id"
    ).fetchall()
    for (passes,), row in zip(got, FORMATS, strict=True):
        assert passes is row[3], row


def test_a_row_without_a_method_is_refused_and_not_lost() -> None:
    """The method column is nullable. The screen's answer for such a row is false, not
    unknown, so a caller asking which rows fail sees it."""
    conn = _evidence([("example.com", None, "cdx capture 19990601120000 example.com", None)])
    failing = f"SELECT count(*) FROM evidence e WHERE NOT {qualifies_sql('e', 'e.domain')}"
    assert conn.execute(failing).fetchone()[0] == 1


def test_the_claims_screen_names_the_record_it_tests() -> None:
    """`web_evidence_exists` needs the record's own name, so no caller can forget it."""
    with pytest.raises(TypeError):
        web_evidence_exists("dy.evidence_id")  # type: ignore[call-arg]
    conn = _evidence(
        [
            ("example.com", "ia_cdx_domain_sweep", "cdx capture 19990601120000 example.com", None),
            ("www.com", "ia_cdx_domain_sweep", "cdx capture 19990601120000 www.www.com", None),
        ]
    )
    conn.execute("CREATE TABLE dy AS SELECT evidence_id, domain FROM evidence")
    shipped = conn.execute(
        f"SELECT domain FROM dy WHERE {web_evidence_exists('dy.evidence_id', 'dy.domain')}"
    ).fetchall()
    assert shipped == [("example.com",)]
