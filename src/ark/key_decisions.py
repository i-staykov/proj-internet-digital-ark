"""`docs/lore/key-decisions.md`: the one surface that asks Ivo for a decision.

Ivo's instruction: "Everything I have to sign-off should be in one place, so I know about
it." **A question raised in a file nobody reads is a question not raised**, and worse,
because the asker believes it was. So one rule, enforced here rather than remembered:
**anything waiting on a human is named under `## OPEN` in `key-decisions.md`, or it is not
waiting on anyone.** The approvals file is still what `ark ingest` enforces.

**This does not write the reasoning.** An entry's body is prose about a judgement, and
generating that produces confident filler. `raise_open` writes a stub saying what is
waiting and where the working is.
"""

import re
from pathlib import Path

DEFAULT_PATH = Path("docs/lore/key-decisions.md")
OPEN_MARK = "## OPEN"
CLOSED_MARK = "## CLOSED"
# Anchored to the start of a line, because the file's own header explains the rule in
# prose and writes "becomes an `## OPEN` entry". A plain substring split found that
# sentence instead of the heading and inserted the first real entry into the middle of
# it, cutting the paragraph in half. Matching a structural marker as a substring is the
# same defect as a glob that matches too much: it works until the prose mentions itself.
_OPEN_HEADING = re.compile(r"^## OPEN[ \t]*$", re.M)
_CLOSED_HEADING = re.compile(r"^## CLOSED[ \t]*$", re.M)
# The placeholder that stands in for an empty OPEN block. It has to go when a real
# entry arrives, or the file says "nothing needs your input" directly above something
# that does, which is worse than either alone.
PLACEHOLDER_RE = re.compile(r"^Nothing needs your input\.[^\n]*(\n(?!##|###|---)[^\n]*)*\n?", re.M)
_HEADING_RE = re.compile(r"^###\s+(?P<title>.+?)\s*$", re.M)
# An entry ends at the next entry, or at the rule that closes the block. Without the
# second boundary, refreshing the last OPEN entry eats the `---` above `## CLOSED` and
# the two sections merge.
_RULE_RE = re.compile(r"^---[ \t]*$", re.M)


def _split(text: str) -> tuple[str, str, str]:
    """(before the OPEN heading, the OPEN block, from the CLOSED heading onwards)."""
    opened = _OPEN_HEADING.search(text)
    if opened is None:
        raise ValueError(f"key-decisions.md has no `{OPEN_MARK}` section heading")
    head, rest = text[: opened.start()], text[opened.end() :]
    closed = _CLOSED_HEADING.search(rest)
    if closed is None:
        return head, rest, ""
    return head, rest[: closed.start()], rest[closed.start() :]


def open_titles(path: Path | str | None = None) -> list[str]:
    """The `### ` headings currently under `## OPEN`, in file order."""
    path = Path(path) if path is not None else DEFAULT_PATH
    if not path.exists():
        return []
    _head, body, _tail = _split(path.read_text(encoding="utf-8"))
    return [m.group("title") for m in _HEADING_RE.finditer(body)]


def is_open(needle: str, path: Path | str | None = None) -> bool:
    """Whether some OPEN entry's heading contains `needle`.

    Substring rather than equality on purpose: the caller owns a stable identifying
    phrase, such as a source and evidence type, and the agent is free to write a
    better heading around it without the check then reporting the entry as missing.
    """
    return any(needle in title for title in open_titles(path))


def raise_open(heading: str, body: str, path: Path | str | None = None) -> bool:
    """Append an OPEN entry. Returns False if one already carries this heading.

    Newest first inside the block, matching the file's own stated convention.
    """
    path = Path(path) if path is not None else DEFAULT_PATH
    text = path.read_text(encoding="utf-8")
    head, block, tail = _split(text)
    if any(heading in title for title in (m.group("title") for m in _HEADING_RE.finditer(block))):
        return False
    block = PLACEHOLDER_RE.sub("", block).strip("\n")
    entry = f"### {heading}\n\n{body.strip()}\n"
    block = f"\n\n{entry}\n{block}\n\n" if block else f"\n\n{entry}\n"
    path.write_text(head + OPEN_MARK + block + tail, encoding="utf-8")
    return True


def refresh_open(
    needle: str,
    body: str,
    path: Path | str | None = None,
    heading: str | None = None,
) -> bool:
    """Rewrite the body of the OPEN entry whose heading contains `needle`.

    **For an entry that carries a live figure rather than a question.** `raise_open` is
    append-once, which is right for a judgement and wrong for a count: a stale number on the
    one surface Ivo reads is worse than no number, because it reads as current.

    The heading is left exactly as found, so one an agent improved by hand survives the
    refresh. Returns False if no OPEN entry matches.

    **Pass `heading` when the heading itself carries the live figure**, or the entry
    disagrees with itself and the stale half is the half he reads first.
    """
    path = Path(path) if path is not None else DEFAULT_PATH
    text = path.read_text(encoding="utf-8")
    head, block, tail = _split(text)
    headings = list(_HEADING_RE.finditer(block))
    for i, match in enumerate(headings):
        if needle not in match.group("title"):
            continue
        ends = [len(block)]
        if i + 1 < len(headings):
            ends.append(headings[i + 1].start())
        rule = _RULE_RE.search(block, match.end())
        if rule is not None:
            ends.append(rule.start())
        end = min(ends)
        # Rebuilt from the title rather than reused from `group(0)`: the heading pattern
        # ends in `\s*$`, and `\s` matches newlines, so the match greedily swallows the
        # blank lines below the heading and re-emitting it grows a gap on every refresh.
        title = heading.strip() if heading else match.group("title")
        entry = f"### {title}\n\n{body.strip()}\n\n"
        path.write_text(
            head + OPEN_MARK + block[: match.start()] + entry + block[end:] + tail,
            encoding="utf-8",
        )
        return True
    return False
