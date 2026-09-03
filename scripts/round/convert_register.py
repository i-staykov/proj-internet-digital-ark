"""One-shot conversion of the `docs/sources.md` register to one row per source.

The register grew as free prose inside two table cells: 437 entries, single lines up
to 7,840 characters, so nothing could read it but a human with a wide terminal.

This rewrites those entries into the eleven columns the reviewer's ledger asks for,
one row per entry, no line over 500 characters. **Nothing is summarised away.** The
row is a projection, never the only copy: whenever a single URL, number or word of an
entry is not in its row, the entry's own text goes in whole and verbatim under
`## Detail` in the same file, and the conversion refuses to write unless every token
of every entry is present in that entry's row or its detail block.

That per-entry check is the point. A first attempt passed a whole-file token count and
still deleted a clause from one entry, because two extractors read different character
windows and one entry's loss hid behind another's gain. So there is one window here
(`WINDOW`), the dating clause is cut out of the body by the same match span that
produces the dating cell, and the assertion is per entry.

Rows whose own verdict word closes the family move to `docs/sources-closed.md`, in the
five columns that file already uses; their detail sections move with them, because a
file's detail sections belong to that file's rows. The link column always holds the
source URL: the detail anchor sits beside it and never replaces it.

    uv run python scripts/round/convert_register.py --dry-run
    uv run python scripts/round/convert_register.py
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCES = REPO / "docs/sources.md"
CLOSED = REPO / "docs/sources-closed.md"

REGISTER_HEADING = "## Evaluated and rejected"
CLOSED_HEADING = "## Closed families, converted from the register"
DETAIL_HEADING = "## Detail"
LINE_LIMIT = 500
WRAP = 96

# The one character window every prose extractor reads. Two windows is how the first
# attempt lost 70 characters of an entry between the dating cell and the quality cell.
WINDOW = 240

COLUMNS = [
    "source",
    "version or date",
    "coverage period",
    "retrieval method",
    "what dates one item",
    "baseline overlap",
    "net-new EE (date)",
    "quality issues",
    "effort",
    "verdict",
    "link",
]
CLOSED_COLUMNS = ["source", "date", "measured", "reason", "link"]

URL_RE = re.compile(r"https?://[^\s<>()\[\]|`\"']+")
ARTIFACT_URL_RE = re.compile(
    r"(?:artifact|artifacts|source|link|url|listing|served|host)s?\**:?\s*[`<(\[]*"
    r"(https?://[^\s<>()\[\]|`\"']+)",
    re.IGNORECASE,
)
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
WORD_RE = re.compile(r"[A-Za-z]+")
STAMP_RE = re.compile(r"\((\d{4}-\d{2}-\d{2})([^)]*)\)")
EE_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:net-new\s+)?(?:post-split\s+)?EE\b", re.IGNORECASE)
DATES_LABEL = re.compile(r"\*{0,2}[Ww]hat dates one item\*{0,2}[:\s]+")
YEAR_RANGE_RE = re.compile(r"(?<!\d)(199[6-9]|200[01])\s*(?:-|to|/)\s*(199[6-9]|200[01])(?!\d)")
WINDOW_YEAR_RE = re.compile(r"(?<![\d-])(199[6-9]|200[01])(?![\d-])")
OVERLAP_RE = re.compile(
    r"(\d+(?:\.\d+)?\s*%[^.,;|]{0,40}?(?:already\s+)?(?:held|known|overlap|novel|baseline))",
    re.IGNORECASE,
)
EFFORT_RES = (
    re.compile(r"(?<![\w.,])(\d[\d,.]*\s*(?:TB|GB|MB|kB|KB|bytes)\b)"),
    re.compile(r"(?<![\w.,])(\d[\d,.]*\s*(?:hours?|minutes?|days?)\b)"),
    re.compile(
        r"(?<![\w.,])(\d[\d,]*\s*(?:requests|queries|captures|items|files|journals|messages"
        r"|documents|editions|volumes|pages|shards)\b)"
    ),
)

# The verdict is the register's own word, earliest one first, so nothing is
# reclassified into a taxonomy the entry never used. `not a source` is carried
# because the report's own count of families searched excludes those rows by that
# phrase, and it must stay readable in the row after the prose is trimmed.
VERDICT_WORDS = (
    "CLOSED",
    "BLOCKED",
    "REJECTED",
    "REJECT",
    "WITHDRAWN",
    "UNRETRIEVABLE",
    "UNAVAILABLE",
    "ZERO",
    "FINDS",
    "FIND",
    "REOPENED",
    "REOPEN",
    "BANKED",
    "PRICED",
    "DEFERRED",
    "PENDING",
    "ADMITTED",
    "SETTLED",
    "WORTH",
)
VERDICT_RE = re.compile(r"\b(" + "|".join(VERDICT_WORDS) + r")\b", re.IGNORECASE)
NOT_A_SOURCE = "not a source"
# Which verdict words move the row to the closed file. `SETTLED`, `BANKED` and
# `WORTH` are outcomes that keep a family open, so they stay in `sources.md`.
CLOSING = {
    "CLOSED",
    "BLOCKED",
    "REJECTED",
    "REJECT",
    "WITHDRAWN",
    "UNRETRIEVABLE",
    "UNAVAILABLE",
    "ZERO",
}

# What a retrieval route looks like in the prose, most specific first, and read off
# the entry rather than guessed: an entry naming no route reads `n/a`. The three
# no-fetch signs lead, or an entry that says it never made a request would be filed
# under the download it declined to do.
RETRIEVAL_SIGNS = (
    ("zero requests", "none, screened"),
    ("no request", "none, screened"),
    ("not fetched", "none, screened"),
    ("no fetch", "none, screened"),
    ("before the fetch", "none, screened"),
    ("robots", "robots refusal"),
    ("cdx", "cdx query"),
    ("timemap", "wayback timemap"),
    ("web.archive.org", "wayback replay"),
    ("wayback", "wayback replay"),
    ("rdap", "rdap query"),
    ("whois", "port 43 whois"),
    ("advancedsearch", "archive.org search api"),
    ("archive.org/metadata", "archive.org metadata api"),
    ("discmaster", "discmaster index"),
    ("ftp", "ftp listing"),
    ("data/raw", "bytes already on disk"),
    ("on disk", "bytes already on disk"),
    ("oai-pmh", "oai-pmh harvest"),
    ("api", "http api"),
    ("curl", "http download"),
    ("download", "http download"),
)

# Room per cell before shrinking, and the order cells give room back in. The source
# cell shrinks last and never below its floor: it is what a reader greps for.
CAPS = {"key": 120, "dates_item": 140, "overlap": 60, "quality": 240, "reason": 260}
FLOORS = {"key": 60, "dates_item": 0, "overlap": 0, "quality": 0, "reason": 0}
SHRINK_ORDER = ("quality", "reason", "dates_item", "overlap", "key")


@dataclass
class Entry:
    """One register entry: its two original cells, and the columns read off them."""

    head: str
    body: str
    line: int
    key: str = "n/a"
    anchor: str = ""
    version: str = "n/a"
    coverage: str = "n/a"
    retrieval: str = "n/a"
    dates_item: str = "n/a"
    overlap: str = "n/a"
    ee: str = "n/a"
    figure: str = "n/a"
    quality: str = "n/a"
    reason: str = "n/a"
    effort: str = "n/a"
    verdict: str = "n/a"
    urls: list[str] = field(default_factory=list)
    closed: bool = False
    detail: bool = False

    @property
    def original(self) -> str:
        """The entry as it was written, which is what the token check compares to."""
        return f"{self.head} | {self.body}"


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _drop_urls(text: str) -> str:
    """Remove whole URLs and the brackets they leave behind.

    A URL is an atom: it lives in the link column and in the detail block, never
    half in a prose cell. Nothing else is removed, so no word is lost this way.
    """
    text = URL_RE.sub(" ", text)
    text = re.sub(r"<\s*>|`\s*`|\(\s*\)|\[\s*\]", " ", text)
    return _squash(text)


def _cell(text: str) -> str:
    """One table cell: no pipe, no emphasis marker, one line, `n/a` when empty.

    The punctuation left where a URL was lifted out is closed up. No word is
    removed with it, so nothing here can cost an entry a token.
    """
    text = _squash(text).replace("|", r"\|").replace("*", "")
    # Only sentence punctuation is closed up. `WT2g / .GOV` names a corpus, and
    # pulling that full stop onto the slash renames it.
    text = re.sub(r"\s+([.,;:])(?=\s|$)", r"\1", re.sub(r"\.\s*(?=[.,]\s)", "", text))
    # A sentence-final full stop is kept: dropping it is the one thing that makes a
    # word-by-word diff of an entry against its row read as a loss.
    text = text.lstrip(" ,;:.").rstrip(" ,;:")
    return text if re.search(r"[A-Za-z0-9]", text) else "n/a"


def _fit(text: str, limit: int) -> str:
    """Cut at a word boundary, never inside a token, so no URL is ever halved."""
    if len(text) <= limit:
        return text
    cut = text[: limit + 1]
    space = cut.rfind(" ")
    if space <= 0:
        return ""
    return text[:space].rstrip(" ,;:-")


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:70] or "entry"


def _sentence(text: str) -> int:
    """Where a clause ends inside the window: the first `. `, else a word boundary."""
    stop = text.find(". ")
    if stop != -1:
        return stop + 1
    if len(text) < WINDOW:
        return len(text)
    space = text.rfind(" ")
    return space if space > 0 else len(text)


def _dating(body: str) -> tuple[str, tuple[int, int] | None]:
    """The `What dates one item` clause and the exact span it occupies in `body`.

    One match, one span, used both for the cell and for what the quality cell drops.
    """
    label = DATES_LABEL.search(body)
    if not label:
        return "", None
    window = body[label.end() : label.end() + WINDOW]
    end = _sentence(window)
    return window[:end], (label.start(), label.end() + end)


def _coverage(text: str) -> str:
    """The in-window years the entry names, and nothing inferred beyond them."""
    span = YEAR_RANGE_RE.search(text)
    if span:
        return f"{span.group(1)}-{span.group(2)}"
    years = sorted({int(y) for y in WINDOW_YEAR_RE.findall(text)})
    if not years:
        return "n/a"
    return str(years[0]) if len(years) == 1 else f"{years[0]}-{years[-1]}"


def _retrieval(text: str) -> str:
    lowered = text.lower()
    for sign, label in RETRIEVAL_SIGNS:
        if sign in lowered:
            return label
    return "n/a"


def _effort(text: str) -> str:
    found = []
    for pattern in EFFORT_RES:
        match = pattern.search(text)
        if match:
            found.append(_squash(match.group(1)))
        if len(found) == 2:
            break
    return ", ".join(found) if found else "n/a"


def _verdict(body: str) -> tuple[str, bool]:
    """The register's own verdict word, plus whether the row closes the family."""
    match = VERDICT_RE.search(body[:WINDOW])
    word = match.group(1) if match else ""
    note = NOT_A_SOURCE if NOT_A_SOURCE in body.lower() else ""
    closed = word.upper() in CLOSING
    verdict = ", ".join(part for part in (word, note) if part)
    return verdict or "n/a", closed


def parse_entry(line: str, number: int) -> Entry:
    """Split one `| source | verdict prose |` register line into the columns."""
    inner = line.strip().removeprefix("|").removesuffix("|")
    at = inner.find(" | ")
    head, body = (inner[:at], inner[at + 3 :]) if at != -1 else (inner, "")
    entry = Entry(head=head.strip(), body=body.strip(), line=number)

    stamps = list(STAMP_RE.finditer(entry.head))
    name = entry.head
    if stamps:
        last = stamps[-1]
        entry.version = _cell(f"{last.group(1)} {last.group(2).strip(', ')}")
        name = entry.head[: last.start()] + entry.head[last.end() :]
    entry.key = _cell(name)

    both = f"{entry.head} {entry.body}"
    clause, span = _dating(entry.body)
    rest = entry.body if span is None else entry.body[: span[0]] + " " + entry.body[span[1] :]

    ee = EE_RE.search(entry.body)
    day = entry.version.split(",")[0].split(" ")[0] if entry.version != "n/a" else "n/a"
    overlap = OVERLAP_RE.search(entry.body)

    entry.urls = _source_url(line)
    entry.coverage = _coverage(both)
    entry.retrieval = _retrieval(both)
    entry.dates_item = _cell(_drop_urls(clause)) if clause else "n/a"
    entry.overlap = _cell(overlap.group(1)) if overlap else "n/a"
    entry.figure = f"{ee.group(1)} EE" if ee else "n/a"
    entry.ee = f"{entry.figure} ({day})" if ee else "n/a"
    entry.quality = _cell(_drop_urls(rest))
    entry.reason = _cell(_drop_urls(entry.body))
    entry.effort = _effort(entry.body)
    entry.verdict, entry.closed = _verdict(entry.body)
    return entry


def tokens(text: str) -> tuple[Counter[str], Counter[str], Counter[str]]:
    """The URLs, numbers and words of a piece of text, as three multisets.

    URLs come out first and whole, so a URL is compared as one atom rather than as
    the words and numbers inside it.
    """
    urls = Counter(URL_RE.findall(text))
    rest = URL_RE.sub(" ", text)
    return urls, Counter(NUM_RE.findall(rest)), Counter(WORD_RE.findall(rest))


def missing(original: str, kept: str) -> tuple[Counter[str], Counter[str], Counter[str]]:
    """What `original` carries that `kept` does not, per class."""
    was, now = tokens(original), tokens(kept)
    return was[0] - now[0], was[1] - now[1], was[2] - now[2]


def link_cell(entry: Entry) -> str:
    """The source URL, whole, plus the detail anchor beside it when there is one.

    Never `[detail](#...)` alone: the standing rule is that every source carries its
    link, and an anchor is not a link to the source, so an entry that names no URL
    says `n/a` here and the anchor sits beside it. Entries naming several URLs keep
    one here and all of them in the detail block, which is verbatim.
    """
    parts = [f"<{entry.urls[0]}>" if entry.urls else "n/a"]
    if entry.detail:
        parts.append(f"[detail](#{entry.anchor})")
    return " ".join(parts)


def _source_url(line: str) -> list[str]:
    """The entry's URLs, the one it calls the artifact first.

    Entries quote other people's URLs in passing, so first-in-the-line picks the
    wrong one: one entry mentions a search engine's home page long before the
    artifact it was measured on.
    """
    urls = URL_RE.findall(line)
    labelled = ARTIFACT_URL_RE.search(line)
    if labelled and labelled.group(1) in urls:
        urls.remove(labelled.group(1))
        urls.insert(0, labelled.group(1))
    return urls


def _row(cells: Iterable[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _shrink_to_fit(entry: Entry, build: Callable[[dict[str, int]], str]) -> str:
    """Build a row, giving room back cell by cell until the line fits the limit."""
    caps = dict(CAPS)
    while True:
        row = build(caps)
        if len(row) <= LINE_LIMIT:
            return row
        for name in SHRINK_ORDER:
            if caps[name] > FLOORS[name]:
                caps[name] = max(FLOORS[name], caps[name] - 20)
                break
        else:
            raise SystemExit(f"line {entry.line}: cannot fit the row inside {LINE_LIMIT} chars")


def open_row(entry: Entry) -> str:
    """The eleven-column row."""

    def build(caps: dict[str, int]) -> str:
        key = _fit(entry.key, caps["key"]) or entry.key[: caps["key"]]
        return _row(
            [
                key,
                entry.version,
                entry.coverage,
                entry.retrieval,
                _fit(entry.dates_item, caps["dates_item"]) or "n/a",
                _fit(entry.overlap, caps["overlap"]) or "n/a",
                entry.ee,
                _fit(entry.quality, caps["quality"]) or "n/a",
                entry.effort,
                entry.verdict,
                link_cell(entry),
            ]
        )

    return _shrink_to_fit(entry, build)


def closed_row(entry: Entry) -> str:
    """The five columns `docs/sources-closed.md` already uses."""

    def build(caps: dict[str, int]) -> str:
        key = _fit(entry.key, caps["key"]) or entry.key[: caps["key"]]
        return _row(
            [
                key,
                entry.version,
                entry.figure,
                _fit(entry.reason, caps["reason"]) or "n/a",
                link_cell(entry),
            ]
        )

    return _shrink_to_fit(entry, build)


def wrap(text: str, width: int = WRAP) -> list[str]:
    """Rewrap prose so no line is over the limit, never splitting a token."""
    out: list[str] = []
    line = ""
    for word in text.split(" "):
        if line and len(line) + 1 + len(word) > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    if line:
        out.append(line)
    return out or [""]


def detail_block(entry: Entry) -> list[str]:
    """The entry's own two cells, verbatim, under a heading carrying its name.

    Verbatim and whole rather than the row's overflow: an overflow block has to be
    computed, and computing it wrong is how the first attempt deleted a clause.
    """
    return [f"### {entry.anchor}", "", *wrap(entry.head), "", *wrap(entry.body), ""]


def read_register(path: Path) -> tuple[list[str], list[Entry], list[str]]:
    """Stream the register out of `sources.md`: prose before, entries, prose after.

    Streamed a line at a time on purpose: this file is over 700 KB and nothing that
    touches it should ever need it whole in memory or in a reader's terminal.
    """
    before: list[str] = []
    tail: list[str] = []
    entries: list[Entry] = []
    where = "before"
    with path.open(encoding="utf-8") as handle:
        for number, raw in enumerate(handle, start=1):
            line = raw.rstrip("\n")
            if where == "before" and line.startswith(REGISTER_HEADING):
                where = "register"
                continue
            if where == "register":
                if line.startswith("## "):
                    where = "after"
                    tail.append(line)
                    continue
                if line.startswith("|") and not _furniture(line):
                    entries.append(parse_entry(line, number))
                continue
            (before if where == "before" else tail).append(line)
    return before, entries, tail


def _furniture(line: str) -> bool:
    """A header or separator row rather than an entry."""
    bare = line.replace("|", "").replace("-", "").replace(":", "").strip()
    return not bare or line.strip().lower().startswith("| source")


def _rewrap(lines: list[str]) -> list[str]:
    """Rewrap the few prose lines over the limit, and nothing else.

    Table rows and fenced code keep their line breaks: a rewrapped command is a
    broken command, and a rewrapped row is a broken table.
    """
    out: list[str] = []
    fenced = False
    for line in lines:
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if len(line) > LINE_LIMIT and not fenced and not line.startswith("|"):
            out.extend(wrap(line))
        else:
            out.append(line)
    return out


def _anchors(entries: list[Entry]) -> None:
    used: Counter[str] = Counter()
    for entry in entries:
        slug = _slug(entry.key)
        used[slug] += 1
        entry.anchor = slug if used[slug] == 1 else f"{slug}-{used[slug]}"


REGISTER_INTRO = [
    "",
    "One row per source evaluated. Families their own verdict word closes are in",
    "[sources-closed.md](sources-closed.md), in that file's five columns. `n/a` means the",
    "entry does not say, never that the answer is nothing. The link column carries the source",
    "URL; where an entry names several, the first is here and all of them are in its `## Detail`",
    "section, which holds the entry as it was written.",
    "",
]
CLOSED_INTRO = [
    "",
    "Converted out of the `Evaluated and rejected` register of [sources.md](sources.md) on",
    "2026-09-03 by `scripts/round/convert_register.py`, in the five columns above. The",
    "`## Detail` sections below hold each row's entry as it was written.",
    "",
]
DETAIL_INTRO = [
    "",
    "Each entry above whose row could not carry all of it, in the words it was written in.",
    "The row is a projection of this, never the only copy.",
    "",
]


def _detail_sections(entries: list[Entry]) -> list[str]:
    out: list[str] = []
    for entry in entries:
        if entry.detail:
            out.extend(detail_block(entry))
    return [DETAIL_HEADING, *DETAIL_INTRO, *out] if out else []


def convert(sources: Path, closed: Path) -> tuple[str, str, list[Entry]]:
    """The two new documents, and the entries with their columns filled in."""
    before, entries, tail = read_register(sources)
    _anchors(entries)

    # A row is a projection, so anything it cannot carry sends the entry's own text
    # to the detail block. Decided per entry and per token class, never per file.
    for entry in entries:
        row = open_row(entry) if not entry.closed else closed_row(entry)
        entry.detail = any(missing(entry.original, row))

    kept = [e for e in entries if not e.closed]
    moved = [e for e in entries if e.closed]

    out = _rewrap(before)
    out += [
        REGISTER_HEADING,
        *REGISTER_INTRO,
        _row(COLUMNS),
        "|" + "|".join(["---"] * len(COLUMNS)) + "|",
        *[open_row(e) for e in kept],
        "",
    ]
    out += _rewrap(tail)
    detail = _detail_sections(kept)
    if detail:
        out += ["", *detail]
    new_sources = "\n".join(out).rstrip("\n") + "\n"

    old_closed = closed.read_text(encoding="utf-8").splitlines()
    out = _rewrap(old_closed)
    out += [
        "",
        CLOSED_HEADING,
        *CLOSED_INTRO,
        _row(CLOSED_COLUMNS),
        "|" + "|".join(["---"] * len(CLOSED_COLUMNS)) + "|",
        *[closed_row(e) for e in moved],
        "",
    ]
    detail = _detail_sections(moved)
    if detail:
        out += ["", *detail]
    new_closed = "\n".join(out).rstrip("\n") + "\n"
    return new_sources, new_closed, entries


def check(entries: list[Entry], old: tuple[str, str], new: tuple[str, str]) -> list[str]:
    """Everything that must hold before either file is written."""
    failures: list[str] = []

    # 1. Per entry: its row plus its detail block carries every token it had. A
    #    whole-file count hides one entry's loss behind another entry's gain.
    for entry in entries:
        row = closed_row(entry) if entry.closed else open_row(entry)
        kept = row + " " + " ".join(detail_block(entry)) if entry.detail else row
        urls, numbers, words = missing(entry.original, kept)
        if urls or numbers or words:
            failures.append(
                f"line {entry.line} ({entry.key[:40]}) lost "
                f"urls={list(urls)[:3]} numbers={list(numbers)[:5]} words={list(words)[:5]}"
            )

    # 2. Whole URLs, as a set over both files: equality catches a lost URL and a
    #    truncated one alike, since half a URL is a URL the set never had.
    before = {url for text in old for url in URL_RE.findall(text)}
    after = {url for text in new for url in URL_RE.findall(text)}
    if before != after:
        failures.append(
            f"urls lost {sorted(before - after)[:3]}, gained {sorted(after - before)[:3]}"
        )

    # 3. Outside the register, the only change allowed is where a line wraps.
    for name, was, now in (("sources.md", old[0], new[0]), ("sources-closed.md", old[1], new[1])):
        lost = missing(_prose(was), _prose(now))
        if any(lost):
            failures.append(f"{name}: prose outside the register lost {lost}")

    # 4. The line limit the hygiene test asserts.
    for name, text in (("sources.md", new[0]), ("sources-closed.md", new[1])):
        over = [len(line) for line in text.splitlines() if len(line) > LINE_LIMIT]
        if over:
            failures.append(f"{name}: {len(over)} lines over {LINE_LIMIT}, longest {max(over)}")
    return failures


def _prose(text: str) -> str:
    """The document with its table rows dropped, which is what rewrapping touches."""
    return "\n".join(line for line in text.splitlines() if not line.startswith("|"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=SOURCES)
    parser.add_argument("--closed", type=Path, default=CLOSED)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    old = (
        args.sources.read_text(encoding="utf-8"),
        args.closed.read_text(encoding="utf-8"),
    )
    if _row(COLUMNS) in old[0]:
        print("already converted; nothing to do")
        return 1
    new_sources, new_closed, entries = convert(args.sources, args.closed)
    kept = [e for e in entries if not e.closed]
    moved = [e for e in entries if e.closed]
    linked = sum(1 for e in entries if e.urls)

    print(f"entries {len(entries)}: {len(kept)} rows kept, {len(moved)} moved to the closed file")
    blocks = (sum(e.detail for e in kept), sum(e.detail for e in moved))
    print(f"detail blocks: {blocks[0]} kept, {blocks[1]} moved")
    print(f"rows carrying a url {linked}, rows whose entry names none {len(entries) - linked}")
    print(f"bytes sources.md {len(old[0])} -> {len(new_sources)}")
    print(f"bytes sources-closed.md {len(old[1])} -> {len(new_closed)}")

    failures = check(entries, old, (new_sources, new_closed))
    if failures:
        print(f"REFUSING to write: {len(failures)} checks failed")
        for line in failures[:10]:
            print(f"  {line}")
        return 1
    print("per-entry tokens, the whole-url set, the prose outside the register and 500 chars: pass")
    if args.dry_run:
        return 0
    args.sources.write_text(new_sources, encoding="utf-8")
    args.closed.write_text(new_closed, encoding="utf-8")
    print(f"wrote {args.sources} and {args.closed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
