"""The agent's runtime (`scripts/agents/run_agent.sh`, `agent_ledger.py`, `billing_guard.py`):
every run is a ledger row, a held tick holds the agent, and a settings file that could bill
another credential refuses the run before any model call."""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "scripts/agents/agent_ledger.py"
GUARD = ROOT / "scripts/agents/billing_guard.py"
RUN = ROOT / "scripts/agents/run_agent.sh"


def stream(tmp_path, *events):
    p = tmp_path / "s.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in events) + "{not json\n")
    return p


RATE = {
    "type": "rate_limit_event",
    "rate_limit_info": {
        "unifiedWindows": {"five_hour": {"utilization": 0.123}, "seven_day": {"utilization": 0.5}}
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


def test_row_reads_turns_tokens_cost_and_the_windows_of_the_preflight(tmp_path):
    run = stream(tmp_path, RESULT)
    pre = (
        stream(tmp_path / "p", RATE, {"type": "result", "subtype": "success"})
        if (tmp_path / "p").mkdir() is None
        else None
    )
    ledger = tmp_path / "runs.tsv"
    args = [
        "--stamp",
        "20260101T0038Z",
        "--mode",
        "triage",
        "--model",
        "m",
        "--seconds",
        "7",
        "--outcome",
        "success",
    ]
    subprocess.run(
        ["python3", LEDGER, "row", ledger, *args, "--stream", run, "--windows", pre], check=True
    )
    head, line = ledger.read_text().splitlines()
    assert head.split("\t")[:3] == ["stamp", "mode", "model"]
    assert line.split("\t") == [
        "20260101T0038Z",
        "triage",
        "m",
        "3",
        "100",
        "5",
        "0.0421",
        "12.3",
        "50.0",
        "7",
        "success",
    ]
    last = json.loads(subprocess.check_output(["python3", LEDGER, "last", ledger]))
    assert (last["turns"], last["five_hour_pct"]) == ("3", "12.3")


def test_ok_only_on_a_successful_result(tmp_path):
    good = stream(tmp_path, RATE, RESULT)
    bad = (
        stream(tmp_path / "b", {"type": "result", "subtype": "error_max_turns", "is_error": True})
        if (tmp_path / "b").mkdir() is None
        else None
    )
    assert subprocess.run(["python3", LEDGER, "ok", good]).returncode == 0
    assert subprocess.run(["python3", LEDGER, "ok", bad]).returncode == 1
    assert (
        subprocess.check_output(["python3", LEDGER, "subtype", bad]).strip() == b"error_max_turns"
    )


def test_a_held_tick_holds_the_agent_and_writes_a_held_row(tmp_path):
    (tmp_path / "hold").write_text("human\n2026-01-01T00:00:00Z\nark-sync.timer\n")
    ledger = tmp_path / "runs.tsv"
    env = os.environ | {
        "ARK_STATE_DIR": str(tmp_path),
        "ARK_AGENT_LEDGER": str(ledger),
        "ARK_AGENT_LOG_DIR": str(tmp_path / "logs"),
    }
    rc = subprocess.run(["bash", RUN, "triage"], env=env, capture_output=True).returncode
    assert rc == 0
    assert ledger.read_text().splitlines()[1].split("\t")[-1] == "held"


def test_billing_guard_refuses_a_helper_and_a_provider_env(tmp_path):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude/settings.json").write_text(json.dumps({"apiKeyHelper": "echo x"}))
    work = tmp_path / "work"
    (work / ".claude").mkdir(parents=True)
    (work / ".claude/settings.json").write_text(
        json.dumps({"env": {"ANTHROPIC_API_KEY": "x", "BASH_MAX_OUTPUT_LENGTH": "1"}})
    )
    out = subprocess.run(
        ["python3", "-I", GUARD, "--home", home, "--workdir", work, "--managed", tmp_path / "none"],
        capture_output=True,
        text=True,
    )
    assert out.returncode == 1
    assert (
        out.stdout.count("FAIL") == 2
        and "apiKeyHelper" in out.stdout
        and "ANTHROPIC_API_KEY" in out.stdout
    )
    (home / ".claude/settings.json").write_text(json.dumps({"permissions": {}}))
    (work / ".claude/settings.json").write_text(
        json.dumps({"env": {"BASH_MAX_OUTPUT_LENGTH": "1"}})
    )
    assert (
        subprocess.run(
            [
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
        ).returncode
        == 0
    )
