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

# (status_code, body); a status below 200 is a transport outcome, not a reply
Fetch = Callable[[str], tuple[int, str]]

# A refused connection and a client-side timeout used to arrive here as the same
# status 0, and they want opposite responses.
#
# Measured 2026-08-06 01:00 CEST, with eight workers running: google.com,
# one.one.one.one and archive.org each answered 8 of 8 requests while
# web.archive.org answered 2 of 8, the failures all giving up at a flat ~3.4 s
# with the TCP connect never completing. So the refusals were that one host
# rate-limiting this IP, not the local link. Stopping the engine restored it
# within 90 s. A refusal that does not slow the governor down is retried at full
# pace, and those retries are themselves connection attempts, so the run holds
# itself in the penalty box. Hence REFUSED backs the pace off like any throttle.
#
# A timeout says the opposite. The server accepted the question and could not
# finish it, which is no evidence about the pace, and asking again is close to
# pure waste because the server kills a heavily archived domain at a consistent
# ~60 s. Those domains are what `lookup_years_per_year` exists to sweep.
REFUSED = 0
TIMED_OUT = -1

_THROTTLE_STATUSES = frozenset({REFUSED, 429, 503, 504})
_RETRYABLE = frozenset({REFUSED, 429, 500, 502, 503, 504})
# one extra attempt only, so a doomed query costs one timeout instead of four
_TIMEOUT_ATTEMPTS = 1
_TIMESTAMP = re.compile(r"^(\d{4})\d{10}")

# a row per year per URL key, so bound the payload; truncation is detected and
# handled rather than silently accepted
DEFAULT_LIMIT = 3000

# Sit just above the server's own limit. Measured 2026-07-25: a collapsed
# six-year query answers a light domain in 2-16 s, and the SERVER kills a heavily
# archived one at a consistent ~60.7 s, so the server already fails fast on
# the client's behalf.
# A client timeout only needs headroom above that. Cutting in earlier is a false
# economy: at 30 s the run answered 51 of 100 domains (695 answers/hour), at 180 s
# it answered 82 of the same 100 (802 answers/hour), because roughly a third of
# domains reply between 30 s and 60 s. Domains the server does give up on are
# swept later by the per-year probe strategy, which succeeds on exactly those.
DEFAULT_TIMEOUT = 70.0

# The cheap tier gets a short leash, because a cheap query that is not cheap is
# by definition the wrong tier for that domain. Measured 2026-08-06 the host match
# answers at a median 2.07 s and a p90 of 6.24 s, so 15 s keeps essentially every
# real answer while cutting the cost of discovering a heavy domain from the
# server's own ~60 s timeout to a quarter of that. The saving is not small: it is
# paid on every domain the tier cannot answer.
HOST_TIMEOUT = 15.0


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


def _is_timeout(exc: BaseException) -> bool:
    """Whether a transport exception is the clock running out rather than a refusal."""
    if isinstance(exc, TimeoutError):
        return True
    reason = getattr(exc, "reason", None)
    return isinstance(reason, TimeoutError)


def _http_get(url: str, timeout: float = DEFAULT_TIMEOUT) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (https)
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
        return exc.code, retry_after
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        # socket.timeout is an alias of TimeoutError, and URLError wraps it in
        # .reason, so both spellings of "the clock ran out" land on TIMED_OUT
        return (TIMED_OUT if _is_timeout(exc) else REFUSED), ""


def http_fetch(timeout: float = DEFAULT_TIMEOUT) -> Fetch:
    """A fetcher with a chosen timeout, since the timeout is a tuning decision."""

    def fetch(url: str) -> tuple[int, str]:
        return _http_get(url, timeout)

    return fetch


# The two outcomes that mean the server could not finish the range scan, as
# opposed to answering it or refusing to talk. Retrying the same scan is close to
# pure waste: measured on the queue head, these domains had already failed four
# and five times over as many batches, each attempt costing a full ~60 s before
# the server gave up. The cheap host shape is tried instead.
_SCAN_TOO_BIG = frozenset({504, TIMED_OUT})

# Enough rows to see all six years several times over, and few enough that a
# heavily archived host cannot bury the answer in payload.
HOST_LIMIT = 50

# Apex and www, as EXACT urls rather than a host match. The distinction is the
# whole point of this tier and it cost a wrong turn to learn: `matchType=host`
# covers every path on the host, which for a heavily archived name is millions of
# rows, and measured 2026-08-06 it returned 504 on `warehouse.co.uk`,
# `gigabyte.com` and `bbc.co.uk` exactly as the wildcard does. An exact url is a
# single CDX key, and the same three domains answered in about 10 s each that way.
ROOT_HOSTS = ("", "www.")


def host_url(host: str, first: int, last: int, limit: int = HOST_LIMIT) -> str:
    """Ask one host, every path on it, instead of every subdomain of the domain.

    Where the saving comes from: CDX is keyed by a SURT of the URL, so
    `url=*.domain` has to walk the key range covering every subdomain, while
    `matchType=host` walks one host's range. Narrowing the range is the win;
    `collapse` and `limit` only bound the payload, and for a very heavily archived
    host the scan can still be slow.

    `www.` comes free. IA's canonicalisation folds `http://www.abc.net.au/` and
    `http://abc.net.au/` onto the same key prefix `au,net,abc)/`, so asking about
    the apex already covers www. Verified rather than assumed: asking for `www.<d>`
    explicitly returned the same year set every time it answered.

    Measured 2026-08-06 against the wildcard scan on domains the scan had already
    answered, which is ground truth we already held: median 2.07 s against roughly
    33 s, and the same years every time.

    It is NOT the answer for a heavily archived domain. One host can still hold
    millions of rows, and this shape returned 504 on `warehouse.co.uk`,
    `gigabyte.com` and `bbc.co.uk` just as the wildcard does. `root_url` is the
    tier for those.
    """
    query = urllib.parse.urlencode(
        {
            "url": host,
            "matchType": "host",
            "from": str(first),
            "to": str(last),
            "filter": "statuscode:200",
            "fl": "timestamp",
            "collapse": "timestamp:4",
            "limit": str(limit),
        }
    )
    return f"{CDX_ENDPOINT}?{query}"


def root_url(host: str, first: int, last: int, limit: int = HOST_LIMIT) -> str:
    """Ask one exact url, the host's root page, which is a single CDX key.

    The cheapest question that can still date a domain, and the only one a
    heavily archived name reliably answers. One key means the server reads a
    contiguous run of rows in time order, so `collapse` plus a small limit lets it
    stop as soon as it has the years, rather than bounding a payload it has
    already had to scan.

    Measured 2026-08-06 on `warehouse.co.uk`, which five batches of the wildcard
    scan had failed on and which `matchType=host` also 504s: apex plus www
    answered in 20.5 s with four years.
    """
    query = urllib.parse.urlencode(
        {
            "url": host,
            "from": str(first),
            "to": str(last),
            "filter": "statuscode:200",
            "fl": "timestamp",
            "collapse": "timestamp:4",
            "limit": str(limit),
        }
    )
    return f"{CDX_ENDPOINT}?{query}"


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
    # Consecutive refusals that mean the host has stopped taking connections from
    # this IP at all. Slowing down does not help once that has happened, because
    # every queue position spent is a certain failure; the useful move is to stop
    # asking for a while. Measured recovery after stopping an eight-worker run
    # was under 90 s, so a minute of quiet is the right order.
    breaker_after: int = 25
    breaker_pause: float = 60.0
    sleep: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        self._lock = Lock()
        self._next_at = 0.0
        self._successes = 0
        self._refusals = 0
        self.throttles = 0
        self.breaker_trips = 0

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
            self._refusals = 0
            if self._successes >= self.ramp_after and self.delay > self.min_delay:
                self._successes = 0
                self.delay = max(self.min_delay, self.delay * self.ramp_factor)

    def on_throttle(self, retry_after: float = 0.0, *, refused: bool = False) -> None:
        """Back off immediately, and honour Retry-After when the server sends one.

        `refused` marks the harsher case where the connection never got made.
        A run of those trips the breaker, which pushes the shared next-start time
        forward and so holds every thread off, not just this one.
        """
        with self._lock:
            self.throttles += 1
            self._successes = 0
            self.delay = min(self.max_delay, self.delay * self.backoff_factor)
            if retry_after > 0:
                self._next_at = max(self._next_at, time.monotonic() + retry_after)
            if not refused:
                self._refusals = 0
                return
            self._refusals += 1
            if self._refusals >= self.breaker_after:
                self._refusals = 0
                self.breaker_trips += 1
                self._next_at = max(self._next_at, time.monotonic() + self.breaker_pause)


def _retry_after_seconds(body: str) -> float:
    try:
        return max(0.0, float(body.strip()))
    except (ValueError, AttributeError):
        return 0.0


def _fetch_retrying(
    url: str,
    fetch: Fetch,
    gov: RateGovernor,
    retries: int,
    stop_on: frozenset[int] = frozenset(),
) -> tuple[int, str]:
    """One request through the governor, retrying only what is worth retrying.

    `stop_on` names statuses the caller has a better answer to than retrying. The
    pace is still adjusted for them, because a 504 does say the server is
    struggling; only the pointless repetition is skipped.
    """
    status, body = REFUSED, ""
    for attempt in range(retries):
        gov.wait()
        status, body = fetch(url)
        if status == 200:
            gov.on_success()
            break
        if status in _THROTTLE_STATUSES:
            gov.on_throttle(_retry_after_seconds(body), refused=status == REFUSED)
        # a timeout is the server giving up on a heavy domain, so one attempt is
        # the whole budget: three more would cost three more minutes of a worker
        # and end the same way. The cheaper shapes are what rescue those.
        if status in stop_on or status == TIMED_OUT or status not in _RETRYABLE:
            break
        if attempt >= retries - 1:
            break
    return status, body


def lookup_years_by_host(
    domain: str,
    first: int,
    last: int,
    fetch: Fetch = _http_get,
    governor: RateGovernor | None = None,
    *,
    retries: int = 4,
    limit: int = HOST_LIMIT,
) -> dict:
    """Date a domain from every path on its own host, in one request.

    Narrower than the wildcard scan by construction: a year evidenced only by
    some OTHER subdomain is not seen. Measured cost of that narrowing, against
    the wildcard answers already in our journals, was zero years lost on the
    domains where both shapes answered.
    """
    gov = governor or RateGovernor()
    status, body = _fetch_retrying(
        host_url(domain, first, last, limit), fetch, gov, retries, stop_on=_SCAN_TOO_BIG
    )
    return {
        "domain": domain,
        "status": status,
        "years": sorted(years_in(body, first, last)) if status == 200 else [],
        "truncated": False,
        "strategy": "by_host",
    }


def lookup_years_by_root(
    domain: str,
    first: int,
    last: int,
    fetch: Fetch = _http_get,
    governor: RateGovernor | None = None,
    *,
    retries: int = 4,
    hosts: tuple[str, ...] = ROOT_HOSTS,
) -> dict:
    """Date a domain from the root pages of its apex and www hosts.

    The last tier, for domains so heavily archived that neither the wildcard scan
    nor a whole-host match can be finished by the server. Narrow by construction,
    since a year evidenced only by some deeper page or other subdomain is not seen,
    but the comparison here is against no answer at all: these are the domains that
    had already failed four and five times over as many batches.

    A host that answers with no rows is still an answer, so the domain counts as
    settled if either host returned 200.
    """
    gov = governor or RateGovernor()
    years: set[int] = set()
    answers = 0
    last_status = REFUSED
    for prefix in hosts:
        status, body = _fetch_retrying(
            root_url(f"{prefix}{domain}", first, last), fetch, gov, retries, stop_on=_SCAN_TOO_BIG
        )
        last_status = status
        if status == 200:
            answers += 1
            years |= years_in(body, first, last)
    return {
        "domain": domain,
        "status": 200 if answers else last_status,
        "years": sorted(years),
        "truncated": False,
        "strategy": "by_root",
    }


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
    host_first: bool = True,
    host_fetch: Fetch | None = None,
) -> dict:
    """Query one domain and return its journal record.

    The record always states what happened, including failure, so a later run
    knows not to repeat it and the run's coverage is auditable.

    The cheap shape is asked first and the wildcard scan is the fallback, which is
    the reverse of how this started. Two measurements moved it:

    The scan is what the server gives up on. Measured 2026-08-06, the first 200
    domains of the unanswered queue were 100% ones earlier batches had already
    failed on, most four or five times over, and the head was heavily archived
    names like `warehouse.co.uk` and `vccs.edu` returning 504 every time. Since
    only an HTTP 200 settles a domain, they returned to the head of every later
    batch, so about a third of each batch went on re-failing the same names.

    And the cheap shape loses nothing measurable. Against the wildcard answers
    already in our journals, which is ground truth already paid for, the host query
    returned the same year set every time both answered, at a median 2.07 s against
    roughly 33 s.

    Three tiers, and each one exists for a failure the others measurably have:

    1. `matchType=host`, one request, answers the ordinary domain in about 2 s.
    2. If the server cannot finish even that, the apex and www ROOT pages, which
       are single keys. This is the tier for the heavily archived names, and it is
       not interchangeable with tier 1: `matchType=host` returned 504 on
       `warehouse.co.uk`, `gigabyte.com` and `bbc.co.uk`, while their root pages
       answered in about 10 s each.
    3. If tier 1 answered but found nothing, the wildcard scan, which is the only
       shape that can see a capture under some other subdomain. Safe to spend
       there precisely because a domain with nothing on its own host is lightly
       archived, so the scan is cheap.
    """
    gov = governor or RateGovernor()

    if host_first:
        record = lookup_years_by_host(
            domain, first, last, host_fetch or fetch, governor=gov, retries=retries
        )
        host_status = record["status"]
        if host_status == 200 and record["years"]:
            return record
        if host_status in _SCAN_TOO_BIG:
            # too big for one host, so it is far too big for every subdomain: the
            # wildcard scan is strictly more work and would only 504 again
            rescued = lookup_years_by_root(
                domain, first, last, fetch, governor=gov, retries=retries
            )
            if rescued["status"] == 200:
                rescued["host_status"] = host_status
                return rescued
            return {"domain": domain, "status": host_status, "years": [], "truncated": False}
        if host_status != 200:
            # refused, so nothing was learned about the domain; a later batch asks again
            return {"domain": domain, "status": host_status, "years": [], "truncated": False}

    status, body = _fetch_retrying(
        cdx_url(domain, first, last, limit), fetch, gov, retries, stop_on=_SCAN_TOO_BIG
    )

    if status != 200:
        if not host_first:
            # scan-first ordering keeps the cheap shapes as the rescue they were
            rescued = lookup_years_by_root(
                domain, first, last, fetch, governor=gov, retries=retries
            )
            if rescued["status"] == 200:
                rescued["scan_status"] = status
                return rescued
        else:
            # tier 1 said "nothing on this host" and the scan could not improve on
            # it. Recording tier 1's answer settles the domain, which is right:
            # leaving these unsettled is what built the clog in the first place
            record["scan_status"] = status
            return record
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
                gov.on_throttle(_retry_after_seconds(probe_body), refused=probe_status == REFUSED)

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
