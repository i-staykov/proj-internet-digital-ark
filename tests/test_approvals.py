"""The approvals gate: what may date a year, and who decided.

`tests/conftest.py` stubs the gate everywhere else, so this is the only place it is
exercised. The property is not "the agent recorded a decision" but "an undecided
master-eligible source cannot be ingested".
"""

import pytest

from ark.approvals import NotApproved, check, pending


def _file(tmp_path, body: str):
    path = tmp_path / "approved-sources-list.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_candidate_only_evidence_needs_no_approval(tmp_path) -> None:
    """A candidate claims nothing, so gating it would stall collection for no gain."""
    empty = _file(tmp_path, "")
    check("anything_at_all", "link_target", empty)  # must not raise


def test_an_unknown_master_class_is_refused(tmp_path) -> None:
    empty = _file(tmp_path, "")
    with pytest.raises(NotApproved, match="has no entry"):
        check("brand_new_source", "artifact_listing", empty)


def test_pending_is_refused_and_says_nothing_is_lost(tmp_path) -> None:
    path = _file(tmp_path, "### some_source / artifact_listing\n\nDecision: pending\n")
    with pytest.raises(NotApproved, match="awaiting classification"):
        check("some_source", "artifact_listing", path)


def test_master_passes(tmp_path) -> None:
    path = _file(tmp_path, "### some_source / cdx_timestamp\n\nDecision: master\n")
    check("some_source", "cdx_timestamp", path)  # must not raise


def test_rejected_binds(tmp_path) -> None:
    """A rejection has to be enforced, or the agent re-proposes it next week."""
    path = _file(tmp_path, "### dead_source / dated_directory\n\nDecision: rejected\n")
    with pytest.raises(NotApproved, match="REJECTED"):
        check("dead_source", "dated_directory", path)


def test_candidate_only_approval_refuses_a_master_spec(tmp_path) -> None:
    """Approving a source as candidate-only must not let a master spec through. This is the
    case that silently promotes: the reviewer said "keep it, but it may not date a year",
    and a master evidence type for the same source ignores that.
    """
    path = _file(tmp_path, "### halfway / artifact_listing\n\nDecision: candidate-only\n")
    with pytest.raises(NotApproved, match="candidate-only"):
        check("halfway", "artifact_listing", path)


def test_an_unparseable_decision_is_treated_as_no_decision(tmp_path) -> None:
    """Fail closed. A typo in the decision word must not read as approval."""
    path = _file(tmp_path, "### some_source / artifact_listing\n\nDecision: maybe-ok\n")
    with pytest.raises(NotApproved, match="has no entry"):
        check("some_source", "artifact_listing", path)


def test_pending_is_listed_for_the_state_document(tmp_path) -> None:
    path = _file(
        tmp_path,
        "### a / artifact_listing\n\nDecision: master\n\n"
        "### b / dated_directory\n\nDecision: pending\n\n"
        "### c / cdx_timestamp\n\nDecision: pending\n",
    )
    assert [p.source_name for p in pending(path)] == ["b", "c"]


def test_a_triage_entry_is_pending_but_marked_as_triage(tmp_path) -> None:
    """The gate treats it like any other pending class; only the reporting differs. A source
    found and not yet priced carries no sample and no figure, so it cannot be decided in two
    minutes, and the distinction must be machine-readable: the alternative is one entry per
    source on the surface Ivo reads, which stops being read once it stops fitting a screen.
    """
    from ark.approvals import load

    doc = tmp_path / "approved-sources-list.md"
    doc.write_text(
        "# x\n\n"
        "## Pending requests\n\n"
        "### priced_thing / artifact_listing\n\n"
        "Decision: pending\n\n"
        "## Found, awaiting triage\n\n"
        "### found_thing / whois_creation\n\n"
        "Decision: pending\n",
        encoding="utf-8",
    )
    found = load(doc)
    assert found[("priced_thing", "artifact_listing")].is_triage is False
    assert found[("found_thing", "whois_creation")].is_triage is True
    assert all(a.decision == "pending" for a in found.values())


def test_a_section_heading_ends_an_unfinished_request_block(tmp_path) -> None:
    """A malformed entry must not swallow the next section's Decision line: an entry whose
    `Decision:` line was forgotten would adopt whatever came next, which is the one
    failure mode a gate must not have, because it reads as approved.
    """
    from ark.approvals import load

    doc = tmp_path / "approved-sources-list.md"
    doc.write_text(
        "# x\n\n"
        "## Pending requests\n\n"
        "### forgot_its_decision / artifact_listing\n\n"
        "some prose and no Decision line\n\n"
        "## Approved before this mechanism existed\n\n"
        "### legitimately_approved / artifact_listing\n\n"
        "Decision: master\n",
        encoding="utf-8",
    )
    found = load(doc)
    assert ("forgot_its_decision", "artifact_listing") not in found
    assert found[("legitimately_approved", "artifact_listing")].decision == "master"
