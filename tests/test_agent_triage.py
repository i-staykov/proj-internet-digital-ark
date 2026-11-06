"""Triage acts: a red clears on green, a unit restarts once a day, a lane never near a tick."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRIAGE = ROOT / "scripts/agents/triage.py"
JUST = shutil.which("just")
STAMP = (
    "echo LastTriggerUSec=$(date -d '{}' '+%a %Y-%m-%d %H:%M:%S %Z'); "
    "echo NextElapseUSecRealtime=n/a"
)


def fake_bin(tmp_path, **scripts):
    """A PATH dir whose commands are tiny bash scripts that log their argv."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name, body in scripts.items():
        f = bin_dir / name
        f.write_text(f'#!/usr/bin/env bash\necho "{name} $*" >> {tmp_path}/calls\n{body}\n')
        f.chmod(0o755)
    return {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}


def triage(tmp_path, env, *args):
    env = {
        **env,
        "ARK_TRIAGE_ACTS": str(tmp_path / "acts.tsv"),
        "ARK_AGENT_QUEUE": str(tmp_path / "q.jsonl"),
    }
    env["ARK_SYNC_LOCK"] = str(tmp_path / "lock")
    return subprocess.run(
        ["python3", str(TRIAGE), *args], cwd=ROOT, env=env, capture_output=True, text=True
    )


def test_a_second_restart_in_a_day_needs_an_open_work_item(tmp_path):
    env = fake_bin(tmp_path, systemctl="exit 0")
    assert triage(tmp_path, env, "restart", "ark-har").returncode == 0
    assert triage(tmp_path, env, "restart", "ark-har").returncode == 3
    assert triage(tmp_path, env, "restart", "ark-eot").returncode == 0
    (tmp_path / "q.jsonl").write_text(json.dumps({"id": "alert-har", "state": "open"}) + "\n")
    assert triage(tmp_path, env, "restart", "ark-har", "--item", "alert-har").returncode == 0
    assert triage(tmp_path, env, "restart", "ark-har", "--item", "nope").returncode == 3
    assert (tmp_path / "calls").read_text().count("restart ark-har") == 2


def test_the_walk_refuses_within_ten_minutes_of_a_tick(tmp_path):
    near = STAMP.format("-3 min")
    env = fake_bin(tmp_path, systemctl=near, just="exit 0")
    assert triage(tmp_path, env, "walk").returncode == 3
    far = STAMP.format("-30 min")
    env = fake_bin(tmp_path, systemctl=far, just="exit 0")
    assert triage(tmp_path, env, "walk").returncode == 0
    assert "just walk install" in (tmp_path / "calls").read_text()


def red_clear(tmp_path, env):
    work = tmp_path / "work"
    (work / "data/logs").mkdir(parents=True, exist_ok=True)
    if not (work / "scripts").exists():
        (work / "scripts").symlink_to(ROOT / "scripts")
    env = {**env, "ARK_SYNC_LOCK": str(tmp_path / "lock")}
    cmd = [
        JUST,
        "--justfile",
        str(ROOT / "justfile"),
        "--working-directory",
        str(work),
        "red-clear",
    ]
    return work / "data/logs/bank_red.json", subprocess.run(
        cmd, env=env, capture_output=True, text=True
    )


@pytest.mark.skipif(JUST is None, reason="needs just")
def test_red_clear_keeps_the_red_on_a_failed_check_and_under_a_held_lock(tmp_path):
    env = fake_bin(tmp_path, just="exit 1", uv="exit 0")
    red, run = red_clear(tmp_path, env)
    assert run.returncode == 0 and "no BANK RED" in run.stdout
    red.write_text("{}")
    _, run = red_clear(tmp_path, env)
    assert run.returncode != 0 and red.exists() and not (tmp_path / "lock").exists()
    assert "uv" not in (tmp_path / "calls").read_text()
    (tmp_path / "lock").mkdir()
    (tmp_path / "lock/pid").write_text(str(os.getpid()))
    _, run = red_clear(tmp_path, fake_bin(tmp_path, just="exit 0", uv="exit 0"))
    assert run.returncode == 3 and red.exists()


@pytest.mark.skipif(JUST is None, reason="needs just")
def test_red_clear_clears_on_green(tmp_path):
    env = fake_bin(tmp_path, just="exit 0", uv="exit 0")
    red, _ = red_clear(tmp_path, env)
    red.write_text("{}")
    _, run = red_clear(tmp_path, env)
    assert run.returncode == 0, run.stderr
    calls = (tmp_path / "calls").read_text()
    assert "just run export" in calls and "just check data" in calls
    assert "uv run python scripts/harness/bank_trigger.py clear" in calls
