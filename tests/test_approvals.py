"""`approvals.check`, which conftest stubs everywhere else, refuses a master class nobody decided
master."""

import pytest

from ark.approvals import NotApproved, check


@pytest.mark.parametrize(
    ("kind", "block", "said"),
    [
        ("link_target", None, None),
        ("cdx_timestamp", "Decision: master", None),
        ("artifact_listing", None, "has no entry"),
        ("artifact_listing", "Decision: pending", "awaiting classification"),
        ("artifact_listing", "Decision: rejected", "REJECTED"),
        ("artifact_listing", "Decision: candidate-only", "candidate-only"),
        ("artifact_listing", "Decision: maybe-ok", "has no entry"),
        ("artifact_listing", "## Next\n\nDecision: master", "has no entry"),
    ],
    ids=["candidate-needs-no-entry", "master", "unknown", "pending", "rejected", "candidate-only",
         "unparseable-fails-closed", "a-section-heading-ends-the-block"],
)  # fmt: skip
def test_a_master_spec_without_a_master_decision_is_refused(tmp_path, kind, block, said):
    path = tmp_path / "approved-sources-list.md"
    path.write_text(f"### some_source / {kind}\n\n{block}\n" if block else "", encoding="utf-8")
    if said is None:
        check("some_source", kind, path)
    else:
        with pytest.raises(NotApproved, match=said):
            check("some_source", kind, path)
