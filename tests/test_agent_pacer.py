"""The agent's pacing (`scripts/agents/pacer.py`): nothing runs at the five-hour stop or over the
seven-day pace line, an unmeasured window does not stop a run, a refused run backs off to the
window's reset once, and the runner writes a `paced` row without a model call."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/agents"))
import pacer  # noqa: E402

K = {"five_hour_stop": 40, "seven_day_ceiling": 50, "pace_days": 7}
NOW = 1_800_000_000.0


def raw(five, seven, resets_in=3 * 86400):
    return {
        "five_hour": {"utilization": five, "resetsAt": NOW + 3600},
        "seven_day": {"utilization": seven, "resetsAt": NOW + resets_in},
    }


def test_decide_stops_on_the_five_hour_stop_and_the_pace_line():
    assert pacer.decide(raw(0.1, 0.1), K, NOW) is None
    assert "five-hour" in pacer.decide(raw(0.4, 0.1), K, NOW)
    # four days in: the line is at 50 * 4/7 = 28.6%
    assert pacer.decide(raw(0.1, 0.28), K, NOW) is None
    assert "pace line at 28.6%" in pacer.decide(raw(0.1, 0.29), K, NOW)
    # a window that just opened: the line is at 0, so even 1% waits
    assert "pace line at 0.0%" in pacer.decide(raw(0.1, 0.01, resets_in=7 * 86400), K, NOW)
    # past pace_days the line is the ceiling
    assert pacer.decide(raw(0.1, 0.49, resets_in=10), K, NOW) is None
    assert pacer.decide(raw(0.1, 0.5, resets_in=10), K, NOW)


def test_an_unmeasured_window_runs_and_a_backoff_holds():
    assert pacer.decide({}, K, NOW) is None
    assert pacer.decide({"five_hour": {"utilization": 0.1}}, K, NOW) is None
    assert "backing off until" in pacer.decide(raw(0.1, 0.1), K, NOW, backoff_until=NOW + 10)


def test_a_refused_run_backs_off_to_the_reset(tmp_path, monkeypatch):
    stream = tmp_path / "run.jsonl"
    stream.write_text(
        json.dumps(
            {
                "type": "rate_limit_event",
                "rate_limit_info": {"status": "rejected", "resetsAt": NOW + 500},
            }
        )
        + "\n"
    )
    assert pacer.refused(str(stream)) == NOW + 500
    clean = tmp_path / "ok.jsonl"
    clean.write_text(json.dumps({"type": "result", "subtype": "success", "result": "OK"}) + "\n")
    assert pacer.refused(str(clean)) is None
    env = os.environ | {"ARK_AGENT_LOG_DIR": str(tmp_path / "logs")}
    out = subprocess.run(
        ["python3", ROOT / "scripts/agents/pacer.py", "backoff", stream],
        env=env,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0 and "backing off" in out.stdout
    assert (tmp_path / "logs/.backoff_until").read_text().strip() == f"{NOW + 500:.0f}"


def test_the_runner_writes_a_paced_row_and_calls_no_model(tmp_path):
    home = tmp_path / "home"
    (home / ".config/ark").mkdir(parents=True)
    (home / ".config/ark/agent.env").write_text("CLAUDE_CODE_OAUTH_TOKEN=" + "sk-ant-oat-fake\n")
    fake = tmp_path / "bin"
    fake.mkdir()
    pre = tmp_path / "pre.jsonl"
    pre.write_text(
        json.dumps(
            {"type": "rate_limit_event", "rate_limit_info": {"unifiedWindows": raw(0.5, 0.1)}}
        )
        + "\n"
        + json.dumps({"type": "result", "subtype": "success"})
        + "\n"
    )
    marker = tmp_path / "ran"
    script = f"case \"$*\" in *'single word ok'*) cat '{pre}' ;; *) touch '{marker}' ;; esac"
    (fake / "claude").write_text("#!/usr/bin/env bash\n" + script + "\n")
    (fake / "claude").chmod(0o755)
    ledger = tmp_path / "runs.tsv"
    env = os.environ | {
        "ARK_STATE_DIR": str(tmp_path),
        "ARK_AGENT_LEDGER": str(ledger),
        "ARK_AGENT_LOG_DIR": str(tmp_path / "logs"),
        "HOME": str(home),
        "PATH": f"{fake}:{os.environ['PATH']}",
    }
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    out = subprocess.run(
        ["bash", ROOT / "scripts/agents/run_agent.sh", "triage"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stderr
    row = ledger.read_text().splitlines()[1].split("\t")
    assert row[-1].startswith("paced:five-hour window at 50%") and row[7] == "50.0"
    assert not marker.exists()
