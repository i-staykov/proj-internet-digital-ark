"""The `auto` selector in `run_agent.sh`: cdx when due; else work when an alert tops the queue,
the last run was not work and work's cap, pre-flight and grace end before the next cdx tick, a
scout's hour included (an issue is not breakage; an open `vm-alert` or `agent-` pull request is
the triage's to queue, never a reason); else the mode due; a busy lock is one row and the mode
missed waits for its next hour; every run's probe directory goes with it."""

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fake_claude(tmp_path):
    """A fake `claude` on PATH answering the pre-flight with quiet windows and a run with success,
    recording the prompt it was given."""
    fake = tmp_path / "bin"
    fake.mkdir()
    pre = tmp_path / "pre.jsonl"
    rate = {
        "type": "rate_limit_event",
        "rate_limit_info": {"unifiedWindows": {"five_hour": {"utilization": 0.1}}},
    }
    pre.write_text(
        json.dumps(rate) + "\n" + json.dumps({"type": "result", "subtype": "success"}) + "\n"
    )
    run = tmp_path / "run.jsonl"
    run.write_text(
        json.dumps({"type": "result", "subtype": "success", "num_turns": 1, "session_id": "s-9"})
        + "\n"
    )
    prompt = tmp_path / "prompt.txt"
    script = (
        f"case \"$*\" in *'single word ok'*) cat '{pre}' ;; *) "
        f"printf '%s' \"$2\" > '{prompt}'; cat '{run}'; "
        f"[ -d \"$ARK_PROBE_DIR\" ] && printf '%s' \"$ARK_PROBE_DIR\" > '{tmp_path}/probe' ;; esac"
    )
    (fake / "claude").write_text("#!/usr/bin/env bash\n" + script + "\n")
    (fake / "claude").chmod(0o755)
    return fake, prompt


def runner(tmp_path):
    """`run_agent.sh auto` against a fake `claude` and the test's own policy (cdx every 4 h from
    02 UTC, a scout an hour after each, work capped at 6600 s), at the UTC time the test names:
    the mode of the row it wrote, and the prompt the fake saw."""
    home = tmp_path / "home"
    (home / ".config/ark").mkdir(parents=True)
    (home / ".config/ark/agent.env").write_text("CLAUDE_CODE_OAUTH_TOKEN=" + "sk-ant-oat-fake\n")
    fake, prompt = fake_claude(tmp_path)
    policy = json.loads((ROOT / "agent/policy.json").read_text())
    policy["schedule"] = {
        "cdx": {"utc_hours": [2, 6, 10, 14, 18, 22]},
        "scout": {"utc_hours": [3, 7, 11, 15, 19, 23]},
    }
    policy["modes"]["work"]["timeout_seconds"] = 6600
    (tmp_path / "policy.json").write_text(json.dumps(policy))
    ledger = tmp_path / "runs.tsv"
    env = os.environ | {
        "ARK_STATE_DIR": str(tmp_path),
        "ARK_AGENT_LEDGER": str(ledger),
        "ARK_AGENT_LOG_DIR": str(tmp_path / "logs"),
        "ARK_AGENT_POLICY": str(tmp_path / "policy.json"),
        "ARK_AGENT_QUEUE": str(tmp_path / "q.jsonl"),
        "HOME": str(home),
        "PATH": f"{fake}:{os.environ['PATH']}",
    }
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)

    def run(day="2026-11-11", hour=12):  # nobody's hour, any day
        at = dt.datetime.fromisoformat(f"{day}T{hour:02d}:38:00+00:00")
        out = subprocess.run(
            ["bash", ROOT / "scripts/agents/run_agent.sh", "auto"],
            env=env | {"ARK_AGENT_NOW": str(int(at.timestamp()))},
            capture_output=True,
            text=True,
        )
        assert out.returncode == 0, out.stderr
        return ledger.read_text().splitlines()[-1].split("\t")[1]

    return run, env, prompt


def test_auto_runs_work_when_something_is_broken(tmp_path):
    run, env, prompt = runner(tmp_path)
    add = [sys.executable, ROOT / "scripts/agents/work_queue.py", "add"]
    assert run() == "triage"  # an empty queue: a vm-alert or an agent PR alone is the triage's
    subprocess.run([*add, "issue", "x", "--id", "issue-1"], env=env, check=True)
    assert run() == "triage"  # an issue is not breakage
    subprocess.run([*add, "alert", "y", "--id", "alert-1"], env=env, check=True)
    assert run(hour=3) == "work"  # an alert, at a scout's hour: cdx at 06:38 is 3 h off
    assert "A work run" in prompt.read_text() and "What persists" in prompt.read_text()
    assert run(hour=4) == "triage"  # never two work runs in a row
    assert run(hour=4) == "work"  # 2 h to cdx: 6600 s, the pre-flight and the grace fit
    assert run(hour=5) == "triage"  # 1 h to cdx: the cap does not fit
    assert run(hour=5) == "triage"
    assert run(hour=6) == "cdx"  # cdx due outranks breakage


def test_a_scheduled_mode_runs_at_its_hour_and_a_busy_lock_is_one_row(tmp_path):
    run, env, prompt = runner(tmp_path)
    assert run(hour=6) == "cdx"
    assert "A cdx run" in prompt.read_text()
    assert run(hour=4) == "triage"  # nobody's hour
    assert run(hour=3) == "scout"
    assert run(hour=23) == "scout"  # an hour after each cdx run
    assert "A scout run" in prompt.read_text()
    flock = Path(env["PATH"].split(":")[0]) / "flock"
    flock.write_text("#!/usr/bin/env bash\nexit 1\n")
    flock.chmod(0o755)
    assert run(hour=3) == "auto"  # the busy row, before a mode was picked
    assert (tmp_path / "runs.tsv").read_text().splitlines()[-1].endswith("\tbusy")
    flock.unlink()
    assert run() == "triage"  # the scout missed waits for its next hour


def test_every_run_has_its_own_probe_directory_and_it_goes_with_the_run(tmp_path):
    run, env, prompt = runner(tmp_path)
    assert run() == "triage"
    probe = Path((tmp_path / "probe").read_text())
    assert probe.name.startswith("probe-") and not probe.exists()
    assert probe.parent == Path("/dev/shm") or probe.parent == tmp_path / "logs"
