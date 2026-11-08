"""The agent's rails (`scripts/agents/rails.py`): one refused command per rule, the allowed shapes
pass, a long command checks in linear time, a git state change is refused on live and allowed on
a branch, a write to a rail, a guarded or the profile path is refused, a public body with an
address is refused, a merge is refused outside the window, and CI fails an ark-agent commit that
touches a rail file."""

import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/agents"))
import rails  # noqa: E402

REFUSED = [
    "git push --force origin B-x",
    "git push -f origin B-x",
    "git -C . push -f origin B-x",
    "git push origin live",
    "git --no-pager push origin live",
    "git push",
    "git push origin HEAD",
    "git push origin HEAD:live",
    "git commit -m x --no-verify",
    "git commit -n -m x",
    "git -c core.hooksPath=/dev/null commit -m x",
    "gh pr merge 5 --admin",
    "sudo apt-get install x",
    "ls; sudo reboot",
    "/usr/bin/sudo ls",
    "systemctl reboot",
    "just hold off ark-sync.timer",
    "bash scripts/harness/hold.sh off",
    "ARK_HOLD_BYPASS=dry-run just sync",
    "systemctl --user enable --now ark-sync.timer",
    "systemctl --user stop ark-agent.timer",
    "crontab -r",
    "if true; then systemctl --user restart ark-har; fi",
    "{ systemctl --user try-restart ark-har; }",
    "bash -lc 'systemctl restart --user ark-{eot,har}'",
    "U=ark-har; systemctl --user restart $U",
    "systemctl --user stop 'ark-*'",
    "bash -euo pipefail -c 'just walk install'",
    "just -f justfile walk install",
    "python3 'scripts/engines/cdx_walk_jobs.py' remove",
    "bash scripts/harness/sync_lock.sh take $$",
    'L=scripts/harness/sync_lock.sh; bash "$L" drop',
    "rm -rf data/logs/.sync*",
    "find data/logs -name '.sync*' -delete",
    "uv run python scripts/harness/bank_trigger.py clear",
    "just prune --round --write",
    "just ship all",
    "pkill -f cdx_extended_walk.py",
    "kill 1234",
    "git commit --author='x <x@invalid>' -m y",
    "git -c User.name=owner commit -m y",
    "GIT_AUTHOR_NAME=owner git commit -m y",
    "echo x > data/held/all.txt",
    "cp a ding/b",
    "rm -rf data/raw/cdx_suffix",
    "sed -i s/a/b/ local.env",
    "cat ~/.config/ark/agent.env",
    "cp x ~/.claude/settings.json",
    "printenv",
    "env",
    "env | grep CLAUDE",
    "export -p",
    "echo $CLAUDE_CODE_OAUTH_TOKEN",
    "printf '%s' $CLAUDE_CODE_OAUTH_TOKEN",
    "export CLAUDE_CODE_OAUTH_TOKEN=x",
    "cat /proc/self/environ",
    "claude setup-token",
    "claude -p x --dangerously-skip-permissions",
    "curl -s https://example.org/robots.txt",
    "ls; wget -q https://example.org/x.gz",
    "/usr/bin/curl https://example.org",
    "timeout 60 curl https://example.org",
    "nice -n 19 ionice -c3 curl x",
    "nohup setsid wget x",
    "timeout 60 stdbuf -oL curl x",
    "env A='x y' curl x",
    "echo https://example.org | xargs wget",
    "X=$(curl https://example.org)",
    "echo x >> AGENTS.md",
    "cp new agent/policy.json",
    "sed -i s/a/b/ .github/workflows/ci.yml",
    "git checkout -- hooks/pre-commit",
    "tee scripts/harness/hold.sh < x",
    "dd if=x of=hooks/pre-commit",
]
ALLOWED = [
    "git push -u origin B-agent-rails",
    "git push origin B-x",
    "git push origin feature/x",
    "git push origin --delete B-x",
    "git commit -m 'a change'",
    "gh pr merge 5 --merge",
    "just agent triage",
    "just check unattended",
    "uv run pytest -q tests/test_rails.py",
    "python3 scripts/agents/triage.py restart ark-har --item a1",
    "python3 scripts/agents/triage.py walk",
    "systemctl --user status ark-har",
    "systemctl --user show ark-har -p ActiveState,ExecMainStartTimestamp",
    "systemctl --user is-active ark-har",
    "systemctl --user list-timers ark-sync.timer --no-pager",
    "just red-clear",
    "just walk status",
    "bash scripts/harness/sync_lock.sh holder",
    "cat data/logs/ticks.tsv | tail",
    "cp data/logs/agent/x.jsonl /tmp/",
    "echo x > data/logs/agent/note",
    "grep -n hold scripts/harness/hold.sh",
    "env -u X true",
    "echo export",
    "timeout --kill-after=5 60 python x.py",
    "kill -0 1234",
    "rm /tmp/x; ls data/raw",
    "cp foo data/heldback/",
    "git log --format=%an origin/live..HEAD",
    "echo 'a b' > data/queue/agent_work.jsonl",
    "sed -n 1,20p AGENTS.md",
    "bash scripts/harness/hold.sh status",
    "uv run python scripts/harness/fetch.py https://example.org/x.gz --to -",
    "grep -n curl scripts/harness/fetch.py",
    "gh issue create --body 'the mirror offers wget only'",
]


@pytest.mark.parametrize("command", REFUSED)
def test_refused(command):
    assert rails.refuse_bash(command), command


@pytest.mark.parametrize("command", ALLOWED)
def test_allowed(command):
    assert rails.refuse_bash(command) is None, command


def test_a_long_command_checks_in_linear_time():
    for command in ("timeout" + " -k 1" * 200, "systemctl" + " -q ark-x" * 200, "just -f x" * 200):
        start = time.perf_counter()
        rails.refuse_bash(command)
        assert time.perf_counter() - start < 0.05, command[:30]


def test_write_paths(monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(ROOT))
    refused = (
        "agent/policy.json",
        ".claude/settings.json",
        "AGENTS.md",
        "data/held/x",
        "ding/x",
        "submissions/x",
        "private/x",
        "local.env",
        str(ROOT / "hooks/pre-commit"),
        "~/.claude/settings.json",
        os.path.join(str(ROOT), "sub", "..", "AGENTS.md"),
    )
    for p in refused:
        assert rails.refuse_path(p), p
    allowed = (
        "scripts/agents/triage.py",
        "docs/lore/laws.md",
        "data/queue/agent_work.jsonl",
        "tests/test_x.py",
        "data/logs/agent/x",
    )
    for p in allowed:
        assert rails.refuse_path(p) is None, p


def git_env():
    # The pre-commit hook exports GIT_DIR and GIT_INDEX_FILE for the repository it runs in, and
    # a git subprocess acts on that repository whatever cwd says: a clean environment here.
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def repo(path, branch):
    env = git_env()

    def git(*a):
        cmd = ["git", "-C", path, *a]
        return subprocess.run(
            cmd, check=True, capture_output=True, text=True, env=env
        ).stdout.strip()

    path.mkdir(exist_ok=True)
    git("init", "-q", "-b", branch)
    git("config", "user.email", "t@invalid")
    git("config", "user.name", "session")
    (path / "agent").mkdir()
    (path / "agent/policy.json").write_text("{}")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    return git


def test_a_git_state_change_is_refused_on_live_and_allowed_on_a_branch(tmp_path, monkeypatch):
    for k in list(os.environ):
        if k.startswith("GIT_"):
            monkeypatch.delenv(k)
    repo(tmp_path / "live", "live")
    repo(tmp_path / "branch", "B-x")
    call = {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}}
    assert rails.hook(call | {"cwd": str(tmp_path / "live")})
    assert rails.hook(call | {"cwd": str(tmp_path / "branch")}) is None
    merge = f"git -C {tmp_path / 'live'} merge B-x"
    assert rails.hook({"tool_name": "Bash", "tool_input": {"command": merge}, "cwd": str(tmp_path)})


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


def test_a_public_body_with_an_address_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(ROOT))
    address = ".".join(["93", "184", "216", "34"])
    (tmp_path / "b.md").write_text(f"the VM at {address} answered\n")
    cwd = str(tmp_path)

    def call(command):
        return rails.hook({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd})

    why = call("gh issue comment 5 --body-file b.md")
    assert why and "public scan" in why and "/" not in why
    assert call(f"gh api repos/x/issues -f body='see {address}'")
    assert call("gh issue comment 5 --body 'ticks banked: 24'") is None


def test_a_merge_is_refused_outside_the_window():
    assert rails.refuse_merge("5", dt.datetime(2026, 1, 1, 12, 20, tzinfo=dt.UTC))
    assert rails.refuse_merge("5", dt.datetime(2026, 1, 1, 12, 5, tzinfo=dt.UTC))


def test_ci_fails_an_agent_commit_on_a_rail_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    env = git_env()
    git = repo(tmp_path, "live")
    base = git("rev-parse", "HEAD")
    (tmp_path / "agent/policy.json").write_text("{ }")
    git("add", "-A")
    git("commit", "-q", "-m", "knob", "--author", "ark-agent <ark-agent@invalid>")
    head = git("rev-parse", "HEAD")
    cmd = ["python3", ROOT / "scripts/agents/rails.py", "--ci", base, head]
    out = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, env=env)
    assert out.returncode == 1 and "agent/policy.json" in out.stdout
    (tmp_path / "x.py").write_text("x = 1\n")
    git("add", "-A")
    git("commit", "-q", "-m", "code", "--author", "ark-agent <ark-agent@invalid>")
    head2 = git("rev-parse", "HEAD")
    cmd = ["python3", ROOT / "scripts/agents/rails.py", "--ci", head, head2]
    assert subprocess.run(cmd, cwd=tmp_path, env=env).returncode == 0
