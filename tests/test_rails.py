"""The agent's rails (`scripts/agents/rails.py`): one refused command per rule, the allowed shapes
pass, a write to a rail or a guarded path is refused, a public body with an address is refused,
and CI fails an ark-agent commit that touches a rail file."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/agents"))
import rails  # noqa: E402

REFUSED = [
    "git push --force origin B-x",
    "git push -f origin B-x",
    "git push origin live",
    "git push",
    "git push origin HEAD:live",
    "git commit -m x --no-verify",
    "gh pr merge 5 --admin",
    "sudo apt-get install x",
    "ls; sudo reboot",
    "systemctl reboot",
    "just hold off ark-sync.timer",
    "bash scripts/harness/hold.sh off",
    "ARK_HOLD_BYPASS=dry-run just sync",
    "uv run python scripts/harness/bank_trigger.py clear",
    "just prune --round --write",
    "just ship all",
    "pkill -f cdx_extended_walk.py",
    "git commit --author='x <x@invalid>' -m y",
    "git -c user.name=owner commit -m y",
    "echo x > data/held/all.txt",
    "cp a ding/b",
    "rm -rf data/raw/cdx_suffix",
    "sed -i s/a/b/ local.env",
    "cat ~/.config/ark/agent.env",
    "printenv",
    "env",
    "env | grep CLAUDE",
    "echo $CLAUDE_CODE_OAUTH_TOKEN",
    "export CLAUDE_CODE_OAUTH_TOKEN=x",
    "claude setup-token",
    "claude -p x --dangerously-skip-permissions",
    "echo x >> AGENTS.md",
    "cp new agent/policy.json",
    "sed -i s/a/b/ .github/workflows/ci.yml",
    "git checkout -- hooks/pre-commit",
    "tee scripts/harness/hold.sh < x",
]
ALLOWED = [
    "git push -u origin B-agent-rails",
    "git push origin B-x",
    "git push origin --delete B-x",
    "git commit -m 'a change'",
    "gh pr merge 5 --merge",
    "just agent triage",
    "just check unattended",
    "uv run pytest -q tests/test_rails.py",
    "systemctl --user restart ark-har",
    "just walk install",
    "cat data/logs/ticks.tsv | tail",
    "grep -n hold scripts/harness/hold.sh",
    "env -u X true",
    "git log --format=%an origin/live..HEAD",
    "echo 'a b' > data/queue/agent_work.jsonl",
    "sed -n 1,20p AGENTS.md",
    "bash scripts/harness/hold.sh status",
]


@pytest.mark.parametrize("command", REFUSED)
def test_refused(command):
    assert rails.refuse_bash(command), command


@pytest.mark.parametrize("command", ALLOWED)
def test_allowed(command):
    assert rails.refuse_bash(command) is None, command


def test_write_paths():
    for p in (
        "agent/policy.json",
        ".claude/settings.json",
        "AGENTS.md",
        "data/held/x",
        "ding/x",
        "submissions/x",
        "private/x",
        "local.env",
        str(ROOT / "hooks/pre-commit"),
    ):
        assert rails.refuse_path(p), p
    for p in (
        "scripts/agents/triage.py",
        "docs/lore/laws.md",
        "data/queue/agent_work.jsonl",
        "tests/test_x.py",
    ):
        assert rails.refuse_path(p) is None, p


def test_hook_refuses_with_exit_2_and_a_reason():
    out = subprocess.run(
        ["python3", ROOT / "scripts/agents/rails.py"],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "sudo ls"}}),
        capture_output=True,
        text=True,
    )
    assert out.returncode == 2 and out.stderr.startswith("rails: refused, sudo")
    ok = subprocess.run(
        ["python3", ROOT / "scripts/agents/rails.py"],
        input=json.dumps({"tool_name": "Write", "tool_input": {"file_path": "docs/x.md"}}),
        capture_output=True,
        text=True,
    )
    assert ok.returncode == 0


def test_a_public_body_with_an_address_is_refused(tmp_path):
    body = tmp_path / "b.md"
    body.write_text("the VM at " + ".".join(["93", "184", "216", "34"]) + " answered\n")
    why = rails.hook(
        {"tool_name": "Bash", "tool_input": {"command": f"gh issue comment 5 --body-file {body}"}}
    )
    assert why and "public scan" in why
    assert (
        rails.hook(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "gh issue comment 5 --body 'ticks banked: 24'"},
            }
        )
        is None
    )


def test_ci_fails_an_agent_commit_on_a_rail_file(tmp_path):
    # The pre-commit hook exports GIT_DIR and GIT_INDEX_FILE for the repository it runs in, and
    # a git subprocess acts on that repository whatever cwd says: a clean environment here.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

    def git(*a):
        return subprocess.run(
            ["git", "-C", tmp_path, *a], check=True, capture_output=True, text=True, env=env
        ).stdout.strip()

    git("init", "-q", "-b", "live")
    git("config", "user.email", "t@invalid")
    git("config", "user.name", "session")
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent/policy.json").write_text("{}")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    base = git("rev-parse", "HEAD")
    (tmp_path / "agent/policy.json").write_text("{ }")
    git("add", "-A")
    git("commit", "-q", "-m", "knob", "--author", "ark-agent <ark-agent@invalid>")
    head = git("rev-parse", "HEAD")
    out = subprocess.run(
        ["python3", ROOT / "scripts/agents/rails.py", "--ci", base, head],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
    )
    assert out.returncode == 1 and "agent/policy.json" in out.stdout
    (tmp_path / "x.py").write_text("x = 1\n")
    git("add", "-A")
    git("commit", "-q", "-m", "code", "--author", "ark-agent <ark-agent@invalid>")
    head2 = git("rev-parse", "HEAD")
    cmd = ["python3", ROOT / "scripts/agents/rails.py", "--ci", head, head2]
    assert subprocess.run(cmd, cwd=tmp_path, env=env).returncode == 0
