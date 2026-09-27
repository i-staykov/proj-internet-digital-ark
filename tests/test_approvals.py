"""The real approvals gate, stubbed by conftest for every other test: a master-eligible source
ingests only once its class is decided master."""

import pytest

from ark.approvals import NotApproved, check, load, pending


def _file(tmp_path, body: str):
    path = tmp_path / "approved-sources-list.md"
    path.write_text(body, encoding="utf-8")
    return path


def _entry(source: str, kind: str, decision: str) -> str:
    return f"### {source} / {kind}\n\nDecision: {decision}\n\n"


@pytest.mark.parametrize(
    ("body", "kind"),
    [("", "link_target"), (_entry("some_source", "cdx_timestamp", "master"), "cdx_timestamp")],
    ids=["candidate-evidence-needs-no-entry", "master"],
)
def test_candidate_evidence_and_a_master_decision_pass(tmp_path, body, kind) -> None:
    """A candidate claims no year, so it is never gated; a master decision lets a class date one."""
    check("some_source", kind, _file(tmp_path, body))  # must not raise


@pytest.mark.parametrize(
    ("decision", "said"),
    [
        (None, "has no entry"),
        ("pending", "awaiting classification"),
        ("rejected", "REJECTED"),
        ("candidate-only", "candidate-only"),
        ("maybe-ok", "has no entry"),
    ],
    ids=["unknown", "pending", "rejected", "candidate-only", "unparseable-fails-closed"],
)
def test_a_master_spec_without_a_master_decision_is_refused(tmp_path, decision, said) -> None:
    """No entry, pending, rejected, candidate-only or a mistyped decision refuses a master spec."""
    body = _entry("some_source", "artifact_listing", decision) if decision else ""
    with pytest.raises(NotApproved, match=said):
        check("some_source", "artifact_listing", _file(tmp_path, body))


def test_pending_is_listed_for_the_state_document(tmp_path) -> None:
    body = (
        _entry("a", "artifact_listing", "master")
        + _entry("b", "dated_directory", "pending")
        + _entry("c", "cdx_timestamp", "pending")
    )
    assert [p.source_name for p in pending(_file(tmp_path, body))] == ["b", "c"]


def test_a_triage_entry_is_pending_but_marked_as_triage(tmp_path) -> None:
    """The gate treats a found, unpriced source like any pending class; only its flag differs."""
    body = (
        "# x\n\n## Pending requests\n\n"
        + _entry("priced_thing", "artifact_listing", "pending")
        + "## Found, awaiting triage\n\n"
        + _entry("found_thing", "whois_creation", "pending")
    )
    found = load(_file(tmp_path, body))
    assert found[("priced_thing", "artifact_listing")].is_triage is False
    assert found[("found_thing", "whois_creation")].is_triage is True
    assert all(a.decision == "pending" for a in found.values())


def test_a_section_heading_ends_an_unfinished_request_block(tmp_path) -> None:
    """An entry missing its Decision line never adopts the next section's, which reads approved."""
    body = (
        "# x\n\n## Pending requests\n\n"
        "### forgot_its_decision / artifact_listing\n\nsome prose and no Decision line\n\n"
        "## Approved before this mechanism existed\n\n"
        + _entry("legitimately_approved", "artifact_listing", "master")
    )
    found = load(_file(tmp_path, body))
    assert ("forgot_its_decision", "artifact_listing") not in found
    assert found[("legitimately_approved", "artifact_listing")].decision == "master"
