"""Replaying result lines onto a fleet file that moved under us.

Three times on 2026-09-08 a stale branch dropped work silently, and the worst of them made the
fleet queue over-report: `origin/main` said 24 open hypotheses when 6 were left, because a bank's
push was rejected and the failure was swallowed. The merge is mechanical because both sides only
ever add, so it is worth pinning rather than trusting.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "harness"))

from merge_result_lines import merge  # noqa: E402

REMOTE = "## alpha | a\nfloor: 1\n\n## beta | b\nfloor: 2\n"
OURS = (
    "## alpha | a\nfloor: 1\nresult: CLOSED at 3 EE\n\n"
    "## beta | b\nfloor: 2\n\n## gamma | g\nfloor: 9\n"
)


def test_a_result_line_survives_a_moved_remote() -> None:
    text, kept, added = merge(OURS, REMOTE)
    assert kept == 1 and added == 1
    assert "result: CLOSED at 3 EE" in text
    # The remote's own blocks are all still there, and ours is appended.
    for slug in ("## alpha", "## beta", "## gamma"):
        assert slug in text


def test_the_remote_wins_when_it_carries_more() -> None:
    """A verdict the remote already has must not be reverted by our older copy."""
    remote_with_verdict = REMOTE.replace("floor: 2\n", "floor: 2\nresult: FIND at 9,000 EE\n")
    text, kept, added = merge(OURS, remote_with_verdict)
    assert "result: FIND at 9,000 EE" in text
    assert "result: CLOSED at 3 EE" in text
    assert added == 1


def test_nothing_is_ever_deleted() -> None:
    text, _, _ = merge("## only | o\nfloor: 5\n", REMOTE)
    assert "## alpha" in text and "## beta" in text and "## only" in text
