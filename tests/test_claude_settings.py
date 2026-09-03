"""The tracked harness settings, which configure the fleet as well as a laptop session.

The fleet runs `claude -p` inside a clone of this branch, so `.claude/settings.json` is read
unattended: a host or a local path in it would be published and would also be wrong on every
other machine. The one deny rule is a `Read()` rule on purpose. Claude Code resolves the file
a Bash command reads and checks it against the `Read()` rules, so a single entry covers the
Read tool, `cat` and a pager alike; `just find` and `grep` stay open.

`.claude/settings.local.json` is the machine-local half and must never become tracked.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from ark.hygiene import IPV4

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / ".claude" / "settings.json"
LOCAL_SETTINGS = ".claude/settings.local.json"

# "Read(./docs/sources*.md)" -> "./docs/sources*.md"
RULE = re.compile(r"^[A-Za-z]+\((.*)\)$")

# The two registers the deny rule exists for, and the only files it may reach.
REGISTERS = {"docs/sources.md", "docs/sources-closed.md"}

ENV_CAPS = {"BASH_MAX_OUTPUT_LENGTH", "CLAUDE_CODE_FILE_READ_MAX_OUTPUT_TOKENS"}

needs_git = pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(),
    reason="needs the git checkout, not an unpacked archive",
)


def _settings() -> dict:
    return json.loads(SETTINGS.read_text(encoding="utf-8"))


def _permission_rules() -> list[str]:
    permissions = _settings()["permissions"]
    return list(permissions.get("allow", [])) + list(permissions.get("deny", []))


def test_settings_match_the_schema_shape() -> None:
    """It parses, and the parts the schema types are the types the schema asks for."""
    settings = _settings()
    assert settings["$schema"].endswith("claude-code-settings.json")

    env = settings["env"]
    assert set(env) == ENV_CAPS, "the env block is the two output caps, nothing else"
    # The schema types every env value as a string. A bare number parses as JSON and is
    # then silently the wrong type, which is exactly the mistake a test can catch.
    assert all(isinstance(value, str) and value.isdigit() for value in env.values()), env

    permissions = settings["permissions"]
    assert permissions["allow"], "the allow list is not empty"
    assert all(isinstance(rule, str) for rule in _permission_rules())


def test_permission_rules_carry_no_address_and_no_local_path() -> None:
    """Nothing in allow or deny names a machine, an account or a path outside the repo."""
    for rule in _permission_rules():
        assert "/Users/" not in rule, rule
        assert "://" not in rule, rule
        assert "@" not in rule, rule
        assert IPV4.search(rule) is None, rule


def test_the_single_deny_reaches_the_two_registers_and_nothing_else() -> None:
    """One deny entry, and what it matches in this tree is exactly the two register pages."""
    deny = _settings()["permissions"]["deny"]
    assert len(deny) == 1, deny

    match = RULE.match(deny[0])
    assert match is not None, deny[0]
    pattern = match.group(1).removeprefix("./")
    reached = {path.relative_to(ROOT).as_posix() for path in ROOT.glob(pattern)}
    assert reached == REGISTERS, reached


@needs_git
def test_local_settings_are_not_tracked() -> None:
    """The machine-local settings file stays out of git, whatever exists on this disk."""
    out = subprocess.run(
        ["git", "ls-files", "--", LOCAL_SETTINGS],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    assert out.decode("utf-8").strip() == "", f"{LOCAL_SETTINGS} is tracked"
