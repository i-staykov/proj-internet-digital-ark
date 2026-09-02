"""Mechanical guards for the tree: nothing orphaned, nothing dangling, nothing leaked.

Each test enforces one rule and says so in its docstring. A rule the tree cannot pass yet
is `xfail(strict=True)` naming the ticket that lifts it, so the commit that fixes the tree
turns the xfail into a gate failure and the marker comes off in the same change.
"""

import ipaddress
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FLEET_LIST = ROOT / "tests" / "fleet_invoked_paths.txt"
DOCS_PAGE = re.compile(r"docs/[^/]+\.md")
DOC_REF = re.compile(r"docs/[a-z_-]+\.md")
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")

# Globally routable addresses already in the tree, each read in context: a host a source
# note says a name resolves to, a root server or public resolver, or a test fixture. A new
# one fails until somebody reads it and adds it here, which is the point of the rule.
KNOWN_ADDRESSES = frozenset(
    {
        # fixture rows in tests/test_isc_hostnames.py and tests/test_ripe_nserver_hostnames.py
        "1.0.0.2",
        "1.125.2.7",
        "1.125.2.8",
        "1.3.3.1",
        "1.3.3.2",
        "1.3.3.3",
        "128.214.4.29",
        "1.2.3.4",
        "8.8.8.8",
        "66.199.183.26",
        "78.47.242.83",
        "130.217.250.15",
        "192.149.252.21",
        "193.166.0.0",
        "193.166.255.255",
        "198.41.0.4",
        "204.96.208.1",
        "207.36.205.194",
    }
)

needs_git = pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(),
    reason="needs the git checkout, not an unpacked archive",
)


def _tracked() -> list[str]:
    """Paths `git ls-files` knows, as repo-relative strings."""
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    ).stdout
    return [p for p in out.decode("utf-8").split("\0") if p and (ROOT / p).is_file()]


def _text(rel: str) -> str | None:
    """The file's text, or None for a binary (git's own test: a NUL in the first 8000 bytes)."""
    data = (ROOT / rel).read_bytes()
    if b"\0" in data[:8000]:
        return None
    return data.decode("utf-8", errors="replace")


def _fleet_paths() -> list[str]:
    lines = FLEET_LIST.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]


@needs_git
def test_fleet_invoked_paths_are_tracked() -> None:
    """Every path on the fleet-invoked list is a tracked file, so the list cannot rot."""
    tracked = set(_tracked())
    missing = [p for p in _fleet_paths() if p not in tracked]
    assert not missing, f"fleet_invoked_paths.txt names files that are not tracked: {missing}"


@needs_git
@pytest.mark.xfail(strict=True, reason="lifted by E3.2")
def test_every_script_has_a_caller() -> None:
    """A `scripts/` module is named in the justfile, a docs page, another file or the fleet list."""
    tracked = _tracked()
    pages = ["justfile", "README.md", *(p for p in tracked if DOCS_PAGE.fullmatch(p))]
    prose = "\n".join(_text(p) or "" for p in pages)
    code = {p: _text(p) or "" for p in tracked if p.endswith((".py", ".sh"))}
    fleet = set(_fleet_paths())
    orphans = []
    for path in tracked:
        if not (path.startswith("scripts/") and path.endswith(".py")):
            continue
        if path in fleet or Path(path).name in prose:
            continue
        # Imports and importlib loaders both spell the stem. A word match keeps
        # `split_usenet` from being credited to `split_usenet_addresses`.
        stem = re.compile(rf"\b{re.escape(Path(path).stem)}\b")
        if any(stem.search(text) for other, text in code.items() if other != path):
            continue
        orphans.append(path)
    assert not orphans, f"nothing names these scripts: {orphans}"


@needs_git
@pytest.mark.xfail(strict=True, reason="lifted by E4.1")
def test_every_docs_page_is_in_the_index() -> None:
    """Every tracked `docs/*.md` is named in `docs/index.md`."""
    index = ROOT / "docs" / "index.md"
    assert index.is_file(), "docs/index.md does not exist"
    text = index.read_text(encoding="utf-8")
    pages = [Path(p).name for p in _tracked() if DOCS_PAGE.fullmatch(p)]
    missing = [n for n in pages if n != "index.md" and n not in text]
    assert not missing, f"docs pages absent from docs/index.md: {missing}"


@needs_git
@pytest.mark.xfail(strict=True, reason="lifted by E4.5")
def test_every_docs_reference_resolves() -> None:
    """Every `docs/<x>.md` string in tracked code and prose names a file that exists."""
    dangling: dict[str, list[str]] = {}
    for path in _tracked():
        # Frozen submissions keep whatever their round referred to.
        if path.startswith("submissions/"):
            continue
        if not path.endswith((".py", ".sh", ".md", ".yaml", ".txt")):
            continue
        for ref in set(DOC_REF.findall(_text(path) or "")):
            if not (ROOT / ref).is_file():
                dangling.setdefault(ref, []).append(path)
    assert not dangling, f"docs references with no file behind them: {dangling}"


@pytest.mark.skipif(shutil.which("just") is None, reason="just not on PATH")
@pytest.mark.xfail(strict=True, reason="lifted by E3.7")
def test_justfile_has_at_most_forty_recipes() -> None:
    """`just --summary` lists at most 40 recipes."""
    out = subprocess.run(
        ["just", "--summary"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout
    recipes = out.split()
    assert len(recipes) <= 40, f"{len(recipes)} recipes: {' '.join(recipes)}"


@pytest.mark.xfail(strict=True, reason="lifted by E4.2")
def test_register_lines_stay_under_500_chars() -> None:
    """No line in `docs/sources.md` or `docs/sources-closed.md` is longer than 500 characters."""
    over: dict[str, int] = {}
    for name in ("sources.md", "sources-closed.md"):
        path = ROOT / "docs" / name
        if not path.is_file():  # sources-closed.md arrives with E4.2
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        count = sum(1 for line in lines if len(line) > 500)
        if count:
            over[name] = count
    assert not over, f"lines over 500 chars: {over}"


@needs_git
@pytest.mark.xfail(strict=True, reason="lifted by E3.8")
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


@needs_git
def test_no_tracked_file_leaks_an_address() -> None:
    """No tracked text file holds a globally routable IPv4 address outside the known list."""
    found: dict[str, list[str]] = {}
    for path in _tracked():
        if path.startswith("submissions/"):
            continue
        text = _text(path)
        if text is None:
            continue
        for hit in set(IPV4.findall(text)):
            try:
                addr = ipaddress.IPv4Address(hit)
            except ValueError:  # 300.1.2.3 is not an address
                continue
            if addr.is_global and hit not in KNOWN_ADDRESSES:
                found.setdefault(hit, []).append(path)
    assert not found, f"addresses not on the known list: {found}"
