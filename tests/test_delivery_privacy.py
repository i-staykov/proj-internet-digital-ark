"""Nothing private, addressed to a person or unwritten reaches the delivery: it ships the code
as `git archive`, so every tracked file not marked `export-ignore` goes in front of the
reviewer. The shape is tested, not filenames: a rule written as a filename leaked three times."""

import io
import shutil
import subprocess
import tarfile
from functools import cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Phrases that mean a document is a letter or a working note to a named person.
ADDRESSED = ("dear professor", "send to:", "notes for ivo")
needs_git = pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(),
    reason="not a git checkout, which is the normal case inside an unpacked delivery",
)


@cache
def shipped() -> frozenset[str]:
    """What the next `git archive` would hold. The INDEX is archived, not HEAD, so a commit
    that removes a shipped file passes; packaging refuses a modified tracked tree, so there
    the two are the same. `--worktree-attributes` reads a rule not yet committed."""
    run = {"cwd": ROOT, "check": True, "capture_output": True}
    tree = subprocess.run(["git", "write-tree"], text=True, **run).stdout.strip()
    tar = subprocess.run(["git", "archive", "--worktree-attributes", "--format=tar", tree], **run)
    with tarfile.open(fileobj=io.BytesIO(tar.stdout)) as tf:
        return frozenset(n.lstrip("./") for n in tf.getnames())


@needs_git
def test_nothing_private_or_addressed_to_a_person_ships() -> None:
    names = shipped()
    assert not [n for n in names if n.startswith("private/")]
    # The known offenders, pinned by name as well as by shape, because they are the proof.
    for path in (
        "docs/report-sendable.md",
        "docs/registers/questions.md",
        "docs/registers/rounds.md",
    ):
        assert path not in names, f"{path} is shipping again"
    offenders = []
    for name in sorted(n for n in names if Path(n).suffix.lower() in {".md", ".txt"}):
        path = ROOT / name
        head = path.read_text(errors="replace")[:4000].lower() if path.is_file() else ""
        offenders += [f"{name} ({p!r})" for p in ADDRESSED if p in head]
    assert not offenders, "mark them export-ignore in .gitattributes: " + "; ".join(offenders)


def test_the_shipped_report_carries_no_unwritten_section() -> None:
    """A `<!-- ROUND` marker is for a human to write; the template carries them by design."""
    report = ROOT / "docs/report.md"
    lines = report.read_text().splitlines() if report.is_file() else []
    assert not [ln for ln in lines if ln.lstrip().lower().startswith("<!-- round")]
