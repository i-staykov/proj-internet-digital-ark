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

# A capture larger than this is truncated before decoding. 1990s pages are small;
# anything much bigger is a database dump or a mislabelled binary, and reading it
# whole costs far more than the classification is worth.
MAX_BODY_BYTES = 2_000_000

DEFAULT_TIMEOUT = 45.0

_WHITESPACE = re.compile(r"\s+")
_SKIP_TAGS = frozenset({"script", "style", "noscript"})


def captures_url(domain: str, year: int, limit: int = DEFAULT_SAMPLES) -> str:
    """Query for distinct in-year HTML captures anywhere under one domain.

    `matchType=domain` reaches subdomains, because in this period the content
    usually lived at `www.` and the bare name often only redirected.
    `collapse=urlkey` asks the server for distinct pages rather than repeat
    captures of one page, so a small sample spans the site instead of sampling
    the same front page three times. The mimetype filter keeps images and
    archives out; classifying a GIF wastes a fetch and returns nothing.
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
            ("fl", "timestamp,original"),
            ("collapse", "urlkey"),
            ("limit", str(limit)),
        ]
    )
    return f"{CDX_ENDPOINT}?{query}"


def parse_captures(body: str, year: int) -> list[tuple[str, str]]:
    """(timestamp, original_url) pairs from a `fl=timestamp,original` response."""
    captures: list[tuple[str, str]] = []
    for line in body.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        timestamp, original = parts[0], parts[1]
        if len(timestamp) != 14 or not timestamp.isdigit():
            continue
        if int(timestamp[:4]) != year:
            continue
        captures.append((timestamp, original))
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


def classify_text(text: str) -> tuple[str | None, float]:
    """(language code, confidence) for one page, or (None, 0.0) if unusable.

    Returns None for text too short to classify, which section 6 calls "not
    reliably classified" and keeps out of the share entirely.
    """
    if len(text) < MIN_TEXT_CHARS:
        return None, 0.0
    lang, confidence = _classifier().classify(text)
    return str(lang), float(confidence)


@dataclass
class Sample:
    """One classified capture behind a verdict."""

    url: str
    language: str | None
    confidence: float
    chars: int


def score_samples(samples: Iterable[Sample]) -> dict:
    """Fold per-capture classifications into one (domain, year) verdict.

    Captures are weighted by the length of their classified text, so a
    substantial English page outweighs a one-line non-English redirect notice
    rather than each counting once. Only reliably classified captures enter the
    denominator, which is exactly what "more than 50% of reliably classified
    body text" says.
    """
    usable = [s for s in samples if s.language is not None and s.confidence >= MIN_CONFIDENCE]
    total = sum(s.chars for s in usable)
    if not usable or total == 0:
        return {
            "verdict": VERDICT_UNDETERMINED,
            "english_share": None,
            "samples": 0,
            "top_other": None,
        }
    by_language: dict[str, int] = {}
    for sample in usable:
        by_language[sample.language] = by_language.get(sample.language, 0) + sample.chars
    english = by_language.get("en", 0)
    share = english / total
    others = {lang: n for lang, n in by_language.items() if lang != "en"}
    top_other = max(others, key=lambda k: others[k]) if others else None
    return {
        "verdict": VERDICT_ENGLISH if share > ENGLISH_THRESHOLD else VERDICT_OTHER,
        "english_share": round(share, 6),
        "samples": len(usable),
        "top_other": top_other,
    }


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
    }

    status, body = _fetch_retrying(captures_url(domain, year, samples), cdx_fetch, gov, retries)
    if status != 200:
        record["status"] = status
        return record

    captures = parse_captures(body, year)
    record["captures_found"] = len(captures)
    if not captures:
        # The archive holds nothing for this domain in this year, so there is no
        # body text to judge and the pair is undetermined. This is a real answer
        # and settles the pair: the archive's index for a past year does not
        # change, so re-asking would return the same emptiness.
        record["status"] = 200
        return record

    collected: list[Sample] = []
    urls: list[str] = []
    for timestamp, original in captures[:samples]:
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
        collected.append(Sample(target, language, confidence, len(text)))
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
    """
    order = " ".join(f"WHEN {year} THEN {i}" for i, year in enumerate(YEAR_PRIORITY))
    query = f"""
        SELECT dy.domain, dy.assigned_year,
               EXISTS (
                   SELECT 1 FROM evidence c
                   WHERE c.domain = dy.domain AND c.evidence_year = dy.assigned_year
                     AND c.evidence_type = 'cdx_timestamp'
               ) AS has_capture
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
        ORDER BY has_capture DESC, CASE dy.assigned_year {order} ELSE 9 END, dy.domain
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
LANGUAGE_SUMMARY_PATH = Path("output/language_summary.csv")

# The marginal contribution, which is the population feedback 6.1 asks about.
_NOT_IN_BASELINE = """
    NOT EXISTS (
        SELECT 1 FROM evidence p
        WHERE p.domain = dy.domain AND p.evidence_year = dy.assigned_year
          AND p.evidence_type = 'prior_reused'
    )
"""


def write_english_annual_files(conn, out_dir: Path = NETNEW_ENGLISH_DIR) -> dict[str, int]:
    """Write the admissible subset: net-new pairs with an `english` verdict.

    These are the annual files the English standard permits. The unrestricted
    `output/netnew/` files stay beside them, because feedback section 7 asks for
    true additions against merged260730 as well, and the two answer different
    questions.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for year in range(1996, 2002):
        query = f"""
            SELECT DISTINCT dy.domain FROM domain_year dy
            JOIN domain_language dl
              ON dl.domain = dy.domain AND dl.assigned_year = dy.assigned_year
            WHERE dy.assigned_year = {year} AND dl.verdict = 'english' AND {_NOT_IN_BASELINE}
            ORDER BY dy.domain
        """  # noqa: S608 (year is an int from range)
        path = out_dir / f"{year}.txt"
        conn.execute(f"COPY ({query}) TO '{path}' (HEADER false)")
        counts[f"english_{year}"] = conn.execute(
            f"SELECT count(*) FROM ({query})"  # noqa: S608
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
            "samples, top_other, evidence_urls) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                row["domain"],
                row["assigned_year"],
                row["verdict"],
                row["english_share"],
                row["samples"],
                row["top_other"],
                row["evidence_urls"],
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
