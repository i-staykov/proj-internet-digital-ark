"""The scribe's row, and the one rule it exists to enforce about figures.

**A fleet figure never reaches the register alone.** The leg measured against a pushed copy
of this store; the laptop measures against the store. So the row carries both, or it says in
words why there is only one. A row that printed a single unlabelled number would read exactly
like a measurement taken here, which is the confusion the whole S9 re-price exists to end.
"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/harness/bank_findings.py"

_SPEC = importlib.util.spec_from_file_location("bank_findings", SCRIPT)
scribe = importlib.util.module_from_spec(_SPEC)
sys.modules["bank_findings"] = scribe
_SPEC.loader.exec_module(scribe)

PROSE = """# a-lead
verdict: FIND
ee: 9,999
what dates one item: Tue, 4 May 1999 in the Received header
artifact: https://example.invalid/list
method: read one month, extracted the relay hosts
"""

SIDECAR = {
    "slug": "a-lead",
    "lane": "price",
    "run_id": "1741",
    "verdict": "FIND",
    "pricing": {"ee": 4786.0, "track": "annual"},
    "verify": {"status": "confirmed", "reason": "re-ran the command"},
}


def lead_dir(tmp_path, store: dict | None = None, sidecar: dict | None = SIDECAR) -> Path:
    incoming = tmp_path / "incoming"
    lead = incoming / "a-lead"
    lead.mkdir(parents=True)
    (lead / "finding.md").write_text(PROSE, encoding="utf-8")
    if sidecar is not None:
        (lead / "finding.json").write_text(json.dumps(sidecar), encoding="utf-8")
    if store is not None:
        (lead / "store_price.json").write_text(json.dumps(store), encoding="utf-8")
    return incoming


def row(incoming: Path) -> str:
    findings = scribe.findings_in(incoming)
    assert len(findings) == 1
    return scribe.register_row(findings[0], "wave-1")


def test_the_sidecar_wins_over_the_prose_on_the_figure(tmp_path):
    # The prose says 9,999 and the JSON says 4,786. The JSON is the one a program checked.
    text = row(lead_dir(tmp_path, store={"status": "priced", "ee": 4102.5}))
    assert "fleet 4,786.0 EE" in text
    assert "9,999" not in text


def test_the_store_figure_sits_beside_the_fleets(tmp_path):
    text = row(lead_dir(tmp_path, store={"status": "priced", "ee": 4102.5}))
    assert "store 4,102.5 EE" in text


def test_a_find_nobody_could_reprice_says_why_rather_than_looking_measured(tmp_path):
    text = row(lead_dir(tmp_path, store={"status": "no items shipped", "ee": None}))
    assert "store not re-priced: no items shipped" in text


def test_the_verify_status_is_in_the_verdict_cell(tmp_path):
    text = row(lead_dir(tmp_path, store={"status": "priced", "ee": 1.0}))
    assert "FIND (confirmed)" in text


def test_a_closed_finding_keeps_one_plain_figure(tmp_path):
    sidecar = dict(SIDECAR, verdict="CLOSED", pricing={"ee": 0.0, "track": "annual"})
    text = row(lead_dir(tmp_path, sidecar=sidecar))
    assert "0.0 EE" in text
    assert "store" not in text


def test_a_loose_markdown_finding_still_books_the_old_way(tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "old-lead.md").write_text(PROSE.replace("# a-lead", "# old-lead"), "utf-8")
    text = row(incoming)
    # No sidecar, so no second figure to name and no verify status to report.
    assert "9999 EE" in text
    assert "store" not in text


def test_a_lead_directory_with_only_a_sidecar_is_still_booked(tmp_path):
    incoming = tmp_path / "incoming"
    lead = incoming / "a-lead"
    lead.mkdir(parents=True)
    (lead / "finding.json").write_text(
        json.dumps({"slug": "a-lead", "verdict": "BLOCKED", "reason": "schema"}), encoding="utf-8"
    )
    text = row(incoming)
    assert "BLOCKED" in text and "schema" in text
