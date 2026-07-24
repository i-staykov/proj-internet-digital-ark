"""RDAP registration-date lookup: turn an undated candidate domain into dated
`whois_creation` evidence, without the slow IA CDX loop.

A queryable RDAP record means the domain is currently registered; its
`registration` event year, plus the fact that a gTLD creation date resets on
re-registration, documents a continuous registration interval `[creation, now]`.
Intersected with 1996-2001 that yields the in-window years — the same
registration-interval reasoning used for AFNIC (see the `whois_creation`
standard in notes.md). This module only extracts the year; the caller writes
evidence. `fetch` and `sleep` are injected so the logic is tested offline.
"""

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable

# (status_code, body) pairs; status 0 means a transport error (retryable)
Fetch = Callable[[str], tuple[int, str]]

RDAP_REDIRECTOR = "https://rdap.org/domain/"
_RETRYABLE = frozenset({0, 429, 500, 502, 503, 504})


def _http_get(url: str, timeout: float = 20.0) -> tuple[int, str]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "internet-digital-ark/1.0", "Accept": "application/rdap+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (https only)
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, ""


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


def creation_year(
    domain: str,
    fetch: Fetch = _http_get,
    *,
    retries: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> int | None:
    """Look up a domain's registration year via RDAP, or None if unavailable.

    None covers every "we cannot date it" case: not currently registered (404),
    no RDAP for the TLD, malformed response, or repeated transport failure.
    """
    url = f"{RDAP_REDIRECTOR}{domain}"
    for attempt in range(retries):
        status, body = fetch(url)
        if status == 200:
            return registration_year(body)
        if status in _RETRYABLE and attempt < retries - 1:
            sleep(2**attempt)
            continue
        return None
    return None
