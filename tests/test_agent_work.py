"""The `auto` selector in `run_agent.sh` and `work_queue.py queue-umbrella`: the umbrella's first
open issue no item names is queued in the umbrella's order; `auto` runs work when the queue holds
an item, the last run was not work and the next hour is not scheduled; a scheduled mode runs at
its hour, or at the next free one after a busy lock; every run's probe directory goes with it."""

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/agents"))
import work_queue  # noqa: E402

UMBRELLA = """Approved. One issue per PR, in this order.

**B. The resident agent**
1. #520 the runtime
2. #521 the rails
3. #522 pacing

**A. The base**
4. #503 the check
5. #504 the heartbeat

Outside the set: #502 closed.
"""


def test_queue_umbrella_takes_the_first_open_issue_no_item_names(tmp_path, monkeypatch):
    monkeypatch.setattr(work_queue, "QUEUE", tmp_path / "q.jsonl")
    body = tmp_path / "u.md"
    body.write_text(UMBRELLA)
    assert work_queue.umbrella_issues("517", str(body)) == ["520", "521", "522", "503", "504"]
    closed = {"520", "521"}
    first = work_queue.queue_umbrella("517", str(body), is_open=lambda n: n not in closed)
    assert first == "issue-522"
    second = work_queue.queue_umbrella("517", str(body), is_open=lambda n: n not in closed)
    assert second == "issue-503"  # 522 is named by an item already, open or not
    after = work_queue.queue_umbrella("517", str(body), after="503", is_open=lambda n: True)
    assert after == "issue-504"  # only the lines after the umbrella's own
    ids = [i["id"] for i in work_queue.load()]
    assert ids == ["issue-522", "issue-503", "issue-504"]
    assert work_queue.top(work_queue.load())["id"] == "issue-522"


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
    """`run_agent.sh auto` against a fake `claude`, at the UTC time the test names: the mode of
    the row it wrote, and the prompt the fake saw."""
    home = tmp_path / "home"
    (home / ".config/ark").mkdir(parents=True)
    (home / ".config/ark/agent.env").write_text("CLAUDE_CODE_OAUTH_TOKEN=" + "sk-ant-oat-fake\n")
    fake, prompt = fake_claude(tmp_path)
    ledger = tmp_path / "runs.tsv"
    env = os.environ | {
        "ARK_STATE_DIR": str(tmp_path),
        "ARK_AGENT_LEDGER": str(ledger),
        "ARK_AGENT_LOG_DIR": str(tmp_path / "logs"),
        "ARK_AGENT_QUEUE": str(tmp_path / "q.jsonl"),
        "ARK_AGENT_UMBRELLA": "0",
        "HOME": str(home),
        "PATH": f"{fake}:{os.environ['PATH']}",
    }
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)

    def run(day="2026-11-11", hour=10):  # nobody's hour, any day
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


def test_auto_runs_work_when_the_queue_holds_an_item_and_the_last_run_was_not_work(tmp_path):
    run, env, prompt = runner(tmp_path)
    assert run() == "triage"  # an empty queue, and umbrella 0 has no body
    subprocess.run(
        ["python3", ROOT / "scripts/agents/work_queue.py", "add", "issue", "x", "--id", "issue-1"],
        env=env,
        check=True,
    )
    assert run() == "work"
    assert "A work run" in prompt.read_text() and "What persists" in prompt.read_text()
    assert run() == "triage"  # never two work runs in a row
    assert run() == "work"
    assert run(hour=5) == "triage"  # 06 is the cdx run's hour: no work the hour before
    assert run(hour=2) == "triage"  # 03 is a scout's, every day
    assert run(hour=4) == "work"  # 05 is nobody's


def test_a_scheduled_mode_runs_at_its_hour_or_at_the_next_free_one_after_a_busy_lock(tmp_path):
    run, env, prompt = runner(tmp_path)
    assert run(hour=6) == "cdx"
    assert "A cdx run" in prompt.read_text()
    assert run(hour=4) == "triage"  # nobody's hour
    assert run(hour=3) == "scout"
    assert run(hour=21) == "scout"  # four times a day
    assert "A scout run" in prompt.read_text()
    flock = Path(env["PATH"].split(":")[0]) / "flock"
    flock.write_text("#!/usr/bin/env bash\nexit 1\n")
    flock.chmod(0o755)
    assert run(hour=3) == "auto"  # the busy row, before a mode was picked
    assert (tmp_path / "runs.tsv").read_text().splitlines()[-1].endswith("\tbusy")
    marker = tmp_path / "logs/.due-scout"
    assert marker.exists()
    flock.unlink()
    assert run() == "scout"  # the next free hour
    assert not marker.exists()
    assert run() == "triage"


def test_every_run_has_its_own_probe_directory_and_it_goes_with_the_run(tmp_path):
    run, env, prompt = runner(tmp_path)
    assert run() == "triage"
    probe = Path((tmp_path / "probe").read_text())
    assert probe.name.startswith("probe-") and not probe.exists()
    assert probe.parent == Path("/dev/shm") or probe.parent == tmp_path / "logs"


def test_the_scout_prompt_hunts_outside_web_archive_org_in_both_windows():
    scout = (ROOT / "agent/prompts/scout.md").read_text()
    wayback = [line for line in scout.splitlines() if "web.archive.org" in line]
    assert len(wayback) == 1 and "refused" in wayback[0]
    assert "1996 to 2001" in scout and "2002 to 2013" in scout
    assert not any(old in scout for old in ("DRUM", "NCSA", "webring", "rankings"))
