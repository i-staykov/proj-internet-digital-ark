"""Search the four register pages without opening one.

`.claude/settings.json` denies reading `docs/sources*.md`, and that deny covers a
`grep` or a `sed` on the same path, so this is the sanctioned route in. It is also
the cheap one: the two pages are 347 KB and 546 KB, and a session that greps either
spends its context on prose it never wanted. Every page is streamed a line at a
time, one truncated line is printed per hit, and no whole row and no whole entry
ever reaches the terminal.

The four pages, all of them registers: `docs/sources.md` (its eleven-column table,
its narrative sections and its `## Detail` blocks), `docs/sources-closed.md`,
`docs/approved-sources-list.md` and `docs/hypotheses-pending.md`.

A hit line is `page:line  key  verdict  net-new EE  where  the matching text`, where
`where` says which shape the term was found in: a table `row`, a `## Detail` block,
a `head`ing, or the `prose` of a section. A row is a projection of its entry, so a
`detail` hit is the signal that the row does not carry what you asked about, and
`--detail` is the only way to get that entry's full text.

    just find iedr                       every hit, over all four pages
    just find iedr_register --detail     that one entry, whole
    just find blocklist squidguard       hits under one source key
    just find 2001 --all                 past the 40-line cap

Exit 0 when something matched, 1 when nothing did, 2 when the search itself could
not run: a session has to tell "not in the register" from "the search failed".
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# The four pages, by the tag the output prints. `docs/` is dropped from the tag: it
# repeats on every line and it is not news.
PAGES = {
    "sources": "docs/sources.md",
    "closed": "docs/sources-closed.md",
    "approved": "docs/approved-sources-list.md",
    "pending": "docs/hypotheses-pending.md",
}

# Every row of `sources-closed.md` is closed by the fact it is in that file, and its
# five columns carry no verdict cell. Nothing else gets a default.
PAGE_VERDICT = {"closed": "closed"}

CAP = 40  # lines printed without --all, footer included
MIN_WIDTH = 60
# Hits buffered while a section's own verdict line is still ahead of the reader. A
# bound, so a term matching a whole section cannot grow the buffer without limit.
PENDING = 200

# The register writes its verdict in capitals, so the case is the discriminator: a
# lowercase "find" is the ordinary verb and appears in most entries.
VERDICT_RE = re.compile(
    r"\b(CLOSED|BLOCKED|REJECTED|REJECT|WITHDRAWN|UNRETRIEVABLE|UNAVAILABLE|ZERO"
    r"|FINDS|FIND|REOPENED|REOPEN|BANKED|PRICED|DEFERRED|PENDING|ADMITTED|SETTLED|WORTH)\b"
)
DECISION_RE = re.compile(r"^\s*[-*]?\s*(?:\*\*)?Decision(?:\*\*)?\s*:\s*(.+)", re.IGNORECASE)
EE_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:net-new\s+)?(?:post-split\s+)?EE\b", re.IGNORECASE)


@dataclass
class Hit:
    """One matching line, and the little that is known about it while streaming."""

    page: str
    line: int
    key: str
    where: str
    text: str
    at: int = 0
    verdict: str = ""
    ee: str = ""


@dataclass
class Block:
    """One heading, which is where an entry's full text starts."""

    page: str
    path: Path
    line: int
    level: int
    heading: str
    detail: bool


def _norm(text: str) -> str:
    """Compare keys across the register's two spellings of one name.

    A detail anchor is slugged (`inaddr-reverse-tree-ns-...`) and the key it names is
    not (`inaddr_reverse_tree_ns_...`), so neither spelling can be the only one that
    matches.
    """
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _fit(text: str, room: int) -> str:
    return text if len(text) <= room else text[: max(0, room - 1)] + "~"


def _snippet(text: str, at: int, room: int) -> str:
    """The match in its context. Never the whole cell, never the whole line."""
    if len(text) <= room:
        return text
    start = max(0, min(at - room // 4, len(text) - room))
    piece = text[start : start + room]
    if start:
        piece = "~" + piece[1:]
    if start + room < len(text):
        piece = piece[:-1] + "~"
    return piece


def _heading_key(text: str) -> str:
    """The source key a heading names: before the colon, before the class, unquoted."""
    key = text.split(":", 1)[0].split(" / ")[0]
    return re.sub(r"\s+", " ", key.replace("`", "").replace("*", "")).strip()


def _cells(line: str) -> list[str]:
    """A table row's cells. `\\|` is an escaped pipe inside a cell, not a boundary."""
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def _is_rule(cells: list[str]) -> bool:
    return not set("".join(cells)) - set("-: ")


def _is_header(cells: list[str]) -> bool:
    return "source" in [cell.lower() for cell in cells]


def _columns(cells: list[str]) -> dict[str, int | None]:
    """Which column is which, read off the header rather than assumed.

    The four pages carry three different tables: eleven columns in `sources.md`, five
    in `sources-closed.md`, eight in the priced table of `hypotheses-pending.md`.
    """
    lower = [cell.lower() for cell in cells]

    def pick(*names: str) -> int | None:
        for name in names:
            if name in lower:
                return lower.index(name)
        for index, cell in enumerate(lower):
            if any(name in cell for name in names):
                return index
        return None

    return {
        "key": pick("source"),
        "verdict": pick("verdict", "decision"),
        "ee": pick("net-new ee (date)", "ee", "measured"),
    }


def _cell(cells: list[str], columns: dict[str, int | None], name: str) -> str:
    index = columns.get(name)
    if index is None or index >= len(cells):
        return ""
    value = cells[index].strip()
    return "" if value.lower() in {"", "n/a", "-"} else value


def _family_ok(family: str, key: str) -> bool:
    return not family or _norm(family) in _norm(key)


def _row_hit(
    tag: str, number: int, cells: list[str], columns: dict[str, int | None], needle: str
) -> Hit | None:
    """The first cell carrying the term, plus the row's own verdict and EE cells."""
    key = _cell(cells, columns, "key") or "-"
    for cell in cells:
        at = cell.lower().find(needle)
        if at >= 0:
            return Hit(
                page=tag,
                line=number,
                key=key,
                where="row",
                text=cell,
                at=at,
                verdict=_cell(cells, columns, "verdict"),
                ee=_cell(cells, columns, "ee"),
            )
    return None


def scan(path: Path, tag: str, term: str, family: str, hits: list[Hit]) -> None:
    """Stream one page, appending its hits.

    Streamed rather than read: these pages are the largest documents in the repo and
    the point of this tool is that neither the terminal nor memory holds one whole.
    A hit is buffered only until its section ends, because the verdict of a
    `### key / class` section is written under the line that matched, not above it.
    """
    needle = term.lower()
    section = ""
    in_detail = False
    columns: dict[str, int | None] | None = None
    decided = ""  # a `Decision:` line, which is the human answer
    spotted = ""  # the register's own capitalised verdict word, as a fallback
    ee = ""
    pending: list[Hit] = []

    def flush() -> None:
        for hit in pending:
            hit.verdict = hit.verdict or decided or spotted or PAGE_VERDICT.get(tag, "")
            hit.ee = hit.ee or ee
        hits.extend(pending)
        pending.clear()

    def keep(hit: Hit) -> None:
        pending.append(hit)
        if len(pending) > PENDING:
            flush()

    with open(path, encoding="utf-8") as handle:
        for number, raw in enumerate(handle, start=1):
            line = raw.rstrip("\n")

            if line.startswith("#"):
                flush()
                level = len(line) - len(line.lstrip("#"))
                text = line.lstrip("#").strip()
                if level <= 2:
                    in_detail = text.lower().startswith("detail")
                section, columns = _heading_key(text), None
                decided, spotted, ee = "", "", ""
                at = text.lower().find(needle)
                if at >= 0 and _family_ok(family, section):
                    where = "detail" if in_detail and level >= 3 else "head"
                    keep(Hit(tag, number, section or "-", where, text, at))
                continue

            if not line.strip():
                columns = None
                continue

            if line.startswith("|"):
                cells = _cells(line)
                if _is_rule(cells):
                    continue
                if _is_header(cells):
                    columns = _columns(cells)
                    # A header row is still searchable text. Skipping it outright made
                    # `find "baseline overlap"` answer "not in the register" for a term
                    # that is one of its column names, which is the one answer this
                    # command must never give: exit 1 has to mean absent, not skipped.
                    at = line.lower().find(needle)
                    if at >= 0 and not family:
                        keep(Hit(tag, number, "-", "header", line.strip(), at))
                    continue
                if columns:
                    hit = _row_hit(tag, number, cells, columns, needle)
                    if hit and _family_ok(family, hit.key):
                        keep(hit)
                    continue
                # A table whose columns this cannot name is searched as prose.
            else:
                columns = None
                decision = DECISION_RE.match(line)
                words = decision.group(1).split() if decision else []
                if words:
                    decided = decided or words[0].strip(".,;`*")
                elif not spotted:
                    word = VERDICT_RE.search(line)
                    if word:
                        spotted = word.group(1)
                if not ee:
                    figure = EE_RE.search(line)
                    if figure:
                        ee = f"{figure.group(1)} EE"

            at = line.lower().find(needle)
            if at >= 0 and _family_ok(family, section):
                keep(Hit(tag, number, section or "-", "detail" if in_detail else "prose", line, at))
        flush()


def search(root: Path, term: str, family: str) -> list[Hit]:
    hits: list[Hit] = []
    for tag, name in PAGES.items():
        path = root / name
        if path.is_file():
            scan(path, tag, term, family, hits)
    return hits


def _layout(width: int) -> dict[str, int]:
    """Column room, so a wide terminal spends it on the match and a narrow one fits."""
    return {
        "tag": 14,
        "key": max(16, min(34, width * 24 // 100)),
        "verdict": 9,
        "ee": max(9, min(22, width * 14 // 100)),
        "where": 6,
    }


def format_hit(hit: Hit, width: int) -> str:
    room = _layout(width)
    # `2189.0 EE (2026-09-01)` loses its date rather than half of it on a narrow
    # terminal: a truncated date reads as a different date.
    ee = hit.ee or "-"
    if len(ee) > room["ee"] and " (" in ee:
        ee = ee.split(" (")[0]
    left = " ".join(
        [
            _fit(f"{hit.page}:{hit.line}", room["tag"]).ljust(room["tag"]),
            _fit(hit.key, room["key"]).ljust(room["key"]),
            _fit(hit.verdict or "-", room["verdict"]).ljust(room["verdict"]),
            _fit(ee, room["ee"]).ljust(room["ee"]),
            hit.where.ljust(room["where"]),
        ]
    )
    return f"{left} {_snippet(hit.text, hit.at, max(16, width - len(left) - 1))}"[:width]


def render(hits: list[Hit], show_all: bool, width: int) -> list[str]:
    """The lines to print: at most `CAP` of them unless --all, and what was dropped."""
    lines = [format_hit(hit, width) for hit in hits]
    detail = sum(1 for hit in hits if hit.where == "detail")
    footer: list[str] = []
    if not show_all and len(lines) > CAP - (1 if detail else 0):
        keep = CAP - 1 - (1 if detail else 0)
        footer.append(
            f"{len(lines) - keep} more hits suppressed: --all prints them, a family narrows them"
        )
        lines = lines[:keep]
    if detail:
        footer.append(
            f"{detail} in a detail block, which its row only projects: "
            "just find <key> --detail prints one whole"
        )
    return lines + [line[:width] for line in footer]


def locate(root: Path, key: str) -> list[Block]:
    """Every heading whose key matches, over all four pages. `tag#heading` names one."""
    page, _, wanted = key.rpartition("#")
    if not _norm(wanted):
        return []
    out: list[Block] = []
    for tag, name in PAGES.items():
        path = root / name
        if (page and page != tag) or not path.is_file():
            continue
        in_detail = False
        with open(path, encoding="utf-8") as handle:
            for number, raw in enumerate(handle, start=1):
                line = raw.rstrip("\n")
                if not line.startswith("#"):
                    continue
                level = len(line) - len(line.lstrip("#"))
                text = line.lstrip("#").strip()
                if level <= 2:
                    in_detail = text.lower().startswith("detail")
                heading = _heading_key(text)
                if _norm(wanted) in _norm(heading):
                    out.append(Block(tag, path, number, level, heading, in_detail and level >= 3))
    return out


def choose(blocks: list[Block], key: str) -> list[Block]:
    """Narrow to one entry: an exact key beats a substring, a detail block beats a row."""
    wanted = key.rpartition("#")[2]
    pool = [block for block in blocks if _norm(block.heading) == _norm(wanted)] or blocks
    return [block for block in pool if block.detail] or pool


def block_lines(block: Block) -> list[str]:
    """One entry as it was written, from its heading to the next of the same level."""
    out: list[str] = []
    with open(block.path, encoding="utf-8") as handle:
        for number, raw in enumerate(handle, start=1):
            if number < block.line:
                continue
            line = raw.rstrip("\n")
            if number == block.line:
                out.append(f"{block.page}:{number} {line}")
                continue
            if line.startswith("#") and len(line) - len(line.lstrip("#")) <= block.level:
                break
            out.append(line)
    while out and not out[-1].strip():
        out.pop()
    return out


def show_detail(root: Path, key: str, show_all: bool, width: int) -> int:
    blocks = locate(root, key)
    if not blocks:
        print(f"no entry named '{key}' in the four register pages", file=sys.stderr)
        return 1
    pool = choose(blocks, key)
    if len(pool) != 1:
        names = ", ".join(f"{block.page}#{block.heading}" for block in pool[:6])
        one_line = f"{len(pool)} entries match '{key}', name one of: {names}"
        print(one_line[: width * 2], file=sys.stderr)
        return 2
    lines = block_lines(pool[0])
    if not show_all and len(lines) > CAP:
        for line in lines[: CAP - 1]:
            print(line)
        print(f"{len(lines) - CAP + 1} more lines of this entry suppressed: --all prints it whole")
    else:
        for line in lines:
            print(line)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="search the four register pages")
    parser.add_argument("term", nargs="?", help="case-insensitive substring")
    parser.add_argument("family", nargs="?", help="restrict to one source key")
    parser.add_argument("--family", dest="family_option", help="same, as an option")
    parser.add_argument("--detail", action="store_true", help="print one named entry whole")
    parser.add_argument("--all", dest="show_all", action="store_true", help="past the line cap")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    parser.add_argument("--width", type=int, default=0, help="output width, default the terminal")
    args = parser.parse_args(argv)

    width = max(MIN_WIDTH, args.width or shutil.get_terminal_size((100, 24)).columns)
    family = args.family_option or args.family or ""
    usage = "usage: just find <term> [family] [--family key] [--detail] [--all]"

    if not any((args.root / name).is_file() for name in PAGES.values()):
        print(f"no register page under {args.root}: the search failed", file=sys.stderr)
        return 2

    if args.detail:
        key = family or args.term or ""
        if not key:
            print(f"--detail needs the entry's key. {usage}", file=sys.stderr)
            return 2
        return show_detail(args.root, key, args.show_all, width)

    if not args.term:
        print(usage, file=sys.stderr)
        return 2

    hits = search(args.root, args.term, family)
    if not hits:
        scope = f" under family '{family}'" if family else ""
        print(f"no hit for '{args.term}'{scope} in the four register pages", file=sys.stderr)
        return 1
    for line in render(hits, args.show_all, width):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
