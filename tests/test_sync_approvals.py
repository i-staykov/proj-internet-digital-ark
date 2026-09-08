"""Approvals reach Ivo as one issue and one mergeable pull request, or not at all."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/harness"))

import sync_approvals as sa  # noqa: E402

TERMS = """### hostlist / artifact_listing

- measured 40,000 EE net-new
- **condition 3 of the standing rule fails: the terms are not held.**
- potential: 40000

Decision: pending
"""

NOT_INGESTED = """### bigcorpus / cdx_timestamp

- **condition 4 of the standing rule cannot be evaluated: nothing has been ingested.**
  Conditions 1 to 3 hold (approved class, machine stamp, terms read).
- potential: 88700

Decision: pending
"""

SMALL = """### tinylist / artifact_listing

- **condition 1 of the standing rule fails: no master-eligible class covers it.**
- potential: 900

Decision: pending
"""

DECIDED = """### donelist / artifact_listing

- potential: 50000

Decision: master
"""


def register(tmp_path: Path, *blocks: str) -> Path:
    path = tmp_path / "approved-sources-list.md"
    path.write_text("# Approvals\n\n" + "\n".join(blocks), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _register(monkeypatch, tmp_path):
    monkeypatch.setattr(sa, "REGISTER", register(tmp_path, TERMS, NOT_INGESTED, SMALL, DECIDED))


def test_a_terms_question_is_filed() -> None:
    """Terms are condition 3: a judgement only Ivo makes, so it earns his attention."""
    names = [r.source for r in sa.requests(floor=5_000)]
    assert names == ["hostlist"]


def test_work_is_not_an_approval() -> None:
    """Condition 4 is a missing ingest.

    Its block says conditions 1 to 3 HOLD, so reading condition numbers from the whole block
    would file it as a terms question. It needs a collector, not a decision.
    """
    assert sa.failed_conditions(NOT_INGESTED) == {"4"}
    assert "bigcorpus" not in [r.source for r in sa.requests(floor=1_000)]


def test_below_the_bar_nothing_is_filed() -> None:
    """Four issues sat unread at four figures and were closed on the bar (Ivo, 2026-09-08)."""
    assert "tinylist" not in [r.source for r in sa.requests(floor=5_000)]
    assert "tinylist" in [r.source for r in sa.requests(floor=100)]


def test_a_decided_source_is_not_a_request() -> None:
    assert "donelist" not in [r.source for r in sa.requests(floor=100)]


def test_the_pull_request_flips_exactly_one_line() -> None:
    """The merge IS the approval, so it must change the decision and nothing else."""
    request = next(r for r in sa.requests(floor=5_000))
    after = sa.approve_line(request)
    before = sa.REGISTER.read_text(encoding="utf-8")
    assert after.count("Decision: master") == before.count("Decision: master") + 1
    assert after.count("Decision: pending") == before.count("Decision: pending") - 1
    changed = [
        (a, b) for a, b in zip(before.splitlines(), after.splitlines(), strict=True) if a != b
    ]
    assert changed == [("Decision: pending", "Decision: master")]


def test_the_branch_name_is_stable_per_source() -> None:
    request = next(r for r in sa.requests(floor=5_000))
    assert request.branch == "approve/hostlist"
    assert request.title == "Approve hostlist? 40,000 EE"
