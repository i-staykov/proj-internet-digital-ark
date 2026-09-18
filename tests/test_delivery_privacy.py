"""Nothing addressed to a person may reach the delivery archive.

`package_delivery.sh` ships the code as `git archive HEAD`, so **every tracked file goes in
front of the reviewer** unless `.gitattributes` marks it `export-ignore`. This tests the
SHAPE rather than the filenames, because a rule written as a filename has leaked three times,
and it reads the real archive manifest, which `.gitattributes` cannot be eyeballed for.
"""

import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Phrases that mean a document is a letter or a working note to a named person. Content
# rather than path, because the path is what everyone gets wrong.
ADDRESSED = (
    "dear professor",
    "send to:",
    "notes for ivo",
)


def _archive_names() -> set[str]:
    """What the next `git archive HEAD` would contain, honouring export-ignore, with two
    deliberate departures. `--worktree-attributes` reads the export-ignore rules from the
    worktree, so a newly written rule does not look broken until it is committed. **And the
    tree archived is the INDEX, not HEAD**, because otherwise removing a file that ships
    fails this test in the very commit that removes it; `package_delivery.sh` refuses to
    build against a modified tracked tree, so at packaging time the two are identical.
    """
    tree = subprocess.run(
        ["git", "write-tree"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    out = subprocess.run(
        ["git", "archive", "--worktree-attributes", "--format=tar", tree],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    import io

    with tarfile.open(fileobj=io.BytesIO(out.stdout)) as tf:
        return {n.lstrip("./") for n in tf.getnames()}


needs_git = pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(),
    reason="not a git checkout, which is the normal case inside an unpacked delivery",
)


@needs_git
def test_no_shipped_file_is_addressed_to_a_person() -> None:
    """The check that would have caught all three incidents."""
    offenders = []
    for name in sorted(_archive_names()):
        path = ROOT / name
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
            continue
        try:
            head = path.read_text(encoding="utf-8", errors="replace")[:4000].lower()
        except OSError:
            continue
        hit = next((p for p in ADDRESSED if p in head), None)
        if hit:
            offenders.append(f"{name} (contains {hit!r})")
    assert not offenders, (
        "these ship inside source/source.tar.gz and read as addressed to a person; "
        "mark them export-ignore in .gitattributes: " + "; ".join(offenders)
    )


@needs_git
def test_the_known_offenders_stay_withheld() -> None:
    """Pinned by name as well as by shape, because these are the proof."""
    names = _archive_names()
    for path in (
        "submissions/phase-5/email-draft.md",
        "docs/report-sendable.md",
        "docs/phase6-plan.md",
        # the two pages written about or to the reviewer, added 2026-09-02
        "docs/registers/questions.md",
        "docs/registers/rounds.md",
    ):
        assert path not in names, f"{path} is shipping again"


@needs_git
def test_every_round_plan_is_withheld_by_pattern_not_by_filename() -> None:
    """A new round must not have to remember to add a line."""
    shipped = {n for n in _archive_names() if "-plan.md" in n and n.startswith("docs/")}
    assert not shipped, f"round plans are shipping: {sorted(shipped)}"


@needs_git
def test_the_private_directory_never_ships() -> None:
    """`private/` is git-ignored, so nothing in it is tracked. Asserted, not assumed:
    the email template and its filled draft live there precisely because of this."""
    assert not [n for n in _archive_names() if n.startswith("private/")]
