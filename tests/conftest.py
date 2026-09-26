"""Shared fixtures.

The approvals gate is relaxed here because unit tests build specs with invented source
names. `tests/test_approvals.py` is where the gate itself is exercised.
"""

import pytest

from ark import approvals, db


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
def _scratch_fleet_ledger(tmp_path, monkeypatch):
    """The fleet ledger is the real spend record, so a drain under test writes a scratch one."""
    monkeypatch.setenv("ARK_FLEET_LEDGER", str(tmp_path / "fleet_ledger.tsv"))


@pytest.fixture(autouse=True, scope="session")
def _db_threads_for_tiny_stores():
    """Tests build tiny in-memory stores; the store's two-thread cap would only slow them."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(db, "DB_THREADS", "8")
        yield
