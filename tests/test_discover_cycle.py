"""The approvals the cycle files for the owner: an ask filed twice or not at all is a decision
lost."""

import json

import pytest
from conftest import script

sa = script("harness/sync_approvals.py", "sync_approvals")


TERMS = "### hostlist / artifact_listing\n- potential: 40000\n"
TERMS += (
    "- **condition 3 of the standing rule fails: the terms are not held.**\nDecision: pending\n"
)
DECIDED = "### donelist / artifact_listing\n- potential: 50000\nDecision: master\n"
PR, TITLE = {"number": 11, "headRefName": "approve/hostlist"}, "Approve hostlist? 40,000 EE"


def register(monkeypatch, tmp_path, *blocks: str) -> str:
    text = "# Approvals\n\n" + "\n".join(blocks)
    (path := tmp_path / "approved-sources-list.md").write_text(text)
    monkeypatch.setattr(sa, "REGISTER", path)
    return text


def fake_gh(monkeypatch, prs=(), issues=()) -> list[list[str]]:
    calls = []

    def gh(args, check=True):
        calls.append(args)
        listed = {"pr list": prs, "issue list": issues}.get(" ".join(args[:2]))
        return json.dumps(list(listed)) if listed is not None else "#1"

    monkeypatch.setattr(sa, "gh", gh)
    return calls


def test_an_ask_is_one_needs_owner_issue_and_a_one_line_pr(monkeypatch, tmp_path, capsys):
    before = register(monkeypatch, tmp_path, TERMS, DECIDED)
    (request,) = sa.requests()
    after = sa.approve_line(request, before).splitlines()
    changed = [(a, b) for a, b in zip(before.splitlines(), after, strict=True) if a != b]
    assert changed == [("Decision: pending", "Decision: master")]
    # Under the gate nothing is filed and the line says how far the asks together stand.
    calls = fake_gh(monkeypatch, prs=[PR])
    monkeypatch.setattr(sa, "GATE", 40_001.0)
    assert sa.main([]) == 0 and "1 asks, 40,000 of 40,001 EE to the gate" in capsys.readouterr().out
    assert not [args for args in calls if args[:2] == ["issue", "create"]]
    monkeypatch.setattr(sa, "GATE", 40_000.0)
    calls = fake_gh(monkeypatch, prs=[PR])
    assert sa.main([]) == 0
    (filed,) = [args for args in calls if args[:2] == ["issue", "create"]]
    assert (filed[filed.index("--label") + 1], filed[filed.index("--title") + 1]) == (
        "needs-owner",
        TITLE,
    )
    body = filed[filed.index("--body") + 1]
    assert f"Blocked on: {request.failed}\n" in body and "Merge 11" in body
    # Re-priced since its issue was filed, the ask is found by its source and not filed again.
    calls = fake_gh(monkeypatch, issues=[{"number": 5, "title": "Approve hostlist? 38,500 EE"}])
    assert sa.main([]) == 0 and "open already: Approve hostlist? 38,500" in capsys.readouterr().out
    # Until live holds the block there is no one line to flip: no branch, no issue.
    calls = fake_gh(monkeypatch)
    monkeypatch.setattr(sa, "live_register", lambda: "# Approvals\n\n" + DECIDED)
    monkeypatch.setattr(sa.subprocess, "run", lambda *a, **k: pytest.fail(f"ran {a}"))
    assert sa.main([]) == 0 and f"not on live yet: {TITLE}" in capsys.readouterr().out
    assert not [args for args in calls if args[:2] in (["pr", "create"], ["issue", "create"])]
    # A dry run asks gh nothing and names the label the issue would carry.
    monkeypatch.setattr(sa, "gh", lambda args, check=True: pytest.fail(f"a dry run ran gh {args}"))
    assert sa.main(["--dry-run"]) == 0
    assert f"issue: would file, labelled needs-owner: {TITLE}" in capsys.readouterr().out
