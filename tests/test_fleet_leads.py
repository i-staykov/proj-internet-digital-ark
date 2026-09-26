"""Writing a lead's fate back into the fleet's queue, and refusing to write the rest.

Quiet in both directions: a settled lead left `verified` is re-dealt for ever, and an
unsettled one marked `banked` disappears from the queue while still waiting on a human. The
interesting cases are the ones in between.

A write is checked by the fleet's own `scripts/contract.py` and `schemas/`, copied into each
scratch fleet from the clone `$ARK_FLEET` names, so the tests that write skip where there is
no clone.
"""

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/harness/fleet_leads.py"

_SPEC = importlib.util.spec_from_file_location("fleet_leads", SCRIPT)
leads = importlib.util.module_from_spec(_SPEC)
sys.modules["fleet_leads"] = leads
_SPEC.loader.exec_module(leads)

FLEET_CLONE = Path(
    os.environ.get("ARK_FLEET") or Path.home() / "Documents/GitHub/ark-fleet"
).expanduser()

LEAD = {
    "slug": "a-lead",
    "lens": "registry publications",
    "status": "verified",
    "scouted_at": "2026-09-09T00:00:00Z",
    "artifact": {
        "url": "https://example.invalid/x",
        "host": "example.invalid",
        "bytes": 10,
        "content_type": "text/plain",
        "terms_url": "https://example.invalid/terms",
        "robots": "allowed",
        "risk": "low",
    },
    "grain": "hostname",
    "evidence_class": "cdx_timestamp",
    "what_dates_one_item": "1999-05-04T11:02:13Z",
    "sample_record": "example.invalid 19990504",
    "size_estimate": {"items": 10, "ee_low": 1.0, "ee_high": 2.0},
    "floor": 1000.0,
    "history": [{"lane": "scout", "run_id": "17", "at": "2026-09-09T00:00:00Z"}],
}

CONFIRMED = {"verdict": "FIND", "verify": {"status": "confirmed"}}


def with_contract(fleet: Path) -> Path:
    """The fleet's validator and schemas, copied in; the clone itself is only read."""
    if not (FLEET_CLONE / "scripts/contract.py").is_file():
        pytest.skip("no ark-fleet clone beside this checkout, so no validator to copy")
    (fleet / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(FLEET_CLONE / "scripts/contract.py", fleet / "scripts/contract.py")
    shutil.copytree(FLEET_CLONE / "schemas", fleet / "schemas")
    return fleet


def outcomes(fleet: Path, *lines: dict) -> None:
    """Outcome lines in the fleet ledger's own month file, as the bank appends them."""
    (fleet / "ledger").mkdir(parents=True, exist_ok=True)
    with (fleet / "ledger/2026-09.jsonl").open("a", encoding="utf-8") as fh:
        for line in lines:
            row = {"kind": "outcome", "decision": "master", "at": "2026-09-26T00:00:00Z", **line}
            row["key"] = f"{row['slug']}:{row['decision']}:{row['banked']}"
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def world(tmp_path, slug: str, finding: dict, lead: dict | None = LEAD, contract: bool = True):
    incoming = tmp_path / "incoming"
    (incoming / slug).mkdir(parents=True)
    (incoming / slug / "finding.json").write_text(
        json.dumps(dict(finding, slug=slug)), encoding="utf-8"
    )
    fleet = tmp_path / "fleet"
    (fleet / "leads").mkdir(parents=True)
    if contract:
        with_contract(fleet)
    lead_file = fleet / "leads" / f"{slug}.json"
    if lead is not None:
        lead_file.write_text(json.dumps(dict(lead, slug=slug)), encoding="utf-8")
    return incoming, fleet, lead_file


def write(incoming, fleet) -> int:
    return leads.main([str(incoming), "--fleet", str(fleet), "--write"])


def status_of(lead_file: Path) -> str:
    return json.loads(lead_file.read_text(encoding="utf-8"))["status"]


def test_a_confirmed_find_with_a_banked_outcome_line_is_banked(tmp_path):
    incoming, fleet, lead_file = world(tmp_path, "a-lead", CONFIRMED)
    outcomes(fleet, {"slug": "a-lead", "decision": "pending", "banked": False})
    outcomes(fleet, {"slug": "a-lead", "banked": True})
    assert write(incoming, fleet) == 0
    assert status_of(lead_file) == "banked"


@pytest.mark.parametrize(
    "banked",
    [False, "true", 1],
    ids=["banked-false", "the-string-true", "the-number-one"],
)
def test_only_a_json_true_banks_a_confirmed_find(tmp_path, banked):
    """The ledger keys a line with `str()`, so a string or a number reaches it intact and
    would read as a booking to anything testing truthiness."""
    incoming, fleet, lead_file = world(tmp_path, "a-lead", CONFIRMED)
    outcomes(fleet, {"slug": "a-lead", "banked": banked})
    write(incoming, fleet)
    assert status_of(lead_file) == "verified"


def test_a_confirmed_find_still_waiting_on_ivo_is_left_alone(tmp_path):
    """No outcome line, or one for another slug, is a find not banked yet."""
    incoming, fleet, lead_file = world(tmp_path, "slow-lead", CONFIRMED)
    outcomes(fleet, {"slug": "a-lead", "banked": True})
    write(incoming, fleet)
    assert status_of(lead_file) == "verified"


def test_every_lead_the_ledger_banks_is_banked_not_only_the_drains(tmp_path, capsys):
    """The owner approves a parked find, or the store ingests it, after its drain has left
    `incoming/`: its lead is banked off the ledger with no finding in sight."""
    incoming, fleet, drained = world(tmp_path, "in-drain", {"verdict": "CLOSED"})
    earlier = fleet / "leads" / "approved-later.json"
    earlier.write_text(json.dumps(dict(LEAD, slug="approved-later")), encoding="utf-8")
    done = fleet / "leads" / "done-already.json"
    done.write_text(json.dumps(dict(LEAD, slug="done-already", status="banked")), "utf-8")
    waiting = fleet / "leads" / "still-pending.json"
    waiting.write_text(json.dumps(dict(LEAD, slug="still-pending")), encoding="utf-8")
    outcomes(
        fleet,
        {"slug": "approved-later", "decision": "pending", "banked": False},
        {"slug": "approved-later", "banked": True},
        {"slug": "done-already", "banked": True},
        {"slug": "in-drain", "banked": True},
        {"slug": "no-lead-file", "banked": True},
        {"slug": "still-pending", "decision": "pending", "banked": False},
    )
    before = done.read_text(encoding="utf-8")
    assert write(incoming, fleet) == 0
    assert status_of(earlier) == "banked"
    assert done.read_text(encoding="utf-8") == before, "a banked lead is not rewritten"
    assert status_of(waiting) == "verified"
    assert status_of(drained) == "closed", "the drain's own verdict decides its slug"
    assert not (fleet / "leads" / "no-lead-file.json").exists()
    assert "2 statuses written" in capsys.readouterr().out


def test_banked_slugs_come_from_outcome_lines_alone(tmp_path):
    """The register is not read: a banked set built from outcome lines, where the approvals
    register once decided it, and one that ignores every other kind of line."""
    fleet = tmp_path / "fleet"
    outcomes(
        fleet,
        {"slug": "a-lead", "banked": True},
        {"slug": "b-lead", "banked": "true"},
        {"slug": "c-lead", "decision": "pending", "banked": False},
    )
    with (fleet / "ledger/2026-09.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "legacy", "slug": "d-lead", "banked": True}) + "\n")
    assert leads.banked_slugs(fleet) == {"a-lead"}
    assert not hasattr(leads, "REGISTER")
    assert "approvals" not in SCRIPT.read_text(encoding="utf-8")


def test_a_measured_negative_is_closed(tmp_path):
    finding = {"verdict": "CLOSED", "reason": "everything is held"}
    incoming, fleet, lead_file = world(tmp_path, "a-lead", finding)
    write(incoming, fleet)
    assert status_of(lead_file) == "closed"


def test_a_disputed_find_is_closed_and_not_banked(tmp_path):
    finding = {"verdict": "FIND", "verify": {"status": "disputed"}}
    incoming, fleet, lead_file = world(tmp_path, "a-lead", finding)
    outcomes(fleet, {"slug": "a-lead", "banked": True})
    write(incoming, fleet)
    assert status_of(lead_file) == "closed"


def test_a_blocked_leg_is_work_to_redo_and_not_a_lead_to_bury(tmp_path):
    finding = {"verdict": "BLOCKED", "reason": "the fetch timed out"}
    incoming, fleet, lead_file = world(tmp_path, "a-lead", finding)
    write(incoming, fleet)
    assert status_of(lead_file) == "verified"


def test_every_other_field_of_the_lead_survives_and_no_history_entry_is_added(tmp_path):
    """The lead schema's history lanes are the fleet's legs, and the laptop is none of them."""
    finding = {"verdict": "CLOSED"}
    incoming, fleet, lead_file = world(tmp_path, "a-lead", finding)
    write(incoming, fleet)
    after = json.loads(lead_file.read_text(encoding="utf-8"))
    assert after["status"] == "closed"
    assert after["sample_record"] == LEAD["sample_record"]
    assert after["artifact"]["terms_url"] == LEAD["artifact"]["terms_url"]
    assert after["history"] == LEAD["history"]
    assert list(after) == list(LEAD), "rewritten key by key, in the order the fleet wrote"


def test_a_lead_that_fails_the_fleet_schema_is_not_written_and_is_named(tmp_path, capsys):
    """The history entry a laptop once wrote by hand, which the lead schema refuses three
    ways: a lane it does not know, no run id, and a key it has no place for."""
    bad = dict(LEAD, history=[{"lane": "laptop", "at": "2026-09-19T00:00:00Z", "note": "x"}])
    incoming, fleet, lead_file = world(tmp_path, "a-lead", {"verdict": "CLOSED"}, lead=bad)
    before = lead_file.read_text(encoding="utf-8")
    assert write(incoming, fleet) == 0
    assert lead_file.read_text(encoding="utf-8") == before
    out = capsys.readouterr().out
    assert "a-lead not written as closed" in out
    assert "laptop" in out
    assert "0 statuses written" in out and "1 refused" in out


def test_a_clone_with_no_validator_gets_nothing_written(tmp_path, capsys):
    incoming, fleet, lead_file = world(tmp_path, "a-lead", {"verdict": "CLOSED"}, contract=False)
    write(incoming, fleet)
    assert status_of(lead_file) == "verified"
    assert "no validator" in capsys.readouterr().out


def test_a_lead_the_fleet_clone_does_not_have_is_reported_not_created(tmp_path, capsys):
    finding = {"verdict": "CLOSED"}
    incoming, fleet, lead_file = world(tmp_path, "a-lead", finding, lead=None, contract=False)
    write(incoming, fleet)
    assert not lead_file.exists()
    assert "no lead file" in capsys.readouterr().out


def test_without_write_nothing_is_written(tmp_path, capsys):
    finding = {"verdict": "CLOSED"}
    incoming, fleet, lead_file = world(tmp_path, "a-lead", finding)
    leads.main([str(incoming), "--fleet", str(fleet)])
    assert status_of(lead_file) == "verified"
    assert "would write: a-lead is closed" in capsys.readouterr().out
