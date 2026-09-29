"""`python -m ark.hygiene`, the scan the pre-commit hook and CI run, still catches each shape
planted in a scratch file, and the list of paths the fleet runs and the local layout stay honest."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import script

from ark.hygiene import scan, tracked_files

ROOT = Path(__file__).resolve().parents[1]
FLEET_LIST = ROOT / "tests" / "fleet_invoked_paths.txt"

# Assembled so this file does not trip the scan it is testing.
ADDRESS, TOKEN = "9.8.7" + ".6", "ghp_" + "0123456789abcdefghijklmnopqrstuvwxyz"
DASHES = "\u2013\u2014"

GIT = shutil.which("git") and (ROOT / ".git").exists()
needs_git = pytest.mark.skipif(not GIT, reason="needs the git checkout, not an unpacked archive")


@needs_git
def test_fleet_invoked_paths_are_tracked() -> None:
    """A moved or deleted script the fleet runs from its clone of `live` fails here first."""
    lines = FLEET_LIST.read_text(encoding="utf-8").splitlines()
    listed = [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]
    tracked = {str(p.relative_to(ROOT)) for p in tracked_files(ROOT)}
    assert listed and [p for p in listed if p not in tracked] == []


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


def test_no_script_shadows_a_standard_library_module() -> None:
    """`scripts/<dir>/` joins `sys.path` when anything in it runs, so a module named after a
    standard one wins every import below it, three libraries deep."""
    scripts = (ROOT / "scripts").rglob("*.py")
    clashes = [str(p.relative_to(ROOT)) for p in scripts if p.stem in sys.stdlib_module_names]
    assert clashes == [], "these shadow a standard library module"


@needs_git
def test_every_tracked_name_is_in_the_layout() -> None:
    """A tracked file or folder at the root or in `data/` the brief would call a stray."""
    layout = script("agents/brief.py").LAYOUT
    parts = [p.relative_to(ROOT).parts for p in tracked_files(ROOT)]
    root = {t[0] for t in parts} - layout[""]
    data = {t[1] for t in parts if t[0] == "data" and len(t) > 1} - layout["data"]
    assert (root, data) == (set(), set())


def test_the_brief_names_strays_and_what_is_held(tmp_path) -> None:
    brief, repo = script("agents/brief.py"), tmp_path / "repo"
    (repo / "data" / "raw").mkdir(parents=True)
    for name in ("plan.md", "data/ark.duckdb.pre-x.bak", "data/migrate"):
        (repo / name).mkdir() if "." not in Path(name).name else (repo / name).touch()
    assert brief.strays(repo) == ["plan.md", "data/ark.duckdb.pre-x.bak", "data/migrate"]
    assert brief.hold_line(None) == "held: nothing"
    held = brief.hold_line("human\n2026-09-29T08:00:00Z\nleg.yaml\nread.yaml\n")
    assert held.startswith("held since 2026-09-29T08:00:00Z: leg.yaml read.yaml")
