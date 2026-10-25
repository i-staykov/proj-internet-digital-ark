"""`python -m ark.hygiene`, the scan the pre-commit hook and CI run, still catches each shape
planted in a scratch file, and the list of paths the fleet runs and the local layout stay honest."""

import shutil
import subprocess
from pathlib import Path

import pytest

from ark.hygiene import local_hosts, scan

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
