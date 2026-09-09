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


# --- which register a finding goes to, and how often -----------------------------


CLOSED_PROSE = """# a-scout-lead
verdict: CLOSED, 20.92 EE (22 net-new pairs of 553) against a 5,000 EE floor
lens: academic-datasets
what dates one item: the origin server's own HTTP `Date:` header
artifact: <http://example.invalid/webkb-data.gtar.gz>, the CMU data set
probe: 5,802 of 8,282 members carry a Date line; the rest are undated
"""


def closed_lead(tmp_path, prose: str = CLOSED_PROSE, lead: dict | None = None) -> Path:
    incoming = tmp_path / "incoming"
    lead_dir = incoming / "a-scout-lead"
    lead_dir.mkdir(parents=True)
    (lead_dir / "finding.md").write_text(prose, encoding="utf-8")
    if lead is not None:
        (lead_dir / "lead.json").write_text(json.dumps(lead), encoding="utf-8")
    return incoming


def test_a_measured_negative_gets_a_closed_row_not_an_all_na_row(tmp_path):
    findings = scribe.one_per_slug(scribe.findings_in(closed_lead(tmp_path)))
    row = scribe.closed_row(findings[0], "wave-1")
    assert row.startswith("| a-scout-lead / ")
    assert "lens academic-datasets" in row
    assert "20.92 EE" in row
    assert "http://example.invalid/webkb-data.gtar.gz" in row
    assert "n/a" not in row


def test_the_closed_row_prefers_the_leads_own_lens_and_class(tmp_path):
    lead = {"lens": "registry publications", "evidence_class": "artifact_listing"}
    findings = scribe.one_per_slug(scribe.findings_in(closed_lead(tmp_path, lead=lead)))
    row = scribe.closed_row(findings[0], "wave-1")
    assert "a-scout-lead / artifact_listing" in row
    assert "lens registry publications" in row


def test_a_negative_with_no_figure_reads_not_priced(tmp_path):
    prose = CLOSED_PROSE.replace("verdict: CLOSED, 20.92 EE", "verdict: CLOSED, 0 EE")
    findings = scribe.one_per_slug(scribe.findings_in(closed_lead(tmp_path, prose=prose)))
    assert "| not priced |" in scribe.closed_row(findings[0], "wave-1")


def test_one_row_per_slug_when_a_leg_directory_duplicates_the_lead(tmp_path):
    # The leg artifact's root is called `findings`, so its copy of a finding used to be
    # booked as a second lead and the same slug reached the register twice.
    incoming = tmp_path / "incoming"
    for name in ("a-lead", "findings"):
        d = incoming / name
        d.mkdir(parents=True)
        (d / "finding.md").write_text(PROSE, encoding="utf-8")
        (d / "finding.json").write_text(json.dumps(SIDECAR), encoding="utf-8")
    findings = scribe.one_per_slug(scribe.findings_in(incoming))
    assert [f["slug"] for f in findings] == ["a-lead"]


def test_a_find_outranks_a_measured_negative_for_the_same_slug(tmp_path):
    incoming = tmp_path / "incoming"
    for name, verdict in (("a-lead", "FIND"), ("copy", "CLOSED")):
        d = incoming / name
        d.mkdir(parents=True)
        (d / "finding.json").write_text(
            json.dumps(dict(SIDECAR, verdict=verdict)), encoding="utf-8"
        )
        (d / "finding.md").write_text(PROSE, encoding="utf-8")
    kept = scribe.one_per_slug(scribe.findings_in(incoming))
    assert len(kept) == 1 and kept[0]["verdict"] == "FIND"


def test_a_slug_already_in_a_register_is_not_booked_again(tmp_path, monkeypatch):
    register = tmp_path / "sources.md"
    register.write_text("## Evaluated and rejected\n\n|---|\n| a-lead | x |\n", "utf-8")
    closed = tmp_path / "sources-closed.md"
    closed.write_text("| source | date |\n|---|---|\n| a-scout-lead / x | y |\n", "utf-8")
    monkeypatch.setattr(scribe, "REGISTER", register)
    monkeypatch.setattr(scribe, "CLOSED", closed)
    assert {"a-lead", "a-scout-lead"} <= scribe.booked_slugs()
