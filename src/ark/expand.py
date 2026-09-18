"""Expand one source into more domains by reading the pages it points at.

The download-and-extract half of the brief's "How to Expand One Source into More Domains"
cycle; the CDX engine validates and the round counter on a domain row feeds back.

**A link is a claim by the LINKING page, not by the linked host.** Dead links, typos and
names registered only later are all common, so an extracted host is candidate-only and
cannot assign a year on its own.

**The exception the brief grants is a curated directory page**, where an editor listed a
site in a dated catalogue and the capture date is item-level evidence for every entry. That
cannot be detected from markup, so it is asserted PER SEED: a seed marked as a directory
yields `dated_directory`, everything else `link_target`.

Snapshots are fetched with the `id_` modifier, which serves the original stored bytes, so
the hrefs are the author's rather than Wayback's redirects. HTML of this era is frequently
malformed, so parsing uses the lenient `HTMLParser` and takes only `href` attributes.
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


def unwrap_redirect(url: str) -> str:
    """The real target inside a click-tracking wrapper, or the url unchanged.

    Portals of the period routed outbound links through a counter, carrying the target
    inside the wrapper:

        http://srd.yahoo.com/goo/Business/*http://www.example.com/

    Left unhandled this is a TOTAL loss: the wrapper's registrable is the page's own domain,
    so every entry is discarded as a self-link and the page reports zero outbound domains,
    which reads as a barren source.

    Take the LAST embedded scheme, not the first, because the wrapper begins with one.
    Percent-encoded targets are unquoted ONLY ONCE: a target may carry an encoded query.
    """
    candidate = url
    if "%3a%2f%2f" in url.lower() or "%3A//" in url:
        candidate = urllib.parse.unquote(url)
    lowered = candidate.lower()
    cut = max(lowered.rfind("http://", 1), lowered.rfind("https://", 1))
    return candidate[cut:] if cut > 0 else candidate


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
        domain = to_registrable(unwrap_redirect(absolute))
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

    The brief lets a curated directory page's capture date evidence every domain on it,
    which is sound for the page and unsound for the parser: archived HTML carries
    transcription typos, this route having produced `arvard.edu` from a `harvard.edu` link
    plus `gov.edu` and `gintysuooly.com`, roughly 40% of never-before-seen names.

    So a name some other source already attests stays curated and its capture date evidences
    the year; a name appearing only here is emitted as an ordinary outbound link, which the
    loader routes to the candidate pool. A statement about corroboration, not about the
    page, and it discards nothing.
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
