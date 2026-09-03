"""A pending amendment must be on its way somewhere.

`docs/brief_amendments.md` is the standing statement of what the reviewer currently asks
for, and intake writes a row into it for every changed paragraph of his brief before a
human has classified it. Such a row carries `pending` in the columns a human fills.

The failure worth guarding is the quiet one: the row is written, nobody classifies it, and
the change it records is never made. So a pending row must do one of two things, both
checkable without reading his mind. Either it quotes words that also stand in
`docs/questions.md`, meaning the ambiguity is on its way back to him, or it names a file
that exists, meaning the change already has a home.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AMENDMENTS = ROOT / "docs" / "brief_amendments.md"
QUESTIONS = ROOT / "docs" / "questions.md"

TABLE_ROW = re.compile(r"^\s*\|(?P<cells>.+)\|\s*$")
PENDING = re.compile(r"\bpending\b", re.I)
# His words, as a row quotes them. Short spans match too much to be evidence of anything.
QUOTED = re.compile(r'"([^"]{12,})"')
# `docs/rules.md`, `src/ark/sources.py`, `scripts/round/package_delivery.sh`.
NAMED_FILE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]*\.[A-Za-z0-9]{2,5}")


def _flatten(text: str) -> str:
    return " ".join(text.split()).lower()


def _rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        match = TABLE_ROW.match(line)
        if match:
            rows.append([cell.strip() for cell in match.group("cells").split("|")])
    return rows


def stranded_pending(amendments: str, questions: str, root: Path) -> list[str]:
    """Pending amendment rows that neither quote an open question nor name a file."""
    asked = _flatten(questions)
    stranded = []
    for cells in _rows(amendments):
        if not any(PENDING.search(cell) for cell in cells):
            continue
        row = " | ".join(cells)
        if any(_flatten(quote) in asked for quote in QUOTED.findall(row)):
            continue
        if any((root / name).is_file() for name in NAMED_FILE.findall(row)):
            continue
        stranded.append(row)
    return stranded


def test_every_pending_amendment_is_asked_or_landed() -> None:
    """No row of the ledger says `pending` without a question or a file behind it."""
    stranded = stranded_pending(
        AMENDMENTS.read_text(encoding="utf-8"), QUESTIONS.read_text(encoding="utf-8"), ROOT
    )
    assert not stranded, "pending amendments with nowhere to go:\n  " + "\n  ".join(stranded)


def test_a_pending_row_needs_the_question_or_the_file() -> None:
    """The check catches a bare pending row and clears the two ways out of it."""
    questions = 'he wrote "count hostnames at full TLD weight" and we asked which weight'
    header = (
        "| date | his words | category | what changed here | landed in |\n|---|---|---|---|---|\n"
    )
    bare = '| 2026-09-04 | "a rule nobody has put to him yet" | scoring | pending | pending |'
    asked = '| 2026-09-04 | "count hostnames at full TLD weight" | scoring | pending | pending |'
    landed = '| 2026-09-04 | "a rule nobody has put to him yet" | scoring | README.md | pending |'

    assert stranded_pending(header + bare, questions, ROOT) == [
        '2026-09-04 | "a rule nobody has put to him yet" | scoring | pending | pending'
    ]
    assert not stranded_pending(header + asked, questions, ROOT)
    assert not stranded_pending(header + landed, questions, ROOT)
