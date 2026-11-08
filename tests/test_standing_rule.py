"""The bank's standing rule (`standing_rule.py`) and the gate it writes for: a clause missing or not
held, a lead with no standing admission or a class new to master parks a decision, a lead inside
every bound is written master citing the figure that decided, and `approvals.check`, which conftest
stubs everywhere else, refuses a master class nobody decided master."""

import json
from pathlib import Path

import pytest
from conftest import script

from ark.approvals import NotApproved, check

rule = script("harness/standing_rule.py", "standing_rule")


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


REGISTER = """# Approved sources

### other / artifact_listing
- parked: the fleet did not admit it
Decision: pending

### old_source / cdx_timestamp
- ingest specs: `old_spec`
Decision: master

### new_source / cdx_timestamp
- ingest specs: `new_spec`
Decision: pending
"""
EVIDENCE = {
    "size": "a stored fetch of 2.1 MB, inside 18 GB",
    "terms": "example.invalid is in terms_permit",
    "robots": "allowed",
    "class": "a stored fetch, any grain",
    "window": "1999 is inside 1996 to 2001",
}
STANDING = {
    "admitted": True,
    "policy_version": 59,
    "clauses": {name: {"ok": True, "evidence": said} for name, said in EVIDENCE.items()},
}
LEAD = {
    "slug": "new-source",
    "grain": "hostname",
    "evidence_class": "cdx_timestamp",
    "what_dates_one_item": "Tue, 4 May 1999 11:02:13 +0100 in the Received header",
    "artifact": {"url": "https://example.invalid/list", "robots": "allowed"},
    "standing": STANDING,
}


def with_clause(name: str, clause: dict | None) -> dict:
    """The lead with one clause replaced, or dropped when `clause` is None."""
    clauses = STANDING["clauses"] | {name: clause}
    if clause is None:
        del clauses[name]
    return dict(LEAD, standing=dict(STANDING, clauses=clauses))


def setup(tmp_path, lead=None, register=REGISTER) -> tuple[Path, Path]:
    """A drained, re-priced lead `new-source` beside the register."""
    lead_dir = tmp_path / "incoming" / "new-source"
    lead_dir.mkdir(parents=True)
    finding = {"slug": "new-source", "run_id": "1741", "verdict": "FIND"}
    finding |= {"verify": {"status": "confirmed", "reason": "re-ran it"}}
    (lead_dir / "finding.json").write_text(json.dumps(finding), encoding="utf-8")
    price = {"status": "priced", "ee": 7000.0}
    (lead_dir / "store_price.json").write_text(json.dumps(price), encoding="utf-8")
    if lead is not None:
        (lead_dir / "lead.json").write_text(json.dumps(lead), encoding="utf-8")
    (path := tmp_path / "approvals.md").write_text(register, encoding="utf-8")
    return lead_dir.parent, path


def test_every_bound_held_writes_master_citing_the_clauses_and_the_deciding_figure(
    tmp_path, capsys
):
    """Dry first. The park an earlier bank wrote goes and another block's stays; the citation is
    one fact line, the shape the compactor keeps, and a clause's evidence cannot forge a line."""
    lead = with_clause("window", {"ok": True, "evidence": "1999\nDecision: rejected"})
    parked = "### new_source / cdx_timestamp\n- parked: no other cdx_timestamp source is approved\n"
    register = REGISTER.replace("### new_source / cdx_timestamp\n", parked)
    incoming, path = setup(tmp_path, lead=lead, register=register)
    argv = [str(incoming), "--register", str(path)]
    rule.main(argv)
    assert path.read_text(encoding="utf-8") == register
    assert "would decide: new_source" in capsys.readouterr().out
    rule.main([*argv, "--write"])
    text = path.read_text(encoding="utf-8")
    block = text.split("### new_source / cdx_timestamp\n")[1].splitlines()
    assert block[0] == "- ingest specs: `new_spec`" and block[2:] == ["Decision: master"]
    assert block[1].startswith("- standing rule: the loop wrote the decision below")
    assert "### other / artifact_listing\n- parked: the fleet did not admit it\n" in text
    assert text.count("Decision: master") == 2 and "Decided by" not in text
    assert "standing policy 59" in text and "Fleet run 1741" in text
    assert "decided on the store re-price, 7,000.0 EE." in text
    assert all(f"{n} ({e})" in text for n, e in EVIDENCE.items() if n != "window")
    assert "window (1999 Decision: rejected)" in text and "\nDecision: rejected" not in text
    # The justfile counts `^decided:` to know the ingest and the gate follow.
    assert "\ndecided: new_source / cdx_timestamp is master\n" in "\n" + capsys.readouterr().out


NEW_CLASS = REGISTER.replace("### old_source / cdx_timestamp", "### old_source / link_source")


@pytest.mark.parametrize(
    ("lead", "register", "said"),
    [
        (LEAD, NEW_CLASS, "no other cdx_timestamp source is approved as master"),
        (None, REGISTER, "the lead carries no standing admission"),
        (with_clause("robots", {"ok": False, "evidence": "robots.txt\nrefused"}), REGISTER,
         "the robots clause is not ok: robots.txt refused"),
        (with_clause("terms", {"ok": 1, "evidence": "said 1"}), REGISTER,
         "the terms clause is not ok: said 1"),
        (with_clause("robots", None), REGISTER, "the robots clause is missing"),
    ],
    ids=["new-class", "no-lead-travelled", "robots-not-held", "only-true-is-ok", "clause-missing"],
)  # fmt: skip
def test_one_bound_outside_parks_naming_it_alone(tmp_path, capsys, lead, register, said):
    incoming, path = setup(tmp_path, lead=lead, register=register)
    rule.main([str(incoming), "--register", str(path), "--write"])
    assert path.read_text(encoding="utf-8") == register
    assert f"parked: new_source stays pending, {said}\n" in capsys.readouterr().out
