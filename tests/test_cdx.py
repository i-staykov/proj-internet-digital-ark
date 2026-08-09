"""IA CDX query construction, year extraction, retry/throttle behaviour.

Network is never touched: `fetch` and the governor's `sleep` are injected.
"""

import time

from ark.cdx import (
    REFUSED,
    TIMED_OUT,
    RateGovernor,
    _is_timeout,
    answered,
    cdx_url,
    evidence_years,
    lookup_years,
    lookup_years_by_host,
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

    record = lookup_years(
        "x.com", 1996, 2001, fetch=fetch, governor=_gov(), limit=2, host_first=False
    )
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
        host_first=False,
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


def test_a_refused_connection_slows_the_pace_down() -> None:
    """The bug this guards: a refusal that does not back off gets retried at full
    pace, and the retries are themselves connection attempts, so the run holds
    itself in the host's penalty box."""
    gov = RateGovernor(delay=1.0, min_delay=0.1, backoff_factor=2.0, sleep=_no_sleep)
    record = lookup_years("x.com", 1996, 2001, fetch=lambda _u: (REFUSED, ""), governor=gov)
    assert record["status"] == REFUSED
    assert gov.throttles > 0
    assert gov.delay > 1.0


def test_a_timeout_is_asked_once_and_does_not_slow_the_pace() -> None:
    """A timeout means the server took the question and could not finish it, which
    is no evidence about the pace. Asking again costs another full timeout and
    ends the same way, so one attempt is the whole budget."""
    scans = {"n": 0}

    def slow(url: str) -> tuple[int, str]:
        if "%2A." in url:
            scans["n"] += 1
        return TIMED_OUT, ""

    gov = RateGovernor(delay=1.0, min_delay=0.1, backoff_factor=2.0, sleep=_no_sleep)
    record = lookup_years(
        "heavy.com", 1996, 2001, fetch=slow, governor=gov, retries=4, host_first=False
    )
    assert scans["n"] == 1  # not four
    assert record["status"] == TIMED_OUT
    assert gov.throttles == 0
    assert gov.delay == 1.0


def test_a_scan_the_server_cannot_finish_falls_back_to_the_cheap_hosts() -> None:
    """Measured on `warehouse.co.uk`, which five batches had failed on: the
    wildcard scan 504s after 60 s with nothing, while apex plus www answers in
    20 s with four years."""
    asked = []

    def fetch(url: str) -> tuple[int, str]:
        asked.append(url)
        if "%2A." in url:  # the wildcard scan the server gives up on
            return 504, ""
        return 200, "19980101000000\n20000202000000\n"

    record = lookup_years(
        "warehouse.co.uk", 1996, 2001, fetch=fetch, governor=_gov(), host_first=False
    )
    assert record["status"] == 200
    assert record["years"] == [1998, 2000]
    assert record["strategy"] == "by_root"
    # the failed scan is still on the record, so the rescue is auditable
    assert record["scan_status"] == 504


def test_the_doomed_scan_is_asked_once_before_falling_back() -> None:
    scans = {"n": 0}

    def fetch(url: str) -> tuple[int, str]:
        if "%2A." in url:
            scans["n"] += 1
            return 504, ""
        return 200, "19980101000000\n"

    lookup_years("heavy.com", 1996, 2001, fetch=fetch, governor=_gov(), retries=4, host_first=False)
    # four 60-second scans that all end the same way is three minutes of a worker
    assert scans["n"] == 1


def test_the_fallback_never_replaces_a_scan_that_answered() -> None:
    # no recall is traded away: a working scan is never second-guessed
    asked = []

    def fetch(url: str) -> tuple[int, str]:
        asked.append(url)
        return 200, "19970101000000\n"

    record = lookup_years("fine.com", 1996, 2001, fetch=fetch, governor=_gov(), host_first=False)
    assert record["years"] == [1997]
    assert "strategy" not in record
    assert len(asked) == 1


def test_host_first_answers_without_ever_running_the_scan() -> None:
    """The throughput change: median 2.07 s for the host query against roughly 33 s
    for the wildcard scan, measured on domains the scan had already answered."""
    asked = []

    def fetch(url: str) -> tuple[int, str]:
        asked.append(url)
        return 200, "19970101000000\n19990505000000\n"

    record = lookup_years("cheap.com", 1996, 2001, fetch=fetch, governor=_gov())
    assert record["years"] == [1997, 1999]
    assert record["strategy"] == "by_host"
    assert len(asked) == 1
    assert "matchType=host" in asked[0]
    assert "%2A." not in asked[0]  # the wildcard was never asked


def test_an_empty_host_answer_still_falls_through_to_the_scan() -> None:
    """Empty is the one case where a subdomain-only capture could be hiding, so it
    is the one case worth paying for the scan."""
    asked = []

    def fetch(url: str) -> tuple[int, str]:
        asked.append(url)
        if "matchType=host" in url:
            return 200, ""  # nothing on the host itself
        return 200, "19980101000000\n"  # but a subdomain has a capture

    record = lookup_years("sub.com", 1996, 2001, fetch=fetch, governor=_gov())
    assert record["years"] == [1998]
    assert record.get("strategy") != "by_host"
    assert any("%2A." in u for u in asked)


def test_an_empty_host_answer_settles_the_domain_when_the_scan_cannot_help() -> None:
    def fetch(url: str) -> tuple[int, str]:
        return (200, "") if "matchType=host" in url else (504, "")

    record = lookup_years("quiet.com", 1996, 2001, fetch=fetch, governor=_gov())
    # settled, not left unanswered: leaving these unsettled is what built the clog
    assert answered(record) is True
    assert record["years"] == []
    assert record["scan_status"] == 504


def test_a_refused_host_query_does_not_buy_an_expensive_scan() -> None:
    """A refusal says the host has stopped taking connections, not that the domain
    is hard. Spending a wildcard scan on it would be the most expensive possible
    response to a problem the scan shares."""
    asked = []

    def fetch(url: str) -> tuple[int, str]:
        asked.append(url)
        return REFUSED, ""

    record = lookup_years("flaky.com", 1996, 2001, fetch=fetch, governor=_gov())
    assert answered(record) is False  # so a later batch asks again
    assert not any("%2A." in u for u in asked)


def test_a_host_too_big_for_the_server_skips_the_scan_and_asks_the_root_pages() -> None:
    """Measured 2026-08-06: `matchType=host` 504s on `warehouse.co.uk`,
    `gigabyte.com` and `bbc.co.uk` exactly as the wildcard does, because one host
    can still hold millions of rows. The wildcard is strictly more work, so trying
    it would only 504 again; the root pages are single keys and do answer."""
    asked = []

    def fetch(url: str) -> tuple[int, str]:
        asked.append(url)
        if "matchType=host" in url:
            return 504, ""
        return 200, "19980101000000\n20000202000000\n"

    record = lookup_years("warehouse.co.uk", 1996, 2001, fetch=fetch, governor=_gov())
    assert record["status"] == 200
    assert record["years"] == [1998, 2000]
    assert record["strategy"] == "by_root"
    assert record["host_status"] == 504
    # the scan is never attempted, because it cannot be cheaper than the host match
    assert not any("%2A." in u for u in asked)
    assert any("url=warehouse.co.uk&" in u for u in asked)
    assert any("url=www.warehouse.co.uk&" in u for u in asked)


def test_the_fallback_reports_failure_when_the_hosts_fail_too() -> None:
    record = lookup_years("hopeless.com", 1996, 2001, fetch=lambda _u: (504, ""), governor=_gov())
    # never recorded as "nothing archived", which would drop it from every later run
    assert answered(record) is False
    assert record["years"] == []


def test_a_host_that_answers_with_no_rows_still_settles_the_domain() -> None:
    record = lookup_years_by_host(
        "empty.com", 1996, 2001, fetch=lambda _u: (200, ""), governor=_gov()
    )
    assert record["status"] == 200
    assert record["years"] == []


def test_a_timeout_never_counts_as_nothing_archived() -> None:
    # the whole evidence wall rests on this: an unanswered question is not a "no"
    assert answered({"status": TIMED_OUT}) is False
    assert answered({"status": REFUSED}) is False


def test_the_breaker_holds_every_thread_off_after_a_run_of_refusals() -> None:
    gov = RateGovernor(
        delay=0.0, min_delay=0.0, breaker_after=3, breaker_pause=30.0, sleep=_no_sleep
    )
    before = time.monotonic()
    for _ in range(3):
        gov.on_throttle(refused=True)
    assert gov.breaker_trips == 1
    # the pause is applied to the shared next-start time, so it holds the whole
    # pool off rather than only the thread that saw the last refusal
    assert gov._next_at >= before + 30.0


def test_a_success_forgives_the_breaker_run() -> None:
    gov = RateGovernor(delay=0.0, min_delay=0.0, breaker_after=3, sleep=_no_sleep)
    gov.on_throttle(refused=True)
    gov.on_throttle(refused=True)
    gov.on_success()
    gov.on_throttle(refused=True)
    gov.on_throttle(refused=True)
    assert gov.breaker_trips == 0  # the run was broken, so no trip


def test_a_served_throttle_does_not_count_toward_the_breaker() -> None:
    # 503 means the host answered; only a refused connection means it stopped talking
    gov = RateGovernor(delay=0.0, min_delay=0.0, breaker_after=2, sleep=_no_sleep)
    for _ in range(6):
        gov.on_throttle()
    assert gov.breaker_trips == 0


def test_timeout_and_refusal_are_told_apart() -> None:
    import urllib.error

    assert _is_timeout(TimeoutError()) is True
    # urllib wraps the timeout in URLError.reason, which is the shape seen in the wild
    assert _is_timeout(urllib.error.URLError(TimeoutError())) is True
    assert _is_timeout(urllib.error.URLError(OSError(50, "Network is down"))) is False
    assert _is_timeout(ConnectionResetError()) is False


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
