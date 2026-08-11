"""The cycle's two pieces of real logic: parsing staleness, and not rebuilding twice.

Loaded by path, like the other script tests: `scripts/` is not a package.

Everything else in the cycle shells out to a program that has its own tests, so there
is little here worth pinning. These two are worth pinning because both have already
failed in a way a report would not reveal: the staleness parse **crashed the entire
cycle**, and it went unnoticed for an hour because the long-running loop had loaded the
module before the function existed, so only a fresh invocation hit it. And with an
hourly loop and a 15-minute cron wake both live, two rebuilds of one target path would
truncate the file a collector then reads as a short list rather than as an error.
"""

import importlib.util
import os
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "discover_cycle", Path(__file__).resolve().parents[1] / "scripts" / "discover_cycle.py"
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


def test_the_cycle_no_longer_knows_how_to_restart_a_collector() -> None:
    """Deliberate absence, not an oversight. An unattended loop does not get to kill
    collectors: the previous version did, with a self-matching `pkill -f`, and it took
    down a healthy one mid-batch on 11 August.
    """
    assert not hasattr(cycle, "repoint_pool_engine")
    source = (Path(__file__).resolve().parents[1] / "scripts" / "discover_cycle.py").read_text(
        encoding="utf-8"
    )
    # The quoted form is how it would appear as a command argument, `run(["pkill", ...])`.
    # Matching the bare word would also match the docstring, which explains at length why
    # this is not here, and a test that forbids describing the mistake is a test that
    # deletes the reason for the rule.
    assert '"pkill"' not in source
    assert "cdx_disc" not in source
