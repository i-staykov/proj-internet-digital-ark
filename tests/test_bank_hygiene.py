"""The bank refuses a clone it must not write in, prunes only verified copies, and gates once."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from ark.baseline import CURRENT_BASELINE_MARKER

_SPEC = importlib.util.spec_from_file_location(
    "bank_hygiene", Path(__file__).resolve().parents[1] / "scripts/harness/bank_hygiene.py"
)
hyg = importlib.util.module_from_spec(_SPEC)
sys.modules["bank_hygiene"] = hyg
_SPEC.loader.exec_module(hyg)
_ENV = hyg.clean_env()  # a hook's GIT_INDEX_FILE would stage these fixture clones into ours
BRIEF = {"field5_percent": "5.010400", "gate_pct": 5.0, "round": "8", "baseline": "m1"}


def _git(cwd: Path, *args: str) -> str:
    who = ["-c", "user.name=t", "-c", "user.email=t@example.org"]
    kw = {"cwd": cwd, "env": _ENV, "capture_output": True, "text": True, "timeout": 60}
    return subprocess.run(["git", *who, *args], check=True, **kw).stdout.strip()


@pytest.mark.parametrize(
    "files,commit,code,said,page",
    [
        ({}, False, 0, "fast-forwarded", "two\n"),
        ({"scratch.txt": "notes\n", "src/new.txt": "draft\n"}, False, 0,
         "untracked, not staged by the bank", "two\n"),
        ({"docs/registers/new.txt": "draft\n"}, False, 2, "docs/registers/new.txt", "one\n"),
        ({"src/page.txt": "mine\n"}, False, 2, "REFUSED: the clone is dirty", "mine\n"),
        ({"src/other.txt": "ours\n"}, True, 2, "diverged", "one\n"),
    ],
    ids=["clean", "untracked-warns", "untracked-staged-refuses", "dirty-refuses", "diverged"],
)  # fmt: skip
def test_only_a_clean_clone_is_pulled(tmp_path, monkeypatch, files, commit, code, said, page):
    """A refusal comes before the pull, and a hook's git variables never reach its git."""
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "nowhere"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "nowhere/index"))
    theirs, ours = tmp_path / "theirs", tmp_path / "ours"
    _git(tmp_path, "init", "-b", "live", "theirs")
    for text in ("one\n", "two\n"):
        for rel in ("src/page.txt", "docs/registers/page.txt"):
            (theirs / rel).parent.mkdir(parents=True, exist_ok=True)
            (theirs / rel).write_text(text, encoding="utf-8")
        _git(theirs, "add", ".")
        _git(theirs, "commit", "-m", text)
        if text == "one\n":
            _git(tmp_path, "clone", "theirs", "ours")
    for rel, text in files.items():
        (ours / rel).write_text(text, encoding="utf-8")
    if commit:
        _git(ours, "add", *files)
        _git(ours, "commit", "-m", "ours")
    head = _git(ours, "rev-parse", "HEAD")
    got, lines = hyg.preflight(root=ours)
    assert got == code and any(said in line for line in lines), lines
    assert said != "untracked, not staged by the bank" or sum(said in ln for ln in lines) == 2
    assert (ours / "src/page.txt").read_text(encoding="utf-8") == page
    assert (_git(ours, "rev-parse", "HEAD") != head) == (code == 0)


@pytest.mark.parametrize(
    "head,space,asked",
    [("main", 0, ["rev-parse"]), ("live", 2, ["rev-parse", "status"])],
    ids=["on-main", "low-space"],
)
def test_preflight_refuses_main_and_low_space_before_the_pull(monkeypatch, head, space, asked):
    monkeypatch.setattr(hyg, "space", lambda **kw: (space, ["REFUSED: low disk"]))
    calls = []
    run = lambda args, cwd: calls.append(args[0]) or (0, head if args[0] == "rev-parse" else "")  # noqa: E731
    code, lines = hyg.preflight(run=run)
    assert code == 2 and lines[-1].startswith("REFUSED") and calls == asked


@pytest.mark.parametrize(
    "setting,free,code",
    [(None, (69, 69), 2), (None, (70, 70), 0), (None, (71, 71), 0), (None, (100, 1), 2),
     *((value, (100, 100), 2) for value in ("0", "-1", "nan", "inf", "x"))],
    ids=["below-floor-and-budget", "at-floor-and-budget", "above", "output-full",
         "setting-0", "setting-negative", "setting-nan", "setting-inf", "setting-invalid"],
)  # fmt: skip
def test_space_is_floor_plus_budget_and_fails_closed(tmp_path, monkeypatch, setting, free, code):
    for name in ("ARK_FREE_SPACE_GIB", "ARK_WRITE_BUDGET_GIB"):
        monkeypatch.delenv(name, raising=False)
    if setting:
        monkeypatch.setenv("ARK_FREE_SPACE_GIB", setting)
    (tmp_path / "data").mkdir()
    (tmp_path / "output").mkdir()
    by_name = dict(zip(("data", "output"), free, strict=True))
    usage = lambda p: Mock(free=by_name[p.name] * hyg.GIB)  # noqa: E731
    monkeypatch.setattr(hyg.shutil, "disk_usage", usage)
    got, lines = hyg.space(root=tmp_path)
    assert got == code
    assert "REFUSED" in lines[0] if setting else "50 floor + 20.0 write budget" in lines[0]


def test_prune_takes_only_old_staging_with_a_verified_copy(tmp_path, monkeypatch) -> None:
    """Dry by default, age alone deletes nothing, and a second run changes nothing."""
    staging, was = tmp_path / "data/fleet_findings", time.time() - 30 * 86400
    (staging / "incoming/run_1").mkdir(parents=True)
    for rel in ("incoming/run_2", "banked/old", "banked/new"):
        (staging / rel).mkdir(parents=True)
        (staging / rel / "finding.md").write_text("f", encoding="utf-8")
    os.utime(staging / "banked/old", (was, was))
    tree = lambda: {p: p.is_file() and p.read_bytes() for p in tmp_path.rglob("*")}  # noqa: E731
    before = tree()
    for write in (False, True):
        lines = hyg.prune(root=tmp_path, days=14, write=write)
        assert any("banked/old" in s for s in lines) and any("HELD" in s for s in lines)
        assert tree() == before
    offsite, path = hyg.round_prune().sibling("offsite"), staging / "banked/old/finding.md"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    record = {"stat": offsite.signature(tmp_path, path), "kind": "sha256", "digest": digest}
    offsite.write_receipt(tmp_path, offsite.REMOTE, {str(path.relative_to(tmp_path)): record})
    listed = json.dumps({"Size": path.stat().st_size, "Hashes": {"sha256": digest}})
    monkeypatch.setattr(offsite, "rclone", lambda *a, **k: Mock(returncode=0, stdout=listed))
    hyg.prune(root=tmp_path, days=14, write=True)
    assert not (staging / "banked/old").exists() and (staging / "banked/new/finding.md").is_file()
    after, lines = tree(), hyg.prune(root=tmp_path, days=14, write=True)
    assert lines == ["staging directories: nothing to prune"] and tree() == after


@pytest.mark.parametrize(
    "brief,listed,said,asked",
    [
        ({"percent": 5.3597, "round_percent": 5.3597, "field5_percent": "0.252400"}, "",
         "at 0.252400%, gate at 5%: not crossed", 0),
        ({}, "12", "gate issue #12 is already open: latched, not re-notifying", 1),
        ({}, "", "opened the gate issue: Round 8 at 5.010400% against m1 (released 2026-09-02)"
         " at 14:03 UTC", 2),
    ],
    ids=["quotes-field-5-only", "open-issue-is-latched", "crossing-opens-one-issue"],
)  # fmt: skip
def test_the_gate_opens_one_issue_per_crossing(tmp_path, brief, listed, said, asked):
    """The second run of each is latched or not crossed, and asks `gh` nothing."""
    calls, now = [], datetime(2026, 9, 3, 14, 3, tzinfo=UTC)
    call = lambda args: calls.append(args) or (0, listed if args[1] == "list" else "issue #7")  # noqa: E731
    kw = {"released": "2026-09-02", "latch_path": tmp_path / "l.tsv", "now": now, "call": call}
    assert hyg.gate({**BRIEF, **brief}, write=True, **kw)[0] == said
    again = said if asked == 0 else "gate already notified against m1: nothing to do"
    assert hyg.gate({**BRIEF, **brief}, write=True, **kw) == [again] and len(calls) == asked
    labels = [args[args.index("--label") + 1] for args in calls if args[1] == "create"]
    assert labels == ["needs-owner"] * (asked == 2)


def test_a_brief_without_field_5_is_refused(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(hyg, "BRIEF", tmp_path / "brief.json")
    hyg.BRIEF.write_text(json.dumps({"percent": 5.5, "baseline": CURRENT_BASELINE_MARKER}))
    assert hyg._brief() is None and "no field5_percent" in capsys.readouterr().out
