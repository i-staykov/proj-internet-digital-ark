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
is exactly what the 2026-07-25 narrowing cost us when only the year was kept.

Journal format: one JSON object per line, gzipped, with keys
`domain`, `queried_at`, `status`, `creation_year`, `response`.
`status` is the HTTP status (0 for a transport failure), `creation_year` is
null whenever the domain could not be dated, and `response` holds the parsed
RDAP body (null unless the query returned 200 with valid JSON).

`fetch` and `sleep` are injected so the logic is tested offline.
"""

import gzip
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

# (status_code, body) pairs; status 0 means a transport error (retryable)
Fetch = Callable[[str], tuple[int, str]]

RDAP_REDIRECTOR = "https://rdap.org/domain/"
_RETRYABLE = frozenset({0, 429, 500, 502, 503, 504})

JOURNAL_DIR = Path("data/raw/rdap")
_JOURNAL_GLOB = "rdap_*.jsonl*"


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


def attested_years(creation: int, first: int = 1996, last: int = 2001) -> tuple[int, ...]:
    """The in-window years an RDAP creation year can attest on its own.

    The creation year itself when it falls inside the window, nothing
    otherwise. A domain created before `first` is left with no attested year:
    RDAP shows it existed by then and exists now, but says nothing about any
    single year in between, so it belongs in the candidate pool until
    year-specific evidence turns up.
    """
    return (creation,) if first <= creation <= last else ()


def _fetch_with_retries(
    url: str, fetch: Fetch, retries: int, sleep: Callable[[float], None]
) -> tuple[int, str]:
    """Fetch once, retrying only the statuses worth retrying."""
    status, body = 0, ""
    for attempt in range(retries):
        status, body = fetch(url)
        if status == 200:
            break
        if status in _RETRYABLE and attempt < retries - 1:
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

    None covers every "we cannot date it" case: not currently registered (404),
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
) -> dict:
    """Query one domain and return its journal record (see the module docstring).

    Records the outcome whether or not the domain could be dated: a failed or
    404 lookup is itself worth journalling, so a later run knows not to retry it
    and the run's coverage is auditable.
    """
    status, body = _fetch_with_retries(f"{RDAP_REDIRECTOR}{domain}", fetch, retries, sleep)
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
    }


def journal_path(directory: Path = JOURNAL_DIR, now: datetime | None = None) -> Path:
    """Path for a new run journal. One file per run, never appended to again."""
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return directory / f"rdap_{stamp}.jsonl.gz"


def open_journal(path: Path) -> IO[str]:
    """Open a journal for reading, gzipped or plain."""
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open(encoding="utf-8", errors="replace")


def open_journal_for_write(path: Path) -> IO[str]:
    """Open a journal for writing, gzipped unless the path says otherwise."""
    if path.suffix == ".gz":
        return gzip.open(path, "wt", encoding="utf-8")
    return path.open("w", encoding="utf-8")


def write_journal_line(fh: IO[str], record: dict) -> None:
    fh.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")


def queried_domains(directory: Path = JOURNAL_DIR) -> set[str]:
    """Every domain already recorded in a run journal, so runs never repeat work.

    Truncation is tolerated: an interrupted run leaves a journal readable up to
    its last flush, and whatever it lost is simply queried again next time.
    """
    seen: set[str] = set()
    if not directory.is_dir():
        return seen
    for path in sorted(directory.glob(_JOURNAL_GLOB)):
        try:
            with open_journal(path) as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        domain = json.loads(line).get("domain")
                    except ValueError:
                        continue
                    if domain:
                        seen.add(domain)
        except (EOFError, OSError):
            continue
    return seen
