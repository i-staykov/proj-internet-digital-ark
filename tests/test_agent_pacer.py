"""The agent's pacing (`scripts/agents/pacer.py`): nothing runs at the five-hour stop or above the
seven-day pace line, an unmeasured window does not stop a run, a warning is not a refusal, a
refused call backs off to the window's reset and the next run reads the back-off before any
call, and the runner writes `paced` and `rate-limited` rows without a model call."""

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
RUN = ROOT / "scripts/agents/run_agent.sh"


def raw(five, seven, resets_in=3 * 86400):
    return {
        "five_hour": {"utilization": five, "resetsAt": NOW + 3600},
        "seven_day": {"utilization": seven, "resetsAt": NOW + resets_in},
    }


def test_decide_stops_on_the_five_hour_stop_and_above_the_pace_line():
    assert pacer.decide(raw(0.1, 0.1), K, NOW) is None
    assert "five-hour" in pacer.decide(raw(0.4, 0.1), K, NOW)
    # four days in: the line is at 50 * 4/7 = 28.6%
    assert pacer.decide(raw(0.1, 0.28), K, NOW) is None
    assert "pace line at 28.6%" in pacer.decide(raw(0.1, 0.29), K, NOW)
    # a window that just opened: the line is at 0, so 0% runs and 1% waits
    assert pacer.decide(raw(0.1, 0.0, resets_in=7 * 86400), K, NOW) is None
    assert "pace line at 0.0%" in pacer.decide(raw(0.1, 0.01, resets_in=7 * 86400), K, NOW)
    # past pace_days the line is the ceiling
    assert pacer.decide(raw(0.1, 0.5, resets_in=10), K, NOW) is None
    assert pacer.decide(raw(0.1, 0.51, resets_in=10), K, NOW)


def test_an_unmeasured_window_runs_and_a_backoff_holds():
    assert pacer.decide({}, K, NOW) is None
    assert pacer.decide({"five_hour": {"utilization": 0.1}}, K, NOW) is None
    assert "backing off until" in pacer.decide(raw(0.1, 0.1), K, NOW, backoff_until=NOW + 10)


def test_a_mode_names_its_own_five_hour_stop():
    policy = str(ROOT / "agent/policy.json")
    assert pacer.knobs("work", policy)["five_hour_stop"] == 25
    assert pacer.knobs("triage", policy)["five_hour_stop"] == 40


def event(status, resets=NOW + 500):
    info = {"status": status, "resetsAt": resets}
    return json.dumps({"type": "rate_limit_event", "rate_limit_info": info})


def test_a_refused_call_backs_off_and_a_warning_does_not(tmp_path):
    refused = tmp_path / "run.jsonl"
    refused.write_text(event("rejected") + "\n")
    assert pacer.refused(str(refused)) == NOW + 500
    warned = tmp_path / "warn.jsonl"
    success = json.dumps({"type": "result", "subtype": "success"})
    warned.write_text(event("allowed_warning") + "\n" + success + "\n")
    assert pacer.refused(str(warned)) is None
    env = os.environ | {"ARK_AGENT_LOG_DIR": str(tmp_path / "logs")}
    cmd = ["python3", ROOT / "scripts/agents/pacer.py", "backoff", refused]
    out = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert out.returncode == 0 and "backing off" in out.stdout
    assert (tmp_path / "logs/.backoff_until").read_text().strip() == f"{NOW + 500:.0f}"


def runner_env(tmp_path, fake):
    home = tmp_path / "home"
    (home / ".config/ark").mkdir(parents=True)
    (home / ".config/ark/agent.env").write_text("CLAUDE_CODE_OAUTH_TOKEN=" + "sk-ant-oat-fake\n")
    env = os.environ | {
        "ARK_STATE_DIR": str(tmp_path),
        "ARK_AGENT_LEDGER": str(tmp_path / "runs.tsv"),
        "ARK_AGENT_LOG_DIR": str(tmp_path / "logs"),
        "HOME": str(home),
        "PATH": f"{fake}:{os.environ['PATH']}",
    }
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    return env


def fake_claude(tmp_path, preflight: str):
    """A fake `claude` answering the pre-flight with `preflight` and counting every call."""
    fake = tmp_path / "bin"
    fake.mkdir()
    pre = tmp_path / "pre.jsonl"
    pre.write_text(preflight)
    calls = tmp_path / "calls"
    script = (
        f"echo 1 >> '{calls}'; case \"$*\" in *'single word ok'*) cat '{pre}' ;; *) exit 0 ;; esac"
    )
    (fake / "claude").write_text("#!/usr/bin/env bash\n" + script + "\n")
    (fake / "claude").chmod(0o755)
    return fake, calls


def last_row(tmp_path):
    return (tmp_path / "runs.tsv").read_text().splitlines()[-1].split("\t")


def test_the_runner_writes_a_paced_row_and_calls_no_model(tmp_path):
    info = {"unifiedWindows": raw(0.5, 0.1)}
    windows = json.dumps({"type": "rate_limit_event", "rate_limit_info": info})
    success = json.dumps({"type": "result", "subtype": "success"})
    fake, calls = fake_claude(tmp_path, windows + "\n" + success + "\n")
    out = subprocess.run(
        ["bash", RUN, "triage"], env=runner_env(tmp_path, fake), capture_output=True, text=True
    )
    assert out.returncode == 0, out.stderr
    row = last_row(tmp_path)
    assert row[-1].startswith("paced:five-hour window at 50%") and row[7] == "50.0"
    assert calls.read_text().count("1") == 1  # the pre-flight alone


def test_a_refused_preflight_backs_off_and_the_next_run_makes_no_call(tmp_path):
    fake, calls = fake_claude(tmp_path, event("rejected", resets=9_999_999_999) + "\n")
    env = runner_env(tmp_path, fake)
    out = subprocess.run(["bash", RUN, "triage"], env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert last_row(tmp_path)[-1].startswith(
        "rate-limited:refused for the limit; backing off until"
    )
    assert calls.read_text().count("1") == 1
    out = subprocess.run(["bash", RUN, "triage"], env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert last_row(tmp_path)[-1].startswith("paced:backing off until")
    assert calls.read_text().count("1") == 1  # no second call
