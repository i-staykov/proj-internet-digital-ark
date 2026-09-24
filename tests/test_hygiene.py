"""The security scan still catches every shape it exists for.

`python -m ark.hygiene` scans the tracked tree in the pre-commit hook and in CI. These tests
plant each shape in a scratch file and check the scan reports it, and keep the two lists it
and the fleet read honest.
"""

import ipaddress
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ark.hygiene import IPV4, KNOWN_ADDRESSES, scan, tracked_files

ROOT = Path(__file__).resolve().parents[1]
FLEET_LIST = ROOT / "tests" / "fleet_invoked_paths.txt"

# Assembled so this file does not trip the scan it is testing.
PLANTED_ADDRESS = "9.8.7" + ".6"
PLANTED_TOKEN = "ghp_" + "0123456789abcdefghijklmnopqrstuvwxyz"
PLANTED_DASHES = (chr(0x2013), chr(0x2014))

needs_git = pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(),
    reason="needs the git checkout, not an unpacked archive",
)


def _fleet_paths() -> list[str]:
    lines = FLEET_LIST.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]


@needs_git
def test_fleet_invoked_paths_are_tracked() -> None:
    """Every path on the fleet-invoked list is a file the scan reads, so the list cannot rot
    and the scan cannot pass the hook by reading nothing."""
    tracked = {str(p.relative_to(ROOT)) for p in tracked_files(ROOT)}
    missing = [p for p in _fleet_paths() if p not in tracked]
    assert not missing, f"fleet_invoked_paths.txt names files that are not tracked: {missing}"


@needs_git
def test_local_settings_are_gitignored() -> None:
    """`.claude/settings.local.json` is ignored by `.gitignore`, not by a local exclude file."""
    proc = subprocess.run(
        ["git", "check-ignore", "-v", "--no-index", ".claude/settings.local.json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, "no ignore rule matches .claude/settings.local.json"
    # `-v` prints `<source>:<line>:<pattern>\t<path>`. `.git/info/exclude` matches too, and
    # it does not travel to the clone that pushes, so only `.gitignore` counts.
    source = proc.stdout.split(":", 1)[0]
    assert Path(source).name == ".gitignore", f"matched by {source}, not .gitignore"


def test_every_known_address_is_one_the_regex_would_catch() -> None:
    """The allowlist holds well-formed globally routable addresses and nothing else."""
    for entry in KNOWN_ADDRESSES:
        assert IPV4.fullmatch(entry), f"{entry} is not the shape the scan looks for"
        assert ipaddress.IPv4Address(entry).is_global, (
            f"{entry} is not routable, so it is not needed"
        )


def test_the_scan_catches_a_planted_address_token_and_dash(tmp_path: Path) -> None:
    """A file carrying any of these shapes is reported, which is what the hook and CI rely on."""
    planted = tmp_path / "leak.txt"
    text = "host " + PLANTED_ADDRESS + "\nexport GH_TOKEN=" + PLANTED_TOKEN + "\n"
    text += "".join(f"1996{dash}2001\n" for dash in PLANTED_DASHES)
    planted.write_text(text, encoding="utf-8")
    found = scan([planted])
    rules = {f.rule for f in found}
    assert "address" in rules, "the planted address was not found"
    assert "github token" in rules, "the planted token was not found"
    assert sum(f.rule == "dash" for f in found) == len(PLANTED_DASHES), "a planted dash was missed"


def test_a_login_against_a_private_address_is_refused(tmp_path) -> None:
    """The address rule fires only on globally routable addresses and the collector host is
    in private space, so a login against it passes every other guard
    (docs/ops/security-posture.md). A documentation-range address is still allowed.
    """
    # Assembled, not written out: this file is scanned too, and a literal here would
    # make the test fail on itself. That is the rule working, so keep it that way.
    login = "someone" + "@" + "10.20.30.40"
    probe = tmp_path / "probe.sh"
    probe.write_text(f'VPS="${{ARK_VPS:-{login}}}"\n')
    assert "host login" in {f.rule for f in scan([probe])}, "a private-address login passed"

    fixture_login = "ark" + "@" + "203.0.113.7"
    allowed = tmp_path / "fixture.py"
    allowed.write_text(f'STATUS = "== VPS ({fixture_login}) =="\n')
    assert not scan([allowed]), "a documentation-range address is a legitimate fixture"


def test_no_script_shadows_a_standard_library_module() -> None:
    """`scripts/<dir>/` joins `sys.path` when anything in it runs, so a module named after a
    standard one wins every import below it, and the failure surfaces three libraries deep.
    """
    stdlib = set(sys.stdlib_module_names)
    clashes = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "scripts").rglob("*.py")
        if path.stem in stdlib and "__pycache__" not in path.parts
    ]
    assert not clashes, f"these shadow a standard library module: {clashes}"
