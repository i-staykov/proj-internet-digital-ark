"""IA CDX query construction, year extraction, retry/throttle behaviour.

Network is never touched: `fetch` and the governor's `sleep` are injected.
"""

from ark.cdx import (
    RateGovernor,
    answered,
    cdx_url,
    evidence_years,
    lookup_years,
    lookup_years_per_year,
    year_probe_url,
    years_in,
)


def _no_sleep(_seconds: float) -> None:
    return None


def _gov(**kw) -> RateGovernor:
    return RateGovernor(delay=0.0, min_delay=0.0, sleep=_no_sleep, **kw)


def test_cdx_url_asks_one_question_for_all_years() -> None:
    url = cdx_url("example.com", 1996, 2001)
    # subdomains included, window bounded, payload trimmed, years folded
    assert "url=%2A.example.com" in url
    assert "from=1996" in url and "to=2001" in url
    assert "fl=timestamp" in url
    assert "collapse=timestamp%3A4" in url
    assert "filter=statuscode%3A200" in url


def test_years_in_extracts_and_filters_to_the_window() -> None:
    body = "19970601120000\n19981212033831\n20030101000000\nnot-a-timestamp\n\n"
    assert years_in(body, 1996, 2001) == {1997, 1998}


def test_lookup_years_returns_every_year_found() -> None:
    body = "19970601120000\n19970602120000\n19991010101010\n"
    record = lookup_years("x.com", 1996, 2001, fetch=lambda _u: (200, body), governor=_gov())
    assert record["domain"] == "x.com"
    assert record["status"] == 200
    assert record["years"] == [1997, 1999]
    assert record["truncated"] is False


def test_lookup_years_records_a_failure_without_years() -> None:
    record = lookup_years("gone.com", 1996, 2001, fetch=lambda _u: (404, ""), governor=_gov())
    assert record["status"] == 404
    assert record["years"] == []


def test_lookup_years_retries_a_throttle_then_succeeds() -> None:
    calls = {"n": 0}

    def flaky(_url: str) -> tuple[int, str]:
        calls["n"] += 1
        return (429, "1") if calls["n"] == 1 else (200, "19980101000000\n")

    gov = _gov()
    record = lookup_years("x.com", 1996, 2001, fetch=flaky, governor=gov)
    assert record["years"] == [1998]
    assert calls["n"] == 2
    # a throttle must be recorded and must have slowed the pace
    assert gov.throttles == 1


def test_lookup_years_probes_only_the_years_a_truncated_response_missed() -> None:
    # limit=2 so two rows counts as truncated; only 1998 is present in the page
    asked = []

    def fetch(url: str) -> tuple[int, str]:
        asked.append(url)
        if "from=1996&to=2001" in url.replace("%2A", "*"):
            return 200, "19980101000000\n19980202000000\n"
        if "from=2000&to=2000" in url:
            return 200, "20000505000000\n"
        return 200, ""

    record = lookup_years("x.com", 1996, 2001, fetch=fetch, governor=_gov(), limit=2)
    assert record["truncated"] is True
    assert record["years"] == [1998, 2000]
    # the year already seen is never re-probed
    assert not any("from=1998&to=1998" in u for u in asked)


def test_truncation_probing_can_be_switched_off() -> None:
    record = lookup_years(
        "x.com",
        1996,
        2001,
        fetch=lambda _u: (200, "19980101000000\n19980202000000\n"),
        governor=_gov(),
        limit=2,
        probe_missing=False,
    )
    assert record["truncated"] is True
    assert record["years"] == [1998]


def test_governor_backs_off_on_throttle_and_eases_up_on_success() -> None:
    gov = RateGovernor(delay=1.0, min_delay=0.1, ramp_after=2, backoff_factor=2.0, sleep=_no_sleep)
    gov.on_throttle()
    assert gov.delay == 2.0  # multiplicative decrease in pace
    gov.on_success()
    assert gov.delay == 2.0  # not yet enough successes to ramp
    gov.on_success()
    assert gov.delay < 2.0  # additive-style easing once healthy


def test_governor_never_paces_below_its_floor() -> None:
    gov = RateGovernor(delay=0.1, min_delay=0.1, ramp_after=1, sleep=_no_sleep)
    for _ in range(20):
        gov.on_success()
    assert gov.delay == 0.1


def test_evidence_years_never_infers_a_year() -> None:
    # exactly the years returned, nothing adjacent, nothing out of window
    assert list(evidence_years({"years": [1996, 1999, 2005]}, 1996, 2001)) == [1996, 1999]
    assert list(evidence_years({}, 1996, 2001)) == []


def test_year_probe_url_asks_one_cheap_question() -> None:
    url = year_probe_url("example.com", 1998)
    assert "from=1998" in url and "to=1998" in url
    # limit=1 is the whole point: the server stops at the first match
    assert "limit=1" in url
    assert "collapse" not in url


def test_per_year_strategy_collects_every_year_that_answers() -> None:
    def fetch(url: str) -> tuple[int, str]:
        if "from=1997" in url:
            return 200, "19970601120000\n"
        if "from=2000" in url:
            return 200, "20000601120000\n"
        return 200, ""

    record = lookup_years_per_year("x.com", 1996, 2001, fetch=fetch, governor=_gov())
    assert record["years"] == [1997, 2000]
    assert record["status"] == 200
    assert record["strategy"] == "per_year"
    assert record["probe_failures"] == 0


def test_per_year_partial_failure_still_reports_the_years_that_answered() -> None:
    def fetch(url: str) -> tuple[int, str]:
        if "from=1998" in url:
            return 0, ""  # this year is unknown, not absent
        return 200, "19960101000000\n" if "from=1996" in url else ""

    record = lookup_years_per_year("x.com", 1996, 2001, fetch=fetch, governor=_gov())
    assert record["years"] == [1996]
    assert record["probe_failures"] == 1
    assert record["status"] == 200  # partial answers are still answers


def test_per_year_total_failure_is_not_recorded_as_nothing_archived() -> None:
    # every probe failed, so the domain must stay unanswered and be retried later
    record = lookup_years_per_year("x.com", 1996, 2001, fetch=lambda _u: (0, ""), governor=_gov())
    assert record["years"] == []
    assert record["status"] == 0
    assert answered(record) is False


def test_answered_only_accepts_a_real_reply() -> None:
    assert answered({"status": 200}) is True
    assert answered({"status": 0}) is False
    assert answered({"status": 503}) is False
