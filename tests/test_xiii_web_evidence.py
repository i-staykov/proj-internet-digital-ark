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


def test_a_non_error_capture_is_required() -> None:
    """XIII asks for a non-error web capture, so the non-200 TimeMap arm stays out."""
    assert "nypw_timemap" in WEB_METHODS
    assert "nypw_timemap_non_200" not in WEB_METHODS


def test_the_reviewers_own_baseline_is_not_our_claim() -> None:
    """`prior_task` is his merged corpus: his remediation, and never our net-new."""
    assert "prior_task" not in WEB_METHODS
    assert "prior_reused" in MASTER_TYPES


def test_the_predicate_names_the_alias_it_was_given() -> None:
    sql = web_evidence_sql("w")
    assert sql.startswith("w.acquisition_method IN (")
    assert "'ia_cdx_domain_sweep'" in sql and "'wayback_availability'" in sql
    # sorted, so the generated SQL does not churn between runs
    methods = sql.split("IN (", 1)[1].rstrip(")").split(", ")
    assert methods == sorted(methods)
