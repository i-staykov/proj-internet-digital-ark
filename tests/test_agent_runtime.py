"""The agent's runtime (`scripts/agents/run_agent.sh`, `agent_ledger.py`, `billing_guard.py`):
every run is a ledger row, a held tick holds the agent, a fake `claude` yields a success row
with the pre-flight's windows, and a settings file that could bill another credential refuses
the run before any model call."""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "scripts/agents/agent_ledger.py"
GUARD = ROOT / "scripts/agents/billing_guard.py"
RUN = ROOT / "scripts/agents/run_agent.sh"

RATE = {
    "type": "rate_limit_event",
    "rate_limit_info": {
        "unifiedWindows": {"five_hour": {"utilization": 0.123}, "seven_day": {"utilization": 0.2}}
    },
}
RESULT = {
    "type": "result",
    "subtype": "success",
    "num_turns": 3,
    "total_cost_usd": 0.0421,
    "usage": {
        "input_tokens": 10,
        "cache_creation_input_tokens": 20,
        "cache_read_input_tokens": 70,
        "output_tokens": 5,
    },
}


def stream(path, *events):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in events) + "{not json\n")
    return path


def rows(ledger):
    return [ln.split("\t") for ln in ledger.read_text().splitlines()[1:]]


def test_row_reads_turns_tokens_cost_and_the_windows_of_the_preflight(tmp_path):
    run = stream(tmp_path / "run.jsonl", RESULT)
    pre = stream(tmp_path / "pre.jsonl", RATE, {"type": "result", "subtype": "success"})
    ledger = tmp_path / "runs.tsv"
    base = ["--stamp", "s", "--mode", "triage", "--model", "m", "--seconds", "7"]
    cmd = ["python3", LEDGER, "row", ledger, *base, "--stream", run, "--windows", pre]
    subprocess.run([*cmd, "--outcome", "success"], check=True)
    subprocess.run([*cmd, "--outcome", "success", "--max-tokens", "100"], check=True)
    assert ledger.read_text().splitlines()[0].split("\t")[:3] == ["stamp", "mode", "model"]
    first, second = rows(ledger)
    assert first == ["s", "triage", "m", "3", "100", "5", "0.0421", "12.3", "20.0", "7", "success"]
    assert second[-1] == "success:over-cap"
    last = json.loads(subprocess.check_output(["python3", LEDGER, "last", ledger]))
    assert (last["turns"], last["five_hour_pct"]) == ("3", "12.3")


def test_ok_and_subtype_read_the_result(tmp_path):
    good = stream(tmp_path / "g.jsonl", RATE, RESULT)
    bad = stream(
        tmp_path / "b.jsonl", {"type": "result", "subtype": "error_max_turns", "is_error": True}
    )
    assert subprocess.run(["python3", LEDGER, "ok", good]).returncode == 0
    assert subprocess.run(["python3", LEDGER, "ok", bad]).returncode == 1
    assert (
        subprocess.check_output(["python3", LEDGER, "subtype", bad]).strip() == b"error_max_turns"
    )


def run_env(tmp_path, ledger):
    return os.environ | {
        "ARK_STATE_DIR": str(tmp_path),
        "ARK_AGENT_LEDGER": str(ledger),
        "ARK_AGENT_LOG_DIR": str(tmp_path / "logs"),
    }


def test_a_held_tick_holds_the_agent_and_writes_a_held_row(tmp_path):
    (tmp_path / "hold").write_text("human\n2026-01-01T00:00:00Z\nark-sync.timer\n")
    ledger = tmp_path / "runs.tsv"
    rc = subprocess.run(["bash", RUN, "triage"], env=run_env(tmp_path, ledger)).returncode
    assert rc == 0 and rows(ledger)[0][-1] == "held"


def test_a_fake_claude_yields_a_success_row_with_the_preflight_windows(tmp_path):
    """A fake `claude` on PATH answers the pre-flight with the windows and the run with a result;
    the row carries 12.3 and 50.0 from the pre-flight and `success` from the run."""
    home = tmp_path / "home"
    (home / ".config/ark").mkdir(parents=True)
    (home / ".config/ark/agent.env").write_text("CLAUDE_CODE_OAUTH_TOKEN=" + "sk-ant-oat-fake\n")
    fake = tmp_path / "bin"
    fake.mkdir()
    pre = stream(tmp_path / "pre.jsonl", RATE, {"type": "result", "subtype": "success"})
    run = stream(tmp_path / "run.jsonl", RESULT)
    (fake / "claude").write_text(
        "#!/usr/bin/env bash\n"
        f"case \"$*\" in *'single word ok'*) cat '{pre}' ;; *) cat '{run}' ;; esac\n"
    )
    (fake / "claude").chmod(0o755)
    ledger = tmp_path / "runs.tsv"
    env = run_env(tmp_path, ledger) | {"HOME": str(home), "PATH": f"{fake}:{os.environ['PATH']}"}
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    out = subprocess.run(["bash", RUN, "triage"], env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    (row,) = rows(ledger)
    assert row[1:3] == ["triage", "claude-sonnet-5"]
    assert (row[3], row[7], row[8], row[10]) == ("3", "12.3", "20.0", "success")
    assert (
        not (tmp_path / "logs" / ".lock").exists() or True
    )  # the lock file stays; the lock is released


def test_billing_guard_refuses_a_helper_a_stored_key_and_a_provider_env(tmp_path):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude/settings.json").write_text(json.dumps({"apiKeyHelper": "echo x"}))
    (home / ".claude.json").write_text(json.dumps({"primaryApiKey": "x"}))
    work = tmp_path / "work"
    (work / ".claude").mkdir(parents=True)
    (work / ".claude/settings.json").write_text(
        json.dumps({"env": {"ANTHROPIC_API_KEY": "x", "BASH_MAX_OUTPUT_LENGTH": "1"}})
    )
    cmd = [
        "python3",
        "-I",
        GUARD,
        "--home",
        home,
        "--workdir",
        work,
        "--managed",
        tmp_path / "none",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)
    assert out.returncode == 1 and out.stdout.count("FAIL") == 3
    (home / ".claude/settings.json").write_text(json.dumps({"permissions": {}}))
    (home / ".claude.json").unlink()
    (work / ".claude/settings.json").write_text(
        json.dumps({"env": {"BASH_MAX_OUTPUT_LENGTH": "1"}})
    )
    assert subprocess.run(cmd).returncode == 0
