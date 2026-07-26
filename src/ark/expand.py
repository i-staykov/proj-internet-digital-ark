"""Expand one source into more domains by reading the pages it points at.

Brief section VII asks for a repeated cycle rather than a single pass: take a
source, extract hosts, validate them against a time-evidence service, download
the pages, extract the links those pages carry, and feed the new hosts back into
the next round. This module is the download-and-extract half; the validation half
is the CDX engine, and the feed-back is the round counter on a domain row.

Two things decide what an extracted link is worth.

A link is a claim by the *linking* page, not by the linked host. A page captured
in 1998 that links to `example.com` shows that its author believed the site
existed, which is not the same as the archive holding a capture of it. Dead
links, typographical errors and names registered only later are all common. So an
extracted host is candidate-only by default and cannot assign a year on its own.

The exception the brief grants is a curated directory page: where a
human editor listed a site in a dated catalogue, the page's capture date is
item-level evidence for every entry on it, with no further verification needed.
That cannot be detected from markup, so it is asserted per seed rather than
guessed: a seed marked as a directory yields `dated_directory` evidence, and
everything else yields `link_target` candidates.

Snapshots are fetched with the `id_` modifier, which serves the original stored
bytes instead of a rewritten page, so the hrefs are the ones the author wrote
rather than Wayback's redirects.

HTML of this era is frequently malformed, so parsing uses the standard library's
lenient `HTMLParser` and takes only `href` attributes. A full DOM parser would
only be needed to tell a catalogue entry from a navigation link structurally,
which is exactly the judgement this module declines to make.
"""

import urllib.parse
from html.parser import HTMLParser

from ark.canonical import to_registrable
from ark.cdx import CDX_ENDPOINT, Fetch, RateGovernor, _fetch_retrying, _http_get

SNAPSHOT_BASE = "https://web.archive.org/web"


class _HrefCollector(HTMLParser):
    """Collect every href on a page, tolerating the malformed markup of the era."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.hrefs.append(value)

    def error(self, message: str) -> None:  # pragma: no cover - HTMLParser hook
        return None


def outbound_domains(html: str, page_url: str) -> list[str]:
    """Registrable domains linked from a page, excluding the page's own domain.

    Relative and fragment-only links resolve to the page itself and drop out with
    it, which is what makes this an *outbound* link extractor.
    """
    collector = _HrefCollector()
    try:
        collector.feed(html)
    except Exception:  # noqa: BLE001 - a malformed page must not end a run
        pass
    own = to_registrable(page_url)
    found: dict[str, None] = {}
    for href in collector.hrefs:
        absolute = urllib.parse.urljoin(page_url, href.strip())
        if not absolute.lower().startswith(("http://", "https://")):
            continue
        domain = to_registrable(absolute)
        if domain is None or domain == own:
            continue
        found[domain] = None
    return list(found)


def page_captures_url(url: str, first: int, last: int, limit: int = 5) -> str:
    """Query for in-window captures of one exact page, newest-first not required."""
    query = urllib.parse.urlencode(
        {
            "url": url,
            "from": str(first),
            "to": str(last),
            "filter": "statuscode:200",
            "fl": "timestamp",
            "collapse": "timestamp:4",
            "limit": str(limit),
        }
    )
    return f"{CDX_ENDPOINT}?{query}"


def snapshot_url(timestamp: str, url: str) -> str:
    """The original stored bytes of a capture, not a rewritten page."""
    return f"{SNAPSHOT_BASE}/{timestamp}id_/{url}"


def expand_page(
    url: str,
    first: int,
    last: int,
    fetch: Fetch = _http_get,
    governor: RateGovernor | None = None,
    *,
    curated: bool = False,
    retries: int = 3,
    per_page_captures: int = 2,
) -> list[dict]:
    """Fetch in-window captures of one page and return a journal record each.

    One record per capture, because a directory page captured in both 1998 and
    2000 evidences its entries for each of those years separately, which is the
    per-year rule applied to this route rather than an exception to it.
    """
    gov = governor or RateGovernor()
    status, body = _fetch_retrying(
        page_captures_url(url, first, last, per_page_captures), fetch, gov, retries
    )
    if status != 200:
        return [
            {
                "page_url": url,
                "status": status,
                "timestamp": None,
                "year": None,
                "curated": curated,
                "domains": [],
            }
        ]

    stamps = [line.strip() for line in body.splitlines() if line.strip().isdigit()]
    records = []
    for stamp in stamps[:per_page_captures]:
        year = int(stamp[:4])
        if not first <= year <= last:
            continue
        page_status, page_body = _fetch_retrying(snapshot_url(stamp, url), fetch, gov, retries)
        records.append(
            {
                "page_url": url,
                "status": page_status,
                "timestamp": stamp,
                "year": year,
                "curated": curated,
                "domains": outbound_domains(page_body, url) if page_status == 200 else [],
            }
        )
    if not records:
        records.append(
            {
                "page_url": url,
                "status": 200,
                "timestamp": None,
                "year": None,
                "curated": curated,
                "domains": [],
            }
        )
    return records


def answered(record: dict) -> bool:
    """Whether a record settles a page, so a later round can skip it.

    A 200 settles it even with no links found, because "this page carries no
    outbound links" is a finding. A transport failure or 5xx does not.
    """
    return record.get("status") == 200


def read_seeds(lines: list[str]) -> list[tuple[str, bool]]:
    """Parse seed lines into (url, curated) pairs.

    A line is a URL, optionally followed by a tab and the word `directory` to
    assert that the page is a curated catalogue whose capture date evidences its
    entries. The assertion is deliberately explicit: it grants master evidence,
    so it should be a decision on the record rather than a guess from markup.
    """
    seeds = []
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        parts = text.split("\t")
        url = parts[0].strip()
        curated = len(parts) > 1 and parts[1].strip().lower() == "directory"
        if url:
            seeds.append((url, curated))
    return seeds


def split_by_corroboration(records: list[dict], known: set[str]) -> tuple[list[dict], list[dict]]:
    """Split expansion records into the corroborated half and the rest.

    The brief lets a curated directory page's capture date evidence every
    domain listed on it. That is sound for the page and unsound for the parser:
    archived HTML carries transcription typos, and this route has produced
    `arvard.edu` from a `harvard.edu` link, plus `gov.edu` and `gintysuooly.com`.
    A sample of the same route measured roughly 40% of never-before-seen names
    as errors, so asserting them would trade precision for a handful of domains.

    A name some other source already attests is therefore kept curated, and its
    capture date evidences the year. A name appearing only here is emitted as an
    ordinary outbound link, which the loader routes to the candidate pool to earn
    its own evidence. The split is a statement about corroboration, not about the
    page, and it never discards anything.
    """
    corroborated: list[dict] = []
    uncorroborated: list[dict] = []
    for record in records:
        listed = record.get("domains") or []
        seen = [d for d in listed if d in known]
        unseen = [d for d in listed if d not in known]
        if seen:
            corroborated.append({**record, "domains": seen, "curated": True})
        if unseen:
            uncorroborated.append({**record, "domains": unseen, "curated": False})
    return corroborated, uncorroborated
