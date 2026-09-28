"""`push_fleet.sh` against a bare origin and two clones of it, the second being the laptop's.

The quiet failure. A leg's collect pushes to the same month file, so a laptop push is often
rejected, and the retry resets the clone onto the remote. A reset drops every ledger line
the laptop added, and the old TSV the legacy lines came from is deleted by then, so nothing
else could write them again.
"""

import json
import os
import subprocess
from pathlib import Path

from test_fleet_ledger import STAND_IN, fleet_ledger

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/harness/push_fleet.sh"
# Under the pre-commit hook git exports GIT_DIR and GIT_INDEX_FILE for the real repository,
# and these clones would stage into it.
ENV = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
MONTH = "ledger/2026-09.jsonl"
LEGACY = [
    {"row": 1, "line": "20260901T1037Z\t432\t68.0", "at": "2026-09-01T10:37:00Z"},
    {"row": 2, "line": "20260901T1037Z\t432\t68.0", "at": "2026-09-01T10:37:00Z"},
]


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, env=ENV, capture_output=True, text=True, check=True, timeout=60
    )
    return done.stdout


def leg(clone: Path, run_id: str) -> None:
    """A leg line as the fleet's collect writes it, committed and pushed."""
    line = {"kind": "leg", "key": run_id, "run_id": run_id, "at": "2026-09-26T08:00:00Z"}
    with (clone / MONTH).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line) + "\n")
    git(clone, "add", MONTH)
    git(clone, "commit", "-q", "-m", f"Leg {run_id}")
    git(clone, "push", "-q", "origin", "main")


def clones(tmp_path: Path) -> tuple[Path, Path]:
    """The fleet's origin with its ledger script and one leg line, and two clones on main."""
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    theirs, ours = tmp_path / "theirs", tmp_path / "ours"
    for clone in (theirs, ours):
        git(tmp_path, "clone", "-q", str(origin), str(clone))
        git(clone, "config", "user.email", "test@example.org")
        git(clone, "config", "user.name", "test")
    git(theirs, "symbolic-ref", "HEAD", "refs/heads/main")
    (theirs / "scripts").mkdir()
    (theirs / "scripts/ledger.py").write_text(STAND_IN, encoding="utf-8")
    (theirs / "ledger").mkdir()
    git(theirs, "add", "scripts")
    leg(theirs, "11")
    git(ours, "fetch", "-q", "origin")
    git(ours, "checkout", "-q", "-B", "main", "origin/main")
    return theirs, ours


def push(ours: Path, tmp_path: Path) -> subprocess.CompletedProcess:
    # Run from a directory with no drain in it, so the lead replay finds nothing to write.
    return subprocess.run(
        ["bash", str(SCRIPT), str(ours), "20260926T0900Z"],
        cwd=tmp_path,
        env={**ENV, "TMPDIR": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=300,
    )


def on_origin(theirs: Path) -> list[dict]:
    git(theirs, "pull", "-q", "origin", "main")
    return [json.loads(text) for text in (theirs / MONTH).read_text().splitlines()]


def test_a_push_that_lands_carries_the_ledger_lines(tmp_path):
    theirs, ours = clones(tmp_path)
    assert fleet_ledger.append(ours, "legacy", LEGACY)[0]
    assert push(ours, tmp_path).returncode == 0
    lines = on_origin(theirs)
    assert [line["row"] for line in lines if line["kind"] == "legacy"] == [1, 2]


def test_a_rejected_push_replays_the_clones_ledger_lines_after_the_reset(tmp_path):
    theirs, ours = clones(tmp_path)
    assert fleet_ledger.append(ours, "legacy", LEGACY)[0]
    leg(theirs, "12")  # a collect lands first, so the laptop's push is rejected
    done = push(ours, tmp_path)
    assert "rejected on attempt 1" in done.stdout, done.stdout + done.stderr
    assert "NOT PUSHED" not in done.stdout
    lines = on_origin(theirs)
    assert [line["run_id"] for line in lines if line["kind"] == "leg"] == ["11", "12"]
    assert [line["row"] for line in lines if line["kind"] == "legacy"] == [1, 2]
