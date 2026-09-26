"""Approvals reach Ivo as one issue and one mergeable pull request, or not at all."""

from __future__ import annotations

import json
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


def register_text(*blocks: str) -> str:
    return "# Approvals\n\n" + "\n".join(blocks)


def register(tmp_path: Path, *blocks: str) -> Path:
    path = tmp_path / "approved-sources-list.md"
    path.write_text(register_text(*blocks), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _register(monkeypatch, tmp_path):
    monkeypatch.setattr(sa, "REGISTER", register(tmp_path, TERMS, NOT_INGESTED, SMALL, DECIDED))


def test_a_terms_question_is_filed() -> None:
    """Terms are condition 3: a judgement only Ivo makes, so it earns his attention."""
    names = [r.source for r in sa.requests(floor=5_000)]
    assert names == ["hostlist"]


def test_work_is_not_an_approval() -> None:
    """Condition 4 is a missing ingest. Its block says conditions 1 to 3 HOLD, so reading
    condition numbers from the whole block would file it as a terms question. It needs a
    collector, not a decision.
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
    before = sa.REGISTER.read_text(encoding="utf-8")
    after = sa.approve_line(request, before)
    assert after.count("Decision: master") == before.count("Decision: master") + 1
    assert after.count("Decision: pending") == before.count("Decision: pending") - 1
    changed = [
        (a, b) for a, b in zip(before.splitlines(), after.splitlines(), strict=True) if a != b
    ]
    assert changed == [("Decision: pending", "Decision: master")]


def test_a_block_live_does_not_hold_yet_is_filed_on_a_later_run(monkeypatch, capsys) -> None:
    """A bank writes a block and runs this before it pushes. The approval branch starts from
    live, so until live holds the block there is no one line to flip: no branch, no issue.
    """
    calls = []

    def fake_gh(args, check=True):
        calls.append(args)
        return "[]"

    monkeypatch.setattr(sa, "gh", fake_gh)
    monkeypatch.setattr(sa, "live_register", lambda: register_text(DECIDED))
    monkeypatch.setattr(sa.subprocess, "run", lambda *a, **k: pytest.fail(f"ran {a}"))
    assert sa.main([]) == 0
    assert "not on live yet: Approve hostlist? 40,000 EE" in capsys.readouterr().out
    assert not [args for args in calls if args[:2] in (["pr", "create"], ["issue", "create"])]


def test_a_block_as_request_approval_writes_it_is_filed() -> None:
    """`just approve` writes the potential among the head lines, then tables and reasons
    before the decision; the figure is still read, so the block reaches an issue."""
    block = """### sampled / artifact_listing
- ingest spec: `sampled`
- source: https://example.org/list
- journal: `data/raw/sampled/items.jsonl`
- potential: 12345

| class | net-new | EE |
|---|---|---|
| master | 9,000 | **12,345.0** |

- reasons: the terms page names no licence

Decision: pending
"""
    sa.REGISTER.write_text(register_text(block), encoding="utf-8")
    (request,) = sa.requests(floor=5_000)
    assert (request.source, request.potential) == ("sampled", 12345.0)
    assert request.failed == "not stated in the block"


def test_the_branch_name_is_stable_per_source() -> None:
    request = next(r for r in sa.requests(floor=5_000))
    assert request.branch == "approve/hostlist"
    assert request.title == "Approve hostlist? 40,000 EE"


def test_the_dry_run_names_the_label_on_every_issue_it_would_file(monkeypatch, capsys) -> None:
    """A dry run asks gh nothing, and each issue it would file says the label it carries."""

    def no_gh(args, check=True):
        raise AssertionError(f"a dry run called gh {args}")

    monkeypatch.setattr(sa, "gh", no_gh)
    assert sa.main(["--dry-run", "--floor", "100"]) == 0
    filed = [line for line in capsys.readouterr().out.splitlines() if "would file" in line]
    assert filed == [
        "issue: would file, labelled needs-owner: Approve hostlist? 40,000 EE",
        "issue: would file, labelled needs-owner: Approve tinylist? 900 EE",
    ]


def test_the_issue_is_filed_under_needs_owner(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(sa, "gh", lambda args, check=True: calls.append(args) or "issue #4")
    request = next(r for r in sa.requests(floor=5_000))
    sa.raise_issue(request, "https://example.org/pull/1", dry_run=False)
    (args,) = calls
    assert args[:2] == ["issue", "create"]
    label = args.index("--label")
    assert args[label : label + 2] == ["--label", "needs-owner"]


def test_only_its_own_titles_are_closed_under_the_shared_label(monkeypatch) -> None:
    """Other asks carry `needs-owner` too. One whose title begins like an approval and names
    a decided source stays open: only a title this script writes is its to close.
    """
    listed = [
        {"number": 3, "title": "Approve donelist? 50,000 EE"},
        {"number": 5, "title": "Approve hostlist? 40,000 EE"},
        {"number": 8, "title": "Approve donelist? The terms page names no licence"},
        {"number": 9, "title": "Rules: asks carry needs-owner"},
    ]
    calls = []

    def fake_gh(args, check=True):
        calls.append(args)
        if args[:2] == ["pr", "list"]:
            return json.dumps([{"number": 11, "headRefName": "approve/hostlist"}])
        if args[:2] == ["issue", "list"]:
            return json.dumps(listed)
        return ""

    monkeypatch.setattr(sa, "gh", fake_gh)
    assert sa.main([]) == 0
    listing = next(args for args in calls if args[:2] == ["issue", "list"])
    label = listing.index("--label")
    assert listing[label : label + 2] == ["--label", "needs-owner"]
    closed = [args[2] for args in calls if args[:2] == ["issue", "close"]]
    assert closed == ["3"]
    assert not [args for args in calls if args[:2] == ["issue", "create"]]
