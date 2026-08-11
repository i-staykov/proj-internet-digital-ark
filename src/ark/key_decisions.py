"""`docs/key-decisions.md`: the one surface that asks Ivo for a decision.

**Why this is a module and not a convention.** Ivo's instruction, 2026-08-11:
"Everything I have to sign-off should be in one place, so I know about it." Before
that there were three places. `notes.md` entries each ended asking for a sign-off he
does not give and does not want; the approvals file accumulated `pending` classes he
had no reason to open; and the hypothesis ledger surfaced five unfinished leads as
though they were his to judge, which he had not known existed. **A question raised in
a file nobody reads is the same as a question not raised**, and worse, because the
asker believes it was.

So there is one rule, enforced here rather than remembered: **anything waiting on a
human is named under `## OPEN` in `key-decisions.md`, or it is not waiting on anyone.**
The other files keep their jobs. The approvals file is still what `ark ingest` enforces
and still the thing he edits; this only guarantees he learns that it wants him.

**What this deliberately does not do.** It does not write the reasoning. An entry's
body is prose about a judgement, and generating that would produce exactly the
confident filler this project distrusts. `raise_open` writes a stub that says what is
waiting and where the working is, and it is the agent's job to make it worth reading.
"""

import re
from pathlib import Path

DEFAULT_PATH = Path("docs/key-decisions.md")
OPEN_MARK = "## OPEN"
CLOSED_MARK = "## CLOSED"
# The placeholder that stands in for an empty OPEN block. It has to go when a real
# entry arrives, or the file says "nothing needs your input" directly above something
# that does, which is worse than either alone.
PLACEHOLDER_RE = re.compile(r"^Nothing needs your input\.[^\n]*(\n(?!##|###|---)[^\n]*)*\n?", re.M)
_HEADING_RE = re.compile(r"^###\s+(?P<title>.+?)\s*$", re.M)


def _split(text: str) -> tuple[str, str, str]:
    """(before OPEN block, OPEN block, from CLOSED onwards)."""
    if OPEN_MARK not in text:
        raise ValueError(f"key-decisions.md has no `{OPEN_MARK}` section")
    head, rest = text.split(OPEN_MARK, 1)
    if CLOSED_MARK in rest:
        body, tail = rest.split(CLOSED_MARK, 1)
        return head, body, CLOSED_MARK + tail
    return head, rest, ""


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
