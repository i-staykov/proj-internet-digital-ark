"""Shared fixtures, and `script`, which loads a script under `scripts/` as a module.

The approvals gate is relaxed here because unit tests build specs with invented source
names. `tests/test_standing_rule.py` is where the gate itself is exercised.
"""

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

from ark import approvals, db, held

ROOT = Path(__file__).resolve().parents[1]


def script(rel: str, name: str = ""):
    """`scripts/<rel>` loaded afresh, in `sys.modules` as `name` if given: a dataclass reads it."""
    spec = importlib.util.spec_from_file_location(name or Path(rel).stem, ROOT / "scripts" / rel)
    module = importlib.util.module_from_spec(spec)
    if name:
        sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _permissive_approvals(tmp_path, monkeypatch):
    """Approve every class, so a unit test is not gated on a human decision."""
    path = tmp_path / "approvals.md"
    path.write_text("", encoding="utf-8")
    monkeypatch.setattr(approvals, "DEFAULT_APPROVALS_PATH", path)
    # An empty file means "no entry", which the gate treats as unapproved, so the
    # check is stubbed rather than fed a file listing every invented test name.
    monkeypatch.setattr(approvals, "check", lambda *a, **k: None)
    return path


@pytest.fixture(autouse=True)
def _held_stays_in_tmp(tmp_path, monkeypatch):
    """No test writes the live `data/held/`, and `held` never finds his real release: a test
    that wants his files stages them and passes the folder."""
    monkeypatch.setattr(held, "HELD_ROOT", tmp_path / "held")
    monkeypatch.setattr(held, "his_dir", lambda: tmp_path / "no-release-here")
    # a store's spill and the readers' scratch, which would otherwise land in the live data/
    monkeypatch.setattr(db, "DB_TEMP_DIR", str(tmp_path / "duckdb_tmp"))
    monkeypatch.setattr(held, "DB_TEMP_DIR", str(tmp_path / "duckdb_tmp"))


@pytest.fixture(scope="session")
def _prepared_release(tmp_path_factory):
    """His release from `tests/his_release.py`, staged and prepared once per session."""
    from his_release import stage

    root = tmp_path_factory.mktemp("his")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(held, "HELD_ROOT", root / "held")
        patch.setattr(held, "DB_TEMP_DIR", str(root / "duckdb_tmp"))
        held.prepare(stage(root / "release"))
    return root


@pytest.fixture
def his_files(_prepared_release, _held_stays_in_tmp, tmp_path, monkeypatch):
    """His release, prepared, where `held` looks for it: the session's, copied with its stamps.
    A test that rewrites a file of his calls `held.prepare(his_files)` again before reading."""
    from his_release import MARKER

    for tree in ("release", "held"):
        shutil.copytree(_prepared_release / tree, tmp_path / tree, dirs_exist_ok=True)
    folder = tmp_path / "release" / MARKER
    monkeypatch.setattr(held, "his_dir", lambda: folder)
    held.load(folder)
    return folder


@pytest.fixture(autouse=True, scope="session")
def _db_threads_for_tiny_stores():
    """Tests build tiny in-memory stores; the store's two-thread cap would only slow them."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(db, "DB_THREADS", "8")
        yield
