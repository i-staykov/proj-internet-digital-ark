"""The single sign-off surface, and the invariant that keeps it single.

Ivo, 2026-08-11: "Everything I have to sign-off should be in one place, so I know about
it." He had not known the hypothesis ledger was asking him for anything, which is the
whole problem in one sentence: **a question raised in a file nobody opens is not a
question anyone asked**, and the asker believes otherwise.

So the property under test is not "the agent wrote an entry" but "a pending approval
cannot exist without appearing under `## OPEN`". The last test checks that against the
live files, so letting one drift out of sight fails here rather than in a week.
"""

import importlib.util
from pathlib import Path

import pytest

from ark.approvals import pending
from ark.key_decisions import is_open, open_titles, raise_open, refresh_open

# Imported rather than repeated. The literal used to appear here AND in
# `discover_cycle.TRIAGE_HEADING`, so renaming the live entry on 2026-08-15 broke this
# test in a way that read as "the entry is missing" when it was merely retitled. Worse,
# the mirror would then have failed to find it and raised a SECOND copy on the next
# cycle. One definition, one failure, and it fails in the right place.
_SPEC = importlib.util.spec_from_file_location(
    "discover_cycle", Path(__file__).resolve().parents[1] / "scripts" / "discover_cycle.py"
)
_discover_cycle = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_discover_cycle)
TRIAGE_HEADING = _discover_cycle.TRIAGE_HEADING

SKELETON = """# Key decisions

---

## OPEN

Nothing needs your input. ADR-001 is left `Open` as a *question* rather than a decision
waiting on you: the cause is unidentified and an interim rule is in force.

---

## CLOSED

### C-1. Something already decided (2026-08-01)

Body.
"""


def _doc(tmp_path: Path, body: str = SKELETON) -> Path:
    path = tmp_path / "key-decisions.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_an_empty_open_block_has_no_titles(tmp_path) -> None:
    """The placeholder prose is not an entry, and must not read as one."""
    assert open_titles(_doc(tmp_path)) == []


def test_a_closed_entry_is_not_reported_as_open(tmp_path) -> None:
    """The whole value of the surface is that OPEN means OPEN."""
    assert "C-1. Something already decided (2026-08-01)" not in open_titles(_doc(tmp_path))


def test_raising_an_entry_makes_it_open(tmp_path) -> None:
    path = _doc(tmp_path)
    assert raise_open("Approve, refuse or downgrade foo / artifact_listing", "Because.", path)
    assert open_titles(path) == ["Approve, refuse or downgrade foo / artifact_listing"]
    assert is_open("foo / artifact_listing", path)


def test_raising_twice_does_not_duplicate(tmp_path) -> None:
    """The cycle runs every fifteen minutes, so an idempotent raise is the difference
    between a surface and a spam folder."""
    path = _doc(tmp_path)
    assert raise_open("Approve, refuse or downgrade foo / cdx_timestamp", "First.", path)
    assert not raise_open("Approve, refuse or downgrade foo / cdx_timestamp", "Second.", path)
    assert len(open_titles(path)) == 1
    assert "Second." not in path.read_text(encoding="utf-8")


def test_the_nothing_needed_placeholder_is_removed_when_something_is(tmp_path) -> None:
    """Otherwise the file says "nothing needs your input" directly above something that
    does, which is worse than either line alone."""
    path = _doc(tmp_path)
    raise_open("Approve, refuse or downgrade foo / whois_creation", "Because.", path)
    body = path.read_text(encoding="utf-8")
    open_block = body.split("## OPEN", 1)[1].split("## CLOSED", 1)[0]
    assert "Nothing needs your input" not in open_block


def test_the_closed_block_is_untouched(tmp_path) -> None:
    path = _doc(tmp_path)
    raise_open("Approve, refuse or downgrade foo / link_source", "Because.", path)
    body = path.read_text(encoding="utf-8")
    assert "### C-1. Something already decided (2026-08-01)" in body
    assert body.index("## OPEN") < body.index("## CLOSED")
    assert body.index("Approve, refuse or downgrade") < body.index("## CLOSED")


def test_refreshing_replaces_a_live_figure_rather_than_freezing_it(tmp_path) -> None:
    """The bug this exists for: the triage mirror said 11 while 44 were waiting.

    `raise_open` is append-once, so an entry carrying a count froze at whatever it was
    when first written, and the one surface Ivo reads under-reported its own queue by 4x
    with nothing about it looking stale.
    """
    path = _doc(tmp_path)
    raise_open("Triage the newly found sources", "**11 source(s)** are waiting.", path)
    assert refresh_open("Triage the newly found sources", "**44 source(s)** are waiting.", path)
    body = path.read_text(encoding="utf-8")
    assert "**44 source(s)** are waiting." in body
    assert "11 source(s)" not in body
    assert open_titles(path) == ["Triage the newly found sources"]


def test_refreshing_the_last_entry_keeps_the_two_blocks_apart(tmp_path) -> None:
    """The rule above `## CLOSED` belongs to the OPEN block, so a naive end-of-entry
    boundary swallows it and merges the sections."""
    path = _doc(tmp_path)
    raise_open("Triage the newly found sources", "Eleven.", path)
    refresh_open("Triage the newly found sources", "Forty four.", path)
    body = path.read_text(encoding="utf-8")
    assert "\n---\n\n## CLOSED" in body
    assert "### C-1. Something already decided (2026-08-01)" not in open_titles(path)


def test_refreshing_repeatedly_does_not_grow_the_gap_under_the_heading(tmp_path) -> None:
    """The heading pattern ends in `\\s*$` and `\\s` matches newlines, so re-emitting the
    raw match adds a blank line every cycle. At one refresh an hour that is visible by
    morning."""
    path = _doc(tmp_path)
    raise_open("Triage the newly found sources", "One.", path)
    first = path.read_text(encoding="utf-8")
    for n in range(2, 6):
        refresh_open("Triage the newly found sources", f"Count {n}.", path)
    grown = path.read_text(encoding="utf-8")
    assert grown.count("\n") == first.count("\n")
    assert "### Triage the newly found sources\n\nCount 5." in grown


def test_refreshing_an_absent_entry_reports_it_rather_than_creating_one(tmp_path) -> None:
    """A refresh is not a raise. Silently creating the entry would hide a caller that
    got its identifying phrase wrong."""
    path = _doc(tmp_path)
    assert not refresh_open("Triage the newly found sources", "Body.", path)
    assert open_titles(path) == []


def test_newest_is_first_within_the_open_block(tmp_path) -> None:
    path = _doc(tmp_path)
    raise_open("Approve, refuse or downgrade a / cdx_timestamp", "One.", path)
    raise_open("Approve, refuse or downgrade b / cdx_timestamp", "Two.", path)
    assert open_titles(path) == [
        "Approve, refuse or downgrade b / cdx_timestamp",
        "Approve, refuse or downgrade a / cdx_timestamp",
    ]


def test_the_marker_is_a_heading_and_not_a_substring(tmp_path) -> None:
    """The header explains the rule in prose and writes "an `## OPEN` entry".

    A substring split found that sentence rather than the heading and inserted the first
    real entry into the middle of it, cutting the paragraph in half in the live file.
    Matching a structural marker as a substring is the same defect as a glob that matches
    too much: it works until the prose mentions itself.
    """
    body = SKELETON.replace(
        "## OPEN\n",
        "Anything waiting becomes an `## OPEN` entry, mentioned here in prose.\n\n## OPEN\n",
        1,
    )
    path = _doc(tmp_path, body)
    assert raise_open("Approve, refuse or downgrade x / cdx_timestamp", "Body.", path)
    written = path.read_text(encoding="utf-8")
    assert "mentioned here in prose." in written
    assert written.index("mentioned here in prose.") < written.index("Approve, refuse or downgrade")
    assert open_titles(path) == ["Approve, refuse or downgrade x / cdx_timestamp"]


def test_a_file_with_no_open_section_is_an_error_rather_than_a_silent_no_op(tmp_path) -> None:
    path = tmp_path / "key-decisions.md"
    path.write_text("# Nothing structured here\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no `## OPEN`"):
        raise_open("Approve, refuse or downgrade x / cdx_timestamp", "Body.", path)


def test_every_pending_approval_is_surfaced_in_the_live_files() -> None:
    """The invariant, against the real documents, in the two shapes it now has.

    A `pending` class that appears nowhere in `key-decisions.md` is a journal waiting
    indefinitely on a human who was never told, which the harness would report as "the
    queue working". Deliberately runs on the live files: this must fail in the suite,
    not in a week.

    **The invariant is "surfaced", not "named individually", and that distinction is
    load-bearing since 2026-08-12.** A priced request carries a sample and a
    counterfactual, is decidable in two minutes, and earns its own entry. A triage entry
    is a source found and not yet priced, and that queue is meant to grow without bound
    on Ivo's instruction, so naming forty of them individually would push the one surface
    he reads past a screen. Those are represented by a single entry naming the count. Both
    are surfaced; only the granularity differs, and a triage queue with no collective
    entry is exactly as invisible as an unnamed priced request.
    """
    root = Path(__file__).resolve().parents[1]
    approvals = root / "docs" / "approved-sources-list.md"
    decisions = root / "docs" / "key-decisions.md"
    waiting = pending(approvals)

    unsurfaced = [
        f"{a.source_name} / {a.evidence_type}"
        for a in waiting
        if not a.is_triage and not is_open(f"{a.source_name} / {a.evidence_type}", decisions)
    ]
    assert not unsurfaced, (
        "priced pending approvals that Ivo would never see, because key-decisions.md is "
        f"the only surface he reads: {unsurfaced}"
    )

    triage = [a for a in waiting if a.is_triage]
    if triage:
        assert is_open(TRIAGE_HEADING, decisions), (
            f"{len(triage)} source(s) sit in the triage queue with no collective entry "
            "under OPEN, so nobody has been told they are there"
        )
