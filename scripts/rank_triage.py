"""Sort the triage queue by potential, so the most promising source is signed off first.

Ivo, 2026-08-12: *"Always sort the open sources in approved-sources-list.md by potential, such
that I sign-off more promising sources first."*

**Why this is a program and not a habit.** The queue grows on every wake and is meant to grow
indefinitely, so an ordering maintained by hand decays on the first pass somebody is in a hurry.
Sorting is also the only part of triage a program can do correctly: the judgement is in the score,
which a human wrote into the entry, and this just puts the entries in that order.

**The score is declared, not inferred.** Every entry carries `- potential: <0-100> (<drivers>)` on
its own line, and the rubric behind it is in the file's own header so a reader can argue with it
rather than guess at it. An entry with no score is a hard error rather than a silent zero: a source
that sorts to the bottom because nobody scored it is exactly the one that never gets looked at.

    uv run python scripts/rank_triage.py            # rewrite the section in order
    uv run python scripts/rank_triage.py --check    # exit 1 if it is out of order, write nothing
"""

import argparse
import re
import sys
from pathlib import Path

DOC = Path("docs/approved-sources-list.md")
TRIAGE_HEADING = "## Found, awaiting triage"
# Any `##` heading ends the section, so a later section cannot be swallowed into the sort.
_NEXT_SECTION = re.compile(r"^## ", re.M)
_ENTRY = re.compile(r"^### (?P<slug>\S+) / (?P<etype>\S+)\s*$", re.M)
_POTENTIAL = re.compile(r"^- potential:\s*(?P<score>\d{1,3})\b", re.M)


class Unscored(RuntimeError):
    """An entry with no `- potential:` line, which must not be sorted silently."""


def split_section(text: str) -> tuple[str, str, str]:
    """(before, section body, after) around the triage section."""
    start = text.index(TRIAGE_HEADING)
    body_start = start + len(TRIAGE_HEADING)
    following = _NEXT_SECTION.search(text, body_start)
    end = following.start() if following else len(text)
    return text[:body_start], text[body_start:end], text[end:]


def parse_entries(body: str) -> tuple[str, list[tuple[int, str, str]]]:
    """(preamble, [(score, title, block)]). Blocks keep their own trailing blank line.

    The preamble is everything before the first `###`, which is the section's explanatory
    header and must stay at the top rather than being sorted with the entries.
    """
    marks = list(_ENTRY.finditer(body))
    if not marks:
        return body, []
    preamble = body[: marks[0].start()]
    entries: list[tuple[int, str, str]] = []
    for index, mark in enumerate(marks):
        stop = marks[index + 1].start() if index + 1 < len(marks) else len(body)
        block = body[mark.start() : stop]
        title = f"{mark.group('slug')} / {mark.group('etype')}"
        # "Closed this pass" and similar prose headings are not entries and are excluded by
        # the entry regexp itself, which requires the `slug / type` shape.
        found = _POTENTIAL.search(block)
        if not found:
            raise Unscored(
                f"'{title}' has no `- potential: <0-100>` line.\n"
                f"Every triage entry must declare its own score, because an unscored entry "
                f"sorts to the bottom and is then the one nobody ever looks at."
            )
        entries.append((int(found.group("score")), title, block))
    return preamble, entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DOC)
    parser.add_argument(
        "--check", action="store_true", help="report and exit 1 if out of order, write nothing"
    )
    args = parser.parse_args()

    text = args.path.read_text(encoding="utf-8")
    if TRIAGE_HEADING not in text:
        print(f"no '{TRIAGE_HEADING}' section in {args.path}", file=sys.stderr)
        return 1

    head, body, tail = split_section(text)
    try:
        preamble, entries = parse_entries(body)
    except Unscored as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not entries:
        print("triage queue is empty, nothing to sort")
        return 0

    # Descending by score, then by title so equal scores have a stable order rather than
    # shuffling on every run and producing a diff that says nothing.
    ordered = sorted(entries, key=lambda row: (-row[0], row[1]))
    was_sorted = [e[1] for e in entries] == [e[1] for e in ordered]

    for rank, (score, title, _block) in enumerate(ordered, start=1):
        print(f"{rank:>3}. {score:>3}  {title}")

    if args.check:
        if was_sorted:
            print("\nin order")
            return 0
        print("\nOUT OF ORDER: run `just triage-rank` to rewrite it", file=sys.stderr)
        return 1

    if was_sorted:
        print(f"\n{len(ordered)} entries, already in order")
        return 0

    rebuilt = head + preamble + "".join(block for _s, _t, block in ordered) + tail
    args.path.write_text(rebuilt, encoding="utf-8")
    print(f"\nrewrote {args.path}: {len(ordered)} entries, highest potential first")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
