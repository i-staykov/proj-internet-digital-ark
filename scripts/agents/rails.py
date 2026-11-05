"""The agent's rails: what a run may never do, refused before the tool runs.

Claude Code calls this as a `PreToolUse` hook from the VM profile's settings
(`agent/settings.json`, installed as the login's `~/.claude/settings.json`), with the tool
call as JSON on stdin; exit 2 refuses it and the stderr line tells the run why. The deny list in
that settings file catches the plain shapes first; this catches the ones a prefix match cannot
(a flag anywhere in a command, a path anywhere in a redirect, a body on its way to a public issue).

Refused: a forced or direct push to `live`, `--no-verify`, `--admin`, `sudo`, a reboot, lifting a
hold or bypassing it, clearing a red, a prune or a ship, killing a walker, a spoofed author, any
write under his files or the secrets, `rm` under the raw data, printing the environment or the
token, a login, and any write to a rail file (`RAILS`: this script's settings, the hooks, the
hygiene scan, CI, the hold, the lock, `AGENTS.md`), which only a session changes. A `gh` body
(`--body`, `--body-file`) is scanned by `ark.hygiene` before it leaves, since the repository is
public.

    python3 scripts/agents/rails.py                 # the hook, JSON on stdin
    python3 scripts/agents/rails.py --ci BASE HEAD  # CI: an ark-agent commit on a rail fails

Standard library only, so the hook runs on the system python inside a run.
"""

from __future__ import annotations

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
# What a run may never write: his files, the secrets, the hold, the shipped archives.
GUARDED = r"(data/held|ding/|submissions/|private/|local\.env|\.config/ark|state/hold|agent\.env)"
RAIL_RE = "|".join(re.escape(p) for p in RAILS)
WRITE_VERB = (
    r"(?:>|>>|\btee\b|\bcp\b|\bmv\b|\brm\b|\brsync\b|\bsed\s+-i|\binstall\b|\btruncate\b"
    r"|\bchmod\b|\bln\b)"
)

BASH_RULES: tuple[tuple[str, str], ...] = (
    (r"git\s+push\b.*(\s--force\b|\s-f\b|--force-with-lease)", "a forced push"),
    (
        r"git\s+push\b(?!\s+(-u\s+|--set-upstream\s+)?origin\s+(--delete\s+)?"
        r"(?!live\b|main\b)[\w./-]+\s*$)",
        "a push that is not `git push origin <branch>` to a branch of its own",
    ),
    (r"--no-verify", "`--no-verify` skips the hook gate"),
    (r"gh\s+pr\s+merge\b.*--admin", "`--admin` routes around CI"),
    (r"(^|[;&|]\s*)sudo\b", "sudo"),
    (
        r"\b(reboot|shutdown|poweroff)\b|systemctl\s+(reboot|poweroff|halt)",
        "a reboot is the tick's alone",
    ),
    (r"hold(\.sh)?\s+off\b|just\s+hold\s+off", "lifting a hold is the owner's or a session's"),
    (r"ARK_HOLD_BYPASS", "bypassing the hold"),
    (r"bank_trigger\.py\s+clear", "a red is cleared only through `just red-clear`"),
    (r"\bprune\b.*--write|prune\s+--round", "a prune deletes what only a session may"),
    (
        r"just\s+ship\b|package_delivery\.sh|ship_mail\.py|verify_delivery\.sh",
        "a ship is the owner's",
    ),
    (
        r"(pkill|killall|kill)\b.*(cdx_extended_walk|cdx_platform_walk|python)",
        "a walker is restarted only by `just walk install`",
    ),
    (
        r"git\s+commit\b.*--author|git\s+-c\s+user\.(name|email)|git\s+config\b.*user\.(name|email)",
        "the author is ark-agent",
    ),
    (WRITE_VERB + r".*" + GUARDED, "a write under his files, the secrets or the hold"),
    (r"\brm\b.*data/raw", "rm under the raw data"),
    (
        r"\b(printenv|env|export|set)\s*(\||;|$)|\becho\b.*\$\{?CLAUDE_CODE_OAUTH_TOKEN|(CLAUDE_CODE_OAUTH_TOKEN|ANTHROPIC_API_KEY)\s*=|\bcat\b.*agent\.env",
        "printing or setting a credential",
    ),
    (
        r"claude\s+(setup-token|login|auth|logout)|--dangerously-skip-permissions",
        "a login or a permission bypass",
    ),
    (WRITE_VERB + r".*(" + RAIL_RE + ")", "a rail file changes only by a session's PR"),
    (
        r"git\s+checkout\s+--\s+.*(" + RAIL_RE + r")|git\s+restore\b.*(" + RAIL_RE + ")",
        "a rail file changes only by a session's PR",
    ),
)
WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
GH_BODY = re.compile(r"^gh\s+(pr|issue)\s+(create|comment|edit)\b")


def refuse_bash(command: str) -> str | None:
    for pattern, why in BASH_RULES:
        if re.search(pattern, command, re.S):
            return why
    return None


def refuse_path(path: str) -> str | None:
    rel = os.path.relpath(path) if os.path.isabs(path) else path
    rel = rel.replace("\\", "/")
    if re.search(GUARDED, rel):
        return "a write under his files, the secrets or the hold"
    if any(rel.startswith(p) or rel == p.rstrip("/") for p in RAILS) or "/" + rel in (
        "/" + r for r in RAILS
    ):
        return "a rail file changes only by a session's PR"
    return None


def body_of(command: str) -> str | None:
    """The body a `gh pr|issue create|comment|edit` would send, or None."""
    if not GH_BODY.match(command):
        return None
    try:
        words = shlex.split(command)
    except ValueError:
        return None
    for i, w in enumerate(words):
        if w in ("--body", "-b") and i + 1 < len(words):
            return words[i + 1]
        if w.startswith("--body="):
            return w[len("--body=") :]
        if w in ("--body-file", "-F") and i + 1 < len(words):
            try:
                return open(words[i + 1], encoding="utf-8", errors="replace").read()
            except OSError:
                return None
    return None


def hygiene(text: str) -> str | None:
    """A FAIL line from `ark.hygiene` over the text, or None when it is clean."""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(text)
    try:
        out = subprocess.run(
            ["uv", "run", "python", "-m", "ark.hygiene", fh.name], capture_output=True, text=True
        )
    finally:
        os.unlink(fh.name)
    if out.returncode == 0:
        return None
    return (out.stdout.strip().splitlines() or ["hygiene refused the body"])[0]


def hook(payload: dict) -> str | None:
    tool, inp = payload.get("tool_name", ""), payload.get("tool_input") or {}
    if tool == "Bash":
        command = str(inp.get("command", ""))
        why = refuse_bash(command)
        if why:
            return why
        body = body_of(command)
        if body is not None:
            hit = hygiene(body)
            if hit:
                return f"the body fails the public scan: {hit}"
    elif tool in WRITE_TOOLS:
        return refuse_path(str(inp.get("file_path") or inp.get("notebook_path") or ""))
    return None


def ci(base: str, head: str) -> list[str]:
    """The rail files an ark-agent commit between base and head touches."""
    authors = subprocess.run(
        ["git", "log", "--format=%an", f"{base}..{head}"], capture_output=True, text=True
    ).stdout.split("\n")
    if AUTHOR not in authors:
        return []
    files = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"], capture_output=True, text=True
    ).stdout.split()
    return [f for f in files if refuse_path(f)]


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
    why = hook(payload)
    if why:
        print(f"rails: refused, {why}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
