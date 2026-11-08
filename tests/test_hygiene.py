"""`python -m ark.hygiene`, the scan the pre-commit hook and CI run, still catches each shape
planted in a scratch file, and the list of paths the fleet runs and the local layout stay honest."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ark.hygiene import local_hosts, refused_identities, scan

ROOT = Path(__file__).resolve().parents[1]

# Assembled so this file does not trip the scan it is testing.
ADDRESS, TOKEN = "9.8.7" + ".6", "ghp_" + "0123456789abcdefghijklmnopqrstuvwxyz"
DASHES = "\u2013\u2014"

GIT = shutil.which("git") and (ROOT / ".git").exists()
needs_git = pytest.mark.skipif(not GIT, reason="needs the git checkout, not an unpacked archive")


@needs_git
def test_local_settings_are_ignored_by_the_gitignore_that_travels() -> None:
    """`.git/info/exclude` matches too, and it does not travel to the clone that pushes."""
    cmd = ["git", "check-ignore", "-v", "--no-index", ".claude/settings.local.json"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    # `-v` prints `<source>:<line>:<pattern>\t<path>`
    assert (proc.returncode, Path(proc.stdout.split(":", 1)[0]).name) == (0, ".gitignore")


def test_the_scan_catches_each_planted_shape(tmp_path: Path) -> None:
    """A frozen submission keeps its decision numbers and nothing else."""
    planted = tmp_path / "leak.txt"
    text = f"host {ADDRESS}\nexport GH_TOKEN={TOKEN}\n" + "".join(f"1996{d}2001\n" for d in DASHES)
    text += "see " + "C" + "-95\n"
    planted.write_text(text, encoding="utf-8")
    found = scan([planted])
    rules = {f.rule for f in found}
    assert {"address", "github token", "dash", "decision number"} <= rules, rules
    assert sum(f.rule == "dash" for f in found) == len(DASHES), "a planted dash was missed"
    frozen = tmp_path / "submissions" / "phase-5" / "leak.txt"
    frozen.parent.mkdir(parents=True)
    frozen.write_text(text, encoding="utf-8")
    assert {f.rule for f in scan([frozen])} == rules - {"decision number"}


def test_a_login_against_a_private_address_is_refused(tmp_path) -> None:
    """The address rule fires only on globally routable addresses and the collector host is
    in private space, so a login against it passes every other guard. A documentation-range
    address is still allowed. Assembled, not written out: this file is scanned too."""
    probe, allowed = tmp_path / "probe.sh", tmp_path / "fixture.py"
    probe.write_text('VPS="${ARK_VPS:-someone' + "@" + '10.20.30.40}"\n')
    assert "host login" in {f.rule for f in scan([probe])}, "a private-address login passed"
    allowed.write_text('STATUS = "== VPS (ark' + "@" + '203.0.113.7) =="\n')
    assert not scan([allowed]), "a documentation-range address is a legitimate fixture"


def test_the_machines_local_env_names_are_refused(tmp_path) -> None:
    """Alias and address by their own strings in any case, a name with any label joined to
    it; a longer word or dotted number passes, and `local` is this machine."""
    env, probe = tmp_path / "local.env", tmp_path / "probe.md"
    env.write_text('ARK_HOSTS="docs-vm:0 someone' + "@" + '203.0.113.9:2 local:1"\n')
    probe.write_text(
        "ssh Docs-VM\nat 203.0.113.9.\nsub.docs-vm.example\nok docs-vm2 203.0.113.90 local\n"
    )
    found = scan([probe], local_hosts(env), hosts_only=True)
    assert [(f.line, f.rule) for f in found] == [(n, "local host") for n in (1, 2, 3)]


@needs_git
def test_a_commit_signed_by_a_machine_is_refused_by_both_hooks(tmp_path, monkeypatch) -> None:
    """As git signs without an identity, `login@hostname`: the pre-push hook refuses the commit
    by its sha, never its address, and pushes an allowlisted one; pre-commit refuses it first.
    No git variable reaches a git here: under the hook gate a GIT_DIR turns `git init` on the
    shared clone, making it bare."""
    clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    uv = tmp_path / "uv"  # `uv run python ARGS` is this test's python
    uv.write_text(f'#!/usr/bin/env bash\nshift 2; exec {sys.executable} "$@"\n')
    uv.chmod(0o755)
    env = {**clean, "PATH": f"{tmp_path}:{clean['PATH']}"}
    repo, machine = tmp_path / "repo", "ops" + "@box.cloud.example.org"

    def git(*args: str, email: str = "t@invalid") -> subprocess.CompletedProcess:
        ident = ["-c", "user.name=t", "-c", f"user.email={email}"]
        return subprocess.run(["git", *ident, *args], cwd=repo, env=env, capture_output=True)

    for init in (["--bare", str(tmp_path / "origin.git")], ["-b", "live", str(repo)]):
        subprocess.run(["git", "init", "-q", *init], env=env, check=True)
    git("remote", "add", "origin", str(tmp_path / "origin.git"))
    (repo / ".git/hooks/pre-push").symlink_to(ROOT / "hooks/pre-push")
    git("commit", "-q", "--allow-empty", "-m", "ok")
    assert git("push", "-q", "origin", "live").returncode == 0
    git("commit", "-q", "--allow-empty", "-m", "leak", email=machine)
    pushed = git("push", "-q", "origin", "live")
    assert pushed.returncode and b"REFUSED" in pushed.stderr and b"box" not in pushed.stderr
    for who, email in (("AUTHOR", machine), ("COMMITTER", "t@invalid")):
        monkeypatch.setenv(f"GIT_{who}_NAME", "t")
        monkeypatch.setenv(f"GIT_{who}_EMAIL", email)
    assert refused_identities(cwd=repo) == ["next author"]
