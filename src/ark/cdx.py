"""Internet Archive CDX lookups: which in-window years hold a capture.

One request answers all six years for a domain. `url=*.domain` matches the
domain and every subdomain, `from`/`to` bound the window, `filter=statuscode:200`
keeps only captures that served content, `fl=timestamp` trims the payload to 14
bytes a row, and `collapse=timestamp:4` asks the server to fold repeated years.

The collapse is only a payload optimisation, never correctness: the server
collapses adjacent rows and results are ordered by URL key, so a domain with
many subdomains still returns a year several times. Years are therefore
deduplicated here. A response that hits `limit` may have been truncated before
some years appeared, so `lookup_years` reports truncation and the caller can
fall back to one cheap probe per missing year.

Throughput is the point. Brief section VI treats rate limits and 504s as signals
to adapt batch size and concurrency rather than to abandon a route, so requests
run through `RateGovernor`, which paces them, ramps up slowly while the service
is healthy, and backs off hard the moment it is not. `fetch` and `sleep` are
injected so every path is tested offline.
"""

import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from threading import Lock

CDX_ENDPOINT = "https://web.archive.org/cdx/search/cdx"
USER_AGENT = "internet-digital-ark/1.0"

# (status_code, body); status 0 means a transport error, which is retryable
Fetch = Callable[[str], tuple[int, str]]

_THROTTLE_STATUSES = frozenset({429, 503, 504})
_RETRYABLE = frozenset({0, 429, 500, 502, 503, 504})
_TIMESTAMP = re.compile(r"^(\d{4})\d{10}")

# a row per year per URL key, so bound the payload; truncation is detected and
# handled rather than silently accepted
DEFAULT_LIMIT = 3000

# Sit just above the server's own limit. Measured 2026-07-25: a collapsed
# six-year query answers a light domain in 2-16 s, and the SERVER kills a heavily
# archived one at a consistent ~60.7 s, so it already fails fast on our behalf.
# A client timeout only needs headroom above that. Cutting in earlier is a false
# economy: at 30 s the run answered 51 of 100 domains (695 answers/hour), at 180 s
# it answered 82 of the same 100 (802 answers/hour), because roughly a third of
# domains reply between 30 s and 60 s. Domains the server does give up on are
# swept later by the per-year probe strategy, which succeeds on exactly those.
DEFAULT_TIMEOUT = 70.0


def cdx_url(domain: str, first: int, last: int, limit: int = DEFAULT_LIMIT) -> str:
    """The one-request query for every in-window year of a domain."""
    query = urllib.parse.urlencode(
        {
            "url": f"*.{domain}",
            "from": str(first),
            "to": str(last),
            "filter": "statuscode:200",
            "fl": "timestamp",
            "collapse": "timestamp:4",
            "limit": str(limit),
        }
    )
    return f"{CDX_ENDPOINT}?{query}"


def years_in(body: str, first: int, last: int) -> set[int]:
    """In-window years present among the returned timestamps."""
    years = set()
    for line in body.splitlines():
        match = _TIMESTAMP.match(line.strip())
        if match is None:
            continue
        year = int(match.group(1))
        if first <= year <= last:
            years.add(year)
    return years


def _http_get(url: str, timeout: float = DEFAULT_TIMEOUT) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (https)
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
        return exc.code, retry_after
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, ""


def http_fetch(timeout: float = DEFAULT_TIMEOUT) -> Fetch:
    """A fetcher with a chosen timeout, since the timeout is a tuning decision."""

    def fetch(url: str) -> tuple[int, str]:
        return _http_get(url, timeout)

    return fetch


def year_probe_url(domain: str, year: int) -> str:
    """Ask only whether ANY capture exists in one year.

    `limit=1` lets the server stop at the first match instead of collecting a
    year's worth of rows, so each probe is cheap. Six of these cost more in total
    than one collapsed query on a normal domain, but they succeed on the heavy
    domains where the collapsed query exceeds the server's own time limit.
    """
    query = urllib.parse.urlencode(
        {
            "url": f"*.{domain}",
            "from": str(year),
            "to": str(year),
            "filter": "statuscode:200",
            "fl": "timestamp",
            "limit": "1",
        }
    )
    return f"{CDX_ENDPOINT}?{query}"


@dataclass
class RateGovernor:
    """Paces requests across threads, ramping up on health and down on refusal.

    Multiplicative decrease on refusal, gradual increase while healthy, applied
    to the delay between request *starts* rather than to a worker count, so the
    pool size stays fixed and only the pace moves.

    The defaults are tuned for what this workload measurably is: a wildcard CDX
    query takes on the order of 20 seconds, so throughput is latency-bound and
    comes from concurrency, not from pacing. Pacing exists only to stay under
    the limiter. Hence a low ceiling and quick recovery: an unlucky patch of
    throttles must not leave the run crawling for hours afterwards, which is
    exactly what a 30-second ceiling with slow recovery did on the first pilot.
    """

    delay: float = 0.2
    min_delay: float = 0.05
    max_delay: float = 5.0
    # successes needed before easing the pace up again
    ramp_after: int = 5
    ramp_factor: float = 0.8
    backoff_factor: float = 1.5
    sleep: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        self._lock = Lock()
        self._next_at = 0.0
        self._successes = 0
        self.throttles = 0

    def wait(self) -> None:
        """Block until this thread's turn, keeping the global pace."""
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next_at)
            self._next_at = start + self.delay
            pause = start - now
        if pause > 0:
            self.sleep(pause)

    def on_success(self) -> None:
        with self._lock:
            self._successes += 1
            if self._successes >= self.ramp_after and self.delay > self.min_delay:
                self._successes = 0
                self.delay = max(self.min_delay, self.delay * self.ramp_factor)

    def on_throttle(self, retry_after: float = 0.0) -> None:
        """Back off immediately, and honour Retry-After when the server sends one."""
        with self._lock:
            self.throttles += 1
            self._successes = 0
            self.delay = min(self.max_delay, self.delay * self.backoff_factor)
            if retry_after > 0:
                self._next_at = max(self._next_at, time.monotonic() + retry_after)


def _retry_after_seconds(body: str) -> float:
    try:
        return max(0.0, float(body.strip()))
    except (ValueError, AttributeError):
        return 0.0


def _fetch_retrying(url: str, fetch: Fetch, gov: RateGovernor, retries: int) -> tuple[int, str]:
    """One request through the governor, retrying only what is worth retrying."""
    status, body = 0, ""
    for attempt in range(retries):
        gov.wait()
        status, body = fetch(url)
        if status == 200:
            gov.on_success()
            break
        if status in _THROTTLE_STATUSES:
            gov.on_throttle(_retry_after_seconds(body))
        if status in _RETRYABLE and attempt < retries - 1:
            continue
        break
    return status, body


def lookup_years_per_year(
    domain: str,
    first: int,
    last: int,
    fetch: Fetch = _http_get,
    governor: RateGovernor | None = None,
    *,
    retries: int = 4,
) -> dict:
    """Ask one cheap question per year instead of one big question per domain.

    Slower per domain (measured 73.6 s against 26.9 s), so this is not the
    default. Its value is that it succeeds where the collapsed query is killed by
    the server's own time limit, which makes it the right sweep for the heavily
    archived domains the primary strategy has to give up on. A year counts as
    evidenced if its probe returns any capture; a probe that fails leaves that
    year unknown rather than absent, and the record says so.
    """
    gov = governor or RateGovernor()
    years: set[int] = set()
    failures = 0
    last_status = 0
    for year in range(first, last + 1):
        status, body = _fetch_retrying(year_probe_url(domain, year), fetch, gov, retries)
        last_status = status
        if status == 200:
            years |= years_in(body, year, year)
        else:
            failures += 1
    return {
        "domain": domain,
        # a partial answer is still an answer for the years that came back, but a
        # run where every probe failed must not be recorded as "nothing archived"
        "status": 200 if failures < (last - first + 1) else last_status,
        "years": sorted(years),
        "truncated": False,
        "strategy": "per_year",
        "probe_failures": failures,
    }


def lookup_years(
    domain: str,
    first: int,
    last: int,
    fetch: Fetch = _http_get,
    governor: RateGovernor | None = None,
    *,
    retries: int = 4,
    limit: int = DEFAULT_LIMIT,
    probe_missing: bool = True,
) -> dict:
    """Query one domain and return its journal record.

    The record always states what happened, including failure, so a later run
    knows not to repeat it and the run's coverage is auditable.
    """
    gov = governor or RateGovernor()
    status, body = _fetch_retrying(cdx_url(domain, first, last, limit), fetch, gov, retries)

    if status != 200:
        return {"domain": domain, "status": status, "years": [], "truncated": False}

    rows = [line for line in body.splitlines() if line.strip()]
    years = years_in(body, first, last)
    truncated = len(rows) >= limit

    # a truncated response may have stopped before a year appeared, so probe only
    # the years still unaccounted for; this is rare and keeps the count honest
    if truncated and probe_missing:
        for year in range(first, last + 1):
            if year in years:
                continue
            gov.wait()
            probe_status, probe_body = fetch(cdx_url(domain, year, year, limit=1))
            if probe_status == 200:
                gov.on_success()
                years |= years_in(probe_body, year, year)
            elif probe_status in _THROTTLE_STATUSES:
                gov.on_throttle(_retry_after_seconds(probe_body))

    return {
        "domain": domain,
        "status": status,
        "years": sorted(years),
        "truncated": truncated,
    }


def answered(record: dict) -> bool:
    """Whether a journal record settles a domain, so a later run can skip it.

    Only an HTTP 200 settles anything. A transport failure or a 5xx means the
    question was never put, and treating it as settled would silently drop the
    domain from every later run.
    """
    return record.get("status") == 200


def evidence_years(record: dict, first: int, last: int) -> Iterable[int]:
    """In-window years a CDX record attests, which is exactly what it returned.

    No inference of any kind: a capture in a year is evidence for that year and
    for no other, which is what brief III.7 requires.
    """
    for year in record.get("years") or []:
        if isinstance(year, int) and first <= year <= last:
            yield year
