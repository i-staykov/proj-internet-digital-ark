"""The agent's rails: what a run may never do, refused before the tool runs.

Claude Code calls this as a `PreToolUse` hook from the VM profile's settings
(`agent/settings.json`, installed as the login's `~/.claude/settings.json`), with the tool
call as JSON on stdin; exit 2 refuses it and the stderr line tells the run why. The deny list
in that settings file catches the plain shapes first; this catches the ones a prefix match
cannot (a flag anywhere in a command, a path anywhere in a redirect, a body on its way out).

Refused: a git state change (commit, merge, rebase, reset, a ref write) while the command's
repository is on `live` or `main`, since the tick pushes the clone's `live` as it stands; a
forced push or any push that is not `git push origin <own branch>`; `--no-verify`, `-n`, a hooks
path or an author of its own; `gh pr merge` of a PR whose CI is not green, whose commits are not
`ark-agent`'s, or outside :36 to :04 UTC; `sudo`, a reboot; lifting or bypassing a hold, moving
an ark unit, the lanes or the sync lock (named anywhere, since the tick, `triage.py` and the
recipes move them outside the hook), a crontab change; clearing a red, a prune, a ship; killing
anything; a write under his files, the secrets, the hold or the Claude profile; `rm` under the
raw data; a login or a permission bypass; `curl` and `wget` in every mode, since a read goes
through `scripts/harness/fetch.py`; any write to a rail file (`RAILS`), which only a session
changes. Any `gh` command and any `git commit` is scanned whole by `ark.hygiene`, its
`--body-file` too, since the repository is public; a scan that cannot run refuses. Printing the
token is refused in its plain shapes only; the public scan is the rail on its way out.

    python3 scripts/agents/rails.py                 # the hook, JSON on stdin
    python3 scripts/agents/rails.py --ci BASE HEAD  # CI: an ark-agent commit on a rail fails

Standard library only, so the hook runs on the system python inside a run.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

AUTHOR = "ark-agent"
RAILS = (
    "agent/",
    ".claude/",
    "hooks/",
    "src/ark/hygiene.py",
    ".github/",
    "scripts/harness/hold.sh",
    "scripts/harness/sync_lock.sh",
    "AGENTS.md",
    "scripts/agents/rails.py",
)
PROFILE = os.path.expanduser("~/.claude")
# What a run may never write: his files, the secrets, the hold, the shipped archives.
GUARDED = (
    r"(?<![\w-])(data/held|ding|submissions|private|local\.env|\.config/ark|state/hold"
    r"|agent\.env|\.claude)(?![\w-])"
)
# A rail directory matches whatever follows its slash; a rail file only as a whole name; the
# run's own `data/logs/agent/` is not the `agent/` rail.
RAIL_RE = (
    r"(?<![\w.-])(?<!logs/)("
    + "|".join(re.escape(p) if p.endswith("/") else re.escape(p) + r"(?![\w-])" for p in RAILS)
    + ")"
)
WRITE_VERB = (
    r"(?:>\|?|>>|\btee\b|\bcp\b|\bmv\b|\brm\b|\brsync\b|\bsed\s+-i|\binstall\b|\btruncate\b"
    r"|\bchmod\b|\bln\b|\bdd\b)"
)
GIT = r"git(?:\s+-[-\w=./]+(?:\s+[^\s-]\S*)?)*"  # git with its own options, `-C path` among them
SEP = r"(?:^|[;&|(]\s*)"
# Up to N words, each a run of non-blanks, so a long command stays linear.
WORDS = r"(?:[ \t]+[^\s;&|]+){0,%d}?[ \t]+"
MENTION = "; a mention goes in a file (`--body-file`, `-F`)"
KILL = r"(?<![\w-])(pkill|killall)(?![\w-])|(?<![\w-])kill(?![\w-])(?!\s+-0\b)"

BASH_RULES: tuple[tuple[str, str], ...] = (
    (GIT + r"\s+push\b.*(\s--force\b|\s-f\b|--force-with-lease)", "a forced push"),
    (
        GIT + r"\s+push\b(?!\s+(-u\s+|--set-upstream\s+)?origin\s+(--delete\s+)?"
        r"(?!live\b|main\b|HEAD\b)[\w./-]+\s*$)",
        "a push that is not `git push origin <branch>` to a branch of its own",
    ),
    (r"--no-verify|git\s+commit\b.*\s-n\b|core\.hooksPath", "skipping the hook gate"),
    (r"gh\s+pr\s+merge\b.*--admin", "`--admin` routes around CI"),
    (r"(?<![\w-])sudo\b", "sudo"),
    (
        r"(?<![\w-])(reboot|shutdown|poweroff)\b|systemctl\s+(reboot|poweroff|halt)",
        "a reboot is the tick's alone",
    ),
    (r"hold(\.sh)?\s+off\b|just\s+hold\s+off", "lifting a hold is the owner's or a session's"),
    (r"ARK_HOLD_BYPASS", "bypassing the hold"),
    (r"\bcrontab\b", "the lanes' cron is not the run's to move"),
    (
        r"\A(?=.*?ark-)(?=.*?systemctl" + WORDS % 8 + r"([^\s;&|]*-)?"
        r"(start|stop|kill|restart|condrestart|enable|disable|mask|reenable)\b)",
        "an ark unit moves only by the tick, a reader by `triage.py restart`" + MENTION,
    ),
    (
        r"\bjust" + WORDS % 6 + r"[\"']?walk[\"']?[ \t]+[\"']?(install|remove)\b"
        r"|cdx_walk_jobs\.py[\"']?[ \t]+[\"']?(install|remove)\b",
        "the lanes reinstall only by `triage.py walk`, away from the tick" + MENTION,
    ),
    (
        r"\A(?=.*?sync_lock\.sh).*?(sync_lock\.sh|\$\{?\w+\}?)[\"']?[ \t]+[\"']?(take|drop)\b"
        r"|\A(?=.*?\.sync)(?=.*?(\b(rm|rmdir|mv)\b|\s-(delete|exec)\b))",
        "the sync lock is taken and dropped only inside the recipes" + MENTION,
    ),
    (r"bank_trigger\.py\s+clear", "a red is cleared only through `just red-clear`"),
    (r"\bprune\b.*--write|prune\s+--round", "a prune deletes what only a session may"),
    (
        r"just\s+ship\b|package_delivery\.sh|ship_mail\.py|verify_delivery\.sh",
        "a ship is the owner's",
    ),
    (KILL, "nothing is killed; a walker restarts only by `triage.py walk`"),
    (
        r"(?i)git\s+commit\b.*--author|git\s+-c\s+user\.(name|email)"
        r"|git\s+config\b.*user\.(name|email)|GIT_(AUTHOR|COMMITTER)_",
        "the author is ark-agent",
    ),
    (
        WRITE_VERB + r"[^;&|]*" + GUARDED,
        "a write under his files, the secrets, the hold or the profile",
    ),
    (r"\brm\b[^;&|]*data/raw", "rm under the raw data"),
    (
        SEP + r"(printenv|env|export|set)\s*(-[0p]\s*)?(\||;|$)"
        r"|\b(echo|printf)\b.*\$\{?CLAUDE_CODE_OAUTH_TOKEN"
        r"|(CLAUDE_CODE_OAUTH_TOKEN|ANTHROPIC_API_KEY)\s*="
        r"|\bcat\b.*(agent\.env|/proc/self/environ)",
        "printing or setting a credential",
    ),
    (
        r"claude\s+(setup-token|login|auth|logout)|--dangerously-skip-permissions",
        "a login or a permission bypass",
    ),
    (
        r"(?:^|[;&|(`\n]\s*|\$\(\s*|\b(?:xargs|timeout|nohup|exec|nice|env)\b[^;&|]*?\s)"
        r"(?:\S*/)?(curl|wget)\b",
        "a read goes through scripts/harness/fetch.py",
    ),
    (WRITE_VERB + r"[^;&|]*" + RAIL_RE, "a rail file changes only by a session's PR"),
    (
        r"git\s+(checkout\s+--|restore\b)[^;&|]*" + RAIL_RE,
        "a rail file changes only by a session's PR",
    ),
)
STATE_CHANGE = re.compile(
    GIT + r"\s+(commit|merge|rebase|reset|cherry-pick|am|apply|update-ref|symbolic-ref"
    r"|branch\s+-[fD]|checkout\s+-[bB]|switch\s+-c)\b"
)
WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
SCANNED = re.compile(r"(^|[;&|]\s*)(gh\s|git\s+commit\b)")
MERGE = re.compile(r"gh\s+pr\s+merge\s+(\d+)")


def refuse_bash(command: str) -> str | None:
    for pattern, why in BASH_RULES:
        if re.search(pattern, command, re.S):
            return why
    return None


def project_dir() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def refuse_path(path: str) -> str | None:
    """A write to a guarded, a rail or a profile path, resolved against the project directory."""
    absolute = os.path.abspath(os.path.join(project_dir(), os.path.expanduser(path)))
    if absolute == PROFILE or absolute.startswith(PROFILE + os.sep):
        return "the Claude profile changes only by a session's PR"
    rel = os.path.relpath(absolute, project_dir()).replace("\\", "/")
    if rel.startswith(".."):
        return None
    if re.search(GUARDED, "/" + rel):
        return "a write under his files, the secrets or the hold"
    if any(rel.startswith(p) or rel == p.rstrip("/") for p in RAILS):
        return "a rail file changes only by a session's PR"
    return None


def repo_branch(command: str, cwd: str) -> str:
    """The branch the command's repository is on: `-C path` in the command, else cwd."""
    m = re.search(r"git\s+(?:-[-\w=./]+\s+)*-C\s+(\S+)", command)
    where = os.path.join(cwd, os.path.expanduser(m.group(1))) if m else cwd
    out = subprocess.run(
        ["git", "-C", where, "symbolic-ref", "--short", "-q", "HEAD"],
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def body_files(command: str) -> list[str]:
    try:
        words = shlex.split(command)
    except ValueError:
        return []
    files = []
    for i, w in enumerate(words):
        if w in ("--body-file", "-F") and i + 1 < len(words):
            files.append(words[i + 1])
        elif w.startswith("--body-file="):
            files.append(w[len("--body-file=") :])
    return files


def hygiene(text: str) -> str | None:
    """A FAIL line from `ark.hygiene` over the text, or None when it is clean."""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(text)
    try:
        out = subprocess.run(
            ["uv", "run", "python", "-m", "ark.hygiene", fh.name],
            capture_output=True,
            text=True,
            cwd=project_dir(),
        )
    except OSError as exc:
        return f"the scan could not run ({type(exc).__name__})"
    finally:
        os.unlink(fh.name)
    if out.returncode == 0:
        return None
    first = (out.stdout.strip().splitlines() or ["hygiene refused the body"])[0]
    return first.split(": ", 1)[-1]


def refuse_merge(number: str, now: dt.datetime | None = None) -> str | None:
    """`gh pr merge N` only inside the window, with CI green and every commit ark-agent's."""
    minute = (now or dt.datetime.now(dt.UTC)).minute
    if 4 < minute < 36:
        return "a merge lands only inside :36 to :04 UTC"
    checks = subprocess.run(["gh", "pr", "checks", number], capture_output=True, text=True)
    if checks.returncode != 0:
        return f"PR {number}'s CI is not green"
    commits = subprocess.run(
        ["gh", "pr", "view", number, "--json", "commits", "--jq", ".commits[].authors[].name"],
        capture_output=True,
        text=True,
    )
    names = set(commits.stdout.split())
    if commits.returncode != 0 or names != {AUTHOR}:
        who = sorted(names) or "nobody"
        return f"PR {number} carries commits by {who}; the agent merges only its own"
    return None


def open_or_empty(path: str) -> str:
    try:
        return open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


def hook(payload: dict) -> str | None:
    tool, inp = payload.get("tool_name", ""), payload.get("tool_input") or {}
    cwd = payload.get("cwd") or os.getcwd()
    if tool == "Bash":
        command = str(inp.get("command", ""))
        why = refuse_bash(command)
        if why:
            return why
        if STATE_CHANGE.search(command) and repo_branch(command, cwd) in ("live", "main"):
            return "no git state change on live or main; the tick pushes live as it stands"
        if SCANNED.search(command):
            text = command + "".join(
                open_or_empty(os.path.join(cwd, f)) for f in body_files(command)
            )
            hit = hygiene(text)
            if hit:
                return f"the command fails the public scan: {hit}"
        merge = MERGE.search(command)
        if merge:
            return refuse_merge(merge.group(1))
    elif tool in WRITE_TOOLS:
        return refuse_path(str(inp.get("file_path") or inp.get("notebook_path") or ""))
    return None


def ci(base: str, head: str) -> list[str]:
    """The rail files an ark-agent commit between base and head touches."""
    log = subprocess.run(
        ["git", "log", "--format=%an", f"{base}..{head}"], capture_output=True, text=True
    )
    if AUTHOR not in log.stdout.split("\n"):
        return []
    diff = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"], capture_output=True, text=True
    )
    return [f for f in diff.stdout.split() if refuse_path(f)]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--ci"]:
        touched = ci(argv[1], argv[2])
        for f in touched:
            print(f"FAIL {f}: an {AUTHOR} commit touches a rail file; a session's PR changes it")
        return 1 if touched else 0
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    try:
        why = hook(payload)
    except Exception as exc:  # a rail that cannot decide refuses
        why = f"the rails could not decide ({type(exc).__name__})"
    if why:
        print(f"rails: refused, {why}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
