"""The standing rule and the gate it writes for: each bound alone parks a decision, the figure it
cites is the one that decided, and `approvals.check`, which conftest stubs everywhere else,
refuses a master class nobody decided master."""

import json
from pathlib import Path

import pytest
from conftest import script

from ark.approvals import NotApproved, check, load, pending

ROOT = Path(__file__).resolve().parents[1]


rule = script("harness/standing_rule.py", "standing_rule")


def _entry(source: str, kind: str, decision: str) -> str:
    return f"### {source} / {kind}\n\nDecision: {decision}\n\n"


@pytest.mark.parametrize(
    ("kind", "decision", "said"),
    [
        ("link_target", None, None),
        ("cdx_timestamp", "master", None),
        ("artifact_listing", None, "has no entry"),
        ("artifact_listing", "pending", "awaiting classification"),
        ("artifact_listing", "rejected", "REJECTED"),
        ("artifact_listing", "candidate-only", "candidate-only"),
        ("artifact_listing", "maybe-ok", "has no entry"),
    ],
    ids=["candidate-needs-no-entry", "master", "unknown", "pending", "rejected", "candidate-only",
         "unparseable-fails-closed"],
)  # fmt: skip
def test_a_master_spec_without_a_master_decision_is_refused(tmp_path, kind, decision, said):
    path = tmp_path / "approved-sources-list.md"
    path.write_text(_entry("some_source", kind, decision) if decision else "", encoding="utf-8")
    if said is None:
        check("some_source", kind, path)
    else:
        with pytest.raises(NotApproved, match=said):
            check("some_source", kind, path)


def test_a_section_heading_ends_an_unfinished_block_and_triage_is_pending(tmp_path):
    """A block missing its Decision line never adopts the next section's, which reads approved."""
    path = tmp_path / "approved-sources-list.md"
    path.write_text(
        "## Pending requests\n\n" + _entry("b", "dated_directory", "pending")
        + "### forgot_its_decision / artifact_listing\n\nno Decision line\n\n"
        + "## Approved before this mechanism existed\n\nDecision: master\n\n"
        + _entry("a", "artifact_listing", "master")
        + "## Found, awaiting triage\n\n" + _entry("found", "whois_creation", "pending"),
        encoding="utf-8",
    )  # fmt: skip
    found = load(path)
    assert ("forgot_its_decision", "artifact_listing") not in found
    assert found[("a", "artifact_listing")].decision == "master"
    assert [(p.source_name, p.is_triage) for p in pending(path)] == [("b", False), ("found", True)]


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
BOTH = {"status": "priced", "ee": 7000.0, "fleet_program_ee": 7050.0}


def with_clause(name: str, clause) -> dict:
    clauses = dict(STANDING["clauses"])
    if clause is None:
        del clauses[name]
    else:
        clauses[name] = clause
    return dict(LEAD, standing=dict(STANDING, clauses=clauses))


def outcome(n: int, store: float | None = 1000.0, program: float | None = 1005.0, **over) -> dict:
    line = {"kind": "outcome", "slug": f"find-{n}", "store_ee": store, "program_ee": program}
    return line | {"decision": "master", "banked": True} | over


AGREEING = [outcome(n) for n in range(10)]


def setup(tmp_path, lead=None, register=REGISTER, price=None, **finding_over) -> tuple[Path, Path]:
    """A drained, re-priced lead `new-source` beside the register."""
    lead_dir = tmp_path / "incoming" / "new-source"
    lead_dir.mkdir(parents=True)
    finding = {"slug": "new-source", "run_id": "1741", "verdict": "FIND"}
    finding |= {"verify": {"status": "confirmed", "reason": "re-ran it"}} | finding_over
    (lead_dir / "finding.json").write_text(json.dumps(finding), encoding="utf-8")
    price = price or {"status": "priced", "ee": 7000.0}
    (lead_dir / "store_price.json").write_text(json.dumps(price), encoding="utf-8")
    if lead is not None:
        (lead_dir / "lead.json").write_text(json.dumps(lead), encoding="utf-8")
    (path := tmp_path / "approvals.md").write_text(register, encoding="utf-8")
    return lead_dir.parent, path


@pytest.mark.parametrize(
    ("streak", "said"),
    [(None, "decided on the store re-price, 7,000.0 EE."),
     (AGREEING, "decided on the program's figure on the pushed snapshot, 7,050.0 EE.")],
    ids=["store-decides", "program-decides-under-the-streak"],
)  # fmt: skip
def test_every_bound_held_writes_master_citing_the_clauses_and_the_deciding_figure(
    tmp_path, capsys, streak, said
):
    """Dry first. The park an earlier bank wrote goes and another block's stays; the citation is
    one fact line, the shape the compactor keeps, and a clause's evidence cannot forge a line."""
    lead = with_clause("window", {"ok": True, "evidence": "1999\nDecision: rejected"})
    parked = "### new_source / cdx_timestamp\n- parked: no other cdx_timestamp source is approved\n"
    register = REGISTER.replace("### new_source / cdx_timestamp\n", parked)
    incoming, path = setup(tmp_path, lead=lead, register=register, price=BOTH)
    argv = [str(incoming), "--register", str(path)]
    if streak:
        (fleet := tmp_path / "fleet/ledger").mkdir(parents=True)
        (fleet / "2026-09.jsonl").write_text("".join(json.dumps(o) + "\n" for o in streak))
        argv += ["--fleet", str(fleet.parent)]
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
    assert "standing policy 59" in text and "Fleet run 1741" in text and said in text
    assert all(f"{n} ({e})" in text for n, e in EVIDENCE.items() if n != "window")
    assert "window (1999 Decision: rejected)" in text and "\nDecision: rejected" not in text
    # The justfile counts `^decided:` to know the ingest and the gate follow.
    assert "\ndecided: new_source / cdx_timestamp is master\n" in "\n" + capsys.readouterr().out


def test_a_whole_reads_block_is_decided_for_its_lead_only_with_its_read(tmp_path, capsys):
    """`fleet_request.py` files a read's block as `fleet_<slug>_hostnames`."""
    register = REGISTER.replace("### new_source /", "### fleet_new_source_hostnames /")
    incoming, path = setup(tmp_path, lead=LEAD, register=register)
    (incoming / "new-source/read.json").write_text("{}", encoding="utf-8")
    rule.main([str(incoming), "--register", str(path), "--write"])
    assert "decided: fleet_new_source_hostnames / cdx_timestamp is master" in (
        capsys.readouterr().out
    )
    (incoming / "new-source/read.json").unlink()
    path.write_text(register, encoding="utf-8")
    rule.main([str(incoming), "--register", str(path), "--write"])
    assert path.read_text(encoding="utf-8") == register


NEW_CLASS = REGISTER.replace("### old_source / cdx_timestamp", "### old_source / link_source")


@pytest.mark.parametrize(
    ("lead", "register", "said"),
    [
        (LEAD, NEW_CLASS, "no other cdx_timestamp source is approved as master"),
        (None, REGISTER, "the lead carries no standing admission"),
        (dict(LEAD, standing=dict(STANDING, admitted="true")), REGISTER,
         'the fleet did not admit it (admitted: "true")'),
        (with_clause("robots", {"ok": False, "evidence": "robots.txt refused"}), REGISTER,
         "the robots clause is not ok: robots.txt refused"),
        (with_clause("window", None), REGISTER, "the window clause is missing"),
        (with_clause("terms", {"ok": 1, "evidence": "said 1"}), REGISTER,
         "the terms clause is not ok: said 1"),
        (with_clause("custody", {"ok": False}), REGISTER,
         "the custody clause is not ok: no evidence recorded"),
        (dict(LEAD, standing="admitted"), REGISTER, "the lead carries no standing admission"),
        (dict(LEAD, standing=dict(STANDING, clauses=list(STANDING["clauses"].values()))),
         REGISTER, "; ".join(f"the {name} clause is missing" for name in rule.CLAUSES)),
        (with_clause("terms", True), REGISTER, "the terms clause is not ok: true"),
    ],
    ids=["new-class", "no-lead-travelled", "not-admitted", "clause-not-ok", "clause-missing",
         "only-true-is-ok", "a-clause-the-fleet-added", "standing-not-a-mapping",
         "clauses-not-keyed-by-name", "a-bare-true-clause"],
)  # fmt: skip
def test_one_bound_outside_parks_naming_it_alone(tmp_path, capsys, lead, register, said):
    incoming, path = setup(tmp_path, lead=lead, register=register)
    rule.main([str(incoming), "--register", str(path), "--write"])
    assert path.read_text(encoding="utf-8") == register
    assert f"parked: new_source stays pending, {said}\n" in capsys.readouterr().out


def test_a_find_its_verify_lane_disputed_is_no_candidate(tmp_path, capsys):
    incoming, path = setup(tmp_path, lead=LEAD, verify={"status": "disputed", "reason": "no"})
    rule.main([str(incoming), "--register", str(path), "--write"])
    assert path.read_text(encoding="utf-8") == REGISTER
    assert "nothing to decide" in capsys.readouterr().out


NINE = AGREEING[:9]
UNPRICED = {"status": "no items to price", "ee": None, "fleet_program_ee": 7050.0}
STORE, PROGRAM = ("store", 7000.0), ("program", 7050.0)


@pytest.mark.parametrize(
    ("price", "outcomes", "want"),
    [
        (BOTH, [], STORE),
        (BOTH, AGREEING, PROGRAM),
        (BOTH, [outcome(0, decision="pending", banked=False), *NINE], STORE),
        (BOTH, [*NINE, outcome(9, program=1011.0)], STORE),
        (BOTH, [*NINE, outcome(9, program=None)], STORE),
        (BOTH, [outcome(0, program=1100.0), *(outcome(n) for n in range(1, 11)),
                outcome(0, program=1100.0)], STORE),
        (BOTH, [*NINE, outcome(98, store=None), outcome(99)], PROGRAM),
        ({"status": "priced", "ee": 7000.0, "fleet_program_ee": 0.0}, AGREEING, STORE),
        ({"status": "priced", "ee": 7000.0, "fleet_program_ee": -5.0}, AGREEING, STORE),
        (UNPRICED, [], None),
        ({"status": "priced", "ee": -5.0}, [], None),
        (UNPRICED, AGREEING, PROGRAM),
    ],
    ids=["no-streak", "ten-agreeing", "nine-finds-one-booked-twice", "one-outside-1pct",
         "one-without-a-program-figure", "a-rebooked-find-counts-at-its-latest-line",
         "a-line-without-a-store-figure-is-no-find", "a-zero-program-figure-never-decides",
         "a-negative-program-figure-never-decides", "unpriced-by-the-store",
         "a-negative-store-figure-is-no-candidate", "unpriced-by-the-store-under-the-streak"],
)  # fmt: skip
def test_ten_agreeing_finds_hand_the_decision_to_the_program_figure(
    tmp_path, price, outcomes, want
):
    incoming, _ = setup(tmp_path, lead=LEAD, price=price)
    got = rule.confirmed_finds(incoming, outcomes).get("new-source")
    assert (got and (got["figure"], got["ee"])) == want
