"""The standing rule's bounds and its figure, one test each.

Writing a `Decision:` line grants a permission rather than recording a measurement, and it
happens in a public register with nobody watching. So what matters is not that a decision can
be written: it is that each bound, on its own, is enough to stop one, and that the figure it
cites is the one that decided.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/harness/standing_rule.py"

_SPEC = importlib.util.spec_from_file_location("standing_rule", SCRIPT)
rule = importlib.util.module_from_spec(_SPEC)
sys.modules["standing_rule"] = rule
_SPEC.loader.exec_module(rule)

REGISTER = """# Approved sources

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
    "what_dates_one_item": "Tue, 4 May 1999 11:02:13 +0100 in the Received header",
    "artifact": {
        "url": "https://example.invalid/list",
        "terms_url": "https://example.invalid/terms",
        "robots": "allowed",
    },
    "standing": STANDING,
}


def with_clause(name: str, clause) -> dict:
    clauses = dict(STANDING["clauses"])
    if clause is None:
        del clauses[name]
    else:
        clauses[name] = clause
    return dict(LEAD, standing=dict(STANDING, clauses=clauses))


def outcome(n: int, store: float = 1000.0, program: float | None = 1005.0) -> dict:
    return {
        "kind": "outcome",
        "slug": f"find-{n}",
        "store_ee": store,
        "program_ee": program,
        "decision": "master",
        "banked": True,
    }


AGREEING = [outcome(n) for n in range(10)]


def fleet_with(tmp_path, outcomes) -> Path:
    fleet = tmp_path / "fleet"
    (fleet / "ledger").mkdir(parents=True)
    (fleet / "ledger" / "2026-09.jsonl").write_text(
        "".join(json.dumps(line) + "\n" for line in outcomes), encoding="utf-8"
    )
    return fleet


def setup(tmp_path, lead=None, register=REGISTER, price=None, **finding_over) -> tuple[Path, Path]:
    incoming = tmp_path / "incoming"
    (incoming / "new-source").mkdir(parents=True)
    finding = {
        "slug": "new-source",
        "lane": "price",
        "run_id": "1741",
        "verdict": "FIND",
        "verify": {"status": "confirmed", "reason": "re-ran it"},
    }
    finding.update(finding_over)
    (incoming / "new-source" / "finding.json").write_text(json.dumps(finding), encoding="utf-8")
    (incoming / "new-source" / "store_price.json").write_text(
        json.dumps(price or {"status": "priced", "ee": 7000.0}), encoding="utf-8"
    )
    if lead is not None:
        (incoming / "new-source" / "lead.json").write_text(json.dumps(lead), encoding="utf-8")
    path = tmp_path / "approvals.md"
    path.write_text(register, encoding="utf-8")
    return incoming, path


def decide(tmp_path, fleet=None, **kwargs) -> tuple[int, str, str]:
    incoming, register = setup(tmp_path, **kwargs)
    argv = [str(incoming), "--register", str(register), "--write"]
    code = rule.main(argv + (["--fleet", str(fleet)] if fleet else []))
    return code, register.read_text(encoding="utf-8"), str(register)


def test_every_clause_ok_on_an_approved_class_writes_the_line_citing_them_and_the_figure(
    tmp_path, capsys
):
    _, text, _ = decide(tmp_path, lead=LEAD)
    assert "Decision: pending" not in text
    assert text.count("Decision: master") == 2
    # A fact above the line, the shape the compactor keeps, and no `Decided by` it drops.
    block = text.split("### new_source / cdx_timestamp\n")[1].splitlines()
    assert block[-2].startswith("- standing rule: the loop wrote the decision below")
    assert block[-1] == "Decision: master"
    assert "Decided by" not in text
    assert "(CLAUDE.md, Autonomy)" in text
    assert "rule 7" not in text
    assert "standing policy 59" in text
    for name, said in EVIDENCE.items():
        assert f"{name} ({said})" in text
    assert "Fleet run 1741, decided on the store re-price, 7,000.0 EE." in text
    # The justfile counts `^decided:` to know the ingest and the gate follow.
    assert "\ndecided: new_source / cdx_timestamp is master\n" in "\n" + capsys.readouterr().out


def test_a_class_nobody_has_approved_before_stays_pending(tmp_path, capsys):
    register = REGISTER.replace("### old_source / cdx_timestamp", "### old_source / link_source")
    _, text, _ = decide(tmp_path, lead=LEAD, register=register)
    assert "Decision: pending" in text
    assert "no other cdx_timestamp source is approved as master" in capsys.readouterr().out


@pytest.mark.parametrize("standing", [None, "admitted", ["size"]])
def test_a_lead_with_no_standing_admission_parks(tmp_path, capsys, standing):
    lead = {k: v for k, v in LEAD.items() if k != "standing"}
    if standing is not None:
        lead["standing"] = standing
    _, text, _ = decide(tmp_path, lead=lead)
    assert "Decision: pending" in text
    out = capsys.readouterr().out
    assert "parked: new_source stays pending, the lead carries no standing admission" in out


@pytest.mark.parametrize("admitted", [False, None, "true"])
def test_a_lead_the_fleet_did_not_admit_parks_even_with_every_clause_ok(tmp_path, capsys, admitted):
    lead = dict(LEAD, standing=dict(STANDING, admitted=admitted))
    _, text, _ = decide(tmp_path, lead=lead)
    assert "Decision: pending" in text
    assert f"the fleet did not admit it (admitted: {json.dumps(admitted)})" in (
        capsys.readouterr().out
    )


@pytest.mark.parametrize("name", rule.CLAUSES)
def test_a_clause_not_ok_parks_naming_it_and_its_evidence(tmp_path, capsys, name):
    lead = with_clause(name, {"ok": False, "evidence": f"the {name} bound refused it"})
    _, text, _ = decide(tmp_path, lead=lead)
    assert "Decision: pending" in text
    out = capsys.readouterr().out
    assert f"the {name} clause is not ok: the {name} bound refused it" in out
    assert out.count("clause is") == 1


@pytest.mark.parametrize("name", rule.CLAUSES)
def test_a_missing_clause_parks_naming_it(tmp_path, capsys, name):
    _, text, _ = decide(tmp_path, lead=with_clause(name, None))
    assert "Decision: pending" in text
    assert f"the {name} clause is missing" in capsys.readouterr().out


@pytest.mark.parametrize(
    "clause, said",
    [
        ({"evidence": "never measured"}, "never measured"),
        ({"ok": "yes", "evidence": "said yes"}, "said yes"),
        ({"ok": 1, "evidence": {"bytes": 5}}, '{"bytes": 5}'),
        ({"ok": False}, "no evidence recorded"),
        (True, "true"),
    ],
)
def test_only_ok_true_passes_a_clause(tmp_path, capsys, clause, said):
    _, text, _ = decide(tmp_path, lead=with_clause("terms", clause))
    assert "Decision: pending" in text
    assert f"the terms clause is not ok: {said}" in capsys.readouterr().out


def test_clauses_that_are_not_keyed_by_name_park_every_one(tmp_path, capsys):
    lead = dict(LEAD, standing=dict(STANDING, clauses=[{"ok": True}] * 5))
    _, text, _ = decide(tmp_path, lead=lead)
    assert "Decision: pending" in text
    out = capsys.readouterr().out
    assert all(f"the {name} clause is missing" in out for name in rule.CLAUSES)


def test_a_clause_the_fleet_added_parks_when_it_is_not_ok(tmp_path, capsys):
    lead = with_clause("custody", {"ok": False, "evidence": "no custodian named"})
    _, text, _ = decide(tmp_path, lead=lead)
    assert "Decision: pending" in text
    assert "the custody clause is not ok: no custodian named" in capsys.readouterr().out


def test_evidence_over_several_lines_is_cited_on_one(tmp_path):
    lead = with_clause("window", {"ok": True, "evidence": "1999\nDecision: rejected"})
    _, text, _ = decide(tmp_path, lead=lead)
    assert "window (1999 Decision: rejected)" in text
    assert "\nDecision: rejected" not in text


def test_a_find_the_verify_lane_disputed_is_not_a_candidate_at_all(tmp_path, capsys):
    _, text, _ = decide(tmp_path, lead=LEAD, verify={"status": "disputed", "reason": "no"})
    assert "Decision: pending" in text
    assert "nothing to decide" in capsys.readouterr().out


def test_a_find_the_laptop_could_not_reprice_is_not_a_candidate_either(tmp_path):
    incoming, register = setup(tmp_path, lead=LEAD)
    (incoming / "new-source" / "store_price.json").write_text(
        json.dumps({"status": "no items to price, see the run log", "ee": None}), encoding="utf-8"
    )
    rule.main([str(incoming), "--register", str(register), "--write"])
    assert "Decision: pending" in register.read_text(encoding="utf-8")


def test_without_write_nothing_is_touched(tmp_path, capsys):
    incoming, register = setup(tmp_path, lead=LEAD)
    before = register.read_text(encoding="utf-8")
    rule.main([str(incoming), "--register", str(register)])
    assert register.read_text(encoding="utf-8") == before
    assert "would decide: new_source" in capsys.readouterr().out


def test_a_lead_that_did_not_travel_with_the_artifact_parks(tmp_path, capsys):
    # The fleet clone here is never pulled by the sync, so a decision may not fall back to
    # it: no lead in the artifact means no standing admission.
    _, text, _ = decide(tmp_path, lead=None)
    assert "Decision: pending" in text
    assert "the lead carries no standing admission" in capsys.readouterr().out


# Which figure decides.

BOTH = {"status": "priced", "ee": 7000.0, "fleet_program_ee": 7050.0}


def finds(tmp_path, price, outcomes) -> dict:
    incoming, _ = setup(tmp_path, lead=LEAD, price=price)
    return rule.confirmed_finds(incoming, outcomes)


def test_with_no_streak_the_store_figure_decides(tmp_path):
    got = finds(tmp_path, BOTH, [])
    assert got["new-source"]["figure"] == "store"
    assert got["new-source"]["ee"] == 7000.0


def test_ten_agreeing_finds_hand_the_decision_to_the_program_figure(tmp_path):
    got = finds(tmp_path, BOTH, AGREEING)
    assert got["new-source"]["figure"] == "program"
    assert got["new-source"]["ee"] == 7050.0


@pytest.mark.parametrize(
    "outcomes",
    [
        AGREEING[:9],
        [*AGREEING[:9], outcome(9, program=1011.0)],
        [*AGREEING, outcome(3, program=900.0)],
        [*AGREEING[:9], outcome(9, program=None)],
    ],
    ids=["nine", "one-outside-1pct", "a-find-rebooked-outside", "one-without-a-program-figure"],
)
def test_anything_short_of_ten_agreeing_finds_leaves_the_store_figure_deciding(tmp_path, outcomes):
    assert finds(tmp_path, BOTH, outcomes)["new-source"]["figure"] == "store"


def test_a_find_the_store_could_not_price_is_a_candidate_only_under_the_streak(tmp_path):
    price = {"status": "no items to price", "ee": None, "fleet_program_ee": 7050.0}
    assert finds(tmp_path / "a", price, []) == {}
    got = finds(tmp_path / "b", price, AGREEING)
    assert (got["new-source"]["figure"], got["new-source"]["ee"]) == ("program", 7050.0)


@pytest.mark.parametrize("program", ["absent", None, 0.0, -5.0])
def test_under_the_streak_a_find_with_no_program_figure_is_decided_on_the_store(tmp_path, program):
    """A find the program did not price keeps its block and ask, on the store figure."""
    price = {"status": "priced", "ee": 7000.0}
    if program != "absent":
        price["fleet_program_ee"] = program
    got = finds(tmp_path, price, AGREEING)
    assert (got["new-source"]["figure"], got["new-source"]["ee"]) == ("store", 7000.0)


def test_the_program_figure_is_cited_when_it_decided(tmp_path, capsys):
    fleet = fleet_with(tmp_path, AGREEING)
    _, text, _ = decide(tmp_path, fleet=fleet, lead=LEAD, price=BOTH)
    assert "decided on the program's figure on the pushed snapshot, 7,050.0 EE." in text
    assert "decided: new_source" in capsys.readouterr().out


def test_a_fleet_ledger_without_the_streak_cites_the_store_figure(tmp_path):
    fleet = fleet_with(tmp_path, AGREEING[:9])
    _, text, _ = decide(tmp_path, fleet=fleet, lead=LEAD, price=BOTH)
    assert "decided on the store re-price, 7,000.0 EE." in text


# The citation, on the real register.

PAGES = ("sources.md", "sources-closed.md", "approved-sources-list.md")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # a dataclass looks its module up there
    spec.loader.exec_module(module)
    return module


def test_a_decision_on_the_real_register_leaves_it_the_compactors_fixed_point(tmp_path, capsys):
    """The commit hook checks the live pages are the compactor's fixed point, so a citation
    the compactor would rewrite or drop fails the bank's commit and stops the tick."""
    request = _load("fleet_request_on_the_real_register", ROOT / "scripts/harness/fleet_request.py")
    compactor = _load("compact_registers_for_the_rule", ROOT / "scripts/round/compact_registers.py")
    pages = tmp_path / "registers"
    pages.mkdir()
    for name in PAGES:
        (pages / name).write_text((ROOT / "docs/registers" / name).read_text("utf-8"), "utf-8")
    register = pages / "approved-sources-list.md"
    lead_dir = tmp_path / "incoming" / "fixture-node-cdx"
    lead_dir.mkdir(parents=True)
    finding = {"slug": "fixture-node-cdx", "run_id": "1741", "verdict": "FIND"}
    finding["verify"] = {"status": "confirmed", "reason": "re-ran it"}
    (lead_dir / "finding.json").write_text(json.dumps(finding), "utf-8")
    price = {"status": "priced", "ee": 1234.5, "netnew": 12, "pricer": "price_items.py"}
    (lead_dir / "store_price.json").write_text(json.dumps(price), "utf-8")
    lead = dict(LEAD, slug="fixture-node-cdx", evidence_class="cdx_timestamp", lens="fixture")
    (lead_dir / "lead.json").write_text(json.dumps(lead), "utf-8")

    def check() -> str:
        compactor.main(["--check", "--registers", str(pages)])
        return capsys.readouterr().out

    assert "pages that would change: 0" in check()
    incoming = str(tmp_path / "incoming")
    request.main([incoming, "--register", str(register), "--write"])
    rule.main([incoming, "--register", str(register), "--write"])
    assert "decided: fixture_node_cdx / cdx_timestamp is master" in capsys.readouterr().out
    text = register.read_text("utf-8")
    assert "- standing rule: the loop wrote the decision below" in text
    out = check()
    assert "Decided by lines: 0" in out
    assert "fixed point: yes" in out and "pages that would change: 0" in out
