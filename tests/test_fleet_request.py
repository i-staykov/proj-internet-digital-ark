"""The block a fleet FIND needs before anything can decide it.

Without it the loop stops one step short and looks complete: a row in `sources.md`, a
confirmed FIND and no `Decision:` line, so the standing rule finds nothing to flip and Ivo is
asked nothing. The tests pin what the block must not do: no invented spec, no invented terms,
no second block for a source already decided.
"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/harness/fleet_request.py"

_SPEC = importlib.util.spec_from_file_location("fleet_request", SCRIPT)
request = importlib.util.module_from_spec(_SPEC)
sys.modules["fleet_request"] = request
_SPEC.loader.exec_module(request)

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


def world(tmp_path, lead=LEAD, ee=7000.0, verify="confirmed", verdict="FIND"):
    incoming = tmp_path / "incoming"
    lead_dir = incoming / "a-lead"
    lead_dir.mkdir(parents=True)
    (lead_dir / "finding.json").write_text(
        json.dumps(
            {
                "slug": "a-lead",
                "run_id": "1741",
                "verdict": verdict,
                "pricing": {"ee": 900000.0, "track": "annual"},
                "verify": {"status": verify, "reason": "re-ran it"},
            }
        ),
        encoding="utf-8",
    )
    (lead_dir / "store_price.json").write_text(
        json.dumps({"status": "priced", "ee": ee, "netnew": 12, "pricer": "price_items.py"}),
        encoding="utf-8",
    )
    if lead is not None:
        (lead_dir / "lead.json").write_text(json.dumps(lead), encoding="utf-8")
    register = tmp_path / "approvals.md"
    register.write_text(REGISTER, encoding="utf-8")
    return incoming, register


def write(incoming, register) -> str:
    request.main([str(incoming), "--register", str(register), "--write"])
    return register.read_text(encoding="utf-8")


def test_a_confirmed_repriced_find_gets_a_pending_block(tmp_path):
    text = write(*world(tmp_path))
    assert "### a_lead / cdx_timestamp" in text
    assert "- potential: 7000" in text


def test_the_rest_of_the_register_survives_the_insert(tmp_path):
    # The insert once truncated the file at the heading it wrote under, which loses every
    # block below it: the whole pending queue.
    text = write(*world(tmp_path))
    assert "### old_source / cdx_timestamp" in text
    assert text.count("Decision: pending") == 2


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
    assert request.surface("dk_zone", "artifact_listing", lead, store, decisions)
    text = decisions.read_text()
    assert "### Approve dk_zone / artifact_listing" in text
    assert "9,702.6 EE net-new on the live store" in text
    assert not request.surface("dk_zone", "artifact_listing", lead, store, decisions), "once"


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
