"""The bank runs hourly and unwatched, so its hygiene has to be a program.

Three properties, each of which has cost something once: a clone that is dirty must
be refused **before** anything is fetched or written, a clone that has diverged must
be fast-forwarded rather than merged, and the gate issue must be opened once per
crossing rather than once per run. The fourth is the one that makes the other three
safe to schedule: two consecutive runs over unchanged state change nothing.

The git tests use real git in a temporary pair of clones, because what is under test
is exactly what git does with a dirty tree and a diverged branch.
"""

import hashlib
import importlib.util
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "bank_hygiene", Path(__file__).resolve().parent.parent / "scripts/harness/bank_hygiene.py"
)
hyg = importlib.util.module_from_spec(_SPEC)
sys.modules["bank_hygiene"] = hyg
_SPEC.loader.exec_module(hyg)


# Under the pre-commit hook, git exports GIT_INDEX_FILE for the real repository, and
# these fixture clones would stage into it. Same environment the tool itself uses.
_ENV = hyg.clean_env()


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=_ENV,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return done.stdout.strip()


def _clones(tmp_path: Path) -> tuple[Path, Path]:
    """A bare origin on `live` and two clones of it, the second being ours."""
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "live", str(origin)],
        check=True,
        capture_output=True,
        timeout=60,
        env=_ENV,
    )
    made = []
    for name in ("theirs", "ours"):
        path = tmp_path / name
        subprocess.run(
            ["git", "clone", str(origin), str(path)],
            check=True,
            capture_output=True,
            timeout=60,
            env=_ENV,
        )
        _git(path, "config", "user.email", "test@example.org")
        _git(path, "config", "user.name", "test")
        made.append(path)
    theirs, ours = made
    (theirs / "src").mkdir()
    (theirs / "src/page.txt").write_text("one\n", encoding="utf-8")
    _git(theirs, "add", "src/page.txt")
    _git(theirs, "commit", "-m", "one")
    _git(theirs, "push", "-u", "origin", "live")
    _git(ours, "pull", "origin", "live")
    return theirs, ours


def _snapshot(root: Path) -> dict[str, str]:
    out = {}
    for path in sorted(root.rglob("*")):
        key = str(path.relative_to(root))
        out[key] = "dir" if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def preflight_in(root: Path) -> tuple[int, list[str]]:
    return hyg.preflight(root=root, branch="live", remote="origin")


def _staging(root: Path, old_days: int = 30) -> None:
    """The directories a bank leaves behind: two run dirs and two banked labels."""
    (root / "data/fleet_findings/incoming/run_1").mkdir(parents=True)
    (root / "data/fleet_findings/incoming/run_2").mkdir(parents=True)
    (root / "data/fleet_findings/incoming/run_2/finding.md").write_text("f", encoding="utf-8")
    for label in ("old", "new"):
        (root / f"data/fleet_findings/banked/{label}").mkdir(parents=True)
        (root / f"data/fleet_findings/banked/{label}/finding.md").write_text("f", encoding="utf-8")
    was = time.time() - old_days * 86400
    os.utime(root / "data/fleet_findings/banked/old", (was, was))


def test_git_runs_free_of_a_hooks_environment(monkeypatch) -> None:
    """Inside a hook, an inherited GIT_INDEX_FILE points every git call at the real index."""
    monkeypatch.setenv("GIT_INDEX_FILE", "/nowhere/index")
    monkeypatch.setenv("GIT_DIR", "/nowhere/.git")
    env = hyg.clean_env()
    assert not any(key.startswith("GIT_") for key in env)
    assert "PATH" in env


def test_a_clean_clone_is_fast_forwarded(tmp_path: Path) -> None:
    """The merge from a phone lands here, and only as a fast-forward."""
    theirs, ours = _clones(tmp_path)
    (theirs / "src/page.txt").write_text("two\n", encoding="utf-8")
    _git(theirs, "commit", "-am", "two")
    _git(theirs, "push", "origin", "live")

    code, lines = preflight_in(ours)
    assert code == 0, lines
    assert any("fast-forwarded" in line for line in lines)
    assert (ours / "src/page.txt").read_text(encoding="utf-8") == "two\n"


def test_a_dirty_clone_is_refused_before_anything_is_fetched(tmp_path: Path) -> None:
    """The bank stages whole directories, so somebody's edit would be committed by it."""
    theirs, ours = _clones(tmp_path)
    head = _git(ours, "rev-parse", "HEAD")
    (theirs / "src/page.txt").write_text("two\n", encoding="utf-8")
    _git(theirs, "commit", "-am", "two")
    _git(theirs, "push", "origin", "live")
    (ours / "src/page.txt").write_text("mine\n", encoding="utf-8")

    code, lines = preflight_in(ours)
    assert code == 2
    assert any("REFUSED: the clone is dirty" in line for line in lines)
    # The refusal came before the pull: HEAD did not move and the edit survives.
    assert _git(ours, "rev-parse", "HEAD") == head
    assert (ours / "src/page.txt").read_text(encoding="utf-8") == "mine\n"


def test_an_untracked_file_is_fatal_only_where_the_bank_stages_by_directory(
    tmp_path: Path,
) -> None:
    """`git add docs/` is how a 1.3 GB copy once reached history; a scratch file is not."""
    _, ours = _clones(tmp_path)
    (ours / "scratch.txt").write_text("notes\n", encoding="utf-8")
    code, lines = preflight_in(ours)
    assert code == 0
    assert any("untracked, not staged by the bank" in line for line in lines)

    (ours / "src/new.txt").write_text("draft\n", encoding="utf-8")
    code, lines = preflight_in(ours)
    assert code == 2
    assert any("src/new.txt" in line for line in lines)


def test_a_diverged_clone_is_refused_rather_than_merged(tmp_path: Path) -> None:
    """A merge commit made unattended is a history nobody chose."""
    theirs, ours = _clones(tmp_path)
    (theirs / "src/page.txt").write_text("theirs\n", encoding="utf-8")
    _git(theirs, "commit", "-am", "theirs")
    _git(theirs, "push", "origin", "live")
    (ours / "src/other.txt").write_text("ours\n", encoding="utf-8")
    _git(ours, "add", "src/other.txt")
    _git(ours, "commit", "-m", "ours")

    code, lines = preflight_in(ours)
    assert code == 2
    assert any("diverged" in line for line in lines)


def test_it_refuses_to_run_on_main() -> None:
    """`main` is reached by a pull request and is never pushed by an agent."""
    calls = []

    def run(args, _cwd):
        calls.append(args[0])
        return 0, "main"

    code, lines = hyg.preflight(run=run)
    assert code == 2
    assert "main" in lines[0]
    assert calls == ["rev-parse"]  # nothing else was asked


def test_prune_lists_before_it_deletes(tmp_path: Path) -> None:
    """Same idiom as the rest of the round tools: dry by default, `--write` acts."""
    _staging(tmp_path)
    before = _snapshot(tmp_path)
    lines = hyg.prune(root=tmp_path, days=14)
    assert any("run_1" in line for line in lines)
    assert any("banked/old" in line for line in lines)
    assert _snapshot(tmp_path) == before


def test_prune_removes_the_spent_staging_directories_only(tmp_path: Path) -> None:
    """An empty run directory holds nothing; a fresh banked label is still readable."""
    _staging(tmp_path)
    hyg.prune(root=tmp_path, days=14, write=True)
    assert not (tmp_path / "data/fleet_findings/incoming/run_1").exists()
    assert (tmp_path / "data/fleet_findings/incoming/run_2/finding.md").is_file()
    assert not (tmp_path / "data/fleet_findings/banked/old").exists()
    assert (tmp_path / "data/fleet_findings/banked/new/finding.md").is_file()


def test_the_gate_does_nothing_below_the_threshold(tmp_path: Path) -> None:
    calls = []
    lines = hyg.gate(
        {"percent": 4.9312, "gate_pct": 5.0, "round": "8", "baseline": "m1"},
        latch_path=tmp_path / "latch.tsv",
        call=lambda args: calls.append(args) or (0, ""),
        write=True,
    )
    assert calls == []
    assert "not crossed" in lines[0]


def test_the_gate_issue_is_opened_once_per_crossing(tmp_path: Path) -> None:
    """Opened once it is information. Opened hourly it is noise, and gets muted."""
    brief = {"percent": 5.0104, "gate_pct": 5.0, "round": "8", "baseline": "m1"}
    latch = tmp_path / "latch.tsv"
    calls = []

    def call(args):
        calls.append(args)
        return 0, "" if args[0] == "issue" and args[1] == "list" else "issue #7"

    now = datetime(2026, 9, 3, 14, 3, tzinfo=UTC)
    first = hyg.gate(brief, released="2026-09-02", latch_path=latch, now=now, call=call, write=True)
    assert "opened the gate issue" in first[0]
    assert "Round 8 at 5.0104% against m1 (released 2026-09-02) at 14:03 UTC" in first[0]
    created = [args for args in calls if args[:2] == ["issue", "create"]]
    assert len(created) == 1

    second = hyg.gate(
        brief, released="2026-09-02", latch_path=latch, now=now, call=call, write=True
    )
    assert "already notified" in second[0]
    assert [args for args in calls if args[:2] == ["issue", "create"]] == created
    assert latch.read_text(encoding="utf-8").count("\n") == 1


def test_an_issue_already_open_is_latched_rather_than_duplicated(tmp_path: Path) -> None:
    """The ledger cannot see an issue somebody opened by hand, so the query is asked too."""
    calls = []
    lines = hyg.gate(
        {"percent": 5.5, "gate_pct": 5.0, "round": "8", "baseline": "m1"},
        latch_path=tmp_path / "latch.tsv",
        call=lambda args: calls.append(args) or (0, "12"),
        write=True,
    )
    assert "#12 is already open" in lines[0]
    assert [args for args in calls if args[:2] == ["issue", "create"]] == []


def test_two_consecutive_banks_with_no_new_data_change_nothing(tmp_path: Path) -> None:
    """E7.5's acceptance, asserted on the tree and on the calls at once.

    The first run is the one that acts: it prunes what is spent and opens the gate
    issue. The second is given exactly the same state, and both the digest of every
    path under the root and the list of `gh` calls must come back unchanged.
    """
    _staging(tmp_path)
    latch = tmp_path / "data/logs/gate_notified.tsv"
    brief = {"percent": 5.0104, "gate_pct": 5.0, "round": "8", "baseline": "m1"}
    calls = []

    def call(args):
        calls.append(args)
        return 0, "" if args[1] == "list" else "issue #7"

    hyg.prune(root=tmp_path, days=14, write=True)
    hyg.gate(brief, latch_path=latch, call=call, write=True)
    after_first = _snapshot(tmp_path)
    calls_after_first = list(calls)

    lines = hyg.prune(root=tmp_path, days=14, write=True)
    hyg.gate(brief, latch_path=latch, call=call, write=True)

    assert lines == ["staging directories: nothing to prune"]
    assert _snapshot(tmp_path) == after_first
    assert calls == calls_after_first  # the second gate asked gh nothing at all
