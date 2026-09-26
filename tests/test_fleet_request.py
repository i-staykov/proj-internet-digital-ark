"""The block a fleet FIND needs before anything can decide it.

Without it the loop stops one step short and looks complete: a row in `sources.md`, a
confirmed FIND and no `Decision:` line, so the standing rule finds nothing to flip and Ivo is
asked nothing. The tests pin what the block must not do: no invented spec, no invented terms,
no second block for a source already decided, and no ask for a source the standing rule
decides in the same bank.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/harness/fleet_request.py"

_SPEC = importlib.util.spec_from_file_location("fleet_request", SCRIPT)
request = importlib.util.module_from_spec(_SPEC)
sys.modules["fleet_request"] = request
_SPEC.loader.exec_module(request)
standing_rule = request.standing_rule

REGISTER = """# Approved sources

## Pending requests

### old_source / cdx_timestamp
Decision: pending
"""

LEAD = {
    "slug": "a-lead",
    "lens": "registry publications",
    "grain": "hostname",
    "evidence_class": "cdx_timestamp",
    "what_dates_one_item": "1999-05-04T11:02:13Z in the capture line",
    "artifact": {"url": "https://example.invalid/x", "terms_url": None, "robots": "allowed"},
}


# A register where another cdx_timestamp source is approved, so the class is not new.
APPROVED_CLASS = """# Approved sources

### old_source / cdx_timestamp
Decision: master

## Pending requests

None.
"""

STANDING = {
    "admitted": True,
    "policy_version": 59,
    "clauses": {
        name: {"ok": True, "evidence": f"{name} inside the bound"}
        for name in ("size", "terms", "robots", "class", "window")
    },
}

DECISIONS = "# Decisions\n\n## OPEN\n\n## CLOSED\n\n| | date | decision |\n|---|---|---|\n"

# Ten finds whose program figure agreed with the store within 1%: the program decides.
AGREEING = [
    {
        "kind": "outcome",
        "slug": f"find-{n}",
        "store_ee": 1000.0,
        "program_ee": 1004.0,
        "decision": "master",
        "banked": True,
    }
    for n in range(10)
]


def ledger(tmp_path, outcomes) -> Path:
    fleet = tmp_path / "fleet"
    (fleet / "ledger").mkdir(parents=True)
    (fleet / "ledger" / "2026-09.jsonl").write_text(
        "".join(json.dumps(line) + "\n" for line in outcomes), encoding="utf-8"
    )
    return fleet


def world(
    tmp_path,
    lead=LEAD,
    ee=7000.0,
    verify="confirmed",
    verdict="FIND",
    register=REGISTER,
    program=None,
    slug="a-lead",
):
    incoming = tmp_path / "incoming"
    lead_dir = incoming / slug
    lead_dir.mkdir(parents=True)
    (lead_dir / "finding.json").write_text(
        json.dumps(
            {
                "slug": slug,
                "run_id": "1741",
                "verdict": verdict,
                "pricing": {"ee": 900000.0, "track": "annual"},
                "verify": {"status": verify, "reason": "re-ran it"},
            }
        ),
        encoding="utf-8",
    )
    price = {"status": "priced", "ee": ee, "netnew": 12, "pricer": "price_items.py"}
    if program is not None:
        price["fleet_program_ee"] = program
    (lead_dir / "store_price.json").write_text(json.dumps(price), encoding="utf-8")
    if lead is not None:
        (lead_dir / "lead.json").write_text(json.dumps(lead), encoding="utf-8")
    path = tmp_path / "approvals.md"
    path.write_text(register, encoding="utf-8")
    return incoming, path


def write(incoming, register, *extra) -> str:
    request.main([str(incoming), "--register", str(register), "--write", *extra])
    return register.read_text(encoding="utf-8")


def test_a_confirmed_repriced_find_gets_a_pending_block(tmp_path):
    text = write(*world(tmp_path))
    assert "### a_lead / cdx_timestamp" in text
    assert "- potential: 7000" in text


def test_the_rest_of_the_register_survives_the_insert(tmp_path):
    # The insert once truncated the file at the heading it wrote under, which loses every
    # block below it: the whole pending queue.
    text = write(*world(tmp_path))
    # Newest first, no blank line inside a block and one between: the compactor's shape.
    new, old = text.split("## Pending requests\n\n")[1].split("\n\n")
    assert new.startswith("### a_lead / cdx_timestamp\n- ingest spec:")
    assert old == "### old_source / cdx_timestamp\nDecision: pending\n"


def test_the_block_carries_the_store_figure_and_names_the_fleets_as_the_other_one(tmp_path):
    text = write(*world(tmp_path))
    assert "7,000.0 EE net-new on the live store" in text
    assert "The fleet said 900,000.0 EE" in text


def test_the_block_invents_no_spec_and_says_a_yes_banks_nothing_yet(tmp_path):
    text = write(*world(tmp_path))
    assert "ingest spec: none in this repository yet" in text
    assert "banked nothing" in text


def test_a_lead_with_no_terms_page_says_so_rather_than_leaving_the_line_blank(tmp_path):
    text = write(*world(tmp_path))
    assert "the lead records no terms page" in text


def test_the_stamp_is_quoted_from_the_lead(tmp_path):
    text = write(*world(tmp_path))
    assert "1999-05-04T11:02:13Z in the capture line" in text


def test_a_source_that_already_has_a_block_is_left_alone(tmp_path, capsys):
    incoming, register = world(tmp_path)
    write(incoming, register)
    before = register.read_text(encoding="utf-8")
    write(incoming, register)
    assert register.read_text(encoding="utf-8") == before
    assert "already has a block" in capsys.readouterr().out


def test_a_disputed_find_is_not_asked_about(tmp_path):
    text = write(*world(tmp_path, verify="disputed"))
    assert "a_lead" not in text


def test_a_find_with_no_store_price_is_not_asked_about(tmp_path):
    text = write(*world(tmp_path, ee=0.0))
    assert "a_lead" not in text


def test_a_candidate_only_class_needs_no_approval(tmp_path, capsys):
    lead = dict(LEAD, evidence_class="link_target")
    write(*world(tmp_path, lead=lead))
    assert "needs no approval" in capsys.readouterr().out


def test_without_write_nothing_is_touched(tmp_path, capsys):
    incoming, register = world(tmp_path)
    before = register.read_text(encoding="utf-8")
    request.main([str(incoming), "--register", str(register)])
    assert register.read_text(encoding="utf-8") == before
    assert "would write: a_lead" in capsys.readouterr().out


def test_the_block_parses_as_an_approval_the_gate_can_read(tmp_path):
    from ark import approvals

    incoming, register = world(tmp_path)
    write(incoming, register)
    parsed = approvals.load(register)
    assert ("a_lead", "cdx_timestamp") in parsed
    assert parsed[("a_lead", "cdx_timestamp")].decision == "pending"


def test_a_drain_outside_the_checkout_still_writes_a_block(tmp_path):
    # tmp_path is not under the repository, which is how this crashed on the journal line.
    incoming, register = world(tmp_path)
    (incoming / "a-lead" / "items.jsonl").write_text('{"item": "x", "year": 1998}\n', "utf-8")
    assert "- journal: `" in write(incoming, register)


def test_a_short_block_also_gets_an_open_entry(tmp_path):
    """2026-09-15: the Danish zone list's block was written, its OPEN entry was not, and
    the sync that raised the request refused its own gate."""
    decisions = tmp_path / "key-decisions.md"
    decisions.write_text(
        "# Decisions\n\n## OPEN\n\n## CLOSED\n\n| | date | decision |\n|---|---|---|\n"
    )
    lead = {"lens": "registry-publications"}
    store = {"ee": 9702.6, "netnew": 56707, "pricer": "price_items.py"}
    find = {"store": store, "figure": "store", "ee": 9702.6}
    assert request.surface("dk_zone", "artifact_listing", lead, find, decisions)
    text = decisions.read_text()
    assert "### Approve dk_zone / artifact_listing" in text
    assert "9,702.6 EE net-new on the live store" in text
    assert not request.surface("dk_zone", "artifact_listing", lead, find, decisions), "once"


# The ask: only for a source the standing rule parks.


def asks(tmp_path, monkeypatch, *, register, lead, extra=()) -> tuple[list, str, str]:
    """Run the request with a scratch decisions file; what surface() was called with, the
    decisions file and the register afterwards."""
    decisions = tmp_path / "key-decisions.md"
    decisions.write_text(DECISIONS, encoding="utf-8")
    called = []
    real = request.surface
    monkeypatch.setattr(request, "surface", lambda *a, **k: called.append(a[:2]) or real(*a, **k))
    incoming, path = world(tmp_path, lead=lead, register=register)
    text = write(incoming, path, "--decisions", str(decisions), *extra)
    return called, decisions.read_text(encoding="utf-8"), text


def test_a_standing_rule_source_gets_its_block_and_no_ask(tmp_path, monkeypatch, capsys):
    lead = dict(LEAD, standing=STANDING)
    called, decisions, text = asks(tmp_path, monkeypatch, register=APPROVED_CLASS, lead=lead)
    assert called == []
    assert decisions == DECISIONS
    assert "### a_lead / cdx_timestamp" in text
    assert "no ask: the standing rule decides it" in capsys.readouterr().out


def test_a_new_class_is_asked_about_once(tmp_path, monkeypatch, capsys):
    lead = dict(LEAD, standing=STANDING)
    called, decisions, text = asks(tmp_path, monkeypatch, register=REGISTER, lead=lead)
    assert called == [("a_lead", "cdx_timestamp")]
    assert decisions.count("### Approve a_lead / cdx_timestamp") == 1
    assert "### a_lead / cdx_timestamp" in text
    assert "and its OPEN entry" in capsys.readouterr().out


@pytest.mark.parametrize(
    "lead",
    [
        LEAD,
        dict(LEAD, standing=dict(STANDING, admitted=False)),
        dict(LEAD, standing=dict(STANDING, clauses={})),
    ],
    ids=["no-standing", "not-admitted", "no-clauses"],
)
def test_a_lead_outside_the_standing_bounds_is_asked_about(tmp_path, monkeypatch, lead):
    called, decisions, _ = asks(tmp_path, monkeypatch, register=APPROVED_CLASS, lead=lead)
    assert called == [("a_lead", "cdx_timestamp")]
    assert "### Approve a_lead / cdx_timestamp" in decisions


def test_the_dry_run_says_whether_it_would_ask(tmp_path, capsys):
    incoming, register = world(
        tmp_path, lead=dict(LEAD, standing=STANDING), register=APPROVED_CLASS
    )
    request.main([str(incoming), "--register", str(register)])
    assert "no ask: the standing rule decides it" in capsys.readouterr().out
    (tmp_path / "approvals.md").write_text(REGISTER, encoding="utf-8")
    request.main([str(incoming), "--register", str(register)])
    assert "and ask" in capsys.readouterr().out


def test_every_block_left_pending_after_the_standing_rule_has_its_ask(tmp_path):
    """The live gate's invariant on a scratch register: the request writes a block with no
    ask only where the standing rule then decides it, so nothing pending goes unsurfaced."""
    from ark import approvals

    decisions = tmp_path / "key-decisions.md"
    decisions.write_text(DECISIONS, encoding="utf-8")
    world(tmp_path, lead=dict(LEAD, standing=STANDING), register=APPROVED_CLASS)
    world(tmp_path, lead=dict(LEAD, slug="b-lead"), register=APPROVED_CLASS, slug="b-lead")
    world(
        tmp_path,
        lead=dict(LEAD, slug="c-lead", evidence_class="link_target"),
        register=APPROVED_CLASS,
        slug="c-lead",
    )
    incoming, register = tmp_path / "incoming", tmp_path / "approvals.md"
    write(incoming, register, "--decisions", str(decisions))
    standing_rule.main([str(incoming), "--register", str(register), "--write"])
    assert approvals.load(register)[("a_lead", "cdx_timestamp")].decision == "master"
    left = [f"{a.source_name} / {a.evidence_type}" for a in approvals.pending(register)]
    assert left == ["b_lead / cdx_timestamp"]
    assert all(f"### Approve {name}" in decisions.read_text() for name in left)


@pytest.mark.parametrize(
    "slug, sidecar", [("a_lead", "a_lead"), ("a-lead", "another-name")], ids=["dir", "sidecar"]
)
def test_a_block_written_with_no_ask_is_the_one_the_standing_rule_decides(tmp_path, slug, sidecar):
    """The block is named after the directory, so the standing rule finds it and reads the
    lead there, whatever the sidecar calls the find; else it would stay pending, unasked."""
    from ark import approvals

    incoming, register = world(
        tmp_path, lead=dict(LEAD, standing=STANDING), register=APPROVED_CLASS, slug=slug
    )
    finding = json.loads((incoming / slug / "finding.json").read_text())
    (incoming / slug / "finding.json").write_text(json.dumps(dict(finding, slug=sidecar)))
    write(incoming, register)
    standing_rule.main([str(incoming), "--register", str(register), "--write"])
    assert approvals.pending(register) == []
    assert approvals.load(register)[("a_lead", "cdx_timestamp")].decision == "master"


# The figure: the standing rule's finds, by its figure.


def test_both_scripts_choose_the_same_finds_by_the_same_figure(tmp_path):
    world(tmp_path, slug="store-only")
    world(tmp_path, slug="both", program=7020.0)
    world(tmp_path, slug="program-only", ee=None, program=7020.0)
    world(tmp_path, slug="disputed", verify="disputed", program=7020.0)
    world(tmp_path, slug="closed", verdict="CLOSED", program=7020.0)
    incoming = tmp_path / "incoming"
    (incoming / "_unread").mkdir()
    for outcomes, figure, chosen in [
        ([], "store", ["both", "store-only"]),
        (AGREEING, "program", ["both", "program-only"]),
    ]:
        picked = request.candidates(incoming, outcomes)
        rule = standing_rule.confirmed_finds(incoming, outcomes)
        assert [lead_dir.name for lead_dir, *_ in picked] == chosen
        assert [find["dir"].name for find in rule.values()] == chosen
        assert all(find["figure"] == figure for *_, find in picked)


def test_under_the_streak_the_block_carries_the_program_figure(tmp_path):
    fleet = ledger(tmp_path, AGREEING)
    text = write(*world(tmp_path, ee=None, program=7020.0), "--fleet", str(fleet))
    assert "7,020.0 EE net-new by the program on the pushed snapshot" in text
    assert "The live store re-price by `price_items.py` said no figure" in text
    assert "the program's figure is the one to read" in text
    assert "- potential: 7020" in text


def test_the_open_entry_carries_the_deciding_figure(tmp_path):
    fleet = ledger(tmp_path, AGREEING)
    decisions = tmp_path / "key-decisions.md"
    decisions.write_text(DECISIONS, encoding="utf-8")
    incoming, register = world(tmp_path, program=7020.0)
    write(incoming, register, "--fleet", str(fleet), "--decisions", str(decisions))
    text = decisions.read_text(encoding="utf-8")
    assert "7,020.0 EE net-new by the program on the pushed snapshot" in text
    assert "Worth: 7020 EE." in text


def read_world(tmp_path, monkeypatch, receipt=True):
    """A lead the fleet read whole: `read.json` beside the finding, parts pulled locally."""
    incoming, register = world(tmp_path, lead=dict(LEAD, evidence_class="artifact_listing"))
    (incoming / "a-lead" / "read.json").write_text("{}", encoding="utf-8")
    pulled = tmp_path / "fleet_read"
    monkeypatch.setattr(request, "FLEET_READ", pulled)
    if receipt:
        (pulled / "a-lead").mkdir(parents=True)
        (pulled / "a-lead" / "receipt.json").write_text(
            json.dumps({"journal_sha256": "ab" * 32, "parts": [{}, {}], "lines": 1234}),
            encoding="utf-8",
        )
    return incoming, register


def test_a_read_lead_asks_for_its_hostname_source_with_the_ingest_line(tmp_path, monkeypatch):
    from ark import approvals

    incoming, register = read_world(tmp_path, monkeypatch)
    text = write(incoming, register)
    block = text.split("### fleet_a_lead_hostnames / cdx_timestamp", 1)[1].split("\n### ")[0]
    assert f"- ingest: ark ingest-hostnames {tmp_path / 'fleet_read' / 'a-lead'}/" in block
    assert f"- journal sha256: {'ab' * 32}, 2 part(s), 1,234 rows" in block
    assert "- ingest spec:" not in block and "- journal: `" not in block
    parsed = approvals.load(register)
    assert parsed[("fleet_a_lead_hostnames", "cdx_timestamp")].decision == "pending"
    assert ("a_lead", "artifact_listing") not in parsed


def test_a_read_lead_whose_parts_never_arrived_says_so(tmp_path, monkeypatch):
    text = write(*read_world(tmp_path, monkeypatch, receipt=False))
    assert "- journal sha256: no receipt on this machine, 0 part(s)" in text
