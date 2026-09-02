"""A count written in prose must match the code it counts.

`ark check` grew from nine invariants to ten on 2026-08-17, and nine days of documentation
went on saying nine: `README.md` in four places, `docs/documentation.md` in two and the
`justfile` in three, including the banner `just ship` prints while running them. Both
`README.md` and `docs/documentation.md` ship to the reviewer, and the report cites the
invariants as the reason the result is trustworthy, so the wrong number is visible exactly
where it costs most.

A hand-written count is a fact about the code stored somewhere the code cannot reach, which
is the same shape as a hardcoded path or a retyped figure. This is the cheapest available
enforcement: it does not generate the prose, it just refuses to let it drift.

Dated log entries are exempt. `docs/notes.md` and the `CLOSED` section of
`docs/key-decisions.md` record what was true on a date, and rewriting them would falsify
history rather than correct it.
"""

import re
from pathlib import Path

from ark.checks import collect_checks
from ark.db import connect, init_db

ROOT = Path(__file__).resolve().parents[1]

# Surfaces that describe the pipeline as it is now. Anything append-only or dated is out.
LIVE_DOCS = (
    "README.md",
    "docs/runbook.md",
    "CLAUDE.md",
    "justfile",
    "docs/documentation.md",
    "docs/delivery_readme.md",
    "docs/discovery.md",
    "docs/report.template.md",
    "docs/metric-explained.md",
    "docs/experience-summary.md",
)

WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}
# "nine invariants", "ten data invariants", "9 integrity invariants".
CLAIM = re.compile(
    r"\b(?P<count>" + "|".join(WORDS) + r"|\d{1,2})\s+(?:data\s+|integrity\s+)?invariants?\b",
    re.I,
)


def _actual() -> int:
    conn = connect(":memory:")
    init_db(conn)
    return len(collect_checks(conn, ROOT / "no-such-export"))


def test_every_live_document_states_the_real_invariant_count() -> None:
    actual = _actual()
    wrong = []
    for name in LIVE_DOCS:
        path = ROOT / name
        if not path.is_file():
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in CLAIM.finditer(line):
                raw = match.group("count").lower()
                claimed = WORDS.get(raw, int(raw) if raw.isdigit() else None)
                # "One invariant reads the exported annual files" counts a single
                # member, not the total, and both live documents use it that way. A
                # document claiming exactly one invariant in total is not a failure mode
                # worth catching at the price of flagging every such sentence.
                if claimed in (None, 1):
                    continue
                if claimed != actual:
                    wrong.append(f"{name}:{line_no} says {claimed}, there are {actual}")
    assert not wrong, "documented invariant counts have drifted from the code:\n  " + "\n  ".join(
        wrong
    )


def test_the_shipped_report_carries_no_unwritten_section() -> None:
    """An empty section 5 reaching the reviewer is what the token mechanism is for.

    `docs/report.template.md` marks each section whose prose a human must write as
    `<!-- ROUND [ROUND]: ... -->`. On 2026-08-18 `docs/report.md` held four of them,
    `fill_report.py --check` reported "would fill cleanly", and `just ship` would have
    packaged a report whose sections 2, 4, 5 and 6 were empty. The template itself calls
    5 and 6 the sections he reads most closely.

    The generated report is checked rather than the template, because the template is
    SUPPOSED to carry the markers between rounds: they are the instruction for writing it.
    """
    report = ROOT / "docs" / "report.md"
    if not report.is_file():
        return  # nothing generated yet in this checkout
    text = report.read_text(encoding="utf-8")
    stubs = [
        line.strip() for line in text.splitlines() if line.lstrip().lower().startswith("<!-- round")
    ]
    assert not stubs, (
        f"docs/report.md has {len(stubs)} unwritten section(s) and would ship that way: {stubs[:2]}"
    )
