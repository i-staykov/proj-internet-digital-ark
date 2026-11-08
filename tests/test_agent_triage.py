"""Triage acts: a red clears on green, a reader restarts once a day, a lane never near a tick."""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRIAGE = ROOT / "scripts/agents/triage.py"
JUST = shutil.which("just")


def fake_bin(tmp_path, **scripts):
    """A PATH dir whose commands are tiny bash scripts that log their argv."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name, body in scripts.items():
        f = bin_dir / name
        f.write_text(f'#!/usr/bin/env bash\necho "{name} $*" >> {tmp_path}/calls\n{body}\n')
        f.chmod(0o755)
    return {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}


def timer(last, nxt):
    """A fake systemctl printing the tick's two stamps as systemd does under TZ=UTC, and a fake
    date answering `-d STAMP +%s` for them: BSD date has no -d, so neither fake calls date."""
    now = dt.datetime.now(dt.UTC).replace(microsecond=0)
    stamps = {}
    for key, offset in (("LastTriggerUSec", last), ("NextElapseUSecRealtime", nxt)):
        if offset:
            at = now + dt.timedelta(minutes=int(offset.split()[0]))
            stamps[key] = (at.strftime("%a %Y-%m-%d %H:%M:%S UTC"), int(at.timestamp()))
    lines = [
        f"echo '{k}={stamps[k][0] if k in stamps else ''}'"
        for k in ("LastTriggerUSec", "NextElapseUSecRealtime")
    ]
    cases = " ".join(f"'{s}') echo {e} ;;" for s, e in stamps.values())
    return {"systemctl": "; ".join(lines), "date": f'case "$2" in {cases} esac'}


def triage(tmp_path, env, *args):
    env = {
        **env,
        "ARK_TRIAGE_ACTS": str(tmp_path / "acts.tsv"),
        "ARK_AGENT_QUEUE": str(tmp_path / "q.jsonl"),
        "ARK_SYNC_LOCK": str(tmp_path / "lock"),
    }
    cmd = ["python3", str(TRIAGE), *args]
    return subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True).returncode


def test_only_a_reader_restarts_and_a_second_in_a_day_needs_an_item_naming_it(tmp_path):
    env = fake_bin(tmp_path, systemctl="exit 0")
    assert triage(tmp_path, env, "restart", "ark-sync.service") == 3
    assert triage(tmp_path, env, "restart", "ark-agent") == 3
    assert triage(tmp_path, env, "restart", "ark-har") == 0
    assert triage(tmp_path, env, "restart", "ark-har.service") == 3
    assert triage(tmp_path, env, "restart", "ark-eot") == 0
    item = {"id": "a1", "state": "open", "title": "ark-har stops mid-item"}
    other = {"id": "a2", "state": "open", "title": "disk"}
    (tmp_path / "q.jsonl").write_text(json.dumps(item) + "\n" + json.dumps(other) + "\n")
    assert triage(tmp_path, env, "restart", "ark-har", "--item", "a2") == 3
    assert triage(tmp_path, env, "restart", "ark-har", "--item", "a1") == 0
    assert triage(tmp_path, env, "restart", "ark-har", "--item", "a1") == 3  # one an item
    assert (tmp_path / "calls").read_text().count("restart ark-har") == 2


def test_a_failed_restart_counts_against_the_day_unless_the_unit_is_not_loaded(tmp_path):
    env = fake_bin(tmp_path, systemctl="exit 5")
    assert triage(tmp_path, env, "restart", "ark-header") == 1
    env = fake_bin(tmp_path, systemctl="exit 1")
    assert triage(tmp_path, env, "restart", "ark-header") == 1
    assert triage(tmp_path, env, "restart", "ark-header") == 3


@pytest.mark.parametrize(
    "last,nxt,code",
    [
        ("-30 min", "+30 min", 0),
        ("-3 min", "+57 min", 3),
        ("-55 min", "+5 min", 3),
        ("", "+30 min", 3),  # never triggered or unreadable: refuse, never act
        ("-30 min", "", 3),
    ],
)
def test_the_walk_refuses_near_a_tick_or_when_it_cannot_tell(tmp_path, last, nxt, code):
    env = fake_bin(tmp_path, **timer(last, nxt), just="exit 0")
    env["TZ"] = "Europe/Paris"
    assert triage(tmp_path, env, "walk") == code
    assert ("just walk install" in (tmp_path / "calls").read_text()) == (code == 0)


def test_the_walk_refuses_while_the_sync_lock_is_held(tmp_path):
    env = fake_bin(tmp_path, **timer("-30 min", "+30 min"), just="exit 0")
    (tmp_path / "lock").mkdir()
    (tmp_path / "lock/pid").write_text(str(os.getpid()))
    assert triage(tmp_path, env, "walk") == 3


def red_clear(tmp_path, env):
    work = tmp_path / "work"
    (work / "data/logs").mkdir(parents=True, exist_ok=True)
    if not (work / "scripts").exists():
        (work / "scripts").symlink_to(ROOT / "scripts")
    env = {**env, "ARK_SYNC_LOCK": str(tmp_path / "lock")}
    cmd = [JUST, "--justfile", str(ROOT / "justfile"), "--working-directory", str(work)]
    run = subprocess.run([*cmd, "red-clear"], env=env, capture_output=True, text=True)
    return work / "data/logs/bank_red.json", run


@pytest.mark.skipif(JUST is None, reason="needs just")
@pytest.mark.parametrize("failing", ["run export", "check data"])
def test_red_clear_keeps_the_red_when_the_export_or_the_check_fails(tmp_path, failing):
    env = fake_bin(tmp_path, just=f'[ "$*" = "{failing}" ] && exit 1; exit 0', uv="exit 0")
    red, run = red_clear(tmp_path, env)
    assert run.returncode == 0 and "no BANK RED" in run.stdout
    red.write_text("{}")
    _, run = red_clear(tmp_path, env)
    assert run.returncode != 0 and red.exists() and not (tmp_path / "lock").exists()
    assert "uv" not in (tmp_path / "calls").read_text()


@pytest.mark.skipif(JUST is None, reason="needs just")
def test_red_clear_refuses_under_a_held_lock_and_clears_on_green(tmp_path):
    env = fake_bin(tmp_path, just="exit 0", uv="exit 0")
    red, _ = red_clear(tmp_path, env)
    red.write_text("{}")
    (tmp_path / "lock").mkdir()
    (tmp_path / "lock/pid").write_text(str(os.getpid()))
    _, run = red_clear(tmp_path, env)
    assert run.returncode == 3 and red.exists() and (tmp_path / "lock/pid").exists()
    shutil.rmtree(tmp_path / "lock")
    _, run = red_clear(tmp_path, env)
    assert run.returncode == 0, run.stderr
    calls = (tmp_path / "calls").read_text().splitlines()
    assert calls[-3:] == [
        "just run export",
        "just check data",
        "uv run python scripts/harness/bank_trigger.py clear",
    ]
