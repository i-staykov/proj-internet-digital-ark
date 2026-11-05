"""Work mode (`agent/prompts/work.md`, the `auto` selector in `run_agent.sh`, `work_queue.py
queue-umbrella`): the umbrella's first open issue no item names is queued in the umbrella's
order, and `auto` runs work when the queue holds an item and the last run was not work."""

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
    ids = [i["id"] for i in work_queue.load()]
    assert ids == ["issue-522", "issue-503"]
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
        f"printf '%s' \"$2\" > '{prompt}'; cat '{run}' ;; esac"
    )
    (fake / "claude").write_text("#!/usr/bin/env bash\n" + script + "\n")
    (fake / "claude").chmod(0o755)
    return fake, prompt


def test_auto_runs_work_when_the_queue_holds_an_item_and_the_last_run_was_not_work(tmp_path):
    home = tmp_path / "home"
    (home / ".config/ark").mkdir(parents=True)
    (home / ".config/ark/agent.env").write_text("CLAUDE_CODE_OAUTH_TOKEN=" + "sk-ant-oat-fake\n")
    fake, prompt = fake_claude(tmp_path)
    ledger = tmp_path / "runs.tsv"
    queue = tmp_path / "q.jsonl"
    env = os.environ | {
        "ARK_STATE_DIR": str(tmp_path),
        "ARK_AGENT_LEDGER": str(ledger),
        "ARK_AGENT_LOG_DIR": str(tmp_path / "logs"),
        "ARK_AGENT_QUEUE": str(queue),
        "ARK_AGENT_UMBRELLA": "0",
        "HOME": str(home),
        "PATH": f"{fake}:{os.environ['PATH']}",
    }
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)

    def run():
        out = subprocess.run(
            ["bash", ROOT / "scripts/agents/run_agent.sh", "auto"],
            env=env,
            capture_output=True,
            text=True,
        )
        assert out.returncode == 0, out.stderr
        return ledger.read_text().splitlines()[-1].split("\t")[1]

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
