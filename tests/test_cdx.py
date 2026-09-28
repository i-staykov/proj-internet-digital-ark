"""IA CDX queries, year and host extraction, and the retry and throttle pace, offline: `fetch` and
the governor's `sleep` are injected."""

import time
import urllib.error
import urllib.request

from ark.cdx import (
    REFUSED,
    TIMED_OUT,
    RateGovernor,
    _http_get,
    _is_timeout,
    answered,
    cdx_url,
    evidence_years,
    host_url,
    hosts_in,
    lookup_years,
    lookup_years_by_host,
    lookup_years_by_root,
    lookup_years_per_year,
    root_url,
    year_probe_url,
    years_in,
)

ONLY_2XX_3XX = "filter=statuscode%3A%5B23%5D%5B0-9%5D%5B0-9%5D"


def gov(delay: float = 0.0, min_delay: float = 0.0, sleep=None, **kw) -> RateGovernor:
    """A governor that never really sleeps; pass `sleep` to record what it would."""
    return RateGovernor(delay=delay, min_delay=min_delay, sleep=sleep or (lambda _s: None), **kw)


def asking(answer, asked: list | None = None):
    """A fake `fetch` that logs each URL into `asked` and returns `answer(url)`."""

    def fetch(url: str) -> tuple[int, str]:
        if asked is not None:
            asked.append(url)
        return answer(url)

    return fetch


def test_every_query_asks_one_bounded_question_for_captures_the_host_answered() -> None:
    url = cdx_url("example.com", 1996, 2001)
    # subdomains included, window bounded, years folded
    assert "url=%2A.example.com" in url
    assert "from=1996" in url and "to=2001" in url
    assert "collapse=timestamp%3A4" in url
    probe = year_probe_url("example.com", 1998)
    assert "from=1998" in probe and "to=1998" in probe
    # limit=1 is the whole point: the server stops at the first match
    assert "limit=1" in probe
    assert "collapse" not in probe
    # every shape keeps the host the archive named, and never an error capture
    for built in (
        url,
        host_url("foo.com", 1996, 2001),
        root_url("www.foo.com", 1996, 2001),
        year_probe_url("foo.com", 1998),
    ):
        assert "fl=timestamp%2Coriginal" in built, built
        assert ONLY_2XX_3XX in built, built


def test_years_in_extracts_and_filters_to_the_window() -> None:
    body = "19970601120000\n19981212033831\n20030101000000\nnot-a-timestamp\n\n"
    assert years_in(body, 1996, 2001) == {1997, 1998}


def test_hosts_in_keeps_the_earliest_in_window_stamp_per_host() -> None:
    body = (
        "19980101000000 http://www.foo.com/\n"
        "19980102000000 http://www.foo.com/deeper/page.html\n"
        "19990202000000 http://shop.foo.com:80/x\n"
        "20040101000000 http://late.foo.com/\n"
        "19970101000000 not-a-url\n"
        "rubbish\n"
    )
    # the window enforced, a port and a path stripped
    assert hosts_in(body, 1996, 2001) == {
        "www.foo.com": "19980101000000",
        "shop.foo.com": "19990202000000",
    }
    # a `timestamp`-only response yields nothing rather than misparsing
    assert hosts_in("19980101000000\n19990101000000\n", 1996, 2001) == {}


def test_lookup_years_returns_every_year_found_and_a_failure_without_years() -> None:
    body = "19970601120000\n19970602120000\n19991010101010\n"
    record = lookup_years("x.com", 1996, 2001, fetch=lambda _u: (200, body), governor=gov())
    assert (record["domain"], record["status"]) == ("x.com", 200)
    assert record["years"] == [1997, 1999]
    assert record["truncated"] is False
    record = lookup_years("gone.com", 1996, 2001, fetch=lambda _u: (404, ""), governor=gov())
    assert (record["status"], record["years"]) == (404, [])


def test_a_throttle_sleeps_out_its_retry_after_then_succeeds(monkeypatch) -> None:
    calls, slept = [], []

    def flaky(_url: str) -> tuple[int, str]:
        calls.append(1)
        return (429, "1") if len(calls) == 1 else (200, "19980101000000\n")

    governor = gov(sleep=slept.append)
    record = lookup_years("x.com", 1996, 2001, fetch=flaky, governor=governor)
    assert record["years"] == [1998]
    assert len(calls) == 2
    assert governor.throttles == 1
    assert len(slept) == 1 and 0.5 < slept[0] <= 1.0, slept

    # the transport hands the server's Retry-After up as the body of a throttle
    def throttled(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 429, "slow", {"Retry-After": "7"}, None)

    monkeypatch.setattr(urllib.request, "urlopen", throttled)
    assert _http_get("https://example.invalid/cdx") == (429, "7")


def test_a_truncated_response_probes_only_the_years_it_missed_unless_switched_off() -> None:
    # limit=2 so two rows counts as truncated; only 1998 is present in the page
    asked = []

    def answer(url: str) -> tuple[int, str]:
        if "from=1996&to=2001" in url.replace("%2A", "*"):
            return 200, "19980101000000\n19980202000000\n"
        return (200, "20000505000000\n") if "from=2000&to=2000" in url else (200, "")

    common = {"governor": gov(), "limit": 2, "host_first": False}
    record = lookup_years("x.com", 1996, 2001, fetch=asking(answer, asked), **common)
    assert record["truncated"] is True
    assert record["years"] == [1998, 2000]
    # the year already seen is never re-probed
    assert not any("from=1998&to=1998" in u for u in asked)
    record = lookup_years("x.com", 1996, 2001, fetch=answer, probe_missing=False, **common)
    assert (record["truncated"], record["years"]) == (True, [1998])


def test_the_governor_backs_off_eases_up_and_never_paces_below_its_floor() -> None:
    governor = gov(delay=1.0, min_delay=0.1, ramp_after=2, backoff_factor=2.0)
    governor.on_throttle()
    assert governor.delay == 2.0  # multiplicative decrease in pace
    governor.on_success()
    assert governor.delay == 2.0  # not yet enough successes to ramp
    governor.on_success()
    assert governor.delay < 2.0  # additive-style easing once healthy
    floor = gov(delay=0.1, min_delay=0.1, ramp_after=1)
    for _ in range(20):
        floor.on_success()
    assert floor.delay == 0.1


def test_the_breaker_trips_only_on_an_unbroken_run_of_refusals() -> None:
    governor = gov(breaker_after=3, breaker_pause=30.0)
    before = time.monotonic()
    for _ in range(3):
        governor.on_throttle(refused=True)
    assert governor.breaker_trips == 1
    # the pause is on the shared next-start time, so it holds the whole pool off
    assert governor._next_at >= before + 30.0
    forgiven = gov(breaker_after=3)
    forgiven.on_throttle(refused=True)
    forgiven.on_throttle(refused=True)
    forgiven.on_success()
    forgiven.on_throttle(refused=True)
    forgiven.on_throttle(refused=True)
    assert forgiven.breaker_trips == 0  # a success broke the run
    # 503 means the host answered; only a refused connection means it stopped talking
    served = gov(breaker_after=2)
    for _ in range(6):
        served.on_throttle()
    assert served.breaker_trips == 0


def test_a_refused_connection_slows_the_pace_down() -> None:
    """A refusal is retried slower, because a retry at full pace is itself another refusal."""
    governor = gov(delay=1.0, min_delay=0.1, backoff_factor=2.0)
    record = lookup_years("x.com", 1996, 2001, fetch=lambda _u: (REFUSED, ""), governor=governor)
    assert record["status"] == REFUSED
    assert governor.throttles > 0
    assert governor.delay > 1.0


def test_a_timeout_is_asked_once_and_does_not_slow_the_pace() -> None:
    """A timeout is the server failing a heavy question, no evidence about the pace."""
    asked = []
    governor = gov(delay=1.0, min_delay=0.1, backoff_factor=2.0)
    fetch = asking(lambda _u: (TIMED_OUT, ""), asked)
    record = lookup_years("heavy.com", 1996, 2001, fetch, governor, retries=4, host_first=False)
    assert len([u for u in asked if "%2A." in u]) == 1  # not four
    assert record["status"] == TIMED_OUT
    assert (governor.throttles, governor.delay) == (0, 1.0)


def test_a_scan_the_server_cannot_finish_is_asked_once_then_falls_back_to_the_roots() -> None:
    asked = []
    fetch = asking(
        lambda u: (504, "") if "%2A." in u else (200, "19980101000000\n20000202000000\n"), asked
    )
    record = lookup_years("warehouse.co.uk", 1996, 2001, fetch, gov(), retries=4, host_first=False)
    assert (record["status"], record["years"]) == (200, [1998, 2000])
    assert record["strategy"] == "by_root"
    # the failed scan is on the record, so the rescue is auditable
    assert record["scan_status"] == 504
    assert len([u for u in asked if "%2A." in u]) == 1


def test_the_fallback_never_replaces_a_scan_that_answered() -> None:
    asked = []
    fetch = asking(lambda _u: (200, "19970101000000\n"), asked)
    record = lookup_years("fine.com", 1996, 2001, fetch=fetch, governor=gov(), host_first=False)
    assert record["years"] == [1997]
    assert "strategy" not in record
    assert len(asked) == 1


def test_host_first_answers_without_ever_running_the_scan() -> None:
    asked = []
    fetch = asking(lambda _u: (200, "19970101000000\n19990505000000\n"), asked)
    record = lookup_years("cheap.com", 1996, 2001, fetch=fetch, governor=gov())
    assert record["years"] == [1997, 1999]
    assert record["strategy"] == "by_host"
    assert len(asked) == 1
    assert "matchType=host" in asked[0]
    assert "%2A." not in asked[0]


def test_an_empty_host_answer_buys_the_scan_and_settles_the_domain_either_way() -> None:
    """Empty is the one case where a subdomain-only capture could hide, so it pays for a scan."""
    asked = []
    fetch = asking(
        lambda u: (200, "") if "matchType=host" in u else (200, "19980101000000\n"), asked
    )
    record = lookup_years("sub.com", 1996, 2001, fetch=fetch, governor=gov())
    assert record["years"] == [1998]
    assert record.get("strategy") != "by_host"
    assert any("%2A." in u for u in asked)

    def doomed(url: str) -> tuple[int, str]:
        return (200, "") if "matchType=host" in url else (504, "")

    record = lookup_years("quiet.com", 1996, 2001, fetch=doomed, governor=gov())
    # settled, not left unanswered: an unsettled domain is asked again every batch
    assert answered(record) is True
    assert record["years"] == []
    assert record["scan_status"] == 504


def test_a_refused_host_query_does_not_buy_an_expensive_scan() -> None:
    """A refusal means the host stopped taking connections, which the scan would share."""
    asked = []
    record = lookup_years("flaky.com", 1996, 2001, asking(lambda _u: (REFUSED, ""), asked), gov())
    assert answered(record) is False  # so a later batch asks again
    assert not any("%2A." in u for u in asked)


def test_a_host_too_big_for_the_server_skips_the_scan_and_asks_the_root_pages() -> None:
    """A host match that 504s means the wildcard would too, so the single-key root pages answer."""
    asked = []
    fetch = asking(
        lambda u: (504, "") if "matchType=host" in u else (200, "19980101000000\n20000202000000\n"),
        asked,
    )
    record = lookup_years("warehouse.co.uk", 1996, 2001, fetch=fetch, governor=gov())
    assert (record["status"], record["years"]) == (200, [1998, 2000])
    assert record["strategy"] == "by_root"
    assert record["host_status"] == 504
    assert not any("%2A." in u for u in asked)
    assert any("url=warehouse.co.uk&" in u for u in asked)
    assert any("url=www.warehouse.co.uk&" in u for u in asked)


def test_only_a_real_reply_settles_a_domain() -> None:
    # the evidence wall rests on this: an unanswered question is not a "no"
    assert answered({"status": 200}) is True
    for status in (0, 503, TIMED_OUT, REFUSED):
        assert answered({"status": status}) is False, status
    record = lookup_years("hopeless.com", 1996, 2001, fetch=lambda _u: (504, ""), governor=gov())
    assert (answered(record), record["years"]) == (False, [])
    record = lookup_years_by_host("empty.com", 1996, 2001, lambda _u: (200, ""), gov())
    assert (record["status"], record["years"]) == (200, [])


def test_timeout_and_refusal_are_told_apart() -> None:
    assert _is_timeout(TimeoutError()) is True
    # urllib wraps the timeout in URLError.reason, which is the shape seen in the wild
    assert _is_timeout(urllib.error.URLError(TimeoutError())) is True
    assert _is_timeout(urllib.error.URLError(OSError(50, "Network is down"))) is False
    assert _is_timeout(ConnectionResetError()) is False


def test_evidence_years_never_infers_a_year() -> None:
    # exactly the years returned, nothing adjacent, nothing out of window
    assert list(evidence_years({"years": [1996, 1999, 2005]}, 1996, 2001)) == [1996, 1999]
    assert list(evidence_years({}, 1996, 2001)) == []


def test_per_year_strategy_collects_every_year_that_answers() -> None:
    def fetch(url: str) -> tuple[int, str]:
        if "from=1997" in url:
            return 200, "19970601120000\n"
        return (200, "20000601120000\n") if "from=2000" in url else (200, "")

    record = lookup_years_per_year("x.com", 1996, 2001, fetch=fetch, governor=gov())
    assert record["years"] == [1997, 2000]
    assert (record["status"], record["strategy"], record["probe_failures"]) == (200, "per_year", 0)


def test_per_year_failures_leave_years_unknown_and_never_nothing_archived() -> None:
    def partial(url: str) -> tuple[int, str]:
        if "from=1998" in url:
            return 0, ""  # this year is unknown, not absent
        return 200, "19960101000000\n" if "from=1996" in url else ""

    record = lookup_years_per_year("x.com", 1996, 2001, fetch=partial, governor=gov())
    assert record["years"] == [1996]
    assert record["probe_failures"] == 1
    assert record["status"] == 200  # partial answers are still answers
    # every probe failed, so the domain stays unanswered and is retried later
    record = lookup_years_per_year("x.com", 1996, 2001, fetch=lambda _u: (0, ""), governor=gov())
    assert (record["years"], record["status"], answered(record)) == ([], 0, False)


def test_every_lookup_strategy_returns_the_hosts_it_saw() -> None:
    body = "19980101000000 http://www.foo.com/\n19990101000000 http://a.foo.com/\n"

    def fetch(url, timeout=None):  # noqa: ANN001, ANN202, ARG001
        return 200, body

    for record in (
        lookup_years_by_host("foo.com", 1996, 2001, fetch),
        lookup_years_by_root("foo.com", 1996, 2001, fetch),
        lookup_years("foo.com", 1996, 2001, fetch),
    ):
        assert set(record["hosts"]) == {"www.foo.com", "a.foo.com"}, record["strategy"]
