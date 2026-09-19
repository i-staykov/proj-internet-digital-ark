"""The cycle's two pieces of real logic: parsing staleness, and not rebuilding twice.

Everything else shells out to a program with its own tests. These two fail in ways a report
would not reveal: a staleness parse error **crashes the entire cycle**, and with an hourly
loop and a 15-minute wake both live, two rebuilds of one target path truncate the file a
collector then reads as a short list rather than as an error.
"""

import importlib.util
import os
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "discover_cycle", Path(__file__).resolve().parents[1] / "scripts/harness/discover_cycle.py"
)
cycle = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cycle)

STALE_LINE = (
    "  [STALE] data/raw/cdx/queue_gap_vps.txt  2026-08-11T13:54:15Z  "
    "0.9h behind the newest pairs  rebuild: build_query_queue.py --population gap"
)


def _parse(text: str) -> dict[str, float]:
    """The parse as `rebuild_derived` performs it, without shelling out to the audit."""
    import re

    out = {}
    for line in text.splitlines():
        if "[STALE]" not in line:
            continue
        parts = line.split()
        hours = next((float(p[:-1]) for p in parts if re.fullmatch(r"[\d.]+h", p)), 0.0)
        out[parts[1]] = hours
    return out


def test_the_hours_field_carries_its_unit_and_must_not_be_floated_whole() -> None:
    """`float("0.9h")` raises, and it took the whole cycle down with it."""
    assert _parse(STALE_LINE) == {"data/raw/cdx/queue_gap_vps.txt": 0.9}


def test_a_line_with_no_hours_field_reads_as_zero_rather_than_raising() -> None:
    assert _parse("  [STALE] some/path.txt  2026-08-11T13:54:15Z  behind") == {"some/path.txt": 0.0}


def test_a_timestamp_is_not_mistaken_for_the_hours_field() -> None:
    """`2026-08-11T13:54:15Z` ends in no `h`, but a looser match on digits would take
    a piece of it. The pattern has to anchor the whole token."""
    assert _parse(STALE_LINE)["data/raw/cdx/queue_gap_vps.txt"] == 0.9


def test_an_absent_lock_has_no_holder(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cycle, "REBUILD_LOCK", tmp_path / "none.lock")
    assert cycle.rebuild_lock_holder() is None


def test_a_lock_held_by_a_live_process_blocks(tmp_path, monkeypatch) -> None:
    lock = tmp_path / "held.lock"
    lock.write_text(str(os.getpid()), encoding="utf-8")
    monkeypatch.setattr(cycle, "REBUILD_LOCK", lock)
    assert cycle.rebuild_lock_holder() == str(os.getpid())


def test_a_lock_whose_holder_is_gone_does_not_block(tmp_path, monkeypatch) -> None:
    """A crashed cycle must not stop every later rebuild, which is how a lock turns
    into the outage it was meant to prevent."""
    lock = tmp_path / "dead.lock"
    # A pid that cannot be running: 0 is never a normal process and os.kill(0, 0)
    # would signal our own group, so use a high pid that is free.
    lock.write_text("999999", encoding="utf-8")
    monkeypatch.setattr(cycle, "REBUILD_LOCK", lock)
    assert cycle.rebuild_lock_holder() is None


def test_a_lock_older_than_the_stale_window_does_not_block(tmp_path, monkeypatch) -> None:
    lock = tmp_path / "old.lock"
    lock.write_text(str(os.getpid()), encoding="utf-8")
    ancient = os.stat(lock).st_mtime - cycle.REBUILD_LOCK_STALE_S - 60
    os.utime(lock, (ancient, ancient))
    monkeypatch.setattr(cycle, "REBUILD_LOCK", lock)
    assert cycle.rebuild_lock_holder() is None


APPROVALS_FIXTURE = """## Decided

### good_source / cdx_timestamp

Decision: master

## Pending requests

### new_source / artifact_listing

Decision: pending
"""

DECISIONS_FIXTURE = """# Key decisions

---

## OPEN

Nothing needs your input.

---

## CLOSED
"""


def test_a_pending_approval_is_mirrored_into_the_one_surface(tmp_path, monkeypatch) -> None:
    """The wiring, not the convention: a `pending` line in a file Ivo does not open is a
    journal waiting on a human who was never told, which the harness reports as the queue
    working (ADR-005).
    """
    approvals = tmp_path / "approved-sources-list.md"
    approvals.write_text(APPROVALS_FIXTURE, encoding="utf-8")
    decisions = tmp_path / "key-decisions.md"
    decisions.write_text(DECISIONS_FIXTURE, encoding="utf-8")
    monkeypatch.setattr(cycle, "APPROVALS", approvals)
    monkeypatch.setattr(cycle, "DECISIONS_DOC", decisions)

    findings, attention = cycle.check_approvals()
    assert cycle.key_decisions.is_open("new_source / artifact_listing", decisions)
    assert any("mirrored into" in f for f in findings)
    assert any("new_source/artifact_listing" in a for a in attention)

    # Idempotent: the cycle runs every fifteen minutes.
    findings2, _ = cycle.check_approvals()
    assert any("already open in key-decisions" in f for f in findings2)
    assert len(cycle.key_decisions.open_titles(decisions)) == 1


def test_an_open_entry_left_behind_after_a_decision_is_flagged(tmp_path, monkeypatch) -> None:
    """The other direction. An OPEN entry for a class that has since been decided makes
    the surface lie about what is waiting, which costs it the trust that makes it work.
    """
    approvals = tmp_path / "approved-sources-list.md"
    approvals.write_text("### settled / artifact_listing\n\nDecision: master\n", encoding="utf-8")
    decisions = tmp_path / "key-decisions.md"
    decisions.write_text(DECISIONS_FIXTURE, encoding="utf-8")
    monkeypatch.setattr(cycle, "APPROVALS", approvals)
    monkeypatch.setattr(cycle, "DECISIONS_DOC", decisions)
    cycle.key_decisions.raise_open(
        "Approve, refuse or downgrade settled / artifact_listing", "Stale.", decisions
    )

    _findings, attention = cycle.check_approvals()
    assert any("no longer pending" in a for a in attention)


def test_unfinished_hypotheses_are_not_raised_at_the_human(tmp_path, monkeypatch) -> None:
    """Ivo: "I had no idea there are hypothesis for me to sign-off." They are the agent's
    queue, so they belong in findings and never in attention.
    """
    ledger = tmp_path / "hypotheses.tsv"
    ledger.write_text(
        "id\tstatus\ttitle\nH003\tscreened\tRFC index\nH009\trejected\tSomething dead\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cycle, "LEDGER", ledger)
    findings, attention = cycle.check_ledger()
    assert attention == []
    assert any("yours to settle" in f for f in findings)


def test_the_cycle_no_longer_knows_how_to_restart_a_collector() -> None:
    """Deliberate absence, not an oversight: an unattended loop does not get to kill
    collectors. A self-matching `pkill -f` once took down a healthy one mid-batch.
    """
    assert not hasattr(cycle, "repoint_pool_engine")
    source = (Path(__file__).resolve().parents[1] / "scripts/harness/discover_cycle.py").read_text(
        encoding="utf-8"
    )
    # The quoted form is how it would appear as a command argument, `run(["pkill", ...])`.
    # Matching the bare word would also match the docstring, which explains at length why
    # this is not here, and a test that forbids describing the mistake is a test that
    # deletes the reason for the rule.
    assert '"pkill"' not in source
    assert "cdx_disc" not in source


def _wave_run(answers):
    """A fake `run` that replies to the two commands `check_wave_chain` issues."""
    calls = []

    def run(cmd, timeout=None):
        calls.append(cmd)
        return answers["dispatch"] if cmd[1] == "workflow" else answers["list"]

    run.calls = calls
    return run


def test_a_quiet_wave_chain_is_restarted(monkeypatch) -> None:
    """The chain ends on a zero-leg wave by design and the cron is meant to restart it.

    Measured 2026-09-19: the cron missed seven consecutive slots and the fleet scouted
    nothing for two and a half hours, so the laptop asks too.
    """
    from datetime import UTC, datetime, timedelta

    old = (datetime.now(UTC) - timedelta(minutes=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
    run = _wave_run({"list": (old, True), "dispatch": ("queued", True)})
    monkeypatch.setattr(cycle, "run", run)
    findings, attention = cycle.check_wave_chain()
    assert any("restarted it" in f for f in findings), findings
    assert attention == [], "a restart that worked is not a thing to wake anyone for"
    assert any(c[1] == "workflow" for c in run.calls), "it never dispatched"


def test_a_busy_wave_chain_is_left_alone(monkeypatch) -> None:
    from datetime import UTC, datetime, timedelta

    recent = (datetime.now(UTC) - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    run = _wave_run({"list": (recent, True), "dispatch": ("queued", True)})
    monkeypatch.setattr(cycle, "run", run)
    findings, _ = cycle.check_wave_chain()
    assert any("5 min ago" in f for f in findings), findings
    assert not any(c[1] == "workflow" for c in run.calls), "it dispatched over a live chain"


def test_a_failed_restart_reaches_a_human(monkeypatch) -> None:
    """A dispatch this laptop cannot make is the one case worth waking someone for."""
    from datetime import UTC, datetime, timedelta

    old = (datetime.now(UTC) - timedelta(minutes=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
    run = _wave_run({"list": (old, True), "dispatch": ("refused", False)})
    monkeypatch.setattr(cycle, "run", run)
    findings, attention = cycle.check_wave_chain()
    assert any("restart failed" in f for f in findings), findings
    assert attention and "no wave" in attention[0]
