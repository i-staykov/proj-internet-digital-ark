"""`run_agent.sh`: a work run cut by its cap keeps its session on the item, the next work run
resumes it once with `--resume`, and the one after starts fresh; the fourth attempt parks the
item."""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "scripts/agents/run_agent.sh"
WQ = ROOT / "scripts/agents/work_queue.py"


def test_a_cap_ended_run_resumes_once_then_starts_fresh_and_parks_after_three(tmp_path):
    home = tmp_path / "home"
    (home / ".config/ark").mkdir(parents=True)
    (home / ".config/ark/agent.env").write_text("CLAUDE_CODE_OAUTH_TOKEN=" + "sk-ant-oat-fake\n")
    fake = tmp_path / "bin"
    fake.mkdir()
    pre = tmp_path / "pre.jsonl"
    pre.write_text(json.dumps({"type": "result", "subtype": "success"}) + "\n")
    run = tmp_path / "run.jsonl"
    # a run cut by its turn cap: the init event names the session, the result says the cap
    init = {"type": "system", "subtype": "init", "session_id": "s-1"}
    capped = {"type": "result", "subtype": "error_max_turns", "is_error": True, "session_id": "s-1"}
    run.write_text(json.dumps(init) + "\n" + json.dumps(capped) + "\n")
    argv = tmp_path / "argv"
    script = (
        f"case \"$*\" in *'single word ok'*) cat '{pre}' ;; *) "
        f"printf '%s' \"$*\" | tr '\\n' ' ' >> '{argv}'; echo >> '{argv}'; cat '{run}' ;; esac"
    )
    (fake / "claude").write_text("#!/usr/bin/env bash\n" + script + "\n")
    (fake / "claude").chmod(0o755)
    env = os.environ | {
        "ARK_STATE_DIR": str(tmp_path),
        "ARK_AGENT_LEDGER": str(tmp_path / "runs.tsv"),
        "ARK_AGENT_LOG_DIR": str(tmp_path / "logs"),
        "ARK_AGENT_QUEUE": str(tmp_path / "q.jsonl"),
        "HOME": str(home),
        "PATH": f"{fake}:{os.environ['PATH']}",
    }
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    subprocess.run(["python3", WQ, "add", "issue", "x", "--id", "issue-1"], env=env, check=True)

    def work():
        subprocess.run(["bash", RUN, "work"], env=env, capture_output=True, text=True)
        return (
            json.loads(subprocess.check_output(["python3", WQ, "top"], env=env))
            if subprocess.run(["python3", WQ, "top"], env=env, capture_output=True).returncode == 0
            else None
        )

    item = work()
    assert (item["attempts"], item["session"]) == (1, "s-1")
    item = work()
    assert (item["attempts"], item["session"]) == (2, "")
    calls = argv.read_text().splitlines()
    assert "--resume s-1" in calls[1] and "--resume" not in calls[0]
    item = work()
    assert (item["attempts"], item["session"]) == (
        3,
        "s-1",
    ) and "--resume" not in argv.read_text().splitlines()[2]
    assert work() is None  # the fourth attempt parks it
    listing = subprocess.check_output(["python3", WQ, "list"], env=env, text=True)
    assert listing.startswith("parked p2 4x issue-1")
    rows = (tmp_path / "runs.tsv").read_text().splitlines()
    assert rows[-1].split("\t")[-1] == "parked:issue-1"
