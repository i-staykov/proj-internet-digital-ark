"""RDAP registration-date lookup, and the run journal it writes.

An RDAP response carries the current state of a registration plus one
historical timestamp: the `registration` event. There is no registration
history, so the only year it can attest is the creation year. Brief III.6
blesses exactly that ("the annual file for the target year in which the
creation date falls") and rules out more: a creation date alone "does not
automatically establish that the domain remained registered ... in every
subsequent year", and later years need evidence "tied to that specific year".
So `attested_years` returns at most the creation year. See the
`whois_creation` standard in notes.md for the full reasoning.

Collection is separated from interpretation. `lookup` queries one domain and
returns a journal record; the caller appends those to a per-run journal file,
and `ark ingest rdap_snapshot <journal>` turns them into evidence through the
same audited loader every other source uses. Keeping the whole response means a
later change of standard is a re-parse rather than a database migration, which
is exactly what the 2026-07-25 narrowing cost when only the year was kept.

Journal format: one JSON object per line, gzipped, with keys
`domain`, `queried_at`, `status`, `creation_year`, `response`, `url`.
`status` is the HTTP status (0 for a transport failure), `creation_year` is
null whenever the domain could not be dated, `response` holds the parsed
RDAP body (null unless the query returned 200 with valid JSON), and `url` is
the endpoint that answered. `url` was added on 2026-08-08 with direct routing
and is absent from earlier journals, so readers must treat it as optional.

Routing: queries go to the authoritative registry endpoint, taken from the IANA
bootstrap file, and fall back to the `rdap.org` redirector only for a TLD the
bootstrap does not list. The redirector is a free service whose own rate limit,
not the registries', is what refused 18.8% of a 2026-08-08 pilot's queries at
under one query a second. Going direct removes that ceiling and lets each
registry be paced on its own, so one registry refusing does not slow the rest.

`fetch` and `sleep` are injected so the logic is tested offline.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from ark.cdx import RateGovernor
from ark.journal import journal_path as _journal_path
from ark.journal import (
    open_journal,
    open_journal_for_write,
    write_journal_line,
)
from ark.journal import queried_domains as _queried_domains

__all__ = [
    "BOOTSTRAP_CACHE",
    "BOOTSTRAP_URL",
    "JOURNAL_DIR",
    "RDAP_REDIRECTOR",
    "Router",
    "attested_years",
    "creation_year",
    "journal_path",
    "load_registries",
    "lookup",
    "open_journal",
    "open_journal_for_write",
    "parse_bootstrap",
    "queried_domains",
    "rdap_url",
    "registration_year",
    "write_journal_line",
]

# (status_code, body) pairs; status 0 means a transport error (retryable)
Fetch = Callable[[str], tuple[int, str]]

RDAP_REDIRECTOR = "https://rdap.org/domain/"
_RETRYABLE = frozenset({0, 429, 500, 502, 503, 504})

# What means "stop asking", as opposed to "this name has no record".
#
# 403 is in here because of what PIR did on 2026-08-08. It answered the first
# ~850 `.org` queries normally and then returned **403 for 9,253 consecutive
# requests**: a block, not a rate limit, and RFC 7480 does not reserve a status
# for that. With 403 outside this set the governor read every one of those as a
# plain error, never slowed down, and the run spent nine thousand requests being
# told no. That is exactly the tight loop of refusals the collection rules forbid.
# It is deliberately NOT in `_RETRYABLE` and NOT in `answered`: a blocked query is
# not retried inside the run, and it never settles the domain either, so the name
# stays queryable once the block lifts.
_THROTTLE_STATUSES = frozenset({0, 403, 429, 503, 504})

JOURNAL_DIR = Path("data/raw/rdap")
JOURNAL_PREFIX = "rdap"

# IANA's registry of registries: every delegated TLD mapped to the base URL of
# the RDAP service authoritative for it. It changes at the pace of the root
# zone, so a cached copy is refreshed weekly rather than fetched per run.
BOOTSTRAP_URL = "https://data.iana.org/rdap/dns.json"
BOOTSTRAP_CACHE = JOURNAL_DIR / "iana_rdap_bootstrap.json"
BOOTSTRAP_MAX_AGE = 7 * 24 * 3600.0


def _http_get(url: str, timeout: float = 20.0) -> tuple[int, str]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "internet-digital-ark/1.0", "Accept": "application/rdap+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (https only)
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        # the body of a refusal is worthless, the Retry-After header is not
        return exc.code, (exc.headers.get("Retry-After", "") if exc.headers else "")
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, ""


def http_fetch(timeout: float = 20.0) -> Fetch:
    """A fetcher with a chosen timeout, since the timeout is a tuning decision."""

    def fetch(url: str) -> tuple[int, str]:
        return _http_get(url, timeout)

    return fetch


def parse_bootstrap(body: str) -> dict[str, str]:
    """Map each TLD in the IANA bootstrap file to its RDAP base URL.

    A service may publish several URLs; https is taken in preference, because
    the alternative is http and these queries are otherwise all TLS.
    """
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return {}
    registries: dict[str, str] = {}
    for entry in data.get("services") or []:
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        tlds, urls = entry[0], entry[1]
        chosen = next(
            (u for u in urls if str(u).startswith("https://")),
            next(iter(urls), None),
        )
        if not chosen:
            continue
        base = str(chosen).rstrip("/") + "/"
        for tld in tlds:
            registries[str(tld).lower().lstrip(".")] = base
    return registries


def load_registries(
    cache: Path = BOOTSTRAP_CACHE,
    fetch: Fetch = _http_get,
    *,
    max_age: float = BOOTSTRAP_MAX_AGE,
    now: float | None = None,
) -> dict[str, str]:
    """The TLD-to-registry map, from cache when fresh and from IANA otherwise.

    A failed refresh falls back to whatever the cache holds, and an empty map is
    a valid answer: it simply routes everything through the redirector.
    """
    stale = True
    if cache.exists():
        age = (now if now is not None else time.time()) - cache.stat().st_mtime
        stale = age > max_age
    if not stale:
        try:
            return parse_bootstrap(cache.read_text(encoding="utf-8"))
        except OSError:
            pass
    status, body = fetch(BOOTSTRAP_URL)
    registries = parse_bootstrap(body) if status == 200 else {}
    if registries:
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(body, encoding="utf-8")
        except OSError:
            pass
        return registries
    if cache.exists():
        try:
            return parse_bootstrap(cache.read_text(encoding="utf-8"))
        except OSError:
            return {}
    return {}


def rdap_url(domain: str, registries: Mapping[str, str] | None = None) -> str:
    """The endpoint to ask about a domain: its registry, or the redirector.

    The redirector is the fallback rather than the default. It answers for every
    TLD but meters the client itself, so it is worth using only where no
    authoritative base URL is known.
    """
    tld = domain.rsplit(".", 1)[-1].lower() if "." in domain else ""
    base = (registries or {}).get(tld)
    return f"{base}domain/{domain}" if base else f"{RDAP_REDIRECTOR}{domain}"


def _host_of(url: str) -> str:
    return urllib.parse.urlsplit(url).netloc.lower()


@dataclass
class Router:
    """Routes each domain to its registry, and paces every registry separately.

    One `RateGovernor` per endpoint host. That separation is the point of going
    direct: Verisign carries `.com` and `.net`, which is 1.34M of the addressable
    pool, and a 429 from a small ccTLD registry must not slow those down. The
    governors ramp up while a registry is healthy and back off on refusal, so the
    sustainable pace per registry is found by measurement rather than declared.
    """

    registries: Mapping[str, str] = field(default_factory=dict)
    delay: float = 0.05
    min_delay: float = 0.01
    max_delay: float = 5.0

    def __post_init__(self) -> None:
        self._lock = Lock()
        self._governors: dict[str, RateGovernor] = {}

    def url(self, domain: str) -> str:
        return rdap_url(domain, self.registries)

    def governor(self, url: str) -> RateGovernor:
        host = _host_of(url)
        with self._lock:
            governor = self._governors.get(host)
            if governor is None:
                governor = RateGovernor(
                    delay=self.delay, min_delay=self.min_delay, max_delay=self.max_delay
                )
                self._governors[host] = governor
            return governor

    def throttles(self) -> dict[str, int]:
        """Refusals seen per registry host, for the run summary."""
        with self._lock:
            return {h: g.throttles for h, g in self._governors.items() if g.throttles}


def registration_year(body: str) -> int | None:
    """Year of the `registration` event in an RDAP domain response, or None."""
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return None
    for event in data.get("events") or []:
        if event.get("eventAction") == "registration":
            date = str(event.get("eventDate", ""))
            if len(date) >= 4 and date[:4].isdigit():
                return int(date[:4])
    return None


def attested_years(creation: int, first: int = 1996, last: int = 2001) -> tuple[int, ...]:
    """The in-window years an RDAP creation year can attest on its own.

    The creation year itself when it falls inside the window, nothing
    otherwise. A domain created before `first` is left with no attested year:
    RDAP shows it existed by then and exists now, but says nothing about any
    single year in between, so it belongs in the candidate pool until
    year-specific evidence turns up.
    """
    return (creation,) if first <= creation <= last else ()


def _retry_after_seconds(body: str) -> float:
    try:
        return max(0.0, float(body.strip()))
    except (ValueError, AttributeError):
        return 0.0


def _fetch_with_retries(
    url: str,
    fetch: Fetch,
    retries: int,
    sleep: Callable[[float], None],
    governor: RateGovernor | None = None,
) -> tuple[int, str]:
    """Fetch once, retrying only the statuses worth retrying.

    With a governor the pace between attempts is the governor's, which is shared
    across threads and adapts to what the registry is willing to take. Without
    one the caller gets the old single-threaded exponential back-off.
    """
    status, body = 0, ""
    for attempt in range(retries):
        if governor is not None:
            governor.wait()
        status, body = fetch(url)
        if status == 200:
            if governor is not None:
                governor.on_success()
            break
        if governor is not None and status in _THROTTLE_STATUSES:
            # a 403 counts as the harsh kind, alongside a connection that never
            # landed: a run of them trips the breaker and holds every thread on
            # this registry off, which is the only useful answer to a block
            governor.on_throttle(_retry_after_seconds(body), refused=status in (0, 403))
        if status in _RETRYABLE and attempt < retries - 1:
            if governor is None:
                sleep(2**attempt)
            continue
        break
    return status, body


def creation_year(
    domain: str,
    fetch: Fetch = _http_get,
    *,
    retries: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> int | None:
    """Look up a domain's registration year via RDAP, or None if unavailable.

    None covers every undatable case: not currently registered (404),
    no RDAP for the TLD, malformed response, or repeated transport failure.
    """
    status, body = _fetch_with_retries(f"{RDAP_REDIRECTOR}{domain}", fetch, retries, sleep)
    return registration_year(body) if status == 200 else None


def lookup(
    domain: str,
    fetch: Fetch = _http_get,
    *,
    retries: int = 3,
    sleep: Callable[[float], None] = time.sleep,
    now: datetime | None = None,
    router: Router | None = None,
) -> dict:
    """Query one domain and return its journal record (see the module docstring).

    Records the outcome whether or not the domain could be dated: a failed or
    404 lookup is itself worth journalling, so a later run knows not to retry it
    and the run's coverage is auditable.

    With a `router` the query goes to the authoritative registry and is paced by
    that registry's own governor. Without one it goes through the redirector, at
    the caller's pace, which is what every journal before 2026-08-08 records.
    """
    url = router.url(domain) if router else f"{RDAP_REDIRECTOR}{domain}"
    governor = router.governor(url) if router else None
    status, body = _fetch_with_retries(url, fetch, retries, sleep, governor)
    response = None
    if status == 200:
        try:
            response = json.loads(body)
        except (ValueError, TypeError):
            response = None
    return {
        "domain": domain,
        "queried_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "status": status,
        "creation_year": registration_year(body) if status == 200 else None,
        "response": response,
        "url": url,
    }


def journal_path(directory: Path = JOURNAL_DIR, now: datetime | None = None) -> Path:
    """Path for a new run journal. One file per run, never appended to again."""
    return _journal_path(directory, JOURNAL_PREFIX, now)


def answered(record: dict) -> bool:
    """Whether a journal record settles a domain, so a later run can skip it.

    A 200 is an answer and so is a 404: "no RDAP record exists for this name" is
    a finding, not a failure, and re-asking will not change it. A transport error
    or a 5xx means the question never landed, and treating that as settled would
    silently drop the domain from every later run.
    """
    return record.get("status") in (200, 404)


def queried_domains(directory: Path = JOURNAL_DIR) -> set[str]:
    """Domains a run journal already ANSWERED, so runs never repeat settled work."""
    return _queried_domains(directory, JOURNAL_PREFIX, answered=answered)
