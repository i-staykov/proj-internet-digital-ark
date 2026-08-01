"""Per-(domain, year) English-website verification from archived page body text.

The governing rule for this round, feedback_v3 section 6:

    "a domain must belong to an English-language website or to a website where
    English accounts for more than 50% of reliably classified body text across
    the sampled captures for the relevant year"

applied "at website level, using archived page body text rather than the spelling
of the domain name or its top-level domain". Mixed-language, low-confidence and
no-content cases stay outside the annual files.

Three consequences shape this module.

**Language is not evidence.** Every existing `evidence_type` answers "did this
domain exist in this year". Language answers "what was this website in this
year", which is orthogonal: a domain can be perfectly evidenced and still
inadmissible. Putting language into `evidence` would corrupt a taxonomy that
`MASTER_TYPES`, the schema CHECK and four integrity checks depend on. Verdicts
land in `domain_language` instead, keyed on the same (domain, year) pair the rest
of the store uses.

**The verdict must be checkable.** Ding's own language table is, in his words, "a
provisional aggregate estimate ... using a TLD-stratified Common Crawl 2024-10
page-language prior and is not a per-domain historical-language verification",
and future reports "must replace the provisional estimate with archived-content
evidence". So every verdict records the exact snapshot URLs it read. A reviewer
can fetch them and re-run the classification. That is the whole difference
between this and a TLD prior.

**Bytes, not text.** Pages of this period are frequently latin-1, Shift-JIS or
GB2312 with no declared charset. Decoding them as UTF-8 turns Japanese into
mojibake, which then classifies as undetermined and quietly inflates the English
share. Snapshots are therefore fetched as bytes and decoded by
`charset_normalizer`, which is why this module has its own fetcher rather than
reusing the one in `cdx.py`.

Collection writes a journal and never opens the store, like the other engines.
"""

import csv
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from charset_normalizer import from_bytes
from loguru import logger

from ark.bulk import _sha256
from ark.cdx import (
    _THROTTLE_STATUSES,
    CDX_ENDPOINT,
    USER_AGENT,
    Fetch,
    RateGovernor,
    _fetch_retrying,
    _http_get,
)
from ark.expand import snapshot_url
from ark.journal import open_journal
from ark.metrics import record_metrics

# (status_code, body_bytes); status 0 means a transport error, which is retryable
FetchBytes = Callable[[str], tuple[int, bytes]]

VERDICT_ENGLISH = "english"
VERDICT_OTHER = "other"
VERDICT_UNDETERMINED = "undetermined"
ALL_VERDICTS = frozenset({VERDICT_ENGLISH, VERDICT_OTHER, VERDICT_UNDETERMINED})

# Below this many characters of stripped body text a capture is "not reliably
# classified" in the wording of section 6. Under-construction notices, image-only
# splash pages and framesets are common in this period and carry almost no text;
# language identification on a dozen words is noise presented as a measurement.
MIN_TEXT_CHARS = 200

# py3langid returns a normalized probability for its top language. Below this the
# capture counts as low-confidence, which section 6 also puts outside the annual
# files, so it is excluded from the share rather than counted as non-English.
MIN_CONFIDENCE = 0.50

# The share that admits a domain. Section 6 says "more than 50%", so this is a
# strict inequality and an exact half fails.
ENGLISH_THRESHOLD = 0.50

# Captures sampled per (domain, year). More samples cost linearly in fetches and
# buy less each time; three distinct pages is enough to catch a site whose front
# page is a language splash screen.
DEFAULT_SAMPLES = 3

# Index rows to consider before choosing which pages to fetch. Deliberately far
# larger than DEFAULT_SAMPLES: one index row is a few bytes of an existing
# response, a page fetch is a whole request against a service that has refused
# this project before. Asking for many candidates and fetching few is the one
# lever here that buys accuracy without buying traffic.
CANDIDATE_LIMIT = 40

# A capture larger than this is truncated before decoding. 1990s pages are small;
# anything much bigger is a database dump or a mislabelled binary, and reading it
# whole costs far more than the classification is worth.
MAX_BODY_BYTES = 2_000_000

DEFAULT_TIMEOUT = 45.0

# Why a pair failed the English standard, as a fixed vocabulary rather than free
# text. Ivo's instruction of 1 August is that every pair we *judged* and rejected
# must be documented per item with its reason, and a reviewer can only aggregate
# or audit those reasons if they are drawn from a closed set.
#
# The distinction these encode, and it is the important one: each of these means
# the archive was asked and answered. A pair the engine has not reached carries
# no reason at all and is reported as `unchecked`, never as a rejection.
REASON_NO_CAPTURE_IN_YEAR = "no_capture_in_year"
REASON_NO_HTML_CAPTURE = "no_readable_html_capture"
REASON_INSUFFICIENT_TEXT = "insufficient_text"
REASON_LOW_CONFIDENCE = "low_confidence"
REASON_NON_SITE_TEXT = "non_site_text"
REASON_OTHER_LANGUAGE = "other_language"
REASON_MIXED_BELOW_THRESHOLD = "mixed_below_threshold"
# Defensive. In the live flow captures that exist but cannot be read leave the
# pair unsettled rather than judged, which is the correct handling and is tested.
# The constant exists so `score_samples` has something honest to say if it is
# ever called with nothing.
REASON_CAPTURES_UNREADABLE = "captures_unreadable"

REASONS = (
    REASON_NO_CAPTURE_IN_YEAR,
    REASON_NO_HTML_CAPTURE,
    REASON_CAPTURES_UNREADABLE,
    REASON_INSUFFICIENT_TEXT,
    REASON_NON_SITE_TEXT,
    REASON_LOW_CONFIDENCE,
    REASON_OTHER_LANGUAGE,
    REASON_MIXED_BELOW_THRESHOLD,
)

_WHITESPACE = re.compile(r"\s+")
_SKIP_TAGS = frozenset({"script", "style", "noscript"})


def captures_url(domain: str, year: int, limit: int = CANDIDATE_LIMIT) -> str:
    """Query for distinct in-year HTML captures anywhere under one domain.

    `matchType=domain` reaches subdomains, because in this period the content
    usually lived at `www.` and the bare name often only redirected.
    `collapse=urlkey` asks the server for distinct pages rather than repeat
    captures of one page, so a small sample spans the site instead of sampling
    the same front page three times. The mimetype filter keeps images and
    archives out; classifying a GIF wastes a fetch and returns nothing.

    **`limit` is the number of candidates to consider, not the number of pages
    to fetch, and conflating the two was a real defect.** The limit used to be
    the sample count, so a run at `--samples 2` asked the index for two rows and
    then reported `captures_found: 2` no matter what the archive actually held.
    Measured on `adguys.com` 2000: the engine saw 2 captures and stored
    `undetermined`, while the same query at `limit=50` returns **33** captures
    including pages of 5,193 bytes. 869 of the 1,152 pairs with any capture,
    75.4%, were censored this way. One index row costs a few bytes of response;
    a page fetch costs a request. Asking for many and fetching few is close to
    free.

    `length` is requested so the caller can spend its fetches on the largest
    pages, which is the difference between reading a frameset and reading the
    site.
    """
    # The CDX API accepts repeated `filter` parameters and ANDs them, which a
    # dict cannot express, so the query is built as ordered pairs.
    query = urllib.parse.urlencode(
        [
            ("url", domain),
            ("matchType", "domain"),
            ("from", str(year)),
            ("to", str(year)),
            ("filter", "statuscode:200"),
            ("filter", "mimetype:text/html"),
            ("fl", "timestamp,original,length"),
            ("collapse", "urlkey"),
            ("limit", str(limit)),
        ]
    )
    return f"{CDX_ENDPOINT}?{query}"


def any_capture_url(domain: str, year: int) -> str:
    """Query for *any* in-year capture under a domain, with no filters at all.

    Used only to settle the difference between "the archive holds nothing here"
    and "the archive holds nothing that our filtered query asked for". Those are
    different claims and only the first one justifies recording a domain as
    having no capture in the year.

    Deliberately minimal: one field and one row, because the answer needed is
    just whether the result is empty. It is the cheapest question the CDX API
    will answer.

    **Not the same as `cdx.year_probe_url`, and they must not be merged.** That
    one filters on `statuscode:200`, which is correct where it is used, because
    there a match only ever admits a pair and a filtered question is the
    conservative direction. Here a match only ever *withholds* a rejection, so
    the same filter would point the caution the wrong way and put the domain
    back on the wrong side of the very claim this function exists to avoid.
    """
    query = urllib.parse.urlencode(
        [
            ("url", domain),
            ("matchType", "domain"),
            ("from", str(year)),
            ("to", str(year)),
            ("fl", "timestamp"),
            ("limit", "1"),
        ]
    )
    return f"{CDX_ENDPOINT}?{query}"


def parse_captures(body: str, year: int) -> list[tuple[str, str, int]]:
    """(timestamp, original_url, stored_length) from a CDX response.

    The length is the archived record's size as the index reports it. It is not
    the length of the body text, but it separates a 400-byte frameset from a
    5 KB page without spending a fetch to find out, and a missing or unparseable
    value sorts last rather than dropping the capture.
    """
    captures: list[tuple[str, str, int]] = []
    for line in body.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        timestamp, original = parts[0], parts[1]
        if len(timestamp) != 14 or not timestamp.isdigit():
            continue
        if int(timestamp[:4]) != year:
            continue
        length = 0
        if len(parts) > 2 and parts[2].isdigit():
            length = int(parts[2])
        captures.append((timestamp, original, length))
    return captures


def _http_get_bytes(url: str, timeout: float = DEFAULT_TIMEOUT) -> tuple[int, bytes]:
    """Fetch raw bytes, because the encoding is what we are about to detect."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (https)
            return response.status, response.read(MAX_BODY_BYTES)
    except urllib.error.HTTPError as exc:
        return exc.code, b""
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, b""


def bytes_fetcher(timeout: float = DEFAULT_TIMEOUT) -> FetchBytes:
    def fetch(url: str) -> tuple[int, bytes]:
        return _http_get_bytes(url, timeout)

    return fetch


def decode_page(raw: bytes) -> str:
    """Decode a captured page without assuming its charset.

    `charset_normalizer` sniffs the encoding from the bytes themselves. A page
    that declares nothing and is actually Shift-JIS decodes as Japanese here and
    as mojibake under a UTF-8 assumption, and mojibake classifies as
    undetermined, which would silently raise the measured English share.
    """
    if not raw:
        return ""
    best = from_bytes(raw).best()
    if best is not None:
        return str(best)
    return raw.decode("latin-1", "replace")


class _TextCollector(HTMLParser):
    """Body text of a page, dropping script and style content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.chunks.append(data)

    def error(self, message: str) -> None:  # pragma: no cover - HTMLParser hook
        return None


def body_text(html: str) -> str:
    """Visible text of a page, collapsed to single spaces.

    Markup of this era is frequently unclosed and misnested, so this uses the
    standard library's lenient parser and accepts whatever it recovers. A
    frameset page legitimately yields almost nothing, which is a no-content case
    rather than a parse failure.
    """
    collector = _TextCollector()
    try:
        collector.feed(html)
    except Exception:  # noqa: BLE001 - a malformed page must not end a run
        pass
    # Joined on a space, not concatenated: a tag boundary is a word boundary, and
    # running "Test" and "Hello" into "TestHello" invents n-grams that the
    # classifier then reads as evidence of some other language.
    return _WHITESPACE.sub(" ", " ".join(collector.chunks)).strip()


_identifier = None


def _classifier():  # pragma: no cover - exercised through classify_text
    """The py3langid model, loaded once and normalised to real probabilities.

    The default `classify` returns an unnormalised log-probability, which cannot
    be compared against a confidence threshold. `norm_probs=True` makes the
    second element a probability in [0, 1], which is what MIN_CONFIDENCE means.
    """
    global _identifier
    if _identifier is None:
        from py3langid.langid import MODEL_FILE, LanguageIdentifier

        _identifier = LanguageIdentifier.from_pickled_model(MODEL_FILE, norm_probs=True)
    return _identifier


# Phrases that mark a page as NOT a website: registrar parking, a frames
# notice, a placeholder. Each was found admitting a domain to the English annual
# files that had no site at all. `ajpca.com` served "ajpca.com currently has no
# web site" and scored english at confidence 1.000; `alpinvest.com` scored
# english 1.0 on a Netscape-frames notice while its other capture was 2,110
# characters of Dutch.
_NON_SITE_MARKERS = (
    "currently has no web site",
    "does not currently have a web site",
    "this domain is registered",
    "this domain name is registered",
    "domain is for sale",
    "this domain may be for sale",
    "under construction",
    "coming soon",
    "designed to be viewed by a browser",
    "browser which supports",
    "does not support frames",
    "your browser does not support frames",
    "no frames capable browser",
    "index of /",
    "default web site page",
    "welcome to your new web server",
)

# A marker inside a substantial page is a passing remark, not the whole page. A
# real site mentioning "under construction" in one corner carries far more text
# than a placeholder whose entire content is the notice.
_NON_SITE_MAX_CHARS = 1000


def is_non_site_text(text: str) -> bool:
    """Whether a page is a placeholder rather than a website.

    Section 6 admits "an English-language website". A registrar parking page is
    not a website in any sense the rule intends, and it is written in fluent
    English, so the classifier is confident and wrong. Rejecting these is the
    difference between measuring what a site was and measuring what its
    registrar's placeholder said.
    """
    if len(text) > _NON_SITE_MAX_CHARS:
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in _NON_SITE_MARKERS)


def classify_text(text: str) -> tuple[str | None, float]:
    """(language code, confidence) for one page, or (None, 0.0) if unusable.

    Returns None for text too short to classify, which section 6 calls "not
    reliably classified" and keeps out of the share entirely, and for a page
    that is a placeholder rather than a website.

    Classification runs on case-folded text. py3langid's model is trained on
    ordinary prose, and an all-capitals page is out of distribution for it:
    measured on one real capture, the same words scored 0.92 upper-case and
    1.000 lower-case, and a shoutier example in the corpus was confidently
    assigned Maltese. Folding costs nothing and only ever raises confidence.
    """
    if len(text) < MIN_TEXT_CHARS or is_non_site_text(text):
        return None, 0.0
    lang, confidence = _classifier().classify(text.lower())
    return str(lang), float(confidence)


def sample_rejection(text: str) -> str | None:
    """Why one capture cannot be counted, or None if it can.

    `classify_text` collapses "too short" and "not a website" into the same
    `(None, 0.0)`, which is right for scoring and useless for reporting: both
    arrive as `undetermined` and a reviewer cannot tell an under-construction
    page from a registrar parking page. This names them apart without changing
    any verdict.
    """
    if len(text) < MIN_TEXT_CHARS:
        return REASON_INSUFFICIENT_TEXT
    if is_non_site_text(text):
        return REASON_NON_SITE_TEXT
    return None


@dataclass
class Sample:
    """One classified capture behind a verdict."""

    url: str
    language: str | None
    confidence: float
    chars: int
    rejection: str | None = None


def score_samples(samples: Iterable[Sample]) -> dict:
    """Fold per-capture classifications into one (domain, year) verdict.

    Captures are weighted by the length of their classified text, so a
    substantial English page outweighs a one-line non-English redirect notice
    rather than each counting once. Only reliably classified captures enter the
    denominator, which is exactly what "more than 50% of reliably classified
    body text" says.
    """
    collected = list(samples)
    usable = [s for s in collected if s.language is not None and s.confidence >= MIN_CONFIDENCE]
    total = sum(s.chars for s in usable)
    if not usable or total == 0:
        return {
            "verdict": VERDICT_UNDETERMINED,
            "english_share": None,
            "samples": 0,
            "top_other": None,
            "reason": _undetermined_reason(collected),
        }
    by_language: dict[str, int] = {}
    for sample in usable:
        by_language[sample.language] = by_language.get(sample.language, 0) + sample.chars
    english = by_language.get("en", 0)
    share = english / total
    others = {lang: n for lang, n in by_language.items() if lang != "en"}
    top_other = max(others, key=lambda k: others[k]) if others else None
    admitted = share > ENGLISH_THRESHOLD
    # A site with no English at all and a site that is 45% English both fail, and
    # they fail differently. The second is the case section 6 calls "mixed", and
    # a reviewer weighing whether the 50% line sits in the right place needs to
    # see how many pairs are near it rather than nowhere near it.
    reason = None
    if not admitted:
        reason = REASON_OTHER_LANGUAGE if english == 0 else REASON_MIXED_BELOW_THRESHOLD
    return {
        "verdict": VERDICT_ENGLISH if admitted else VERDICT_OTHER,
        "english_share": round(share, 6),
        "samples": len(usable),
        "top_other": top_other,
        "reason": reason,
    }


def _undetermined_reason(collected: list[Sample]) -> str:
    """Which of the four undetermined cases this was.

    A pair can fail for more than one reason across its samples, so the reported
    one is the most common. Ties go to the order in `REASONS`, which puts the
    structural failures before the judgement calls, because "there was nothing to
    read" is a more useful thing to tell a reviewer than "what there was scored
    badly".
    """
    if not collected:
        return REASON_CAPTURES_UNREADABLE
    counts = Counter(s.rejection or REASON_LOW_CONFIDENCE for s in collected)
    return min(counts, key=lambda r: (-counts[r], REASONS.index(r) if r in REASONS else 99))


def pair_key(domain: str, year: int) -> str:
    """Journal key for a (domain, year), the unit this engine works in.

    `queried_domains` keys resumability on the record's `domain` field, so the
    composite goes there and the parts are repeated in their own fields for the
    ingester. `expand.py` does the same with a page URL.
    """
    return f"{domain}#{year}"


def classify_pair(
    domain: str,
    year: int,
    cdx_fetch: Fetch = _http_get,
    page_fetch: FetchBytes | None = None,
    governor: RateGovernor | None = None,
    *,
    samples: int = DEFAULT_SAMPLES,
    retries: int = 3,
) -> dict:
    """Verify one (domain, year) against archived body text.

    The record always states what happened, including failure, so a later run
    knows whether the question was answered or merely attempted.
    """
    gov = governor or RateGovernor()
    fetch_bytes = page_fetch or bytes_fetcher()
    record: dict = {
        "domain": pair_key(domain, year),
        "registered_domain": domain,
        "year": year,
        "status": 0,
        "verdict": VERDICT_UNDETERMINED,
        "english_share": None,
        "samples": 0,
        "top_other": None,
        "evidence_urls": [],
        "captures_found": 0,
        "fetch_failures": 0,
        "reason": None,
    }

    # CANDIDATE_LIMIT, not `samples`: the index limit is how many captures to
    # CHOOSE FROM, and passing the fetch count here is what censored
    # `captures_found` and starved the selection.
    status, body = _fetch_retrying(
        captures_url(domain, year, CANDIDATE_LIMIT), cdx_fetch, gov, retries
    )
    if status != 200:
        record["status"] = status
        return record

    captures = parse_captures(body, year)
    record["captures_found"] = len(captures)
    # Spend the fetches on the largest archived records. The index reports each
    # record's stored size, so the biggest pages can be picked without fetching
    # anything, and page size is the best available proxy for "has body text".
    # Taking the first N rows instead sampled whatever sorted first by URL key,
    # which is how framesets and redirect stubs came to dominate the sample.
    captures.sort(key=lambda c: c[2], reverse=True)
    if not captures:
        # **The query above is filtered, so its emptiness is not the claim we
        # want to record.** It asks for captures that are `statuscode:200` and
        # `mimetype:text/html`; a year in which the archive holds only redirects,
        # plain text, or records it labelled differently comes back empty from a
        # question that was never "does anything exist here".
        #
        # Writing that down as "no capture in this year" would be disqualifying a
        # domain on an assumption, which is the one thing this engine must not
        # do. So ask the unfiltered question before concluding. It costs one
        # cheap index request on the ~23% of pairs that reach this branch, and it
        # turns a guess into a measurement.
        probe_status, probe_body = _fetch_retrying(
            any_capture_url(domain, year), cdx_fetch, gov, retries
        )
        if probe_status != 200:
            # The probe failed, so we still do not know. Leave the pair
            # unsettled rather than record a verdict we cannot support.
            record["status"] = probe_status
            return record
        record["status"] = 200
        record["reason"] = (
            REASON_NO_HTML_CAPTURE if probe_body.strip() else REASON_NO_CAPTURE_IN_YEAR
        )
        return record

    collected: list[Sample] = []
    urls: list[str] = []
    for timestamp, original, _length in captures[:samples]:
        target = snapshot_url(timestamp, original)
        gov.wait()
        page_status, raw = fetch_bytes(target)
        if page_status != 200 or not raw:
            record["fetch_failures"] += 1
            # A transport error (status 0) backs the pace off just like an
            # explicit 429. When the archive stops wanting our traffic it does
            # not always say so politely: on 1 August it began refusing TCP
            # connections outright while ping and DNS stayed healthy, and
            # because status 0 was not a throttle signal the run kept dialling
            # at full pace. Treating silence as refusal is the safe reading.
            if page_status in _THROTTLE_STATUSES or page_status == 0:
                gov.on_throttle()
            continue
        gov.on_success()
        text = body_text(decode_page(raw))
        language, confidence = classify_text(text)
        collected.append(Sample(target, language, confidence, len(text), sample_rejection(text)))
        urls.append(target)

    if not collected and record["fetch_failures"]:
        # Captures exist but none could be read, so nothing was learned and the
        # pair stays eligible for a later run rather than being recorded as
        # undetermined on the strength of a transport failure.
        record["status"] = 0
        return record

    record["status"] = 200
    record["evidence_urls"] = urls
    record["text_chars"] = sum(s.chars for s in collected)
    record.update(score_samples(collected))
    return record


def answered(record: dict) -> bool:
    """Whether a journal record settles a (domain, year).

    Only a completed question settles anything. A CDX failure, or captures that
    exist but could not be fetched, means the question never landed; recording
    that as `undetermined` would permanently exclude a pair that might well be
    English. This predicate is the same guard the RDAP engine needed after it
    marked 12,888 domains done without ever having answered them.
    """
    return record.get("status") == 200


# --- choosing what to classify ----------------------------------------------

LANG_SOURCE_NAME = "lang_verification"
JOURNAL_DIR = Path("data/raw/lang")
JOURNAL_PREFIX = "lang"
TARGETS_PATH = JOURNAL_DIR / "lang_targets.txt"

# Within the capture-backed group, work the years whose additions are largest
# first, so a run that stops early has still produced the most admissible pairs.
YEAR_PRIORITY = (2000, 2001, 1998, 1996, 1997, 1999)


def write_lang_targets(conn, path: Path = TARGETS_PATH) -> dict:
    """Write every net-new (domain, year) that has no language verdict yet.

    The work list is the marginal contribution, not the whole store: feedback
    section 6.1 asks for the language profile of "records newly added by this
    submission", and the baseline's own language mix is Ding's to measure, not
    ours to re-derive at several page fetches per pair.

    **Pairs that already have `cdx_timestamp` evidence come first**, and this
    ordering is the difference between a useful run and a wasted one. Such a pair
    provably has an in-year capture, so there is body text to read and it can
    earn an `english` verdict. A pair evidenced only by a registry creation date
    has no such guarantee, and measurement says the guarantee usually fails:
    across the 32,698 additions, 1998, 2000 and 2001 are 86 to 96% capture-backed
    while 1996, 1997 and 1999 are 0.0 to 5.9%. A first calibration run spent its
    whole budget on 1996 and returned 74 answers, every one of them
    `undetermined` with zero captures found.

    Requests against the archive are the scarce resource, so they go where a
    verdict can actually change the admitted set.

    **Within that group the years are interleaved rather than worked in order.**
    A run reaches only a fraction of the list, and feedback 6.1 requires the
    language mix reported *per year*. Working 2000 to exhaustion before touching
    2001 would spend a whole night producing one year's rate; round-robin over
    the years produces a usable rate for each of them from the same budget. The
    year priority then only decides who wins the remainder.
    """
    order = " ".join(f"WHEN {year} THEN {i}" for i, year in enumerate(YEAR_PRIORITY))
    query = f"""
        SELECT domain, assigned_year, has_capture FROM (
            SELECT dy.domain, dy.assigned_year,
                   EXISTS (
                       SELECT 1 FROM evidence c
                       WHERE c.domain = dy.domain AND c.evidence_year = dy.assigned_year
                         AND c.evidence_type = 'cdx_timestamp'
                   ) AS has_capture,
                   row_number() OVER (
                       PARTITION BY dy.assigned_year ORDER BY dy.domain
                   ) AS rank_in_year
            FROM domain_year dy
            WHERE NOT EXISTS (
                SELECT 1 FROM evidence p
                WHERE p.domain = dy.domain AND p.evidence_year = dy.assigned_year
                  AND p.evidence_type = 'prior_reused'
            )
            AND NOT EXISTS (
                SELECT 1 FROM domain_language dl
                WHERE dl.domain = dy.domain AND dl.assigned_year = dy.assigned_year
            )
        )
        ORDER BY has_capture DESC, rank_in_year,
                 CASE assigned_year {order} ELSE 9 END, domain
    """  # noqa: S608 (order clause is built from an integer tuple)
    rows = conn.execute(query).fetchall()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for domain, year, _has_capture in rows:
            fh.write(f"{domain}\t{year}\n")
    by_year: Counter = Counter(year for _, year, _ in rows)
    stats = {
        "targets": len(rows),
        # the ceiling on how many verdicts can be anything but undetermined
        "capture_backed": sum(1 for _, _, has_capture in rows if has_capture),
        **{f"year_{y}": n for y, n in sorted(by_year.items())},
    }
    logger.info(f"lang-targets: {stats} -> {path}")
    return stats


def read_targets(lines: Iterable[str]) -> list[tuple[str, int]]:
    """Parse a `domain<TAB>year` work list, skipping blanks and comments."""
    targets: list[tuple[str, int]] = []
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        parts = text.replace("\t", " ").split()
        if len(parts) < 2 or not parts[1].isdigit():
            continue
        targets.append((parts[0], int(parts[1])))
    return targets


# --- reporting --------------------------------------------------------------

NETNEW_ENGLISH_DIR = Path("output/netnew_english")
NETNEW_UNVERIFIED_DIR = Path("output/netnew_unverified")
DISQUALIFIED_PATH = Path("output/disqualified.csv")
LANGUAGE_SUMMARY_PATH = Path("output/language_summary.csv")

# A judged rejection whose reason pre-dates the reason vocabulary. Distinct from
# an empty cell, which would read as "no reason applies", and distinct from
# `unchecked`, which is not a rejection at all.
REASON_NOT_RECORDED = "not_recorded"

# The marginal contribution, which is the population feedback 6.1 asks about.
_NOT_IN_BASELINE = """
    NOT EXISTS (
        SELECT 1 FROM evidence p
        WHERE p.domain = dy.domain AND p.evidence_year = dy.assigned_year
          AND p.evidence_type = 'prior_reused'
    )
"""


# One row per net-new (domain, year), carrying its verdict if it has one. Both
# halves of the partition are cut from this, which is why they cannot disagree:
# a pair appears in exactly one of them because the CASE is exhaustive.
_PARTITION_SQL = f"""
    SELECT dy.domain,
           dy.assigned_year AS year,
           CASE WHEN dl.verdict = 'english' THEN 'english' ELSE 'unverified' END AS side,
           CASE WHEN dl.verdict IS NULL THEN 'unchecked'
                WHEN dl.verdict = 'english' THEN 'verified'
                ELSE 'disqualified' END AS status,
           dl.verdict AS verdict,
           coalesce(dl.reason,
                    CASE WHEN dl.verdict IS NULL THEN ''
                         ELSE '{REASON_NOT_RECORDED}' END) AS reason,
           dl.english_share AS english_share,
           dl.top_other AS top_other,
           coalesce(dl.samples, 0) AS samples,
           coalesce(dl.evidence_urls, '') AS snapshot_urls
    FROM domain_year dy
    LEFT JOIN domain_language dl
      ON dl.domain = dy.domain AND dl.assigned_year = dy.assigned_year
    WHERE {_NOT_IN_BASELINE}
"""


def write_partitioned_annual_files(
    conn,
    english_dir: Path = NETNEW_ENGLISH_DIR,
    unverified_dir: Path = NETNEW_UNVERIFIED_DIR,
    register_path: Path = DISQUALIFIED_PATH,
) -> dict[str, int]:
    """Write the two disjoint sets, plus the per-item register of rejections.

    **Disjoint is the point.** The previous shape shipped `netnew/` holding every
    addition and `netnew_english/` holding a subset of those same pairs, so the
    two overlapped and a reviewer adding them up would double-count. From this
    round the deliverable is a partition: a pair is English-verified or it is
    not, it appears in exactly one side, and the two sides sum to the total.
    Ding merges against the baseline himself, so nothing here is pre-merged.

    Three distinctions the files preserve, because collapsing any of them would
    overstate what we know:

    - `english` means archived body text for that year was read and was more
      than half English. Nothing else earns it.
    - `disqualified` means the archive was asked and answered, and the pair
      failed. Every one carries a reason from a closed vocabulary and is listed
      individually in the register.
    - `unchecked` means the engine has not reached the pair. **No claim is made
      about its language**, and in particular no claim is made about whether the
      archive holds a capture for it. Guessing there would be exactly the
      assumption this engine exists to avoid.
    """
    english_dir.mkdir(parents=True, exist_ok=True)
    unverified_dir.mkdir(parents=True, exist_ok=True)
    register_path.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}

    for year in range(1996, 2002):
        base = f"SELECT * FROM ({_PARTITION_SQL}) WHERE year = {year}"  # noqa: S608

        english = f"SELECT DISTINCT domain FROM ({base}) WHERE side = 'english' ORDER BY domain"  # noqa: S608
        conn.execute(f"COPY ({english}) TO '{english_dir / f'{year}.txt'}' (HEADER false)")
        english_csv = (
            "SELECT domain, year, english_share, samples, snapshot_urls "  # noqa: S608
            f"FROM ({base}) WHERE side = 'english' ORDER BY domain"
        )
        conn.execute(f"COPY ({english_csv}) TO '{english_dir / f'{year}.csv'}' (HEADER true)")

        unverified = (
            f"SELECT DISTINCT domain FROM ({base}) WHERE side = 'unverified' ORDER BY domain"  # noqa: S608
        )
        conn.execute(f"COPY ({unverified}) TO '{unverified_dir / f'{year}.txt'}' (HEADER false)")
        unverified_csv = (
            "SELECT domain, year, status, reason, english_share, top_other, "  # noqa: S608
            f"snapshot_urls FROM ({base}) WHERE side = 'unverified' ORDER BY status, domain"
        )
        conn.execute(f"COPY ({unverified_csv}) TO '{unverified_dir / f'{year}.csv'}' (HEADER true)")

        for label, side in (("english", "english"), ("unverified", "unverified")):
            counts[f"{label}_{year}"] = conn.execute(
                f"SELECT count(*) FROM ({base}) WHERE side = '{side}'"  # noqa: S608
            ).fetchone()[0]

    register = (
        "SELECT domain, year, verdict, reason, english_share, top_other, samples, "  # noqa: S608
        f"snapshot_urls FROM ({_PARTITION_SQL}) WHERE status = 'disqualified' "
        "ORDER BY year, reason, domain"
    )
    conn.execute(f"COPY ({register}) TO '{register_path}' (HEADER true)")
    counts["disqualified"] = conn.execute(
        f"SELECT count(*) FROM ({_PARTITION_SQL}) WHERE status = 'disqualified'"  # noqa: S608
    ).fetchone()[0]
    counts["unchecked"] = conn.execute(
        f"SELECT count(*) FROM ({_PARTITION_SQL}) WHERE status = 'unchecked'"  # noqa: S608
    ).fetchone()[0]
    return counts


def language_summary(conn) -> list[dict]:
    """Per-year and total language mix of the marginal additions.

    Feedback 6.1 requires English, named other, undetermined and
    syntax-anomalous counts, per year and for the six-year total, reported for
    both domain-year records and cross-year unique domains. `unclassified` is
    ours rather than theirs: a pair the engine has not reached yet is not the
    same claim as one it judged undetermined, and collapsing the two would
    overstate how much of the list has actually been read.
    """
    rows = conn.execute(f"""
        SELECT dy.assigned_year,
               coalesce(dl.verdict, 'unclassified') AS verdict,
               count(*) AS pairs
        FROM domain_year dy
        LEFT JOIN domain_language dl
          ON dl.domain = dy.domain AND dl.assigned_year = dy.assigned_year
        WHERE {_NOT_IN_BASELINE}
        GROUP BY 1, 2
    """).fetchall()  # noqa: S608 (no interpolated user input)
    by_year: dict[int, Counter] = {}
    for year, verdict, pairs in rows:
        by_year.setdefault(year, Counter())[verdict] = pairs

    summary = []
    for year in sorted(by_year):
        counts = by_year[year]
        added = sum(counts.values())
        summary.append(
            {
                "year": year,
                "added_records": added,
                "english": counts.get("english", 0),
                "other": counts.get("other", 0),
                "undetermined": counts.get("undetermined", 0),
                "unclassified": counts.get("unclassified", 0),
            }
        )
    total = {
        "year": "TOTAL",
        "added_records": sum(r["added_records"] for r in summary),
        "english": sum(r["english"] for r in summary),
        "other": sum(r["other"] for r in summary),
        "undetermined": sum(r["undetermined"] for r in summary),
        "unclassified": sum(r["unclassified"] for r in summary),
    }
    summary.append(total)

    # Cross-year unique domains, which 6.1 asks for as a separate measure. A
    # domain counts as English if any of its net-new years is English, since the
    # standard admits per (domain, year) and the unique count is a roll-up.
    unique = conn.execute(f"""
        SELECT count(DISTINCT dy.domain) FILTER (WHERE dl.verdict = 'english'),
               count(DISTINCT dy.domain) FILTER (WHERE dl.verdict = 'other'),
               count(DISTINCT dy.domain) FILTER (WHERE dl.verdict = 'undetermined'),
               count(DISTINCT dy.domain)
        FROM domain_year dy
        LEFT JOIN domain_language dl
          ON dl.domain = dy.domain AND dl.assigned_year = dy.assigned_year
        WHERE {_NOT_IN_BASELINE}
    """).fetchone()  # noqa: S608 (no interpolated user input)
    summary.append(
        {
            "year": "UNIQUE_DOMAINS",
            "added_records": unique[3],
            "english": unique[0],
            "other": unique[1],
            "undetermined": unique[2],
            "unclassified": None,
        }
    )
    return summary


def write_language_summary(conn, path: Path = LANGUAGE_SUMMARY_PATH) -> list[dict]:
    """Write the 6.1 language table as CSV and return its rows."""
    rows = language_summary(conn)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "year",
                "added_records",
                "english",
                "other",
                "undetermined",
                "unclassified",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    logger.info(f"language summary -> {path}")
    return rows


def format_language_summary(rows: list[dict]) -> str:
    """A readable version of the 6.1 table for the terminal and the report."""
    header = f"{'year':<15}{'added':>10}{'english':>10}{'other':>10}{'undet':>10}{'unclass':>10}"
    lines = [header, "-" * len(header)]
    for row in rows:
        unclassified = "-" if row["unclassified"] is None else f"{row['unclassified']:,}"
        lines.append(
            f"{str(row['year']):<15}{row['added_records']:>10,}{row['english']:>10,}"
            f"{row['other']:>10,}{row['undetermined']:>10,}{unclassified:>10}"
        )
    return "\n".join(lines)


# --- turning journals into verdicts -----------------------------------------


def iter_verdicts(path: Path, stats: Counter) -> Iterator[dict]:
    """Yield one verdict row per settled (domain, year) in a journal."""
    try:
        with open_journal(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                stats["journal_lines"] += 1
                try:
                    record = json.loads(line)
                except ValueError:
                    stats["unparseable_line"] += 1
                    continue
                if not answered(record):
                    stats["unanswered"] += 1
                    continue
                domain = record.get("registered_domain")
                year = record.get("year")
                verdict = record.get("verdict")
                if not domain or not isinstance(year, int) or verdict not in ALL_VERDICTS:
                    stats["malformed"] += 1
                    continue
                stats[f"verdict_{verdict}"] += 1
                yield {
                    "domain": domain,
                    "assigned_year": year,
                    "verdict": verdict,
                    "english_share": record.get("english_share"),
                    "samples": record.get("samples") or 0,
                    "top_other": record.get("top_other"),
                    "evidence_urls": " ".join(record.get("evidence_urls") or []),
                    # Absent from journals written before the reason vocabulary
                    # existed. Those verdicts stay valid; they just cannot say
                    # why, and the export labels them so rather than guessing.
                    "reason": record.get("reason"),
                }
    except (EOFError, OSError):
        # journal from an interrupted run; everything before the last flush was
        # already yielded, and the missing tail is re-queried on the next run
        stats["truncated_tail"] += 1


def ingest_language_journal(conn, path: Path) -> dict:
    """Fold one `ark lang` journal into `domain_language`.

    Ledgered by content hash like every other source file, so a re-ingest of the
    same bytes is a no-op and a changed file is refused rather than silently
    double-counted.

    A verdict is replaced rather than ignored when the same pair is classified
    again, because a later run may have reached captures an earlier one could
    not. This is the opposite of the evidence tables, where the first assignment
    wins: evidence accumulates, whereas a language verdict is a current best
    reading of the same underlying pages.
    """
    marker = path.name
    sha256 = _sha256(path)
    ledgered = conn.execute(
        "SELECT sha256 FROM ingested_file WHERE source_name = ? AND file_name = ?",
        [LANG_SOURCE_NAME, marker],
    ).fetchone()
    if ledgered:
        if ledgered[0] != sha256:
            raise ValueError(
                f"{marker}: ledgered with different content (sha256 mismatch); "
                "rename the file or clear its ledger row before re-ingesting"
            )
        logger.info(f"{marker}: already ingested, skipping")
        return {"file": marker, "skipped": True}

    stats: Counter = Counter()
    rows = list(iter_verdicts(path, stats))
    # A verdict about a domain the store does not hold would violate the foreign
    # key. That should not happen, since the work list comes from the store, but
    # a stale journal must not abort the whole ingest.
    known: set[str] = set()
    if rows:
        placeholders = ",".join("?" * len(rows))
        known = {
            r[0]
            for r in conn.execute(
                f"SELECT domain FROM domain WHERE domain IN ({placeholders})",  # noqa: S608
                [r["domain"] for r in rows],
            ).fetchall()
        }
    written = 0
    for row in rows:
        if row["domain"] not in known:
            stats["unknown_domain"] += 1
            continue
        conn.execute(
            "DELETE FROM domain_language WHERE domain = ? AND assigned_year = ?",
            [row["domain"], row["assigned_year"]],
        )
        conn.execute(
            "INSERT INTO domain_language (domain, assigned_year, verdict, english_share, "
            "samples, top_other, evidence_urls, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                row["domain"],
                row["assigned_year"],
                row["verdict"],
                row["english_share"],
                row["samples"],
                row["top_other"],
                row["evidence_urls"],
                row["reason"],
            ],
        )
        written += 1
    stats["verdicts_written"] = written
    conn.execute(
        "INSERT INTO ingested_file (source_name, file_name, sha256, record_rows) "
        "VALUES (?, ?, ?, ?)",
        [LANG_SOURCE_NAME, marker, sha256, written],
    )
    summary = {"file": marker, "skipped": False, **dict(stats)}
    logger.info(str(summary))
    record_metrics(conn, "ingest-lang", marker, summary)
    return summary
