"""Writing a lead's fate back into the fleet's queue, and refusing to write the rest.

The failure this guards is quiet in both directions: a settled lead left `verified` is
re-dealt for ever, and an unsettled one marked `banked` disappears from the queue while
still waiting on a human. So the interesting cases are the ones in between.
"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/harness/fleet_leads.py"

_SPEC = importlib.util.spec_from_file_location("fleet_leads", SCRIPT)
leads = importlib.util.module_from_spec(_SPEC)
sys.modules["fleet_leads"] = leads
_SPEC.loader.exec_module(leads)

REGISTER = """# Approved sources

### a_lead / cdx_timestamp

Decision: master

### slow_lead / cdx_timestamp

Decision: pending
"""

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
    "history": [],
}


def world(tmp_path, slug: str, finding: dict, lead: dict | None = LEAD):
    incoming = tmp_path / "incoming"
    (incoming / slug).mkdir(parents=True)
    (incoming / slug / "finding.json").write_text(json.dumps(finding), encoding="utf-8")
    fleet = tmp_path / "fleet"
    (fleet / "leads").mkdir(parents=True)
    lead_file = fleet / "leads" / f"{slug}.json"
    if lead is not None:
        lead_file.write_text(json.dumps(dict(lead, slug=slug)), encoding="utf-8")
    register = tmp_path / "approvals.md"
    register.write_text(REGISTER, encoding="utf-8")
    return incoming, fleet, register, lead_file


def write(incoming, fleet, register) -> int:
    args = [str(incoming), "--fleet", str(fleet), "--register", str(register), "--write"]
    return leads.main(args)


def status_of(lead_file: Path) -> str:
    return json.loads(lead_file.read_text(encoding="utf-8"))["status"]


def test_a_confirmed_find_the_register_has_decided_is_banked(tmp_path):
    finding = {"slug": "a-lead", "verdict": "FIND", "verify": {"status": "confirmed"}}
    incoming, fleet, register, lead_file = world(tmp_path, "a-lead", finding)
    write(incoming, fleet, register)
    assert status_of(lead_file) == "banked"


def test_a_confirmed_find_still_waiting_on_ivo_is_left_alone(tmp_path):
    finding = {"slug": "slow-lead", "verdict": "FIND", "verify": {"status": "confirmed"}}
    incoming, fleet, register, lead_file = world(tmp_path, "slow-lead", finding)
    write(incoming, fleet, register)
    assert status_of(lead_file) == "verified"


def test_a_measured_negative_is_closed(tmp_path):
    finding = {"slug": "a-lead", "verdict": "CLOSED", "reason": "everything is held"}
    incoming, fleet, register, lead_file = world(tmp_path, "a-lead", finding)
    write(incoming, fleet, register)
    assert status_of(lead_file) == "closed"


def test_a_disputed_find_is_closed_and_not_banked(tmp_path):
    finding = {"slug": "a-lead", "verdict": "FIND", "verify": {"status": "disputed"}}
    incoming, fleet, register, lead_file = world(tmp_path, "a-lead", finding)
    write(incoming, fleet, register)
    assert status_of(lead_file) == "closed"


def test_a_blocked_leg_is_work_to_redo_and_not_a_lead_to_bury(tmp_path):
    finding = {"slug": "a-lead", "verdict": "BLOCKED", "reason": "the fetch timed out"}
    incoming, fleet, register, lead_file = world(tmp_path, "a-lead", finding)
    write(incoming, fleet, register)
    assert status_of(lead_file) == "verified"


def test_every_other_field_of_the_lead_survives(tmp_path):
    finding = {"slug": "a-lead", "verdict": "CLOSED"}
    incoming, fleet, register, lead_file = world(tmp_path, "a-lead", finding)
    write(incoming, fleet, register)
    after = json.loads(lead_file.read_text(encoding="utf-8"))
    assert after["sample_record"] == LEAD["sample_record"]
    assert after["artifact"]["terms_url"] == LEAD["artifact"]["terms_url"]


def test_a_lead_the_fleet_clone_does_not_have_is_reported_not_created(tmp_path, capsys):
    finding = {"slug": "a-lead", "verdict": "CLOSED"}
    incoming, fleet, register, lead_file = world(tmp_path, "a-lead", finding, lead=None)
    write(incoming, fleet, register)
    assert not lead_file.exists()
    assert "no lead file" in capsys.readouterr().out


def test_without_write_nothing_is_written(tmp_path, capsys):
    finding = {"slug": "a-lead", "verdict": "CLOSED"}
    incoming, fleet, register, lead_file = world(tmp_path, "a-lead", finding)
    leads.main([str(incoming), "--fleet", str(fleet), "--register", str(register)])
    assert status_of(lead_file) == "verified"
    assert "would write: a-lead is closed" in capsys.readouterr().out
