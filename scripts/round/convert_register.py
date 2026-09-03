"""One-shot conversion of the `docs/sources.md` register to one row per source.

The register grew as free prose inside two table cells: 437 entries, 580 KB of the
file's 704 KB, single lines up to 7,840 characters. Nothing could read it but a
human with a wide terminal, and the file could not be opened whole.

This rewrites those entries into the columns the reviewer's brief asks for (source
name and version, coverage period, retrieval method, baseline overlap, quality
issues, effort, and the reason to retain, deprioritize or revisit), one row per
entry, no line over 500 characters. Whatever does not fit the row keeps its
original wording verbatim under `## Detail`, so the conversion moves text and
never rewrites or drops it. Closed entries land in `docs/sources-closed.md` in the
five columns that file already has.

It streams the input and asserts two invariants on the way out: the set of source
keys is unchanged, and every URL occurrence is still there exactly once.

    uv run python scripts/round/convert_register.py --dry-run
    uv run python scripts/round/convert_register.py
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCES = REPO / "docs/sources.md"
CLOSED = REPO / "docs/sources-closed.md"

REGISTER_HEADING = "## Evaluated and rejected"
DETAIL_HEADING = "## Detail"
LINE_LIMIT = 500

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

URL_RE = re.compile(r"https?://[^\s<>()\[\]|`\"']+")
DATE_RE = re.compile(r"\((\d{4}-\d{2}-\d{2})([^)]*)\)\s*$")
EE_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:net-new\s+)?(?:post-split\s+)?EE", re.IGNORECASE)
DATES_ITEM_RE = re.compile(r"[Ww]hat dates one item[:\s]*(.{0,200}?)(?:\.\s|\.\.|$)")
DATING_RE = re.compile(r"\*\*Dating[:\s]*(.{0,200}?)(?:\.\s|\*\*|$)")
WINDOW_YEAR_RE = re.compile(r"(?<![\d-])(199[6-9]|200[01])(?![\d-])")
YEAR_RANGE_RE = re.compile(r"(?<!\d)(199[6-9]|200[01])\s*[-/](199[6-9]|200[01])(?!\d)")
OVERLAP_RE = re.compile(
    r"(\d+(?:\.\d+)?\s*%[^.,;]{0,30}?(?:already\s+)?(?:held|known|overlap|novel))",
    re.IGNORECASE,
)
EFFORT_RES = [
    re.compile(r"(?<![\w.,])(\d[\d,.]*\s*(?:TB|GB|MB|kB|KB|B|bytes)\b)"),
    re.compile(r"(?<![\w.,])(\d[\d,.]*\s*(?:hours?|minutes?|days?)\b)"),
    re.compile(
        r"(?<![\w.,])(\d[\d,]*\s*(?:requests|queries|captures|items|files|journals|pages"
        r"|archives|messages|documents|editions|shards)\b)"
    ),
]
# The verdict is whichever of these words comes FIRST in the entry's opening
# clause. Any-match lost eight entries to the word "priced" appearing halfway
# through a sentence that opened with CLOSED.
VERDICT_WORDS = [
    ("active", re.compile(r"\bBANKED\b")),
    (
        "parked",
        re.compile(r"\b(?:FIND|FINDS|REOPEN|REOPENED|PRICED|DEFERRED|DEFERRAL|WORTH|PENDING)\b"),
    ),
    (
        "closed",
        re.compile(r"\b(?:CLOSED|BLOCKED|REJECT|REJECTED|ZERO|UNAVAILABLE|CORRUPT|WITHDRAWN)\b"),
    ),
]
VERDICT_WORD_RE = re.compile(
    r"\b(CLOSED|BLOCKED|FIND|REOPENED|BANKED|PRICED|REJECT|REJECTED|ZERO|Closed|Zero)\b",
    re.IGNORECASE,
)

# What a retrieval route looks like in the prose, most specific first. Read off
# the entry rather than guessed, so an entry with no route reads `n/a`.
RETRIEVAL_SIGNS = [
    ("no fetch", "none, screened"),
    ("not fetched", "none, screened"),
    ("no request", "none, screened"),
    ("before the fetch", "none, screened"),
    ("robots", "robots refusal"),
    ("web.archive.org", "wayback replay"),
    ("cdx", "cdx query"),
    ("wayback", "wayback replay"),
    ("timemap", "wayback timemap"),
    ("rdap", "rdap query"),
    ("whois", "port 43 whois"),
    ("ftp", "ftp listing"),
    ("advancedsearch", "archive.org search api"),
    ("archive.org/metadata", "archive.org metadata api"),
    ("api", "http api"),
    ("data/raw", "bytes already on disk"),
    ("on disk", "bytes already on disk"),
    ("discmaster", "discmaster index"),
    ("curl", "http download"),
    ("download", "http download"),
]


@dataclass
class Entry:
    """One register entry, already split into the reviewer's columns."""

    key: str
    head: str
    version: str
    coverage: str
    retrieval: str
    dates_item: str
    overlap: str
    ee: str
    quality: str
    reason: str
    effort: str
    verdict: str
    urls: list[str] = field(default_factory=list)
    body: str = ""
    anchor: str = ""
    detail: bool = False


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_urls(text: str) -> str:
    """Drop URLs from prose that is about to sit beside a link column.

    They move to that column verbatim, and leaving a copy behind would count the
    same URL twice.
    """
    text = re.sub(r"[`<]?" + URL_RE.pattern + r"[`>]?", "", text)
    return _squash(re.sub(r"\(\s*\)|,\s*,", "", text))


def _tidy(text: str) -> str:
    """Drop the URLs and close the gap the label they followed leaves behind."""
    text = _strip_urls(text)
    text = re.sub(r"\b(?:Artifact|Artifacts|Source|Link|URL)s?:\s*(?=[.,;]|$)", "", text)
    text = re.sub(r"(?:\s*\.){2,}", ".", text)
    text = re.sub(r"([;,])\s*\.", r"\1", text)
    return _squash(text).lstrip(".,;: ")


def _fit(text: str, limit: int) -> str:
    """Cut `text` at a word boundary, never inside a URL or a code span."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    if space > limit // 2:
        cut = cut[:space]
    if "http" in cut and not URL_RE.search(cut):
        cut = cut[: cut.rindex("http")]
    if cut.count("`") % 2:
        cut = cut[: cut.rindex("`")]
    return cut.rstrip(" ,;:-") or text[:limit]


def _slug(key: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")
    return slug[:60] or "entry"


def _verdict(head: str) -> str:
    upper = head[:110].upper()
    best = (len(upper) + 1, "closed")
    for verdict, pattern in VERDICT_WORDS:
        match = pattern.search(upper)
        if match and match.start() < best[0]:
            best = (match.start(), verdict)
    return best[1]


def _coverage(text: str) -> str:
    span = YEAR_RANGE_RE.search(text)
    if span:
        return f"{span.group(1)}-{span.group(2)}"
    years = sorted({int(y) for y in WINDOW_YEAR_RE.findall(text)})
    if not years:
        return "n/a"
    if len(years) == 1:
        return str(years[0])
    return f"{years[0]}-{years[-1]}"


def _retrieval(text: str) -> str:
    lowered = text.lower()
    for sign, label in RETRIEVAL_SIGNS:
        if sign in lowered:
            return label
    return "n/a"


def _effort(text: str) -> str:
    found: list[str] = []
    for pattern in EFFORT_RES:
        match = pattern.search(text)
        if match:
            found.append(_squash(match.group(1)))
        if len(found) == 2:
            break
    return ", ".join(found) if found else "n/a"


def _quality(body: str) -> str:
    """What the entry says beyond its verdict, its figure and its dating claim.

    Those three have columns of their own, so repeating them here would spend the
    row's 500 characters saying the same thing three times.
    """
    text = body
    opener = re.match(r"\*\*(.{0,200}?)\*\*[:.\s]*", text)
    if opener and (EE_RE.search(opener.group(1)) or VERDICT_WORD_RE.search(opener.group(1))):
        text = text[opener.end() :]
    text = DATES_ITEM_RE.sub("", text, count=1)
    return _tidy(text)


def _dates_item(text: str) -> str:
    match = DATES_ITEM_RE.search(text) or DATING_RE.search(text)
    if not match:
        return "n/a"
    return _strip_urls(match.group(1)).strip(" *`") or "n/a"


def _is_table_furniture(line: str) -> bool:
    """A header or separator row, not an entry."""
    bare = line.strip().strip("|").replace("|", "").replace("-", "").replace(" ", "")
    return not bare or line.strip().startswith("| Source")


def parse_entry(line: str) -> Entry:
    """Split one `| source | verdict |` register line into columns."""
    cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
    head = cells[0]
    body = " | ".join(cells[1:]).strip()
    urls = URL_RE.findall(line)

    stamped = DATE_RE.search(head.rstrip("* "))
    version = "n/a"
    if stamped:
        version = _squash(stamped.group(1) + " " + stamped.group(2).strip(", "))
        head = head.rstrip("* ")[: stamped.start()]
    key = _strip_urls(head.strip("* ")).strip(" ,")
    key = _fit(key, 120) or "unnamed entry"

    ee_match = EE_RE.search(body)
    ee_value = float(ee_match.group(1).replace(",", "")) if ee_match else -1.0
    day = version.split(" ")[0] if version != "n/a" else "n/a"
    ee = f"{ee_match.group(1)} ({day})" if ee_match else "n/a"

    overlap = OVERLAP_RE.search(body)
    entry = Entry(
        key=key,
        head=cells[0].strip("* "),
        version=version,
        coverage=_coverage(head + " " + body),
        retrieval=_retrieval(head + " " + body),
        dates_item=_fit(_dates_item(body), 130),
        overlap=_fit(_squash(overlap.group(1)).strip("*)(`, "), 50) if overlap else "n/a",
        ee=ee,
        quality=_quality(body),
        # the closed file has five columns and no verdict of its own, so its
        # reason cell keeps the verdict clause the eleven-column row splits out
        reason=_tidy(body),
        effort=_effort(body),
        verdict=_verdict(body),
        urls=urls,
        body=body,
    )
    entry.detail = ee_value > 5000
    return entry


def _balance(cell: str) -> str:
    """Drop a formatting marker whose partner was cut off with the sentence.

    A cell ending in a lone `**` or backtick renders the rest of the row as bold
    or as code, which is how a trimmed verdict starts looking like a claim.
    """
    for marker in ("**", "`"):
        if cell.count(marker) % 2:
            at = cell.rfind(marker)
            cell = cell[:at] + cell[at + len(marker) :]
    return cell.strip()


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(_balance(c) for c in cells) + " |"


def _links(entry: Entry) -> str:
    return " ".join(f"<{url}>" for url in entry.urls)


def open_row(entry: Entry) -> str:
    """The eleven-column row, shrunk until it fits, overflow marked for detail."""
    quality_room = 240
    while True:
        quality = _fit(entry.quality, quality_room)
        if len(quality) < len(entry.quality):
            entry.detail = True
        # a URL belongs either to the row or to the detail block, never to both,
        # or the same link is counted twice
        link = f"[detail](#{entry.anchor})" if entry.detail else _links(entry) or "n/a"
        row = _row(
            [
                entry.key,
                entry.version,
                entry.coverage,
                entry.retrieval,
                entry.dates_item,
                entry.overlap,
                entry.ee,
                quality or "n/a",
                entry.effort,
                entry.verdict,
                link,
            ]
        )
        if len(row) <= LINE_LIMIT:
            return row
        if not entry.detail:
            entry.detail = True
            continue
        if quality_room > 40:
            quality_room -= 40
            continue
        entry.dates_item = _fit(entry.dates_item, 60)
        entry.overlap = _fit(entry.overlap, 30)
        quality_room = 40
        if len(_row([f"`{entry.key}`", entry.version, "", "", "", "", "", "", "", "", ""])) > 460:
            entry.key = _fit(entry.key, 60)


def closed_row(entry: Entry) -> str:
    """The five columns `docs/sources-closed.md` already uses."""
    reason_room = 330
    while True:
        reason = _fit(entry.reason, reason_room)
        if len(reason) < len(entry.reason):
            entry.detail = True
        link = f"[detail](#{entry.anchor})" if entry.detail else _links(entry)
        row = _row([entry.key, entry.version, entry.ee, reason or "n/a", link])
        if len(row) <= LINE_LIMIT:
            return row
        if not entry.detail:
            entry.detail = True
            continue
        reason_room = max(40, reason_room - 40)


def wrap(text: str, width: int = 95) -> list[str]:
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
    return out


def detail_block(entry: Entry) -> list[str]:
    """The entry's own words, kept whole under a heading carrying its key.

    The head cell goes in verbatim because some entries carry their artifact URL
    in the name, and the row above has no room for it.
    """
    return [
        f"### {entry.anchor}",
        "",
        *wrap(f"**{entry.head}**"),
        "",
        *wrap(entry.body),
    ]


def convert(sources_text: str, closed_text: str) -> tuple[str, str, list[Entry]]:
    """Rewrite both documents. Returns the new texts and the parsed entries."""
    lines = sources_text.splitlines()
    before: list[str] = []
    entries: list[Entry] = []
    after: list[str] = []
    where = "before"
    for line in lines:
        if where == "before" and line.startswith(REGISTER_HEADING):
            where = "register"
            continue
        if where == "register":
            if line.startswith("## "):
                where = "after"
                after.append(line)
                continue
            if line.startswith("|") and not _is_table_furniture(line):
                entries.append(parse_entry(line))
            continue
        (before if where == "before" else after).append(line)

    used: Counter[str] = Counter()
    for entry in entries:
        slug = _slug(entry.key)
        used[slug] += 1
        entry.anchor = slug if used[slug] == 1 else f"{slug}-{used[slug]}"

    open_entries = [e for e in entries if e.verdict != "closed"]
    closed_entries = [e for e in entries if e.verdict == "closed"]
    open_rows = [open_row(e) for e in open_entries]
    closed_rows = [closed_row(e) for e in closed_entries]

    out = [wrap(line)[0] if len(line) > LINE_LIMIT else line for line in before]
    out += [
        REGISTER_HEADING,
        "",
        "One row per evaluated source. Closed ones are in [sources-closed.md](sources-closed.md);",
        "what did not fit a row is under `## Detail` below, in the words the entry was written in.",
        "",
        _row(COLUMNS),
        # spaceless, like every other separator in docs/, and `bank_findings.py`
        # finds the insertion point by searching for `|---|---|`
        "|" + "|".join(["---"] * len(COLUMNS)) + "|",
        *open_rows,
        "",
    ]
    out += _rewrap(after)
    detail = [e for e in open_entries if e.detail]
    if detail:
        out += ["", DETAIL_HEADING, "", "Overflow from the rows above, verbatim.", ""]
        for entry in detail:
            out += ["", *detail_block(entry)]
    new_sources = "\n".join(out).rstrip("\n") + "\n"

    closed_lines = closed_text.splitlines()
    tail = len(closed_lines)
    while tail and not closed_lines[tail - 1].startswith("|"):
        tail -= 1
    new_closed = closed_lines[:tail] + closed_rows + closed_lines[tail:]
    detail = [e for e in closed_entries if e.detail]
    if detail:
        new_closed += ["", DETAIL_HEADING, "", "Overflow from the rows above, verbatim.", ""]
        for entry in detail:
            new_closed += ["", *detail_block(entry)]
    return new_sources, "\n".join(new_closed).rstrip("\n") + "\n", entries


def _rewrap(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        out.extend(wrap(line) if len(line) > LINE_LIMIT and not line.startswith("|") else [line])
    return out


def keys_before(sources_text: str) -> set[str]:
    """The source keys the old register carried, read with the old row shape."""
    keys = set()
    inside = False
    for line in sources_text.splitlines():
        if line.startswith("## "):
            inside = line.startswith(REGISTER_HEADING)
            continue
        if inside and line.startswith("|") and not _is_table_furniture(line):
            keys.add(parse_entry(line).key)
    return keys


def table_keys(text: str) -> set[str]:
    """First-cell values of every row of a `| source | ...` table in `text`.

    Tables that describe something other than a source, like the two-column
    `closed here | what closed it` notes inside a prose section, are skipped by
    requiring the header's first column to be `source`.
    """
    keys: set[str] = set()
    inside = False
    for line in text.splitlines():
        if not line.startswith("|"):
            inside = False
            continue
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        if cells[0].lower() == "source":
            inside = True
            continue
        if inside and not _is_table_furniture(line):
            keys.add(cells[0])
    return keys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=SOURCES)
    parser.add_argument("--closed", type=Path, default=CLOSED)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sources_text = args.sources.read_text(encoding="utf-8")
    closed_text = args.closed.read_text(encoding="utf-8")
    if REGISTER_HEADING not in sources_text:
        print("no register section found; nothing to convert")
        return 1
    if _row(COLUMNS) in sources_text:
        print("already converted; nothing to do")
        return 1

    new_sources, new_closed, entries = convert(sources_text, closed_text)

    old_keys = keys_before(sources_text)
    # the 33 rows `sources-closed.md` already held came from another document
    new_keys = (table_keys(new_sources) | table_keys(new_closed)) - table_keys(closed_text)
    old_urls = Counter(URL_RE.findall(sources_text)) + Counter(URL_RE.findall(closed_text))
    new_urls = Counter(URL_RE.findall(new_sources)) + Counter(URL_RE.findall(new_closed))
    long_lines = [
        len(line)
        for text in (new_sources, new_closed)
        for line in text.splitlines()
        if len(line) > LINE_LIMIT
    ]
    verdicts = Counter(e.verdict for e in entries)

    print(
        f"entries {len(entries)}: {dict(verdicts)}, detail blocks {sum(e.detail for e in entries)}"
    )
    print(
        f"source keys before {len(old_keys)}, after {len(new_keys)}, equal {old_keys == new_keys}"
    )
    print(f"url occurrences before {sum(old_urls.values())}, after {sum(new_urls.values())}")
    print(
        f"distinct urls before {len(old_urls)}, after {len(new_urls)}, equal {old_urls == new_urls}"
    )
    print(f"lines over {LINE_LIMIT} chars: {len(long_lines)}")
    print(f"bytes sources.md {len(sources_text)} -> {len(new_sources)}")
    print(f"bytes sources-closed.md {len(closed_text)} -> {len(new_closed)}")
    if old_keys != new_keys or old_urls != new_urls or long_lines:
        print("REFUSING to write: an invariant failed")
        for key in sorted(old_keys - new_keys)[:5]:
            print(f"  lost key {key!r}")
        for url in sorted(set(old_urls) - set(new_urls))[:5]:
            print(f"  lost url {url}")
        return 1
    if args.dry_run:
        return 0
    args.sources.write_text(new_sources, encoding="utf-8")
    args.closed.write_text(new_closed, encoding="utf-8")
    print(f"wrote {args.sources} and {args.closed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
