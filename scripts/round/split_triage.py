"""Split the triage section of `docs/registers/approved-sources-list.md` by Decision.

`## Found, awaiting triage` grew to 100 entries holding three populations under one
heading: master blocks that are the ingest gate's approval record, rejected blocks with
a measured figure, and open hypotheses nobody has priced. The gate reads a `Decision:`
line wherever it sits, so moving a block changes no decision:

- `master` blocks move into `## Decided, ...` unchanged;
- `rejected` blocks become one row each in `docs/registers/sources-closed.md`, replacing the
  source's old row there, and leave a two-line stub (heading and `Decision: rejected`) in
  Decided, so `ark ingest` and the request generator keep refusing them; the full block stays
  in this file's history;
- everything else, the pending blocks with whatever prose sits inside them, stays in
  triage. One queue, one place; `queue.md` ranks what is worth deciding.

Safe to run again when decided blocks accumulate in triage: blocks are appended, and a row
replaces the one its source already has.

    uv run python scripts/round/split_triage.py --dry-run
    uv run python scripts/round/split_triage.py
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/harness"))

from bank_findings import drop_decision_numbers, links  # noqa: E402

from ark.approvals import parse as parse_approvals  # noqa: E402

DOC = Path("docs/registers/approved-sources-list.md")
CLOSED = Path("docs/registers/sources-closed.md")
TRIAGE_HEADING = "## Found, awaiting triage"
DECIDED_HEADING = "## Decided, with the request that was reviewed"
CLOSED_COLUMNS = ("source", "date", "measured", "reason", "link")
VERDICT = "REJECTED"
# The hygiene limit for table pages; a longer row is one nobody reads.
ROW_LIMIT = 500
REASON_LIMIT = 280

_NEXT_SECTION = re.compile(r"^## ", re.M)
_ENTRY = re.compile(r"^### (?P<slug>\S+) / (?P<etype>\S+)\s*$", re.M)
# Wider than the gate's own regexp on purpose: one entry reads "Decision: pending, but
# externally blocked", which the gate ignores and this split must still move.
_DECISION = re.compile(r"^Decision:\s*(?P<value>master|rejected|pending|candidate-only)\b", re.M)
_DECISION_LINE = re.compile(r"^\s*Decision:", re.M)
_ISO_DATE = re.compile(r"\b(20\d\d-\d\d-\d\d)\b")
_EE = re.compile(r"(?P<figure>~?\d[\d,]*(?:\.\d+)?)\s*(?:net-new\s+)?(?:post-split\s+)?EE\b")
_URL = re.compile(r"https?://[^\s`)>\]<]+")
_MEASURED = re.compile(r"^- measured:\s*(.+?)(?=\n- |\n\n|\Z)", re.M | re.S)
_BOLD_BULLET = re.compile(r"^- \*\*(.+?)(?=\n- |\n\n|\Z)", re.M | re.S)
_TABLE_ROW = re.compile(r"^\|.*\|\s*$")
_TABLE_RULE = re.compile(r"^\|[\s:|-]+\|\s*$")
_PIPE = re.compile(r"(?<!\\)\|")
_LEGACY_ROW = re.compile(r"^\|\s*\d+\s*\|\s*(?P<slug>\S+)")
# A figure in this company is a bound or a projection, not what the source paid.
_NOT_MEASURED = re.compile(r"ceiling|floor|gross|pre-split|band|estimate|project|about", re.I)
_SPLIT_WORDS = re.compile(r"post-split|after the split", re.I)
# Matched against the row's reason only, not the whole verdict, so a passing mention of
# a superseded test elsewhere in the block cannot relabel a measured figure.
_DUPLICATE = re.compile(
    r"duplicate|superseded, not refused|same artifact as|same corpus as|"
    r"one artifact under two entries",
    re.I,
)


@dataclass(frozen=True)
class Block:
    slug: str
    etype: str
    text: str
    decision: str

    @property
    def key(self) -> str:
        return f"{self.slug} / {self.etype}"


def split_section(text: str, heading: str) -> tuple[str, str, str]:
    """(before, section body, after). The body starts right after the heading line."""
    start = text.index(heading)
    body_start = start + len(heading)
    following = _NEXT_SECTION.search(text, body_start)
    end = following.start() if following else len(text)
    return text[:body_start], text[body_start:end], text[end:]


def parse_blocks(body: str) -> tuple[str, list[Block]]:
    """(preamble, blocks). A block runs from its heading to the next one, blank lines kept."""
    marks = list(_ENTRY.finditer(body))
    if not marks:
        return body, []
    preamble = body[: marks[0].start()]
    blocks: list[Block] = []
    for index, mark in enumerate(marks):
        stop = marks[index + 1].start() if index + 1 < len(marks) else len(body)
        chunk = body[mark.start() : stop]
        found = _DECISION.findall(chunk)
        if len(found) != 1:
            raise SystemExit(
                f"{mark.group('slug')} carries {len(found)} Decision lines; fix it before splitting"
            )
        blocks.append(Block(mark.group("slug"), mark.group("etype"), chunk, found[0]))
    return preamble, blocks


def _plain(text: str) -> str:
    return " ".join(text.replace("**", "").split())


def _sentences(text: str, limit: int) -> str:
    """Whole sentences from the front of the text, up to the limit; a long first one is clipped."""
    parts = re.split(r"(?<=\.)\s+(?=[A-Z`*\"(])", _plain(text))
    out = ""
    for part in parts:
        if out and len(out) + 1 + len(part) > limit:
            # A one-line opener followed by the real reason: clip the reason rather than
            # drop it, so the row says more than "Not an open question".
            if len(out) < limit // 2:
                out = f"{out} {part}"
            break
        out = f"{out} {part}".strip()
    if len(out) > limit:
        out = out[: limit - 3].rsplit(" ", 1)[0] + "..."
    return out


def _figure(text: str) -> str | None:
    """The EE figure the block reports as measured, or None.

    Post-split phrasing wins, then a figure the text calls measured, then the first one
    left; anything a bound, projection or approximation is skipped. Context is read within
    the figure's own sentence, and to the right only up to the next punctuation, so one
    figure's "floor" cannot disqualify the next.
    """
    text = _plain(text)
    best: tuple[int, int, str] | None = None
    for found in _EE.finditer(text):
        figure = found.group("figure")
        left = text[: found.start()].rsplit(". ", 1)[-1]
        right = re.split(r"[,.;()]", text[found.end() :], maxsplit=1)[0]
        if figure.startswith("~") or _NOT_MEASURED.search(left[-25:] + " " + right):
            continue
        if _SPLIT_WORDS.search(left[-30:] + " " + right):
            rank = 0
        elif "measured" in left.lower():
            rank = 1
        else:
            rank = 2
        if best is None or rank < best[0]:
            best = (rank, found.start(), figure)
    return best[2] if best else None


def legacy_table(body: str) -> dict[str, list[str]]:
    """Rows of the old triage table in the section, keyed by source slug."""
    out: dict[str, list[str]] = {}
    for line in body.splitlines():
        found = _LEGACY_ROW.match(line)
        if found:
            out[found.group("slug")] = [c.strip() for c in line.strip().strip("|").split("|")]
    return out


def closed_fields(block: Block, table: dict[str, list[str]]) -> dict[str, str]:
    """The five columns of a closed row, read from the block's own words.

    The verdict is whatever follows the Decision line; when the writer put it above the
    line instead, the last bold bullet is the verdict, then the measured bullet. A block
    with none of those falls back to its row in the section's legacy table. The reason
    opens with REJECTED, the verdict word every closed row starts with, and cites no
    decision number.
    """
    head, _, tail = block.text.partition("\nDecision:")
    verdict = tail.partition("\n")[2].strip()
    bold = _BOLD_BULLET.findall(head)
    measured = _MEASURED.search(head)
    candidates = [verdict] + bold[::-1] + ([measured.group(1)] if measured else [])
    source = next((c for c in candidates if c.strip()), "")
    reason = _sentences(source, REASON_LIMIT)
    row = table.get(block.slug)
    figure = None
    if reason:
        figure = _figure(source) or (_figure(measured.group(1)) if measured else None)
    elif row and len(row) >= 7:
        # Legacy table: #, source, what dates an item, type, net-new pairs, EE, evidence, decision
        reason = f"{row[2]}; net-new pairs {row[4]}; evidence {row[6]}"
        figure = row[5] if re.fullmatch(r"[\d,.]+", row[5]) else None
    reason = " ".join(drop_decision_numbers(reason).split())
    if _DUPLICATE.search(reason):
        priced = "duplicate"
    else:
        priced = f"{figure} EE" if figure else "not priced"
    stamps = _ISO_DATE.findall(source) or _ISO_DATE.findall(block.text)
    link = _URL.search(block.text)
    return {
        "source": block.key,
        "date": max(stamps) if stamps else "",
        "measured": priced,
        # A reason that already opens with the verdict keeps its own words after it.
        "reason": (
            VERDICT + reason[len(VERDICT) :]
            if re.match(rf"{VERDICT}\b", reason, re.I)
            else f"{VERDICT}. {reason}".strip()
        ),
        "artifact": link.group(0).rstrip(".,;") if link else "",
    }


def _pick(fields: dict[str, str], column: str) -> str:
    """The field a column of another header most plausibly wants; unknown columns stay empty."""
    name = column.lower()
    for words, key in (
        (("source", "name"), "source"),
        (("date",), "date"),
        (("measured", "ee", "figure"), "measured"),
        (("reason", "verdict", "why"), "reason"),
        (("link", "url"), "link"),
    ):
        if any(re.search(rf"\b{w}\b", name) for w in words):
            return fields[key]
    return ""


def closed_row(fields: dict[str, str], columns: tuple[str, ...]) -> str:
    """One table row in the page's own column order.

    Over the limit the reason gives way first, after its verdict word. The link cell holds the
    artifact, then each URL the reason names, which is what the compactor would make of it.
    """
    fields = {**fields, "link": links(fields["artifact"], [fields["reason"]])}
    row = "| " + " | ".join(_pick(fields, c).replace("|", "\\|") for c in columns) + " |"
    head, why = fields["reason"][: len(VERDICT) + 1].rstrip(), fields["reason"][len(VERDICT) + 1 :]
    if len(row) > ROW_LIMIT and len(why) > 40:
        shorter = {**fields, "reason": f"{head} {_sentences(why, len(why) - 40)}"}
        return closed_row(shorter, columns)
    return row


def source_key(cell: str) -> str:
    """The key a source cell files under, as the compactor reads it: its name before ` / type`."""
    return re.sub(r"[^a-z0-9]+", "-", cell.split(" / ")[0].strip("`* ").lower()).strip("-")


def existing_columns(text: str) -> tuple[str, ...] | None:
    """Column names of the first table on a page, or None when it has no table."""
    lines = text.splitlines()
    for first, second in zip(lines, lines[1:], strict=False):
        if _TABLE_ROW.match(first) and _TABLE_RULE.match(second):
            return tuple(c.strip() for c in first.strip().strip("|").split("|"))
    return None


def closed_page(existing: str | None, rows: list[dict[str, str]]) -> str:
    """The closed-sources page with the rows in its one table: one row per source, so a row
    replaces the one its source already has, and a new source's row goes at the end.

    The date is the latest one the entry cites, the figure is what the entry reports as
    measured, and the full block is in the approved list's history before the split.
    """
    columns = existing_columns(existing) if existing else None
    if existing is None or columns is None:
        page = (
            "# Closed sources\n\n"
            "One row per source measured and closed, so nobody re-tests it. Look one up with "
            "`just find <term>`.\n\n"
            f"| {' | '.join(CLOSED_COLUMNS)} |\n|{'---|' * len(CLOSED_COLUMNS)}\n"
        )
        return page + "".join(closed_row(r, CLOSED_COLUMNS) + "\n" for r in rows)
    lines = existing.rstrip("\n").split("\n")
    start = next(i for i, line in enumerate(lines) if _TABLE_RULE.match(line)) + 1
    end = start
    while end < len(lines) and _TABLE_ROW.match(lines[end]):
        end += 1
    table = lines[start:end]
    where = next((i for i, c in enumerate(columns) if re.search(r"\b(source|name)\b", c, re.I)), 0)
    keys = [source_key((_PIPE.split(line.strip()[1:]) + [""] * where)[where]) for line in table]
    for fields in rows:
        key, row = source_key(fields["source"]), closed_row(fields, columns)
        if key in keys:
            table[keys.index(key)] = row
        else:
            table.append(row)
            keys.append(key)
    return "\n".join([*lines[:start], *table, *lines[end:]]) + "\n"


def _blocks_text(blocks: list[Block]) -> str:
    return "".join(b.text.rstrip("\n") + "\n\n" for b in blocks)


def rebuild_register(
    text: str, masters: list[Block], rejected: list[Block], kept: list[Block], preamble: str
) -> str:
    before, _body, after = split_section(text, TRIAGE_HEADING)
    decided_before, decided_body, decided_after = split_section(before, DECIDED_HEADING)
    # A rejected block leaves its stub, which keeps the rejection binding for `ark ingest`
    # and the request generator; its row is in `sources-closed.md`.
    stubs = "".join(f"### {b.key}\nDecision: rejected\n\n" for b in rejected)
    decided_body = decided_body.rstrip("\n") + "\n\n" + _blocks_text(masters) + stubs
    # The undecided blocks stay here, under the section's own preamble: one queue in one
    # place, ranked by measured EE in the generated `queue.md`.
    intro = preamble.strip()
    triage_body = "\n\n" + (f"{intro}\n\n" if intro else "") + _blocks_text(kept)
    # `split_section` keeps each heading at the end of its `before` part.
    text = decided_before + decided_body.rstrip("\n") + "\n\n" + decided_after + triage_body + after
    return text.rstrip("\n") + "\n"


def decisions_by_value(text: str) -> Counter:
    return Counter(m.group("value") for m in _DECISION.finditer(text))


def gate_reads(text: str, value: str) -> set[tuple[str, str]]:
    """What the gate itself would read from this text, through its own parser."""
    return {k for k, a in parse_approvals(text).items() if a.decision == value}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DOC)
    parser.add_argument("--closed", type=Path, default=CLOSED)
    parser.add_argument("--dry-run", action="store_true", help="report the split, write nothing")
    args = parser.parse_args()

    text = args.path.read_text(encoding="utf-8")
    if TRIAGE_HEADING not in text or DECIDED_HEADING not in text:
        print(f"{args.path} lacks the triage or the decided heading", file=sys.stderr)
        return 1
    _before, body, _after = split_section(text, TRIAGE_HEADING)
    preamble, blocks = parse_blocks(body)
    masters = [b for b in blocks if b.decision == "master"]
    rejected = [b for b in blocks if b.decision == "rejected"]
    kept = [b for b in blocks if b.decision not in ("master", "rejected")]
    if not blocks:
        print("the triage section is empty, nothing to split")
        return 0

    table = legacy_table(body)
    rows = [closed_fields(b, table) for b in rejected]
    register = rebuild_register(text, masters, rejected, kept, preamble)
    existing = args.closed.read_text(encoding="utf-8") if args.closed.exists() else None
    closed = closed_page(existing, rows)
    columns = (existing_columns(existing) if existing else None) or CLOSED_COLUMNS

    headings = re.findall(r"^## .*$", text, re.M)
    if re.findall(r"^## .*$", register, re.M) != headings:
        print("the rewrite changed the section headings", file=sys.stderr)
        return 1
    still_in_triage = [
        a for a in parse_approvals(register).values() if a.is_triage and a.decision != "pending"
    ]
    if still_in_triage:
        print(f"{len(still_in_triage)} decided entries still read as triage", file=sys.stderr)
        return 1

    was, now = decisions_by_value(text), decisions_by_value(register)
    print(f"triage blocks: {len(blocks)} = {len(masters)} master + {len(rejected)} rejected")
    print(f"  + {len(kept)} pending or unparsed, left in triage")
    lines_before = len(_DECISION_LINE.findall(text))
    lines_after = len(_DECISION_LINE.findall(register))
    print(f"Decision lines: {lines_before} before, {lines_after} after")
    for value in ("master", "rejected", "pending", "candidate-only"):
        print(f"  {value:15} {was[value]:>4} -> {now[value]:>4}")
    for value in ("master", "rejected", "candidate-only"):
        a, b = gate_reads(text, value), gate_reads(register, value)
        print(f"gate reads {value}: {len(a)} before, {len(b)} after, identical={a == b}")
        if a != b:
            print(f"the {value} set changed: {sorted(a ^ b)}", file=sys.stderr)
            return 1
    if was["master"] != now["master"] or was["rejected"] != now["rejected"]:
        print("a master or rejected Decision line went missing", file=sys.stderr)
        return 1
    if was["pending"] != now["pending"]:
        print("a pending Decision line went missing", file=sys.stderr)
        return 1
    # Only the rows this run writes: a row already on the page is not this run's to refuse.
    long_rows = [r for r in (closed_row(f, columns) for f in rows) if len(r) > ROW_LIMIT]
    if long_rows:
        print(f"{len(long_rows)} new closed rows exceed {ROW_LIMIT} chars", file=sys.stderr)
        return 1
    if args.dry_run:
        for fields in rows:
            print(closed_row(fields, CLOSED_COLUMNS))
        return 0

    args.path.write_text(register, encoding="utf-8")
    args.closed.write_text(closed, encoding="utf-8")
    print(f"wrote {args.path}, {args.closed} (+{len(rows)} rows); {len(kept)} left in triage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
