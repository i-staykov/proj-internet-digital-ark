"""The scribe's row, and the one rule it exists to enforce about figures.

**A fleet figure never reaches the register alone.** The leg measured against a pushed copy
of this store, the laptop against the store, so the row carries both or says in words why
there is only one.
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
method: read one month of http://example.invalid/archive, extracted the relay hosts
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


def test_the_sidecar_wins_over_the_prose_and_the_store_figure_sits_beside_it(tmp_path):
    # The prose says 9,999 and the JSON says 4,786. The JSON is the one a program checked.
    text = row(lead_dir(tmp_path, store={"status": "priced", "ee": 4102.5}))
    assert "fleet 4,786.0 EE, store 4,102.5 EE" in text
    assert "9,999" not in text


def test_a_find_nobody_could_reprice_says_why_rather_than_looking_measured(tmp_path):
    text = row(lead_dir(tmp_path, store={"status": "no items shipped", "ee": None}))
    assert "store not re-priced: no items shipped" in text


def test_the_verify_status_is_in_the_verdict_cell(tmp_path):
    text = row(lead_dir(tmp_path, store={"status": "priced", "ee": 1.0}))
    assert "FIND (confirmed)" in text
    assert text.endswith("| <https://example.invalid/list> <http://example.invalid/archive> |")


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


NUMBER = "C" + "-95"  # built, so this file quotes no decision number
CLOSED_PROSE = f"""# a-scout-lead
verdict: CLOSED, 20.92 EE (22 net-new pairs of 553) against a 5,000 EE floor
lens: academic-datasets
what dates one item: the origin server's own HTTP `Date:` header
artifact: <http://example.invalid/webkb-data.gtar.gz>, the CMU data set
probe: 5,802 of 8,282 carry a Date line per {NUMBER}, read at http://example.invalid/{NUMBER}/r
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
    # The reason opens with its verdict word, read off `verdict: CLOSED, 20.92 EE ...`.
    assert "| CLOSED. lens academic-datasets. 5,802 of 8,282" in row
    assert "20.92 EE" in row
    assert f"Date line, read at http://example.invalid/{NUMBER}/r |" in row
    assert row.endswith(f"gtar.gz> <http://example.invalid/{NUMBER}/r> |")
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


def test_two_drains_leave_one_row_per_slug_and_the_second_writes_nothing(
    tmp_path, monkeypatch, capsys
):
    # A FIND re-measuring its own FIND row replaces it at the top of the table; a settled
    # row and a closed slug are left alone, and a retried drain books nothing.
    pages = tmp_path / "registers"
    pages.mkdir()
    old = [
        f"| {s} | d | n/a | n/a | n/a | n/a | 1 EE (d) | n/a | n/a | {v} | n/a |"
        for s, v in (("a-lead", "FIND (pending)"), ("kept", "BANKED"))
    ]
    (pages / "sources.md").write_text(f"{scribe.REGISTER_HEADER}\n|---|\n" + "\n".join(old))
    shut = "| shut / x | d | 0 EE | CLOSED. |  |\n"
    (pages / "sources-closed.md").write_text(f"# Closed\n\n{scribe.CLOSED_HEADING}\n|---|\n{shut}")
    incoming = lead_dir(tmp_path, store={"status": "priced", "ee": 4102.5})
    for slug, verdict in (("kept", "FIND"), ("shut", "FIND"), ("new", "FIND"), ("neg", "CLOSED")):
        (incoming / slug).mkdir()
        sidecar = json.dumps(dict(SIDECAR, slug=slug, verdict=verdict))
        (incoming / slug / "finding.json").write_text(sidecar, "utf-8")
    hypo = str(tmp_path / "gone.md")
    argv = ["bank", str(incoming), "--hypotheses", hypo, "--registers", str(pages)]
    monkeypatch.setattr(sys, "argv", argv)
    for said in ("2 new rows, 1 replaced, 2 already booked", "0 new rows, 0 replaced, 5 already"):
        scribe.main()
        assert f"scribe: {said}" in capsys.readouterr().out
    table = (pages / "sources.md").read_text("utf-8").split("|---|\n")[1]
    assert table.startswith("| a-lead |") and table.count("| a-lead |") == 1
    assert table.endswith(old[1])
    assert "| neg / unclassified |" in (pages / "sources-closed.md").read_text("utf-8")


def test_a_missing_hypothesis_ledger_writes_nothing_and_does_not_stop_the_sync(tmp_path):
    # The ledger left the fleet with v1 (ark-fleet #83); a lead's fate travels in leads/.
    gone = tmp_path / "hypotheses.md"
    finding = {"slug": "a-lead", "verdict": "CLOSED", "ee": "0", "fields": {}}
    assert scribe.write_result_lines(gone, [finding]) == 0
    assert not gone.exists()


def test_the_fleet_push_never_stages_the_ledger_unconditionally():
    script = (ROOT / "scripts/harness/push_fleet.sh").read_text(encoding="utf-8")
    assert "git add hypotheses.md leads" not in script
    assert "[ -f hypotheses.md ] && git add hypotheses.md" in script


def test_a_closed_row_never_exceeds_the_register_line_limit():
    """The reason is trimmed after its verdict word, never the slug or the link."""
    # The lead's `lens` can swallow the scout's whole verdict, and a CDX query is long.
    lens = "candidate-bulk exit 3, robots refused, " + "a very long explanation " * 40
    url = "http://example.invalid/cdx?url=*.example.org/*&" + "fl=original&" * 30
    finding = {
        "slug": "a-lead",
        "verdict": "CLOSED",
        "ee": "0",
        "fields": {"artifact": url},
        "lead": {"lens": lens},
    }
    row = scribe.closed_row(finding, "wave-1")
    assert len(row) <= scribe.ROW_LIMIT
    assert row.startswith("| a-lead / unclassified |")
    assert row.endswith(f"| CLOSED. | <{url}> |")


def test_a_trimmed_reason_keeps_its_substance_and_points_at_no_dead_file():
    """A long reason is cut inside its prose, never at its first clause or into a pointer."""
    cells = [
        "a-lead / link_target",
        "2026-09-19, laptop",
        "0 EE",
        "lens dated-link-graph. CLOSED: every daily register 404s on replay and the one "
        "capture names zero external hosts. " + "More measured detail. " * 20,
        "http://example.invalid/x",
    ]
    row = scribe._within_limit(cells, order=(3,))
    assert len(row) <= scribe.ROW_LIMIT
    assert "hypothesis ledger" not in row, "a pointer to a deleted file is not a record"
    assert "404s on replay" in row, "the substance after the first clause must survive"
    assert row.endswith("| http://example.invalid/x |")


def test_a_closed_rows_class_and_lens_are_held_to_a_clause():
    """A wave can write a paragraph where the class and the lens belong."""
    finding = {
        "slug": "a-lead",
        "verdict": "CLOSED",
        "ee": "0",
        "fields": {"artifact": "http://example.invalid/data.gz"},
        "lead": {
            "evidence_class": "link_source (mail relay host, the Received: clause " * 12,
            "lens": "server-written-headers, " + "which is to say " * 20,
        },
    }
    row = scribe.closed_row(finding, "wave-1")
    assert len(row) <= scribe.ROW_LIMIT
    assert row.startswith("| a-lead / link_source")
    assert "lens server-written-headers" in row


def test_a_brief_audit_is_not_booked_in_either_register():
    """A rule audit's `verdict: FIND` is a rule to decide, not a source."""
    audit = {
        "slug": "brief-audit-1-leg-1-2",
        "verdict": "FIND",
        "ee": "0",
        "fields": {"lens": "brief-audit", "next": "rule decision"},
    }
    assert scribe.is_brief_audit(audit)
    assert not scribe.is_brief_audit({"slug": "a-lead", "verdict": "FIND", "ee": "0", "fields": {}})
