"""The approvals gate: what may date a year, and who decided.

`tests/conftest.py` stubs the gate for every other test, because unit tests build
specs with invented source names and would otherwise all be refused. **So this file
is the only place the gate is actually exercised**, and it tests the gate rather than
the convention: each case calls `check` with its own fixture file.

The property under test is not "the agent recorded a decision" but "an undecided
master-eligible source cannot be ingested". The agent's reasoning is exactly what is
being distrusted, so the enforcement has to live in code.
"""

from pathlib import Path

import pytest

from ark.approvals import NotApproved, check, load, pending


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
    """Approving a source as candidate-only must not let a master spec through.

    This is the case that would otherwise silently promote: the reviewer said "keep
    it, but it may not date a year", and a spec carrying a master evidence type for
    the same source would ignore that.
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


def test_the_real_file_covers_every_master_class_the_specs_can_produce() -> None:
    """A spec with no entry cannot be ingested, so an unlisted one is a latent stop.

    This runs against the live `docs/approved-sources-list.md` on purpose: adding a source
    without classifying it should fail here rather than at 3am in an unattended run.
    """
    from pathlib import Path

    from ark.evidence_types import MASTER_TYPES
    from ark.sources import SOURCES

    # The real file, named explicitly: conftest repoints the module attribute at a
    # temp file for every other test, and reading that here would pass vacuously.
    real = Path(__file__).resolve().parents[1] / "docs" / "approved-sources-list.md"
    recorded = load(real)
    missing = sorted(
        {
            (spec.source_name, spec.evidence_type)
            for spec in SOURCES.values()
            if spec.evidence_type in MASTER_TYPES
        }
        - set(recorded)
    )
    assert not missing, f"master-eligible specs with no approval entry: {missing}"


def test_a_triage_entry_is_pending_but_marked_as_triage(tmp_path) -> None:
    """The gate treats it like any other pending class; only the reporting differs.

    A source found and not yet priced carries no sample and no measured figure, so it
    cannot be decided in two minutes the way a priced request can. The distinction has
    to be machine-readable, because the alternative is one entry per source on the one
    surface Ivo reads, and that surface stops being read the moment it stops fitting on
    a screen.
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
    """A malformed entry must not swallow the next section's Decision line.

    Without this, an entry whose `Decision:` line was forgotten would silently adopt the
    decision of whatever came next, which is the one failure mode a gate must not have:
    it would read as approved.
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


def test_the_live_file_parses_and_its_triage_section_is_recognised() -> None:
    """Against the real document, so a rename of the heading cannot pass silently."""
    from ark.approvals import TRIAGE_SECTION, load

    found = load(Path("docs/approved-sources-list.md"))
    assert found, "the live approvals file parsed to nothing"
    assert TRIAGE_SECTION == "Found, awaiting triage"
    assert any(a.decision == "master" for a in found.values())
