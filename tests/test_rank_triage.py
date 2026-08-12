"""Ordering of the triage queue, which Ivo reads top down.

He signs off the most promising source first, so the order IS the interface. Two things
must hold: an unscored entry stops the sort loudly rather than sinking to the bottom, and
sorting must not disturb anything outside the section, since the same file is the gate
`ark ingest` enforces.
"""

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "rank_triage", Path(__file__).resolve().parents[1] / "scripts" / "rank_triage.py"
)
rank_triage = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rank_triage)

HEADER = "# x\n\n## Found, awaiting triage\n\nsome preamble\n\n"
AFTER = (
    "## Approved before this mechanism existed\n\n### held / artifact_listing\n\nDecision: master\n"
)


def _entry(slug: str, score: int) -> str:
    return f"### {slug} / whois_creation\n\n- potential: {score} (because)\n\nDecision: pending\n\n"


def test_entries_are_rewritten_highest_potential_first(tmp_path):
    doc = tmp_path / "a.md"
    doc.write_text(HEADER + _entry("low", 10) + _entry("high", 90) + _entry("mid", 50) + AFTER)
    import sys

    sys.argv = ["rank_triage", "--path", str(doc)]
    assert rank_triage.main() == 0
    order = [line for line in doc.read_text().splitlines() if line.startswith("### ")]
    assert order[:3] == [
        "### high / whois_creation",
        "### mid / whois_creation",
        "### low / whois_creation",
    ]


def test_a_later_section_is_not_swallowed_into_the_sort(tmp_path):
    """The same file is the gate. Sorting must not move an approved entry."""
    doc = tmp_path / "a.md"
    doc.write_text(HEADER + _entry("low", 10) + _entry("high", 90) + AFTER)
    import sys

    sys.argv = ["rank_triage", "--path", str(doc)]
    rank_triage.main()
    text = doc.read_text()
    assert text.rstrip().endswith("Decision: master")
    assert (
        "### held / artifact_listing" in text.split("## Approved before this mechanism existed")[1]
    )


def test_an_unscored_entry_is_a_hard_error(tmp_path):
    doc = tmp_path / "a.md"
    doc.write_text(HEADER + "### forgot / whois_creation\n\nDecision: pending\n\n" + AFTER)
    with pytest.raises(rank_triage.Unscored, match="forgot / whois_creation"):
        rank_triage.parse_entries(rank_triage.split_section(doc.read_text())[1])


def test_the_live_queue_is_in_order():
    """Against the real file, so a hand edit that breaks the order fails the suite."""
    doc = Path(__file__).resolve().parents[1] / "docs" / "approved-sources-list.md"
    _head, body, _tail = rank_triage.split_section(doc.read_text())
    _preamble, entries = rank_triage.parse_entries(body)
    keys = [(row[3], -row[0]) for row in entries]
    assert keys == sorted(keys), f"triage queue is out of order: {keys}"


def test_a_decided_entry_sinks_below_everything_still_open(tmp_path):
    """The instruction is to sort the OPEN sources, so a decided one must not hold rank 3.

    educause_edu_whois_activation scored 78 and was rejected on the server's own terms. Sorting
    on score alone put it third in a queue whose entire purpose is to show what still needs a
    decision.
    """
    import sys

    doc = tmp_path / "a.md"
    decided = "### done / whois_creation\n\n- potential: 99 (top)\n\nDecision: rejected\n\n"
    doc.write_text(HEADER + decided + _entry("open_low", 5) + AFTER)
    sys.argv = ["rank_triage", "--path", str(doc)]
    assert rank_triage.main() == 0
    order = [line for line in doc.read_text().splitlines() if line.startswith("### ")]
    assert order[:2] == ["### open_low / whois_creation", "### done / whois_creation"]
