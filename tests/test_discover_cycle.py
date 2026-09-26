"""The cycle's two pieces of real logic: parsing staleness, and not rebuilding twice.

Everything else shells out to a program with its own tests. These two fail in ways a report
would not reveal: a staleness parse error **crashes the entire cycle**, and with an hourly
loop and a 15-minute wake both live, two rebuilds of one target path truncate the file a
collector then reads as a short list rather than as an error.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "discover_cycle", Path(__file__).resolve().parents[1] / "scripts/harness/discover_cycle.py"
)
cycle = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cycle)


def test_the_staleness_parse_takes_hours_with_their_unit(tmp_path, monkeypatch) -> None:
    """`float("0.9h")` raises and took the whole cycle down; no hours field reads as zero."""
    audit = (
        "  [STALE] data/raw/rdap/pool_targets_measured.txt  2026-08-11T13:54:15Z  0.9h behind\n"
        "  [STALE] some/path.txt  2026-08-11T13:54:15Z  behind\n"
    )
    monkeypatch.setattr(cycle, "run", lambda *a, **k: (audit, True))
    monkeypatch.setattr(cycle, "REBUILD_LOCK", tmp_path / "rebuild.lock")
    assert cycle.rebuild_derived()[0] == [
        "derived: pool_targets_measured.txt 0.9h behind, under the threshold",
        "derived: path.txt 0.0h behind, under the threshold",
    ]


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


def _fleet(tmp_path, max_parallel) -> Path:
    fleet = tmp_path / "fleet"
    fleet.mkdir()
    (fleet / "policy.json").write_text(json.dumps({"wave": {"max_parallel": max_parallel}}))
    return fleet


def _fake_gh(tmp_path, monkeypatch, runs) -> Path:
    """A `gh` on PATH that records its argv, one call per line. `run list` prints `runs` as
    JSON, or, given a string, prints it to stderr and exits 1 the way an HTTP error does."""
    log, answer = tmp_path / "gh.log", tmp_path / "answer"
    answer.write_text(json.dumps(runs) if isinstance(runs, list) else runs)
    rc = 0 if isinstance(runs, list) else 1
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        f'#!/bin/sh\necho "$*" >> "{log}"\n'
        f'[ "$1 $2" = "run list" ] || exit 0\n'
        f'if [ {rc} = 0 ]; then cat "{answer}"; else cat "{answer}" >&2; fi\nexit {rc}\n'
    )
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return log


def test_an_idle_leg_slot_is_reported_and_nothing_is_dispatched(tmp_path, monkeypatch) -> None:
    """`leg.yaml`'s schedule is the watchdog that starts an idle slot, so the laptop reports
    and never runs `gh workflow run`: the old check dispatched the next wave itself."""
    runs = [
        {"displayTitle": "Leg watchdog", "status": "in_progress"},
        {"displayTitle": "Leg slot 0", "status": "in_progress"},
        {"displayTitle": "Leg slot 1", "status": "completed"},
        {"displayTitle": "Leg slot 2", "status": "queued"},
        {"displayTitle": "Leg slot 01", "status": "in_progress"},
        {"displayTitle": "Leg slot 5", "status": "in_progress"},
    ]
    log = _fake_gh(tmp_path, monkeypatch, runs)
    findings, attention = cycle.check_leg_slots(_fleet(tmp_path, 3))
    said = "leg slots: 1 of 3 idle (slot 1), for leg.yaml's watchdog to start"
    assert (findings, attention) == ([said], [])
    calls = log.read_text().splitlines()
    assert len(calls) == 1 and calls[0].startswith("run list"), calls
    assert "--workflow leg.yaml" in calls[0]
    assert not any(c.startswith("workflow") for c in calls), "it dispatched a workflow"


def test_every_slot_held_says_so(tmp_path, monkeypatch) -> None:
    runs = [
        {"displayTitle": "Leg slot 0", "status": "waiting"},
        {"displayTitle": "Leg slot 1", "status": "in_progress"},
    ]
    _fake_gh(tmp_path, monkeypatch, runs)
    findings, _ = cycle.check_leg_slots(_fleet(tmp_path, 2))
    assert findings == ["leg slots: all 2 held by a run"]


def test_a_zero_bound_asks_github_nothing(tmp_path, monkeypatch) -> None:
    """`max_parallel` 0 stops every slot, which is how Leg lands, so no slot is idle."""
    log = _fake_gh(tmp_path, monkeypatch, [])
    findings, _ = cycle.check_leg_slots(_fleet(tmp_path, 0))
    assert findings == ["leg slots: policy.json wave.max_parallel is 0, so no slot runs"]
    assert not log.exists()


def test_a_workflow_github_cannot_find_is_could_not_check(tmp_path, monkeypatch) -> None:
    """Until `leg.yaml` is on the fleet's main, gh answers 404, which is not an idle fleet."""
    _fake_gh(tmp_path, monkeypatch, "HTTP 404: workflow leg.yaml not found on the default branch")
    findings, attention = cycle.check_leg_slots(_fleet(tmp_path, 1))
    assert findings[0].startswith("leg slots: COULD NOT CHECK, gh said: HTTP 404"), findings
    assert attention == []
    findings, _ = cycle.check_leg_slots(tmp_path / "no-fleet")
    assert findings[0].startswith("leg slots: COULD NOT CHECK, policy.json"), findings


def test_slots_only_runs_the_check_alone_and_exits(tmp_path, monkeypatch, capsys):
    """`com.ark.cycle` fires four times a day, so the hourly sync calls this flag instead. It
    must not drag the rest of the cycle in with it, and it reads the fleet it is given."""
    called, seen = [], []

    def check(fleet):
        seen.append(fleet)
        return ["leg slots: all 1 held by a run"], []

    monkeypatch.setattr(cycle, "check_leg_slots", check)
    monkeypatch.setattr(cycle, "cycle", lambda *a, **kw: called.append("the whole cycle ran"))
    argv = ["discover_cycle.py", "--slots-only", "--fleet", str(tmp_path)]
    monkeypatch.setattr(sys, "argv", argv)
    cycle.main()
    assert called == [], "only the slot check may run"
    assert seen == [tmp_path]
    assert "all 1 held by a run" in capsys.readouterr().out


def test_the_sync_asks_for_the_slot_check_every_run():
    """It sits before the findings branch and the bank, so a tick with nothing to bank still
    reports an idle slot, on the fleet the tick drains, and it is never fatal: a GitHub that
    does not answer must not take the bank down."""
    recipe = (Path(__file__).resolve().parents[1] / "justfile").read_text(encoding="utf-8")
    line = next(ln for ln in recipe.splitlines() if "--slots-only" in ln)
    assert '--fleet "$FLEET"' in line
    assert line.strip().endswith("|| true")
    assert recipe.index("--slots-only") < recipe.index("bank_trigger.py check")
    assert "--wave-only" not in recipe


def test_the_slot_check_is_bounded_for_its_hourly_caller(tmp_path, monkeypatch):
    """`STEP_TIMEOUT` is an hour, which is right for a cycle step and wrong inside the
    hourly sync: a slow GitHub would hold the bank for the whole window and the next sync
    would land on top of it."""
    seen = []

    def fake_run(cmd, timeout=cycle.STEP_TIMEOUT):
        seen.append(timeout)
        return ("[]", True)

    monkeypatch.setattr(cycle, "run", fake_run)
    cycle.check_leg_slots(_fleet(tmp_path, 1))
    assert seen, "the check must ask GitHub something"
    assert all(t <= 120 for t in seen), f"unbounded call in the sync's path: {seen}"
