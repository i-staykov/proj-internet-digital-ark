"""Shared fixtures.

**Why the approvals gate is relaxed here, and how it stays tested.** `ingest_files`
refuses any master-eligible source whose class a human has not classified in
`docs/open-approvals.md`. Unit tests build specs with invented source names, so
without this they would all be refused, and the honest options are to relax the gate
for unit tests or to bypass it in production code. Relaxing it here is the safer of
the two, and the gate itself is covered directly in `tests/test_approvals.py`,
including that it refuses an unapproved ingest.
"""

import pytest

from ark import approvals


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
