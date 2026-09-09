"""The four conditions of the standing approval rule, one test each.

Writing a `Decision:` line is the one thing in the loop that grants a permission rather than
recording a measurement, and it happens in a public register with nobody watching. So the
test that matters is not that a decision can be written: it is that each condition, on its
own, is enough to stop one.
"""

import importlib.util
import json
import sys
from pathlib import Path

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

LEAD = {
    "slug": "new-source",
    "grain": "hostname",
    "what_dates_one_item": "Tue, 4 May 1999 11:02:13 +0100 in the Received header",
    "artifact": {
        "url": "https://example.invalid/list",
        "terms_url": "https://example.invalid/terms",
        "robots": "allowed",
    },
}


def setup(tmp_path, lead=None, register=REGISTER, **finding_over) -> tuple[Path, Path, Path]:
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
        json.dumps({"status": "priced", "ee": 7000.0}), encoding="utf-8"
    )
    fleet = tmp_path / "fleet"
    (fleet / "leads").mkdir(parents=True)
    if lead is not None:
        (fleet / "leads" / "new-source.json").write_text(json.dumps(lead), encoding="utf-8")
    path = tmp_path / "approvals.md"
    path.write_text(register, encoding="utf-8")
    return incoming, fleet, path


def decide(tmp_path, **kwargs) -> tuple[int, str, str]:
    incoming, fleet, register = setup(tmp_path, **kwargs)
    out = []
    code = rule.main([str(incoming), "--fleet", str(fleet), "--register", str(register), "--write"])
    out.append(register.read_text(encoding="utf-8"))
    return code, out[0], str(register)


def test_all_four_conditions_hold_so_the_line_is_written_and_the_rule_is_cited(tmp_path, capsys):
    _, text, _ = decide(tmp_path, lead=LEAD)
    assert "Decision: pending" not in text
    assert text.count("Decision: master") == 2
    assert "CLAUDE.md rule 7" in text
    # The stamp is quoted, which is the rule's own wording, and the terms are named.
    assert '"Tue, 4 May 1999 11:02:13 +0100 in the Received header"' in text
    assert "https://example.invalid/terms" in text
    assert "decided: new_source" in capsys.readouterr().out


def test_a_class_nobody_has_approved_before_stays_pending(tmp_path, capsys):
    register = REGISTER.replace("### old_source / cdx_timestamp", "### old_source / link_source")
    _, text, _ = decide(tmp_path, lead=LEAD, register=register)
    assert "Decision: pending" in text
    assert "no other cdx_timestamp source is approved as master" in capsys.readouterr().out


def test_a_stamp_with_no_digit_in_it_is_a_category_and_stays_pending(tmp_path, capsys):
    lead = dict(LEAD, what_dates_one_item="the Received headers carry a date")
    _, text, _ = decide(tmp_path, lead=lead)
    assert "Decision: pending" in text
    assert "names a category" in capsys.readouterr().out


def test_terms_nobody_recorded_stay_pending(tmp_path, capsys):
    lead = dict(LEAD, artifact=dict(LEAD["artifact"], terms_url=None))
    _, text, _ = decide(tmp_path, lead=lead)
    assert "Decision: pending" in text
    assert "no terms page" in capsys.readouterr().out


def test_robots_that_refused_stays_pending(tmp_path, capsys):
    lead = dict(LEAD, artifact=dict(LEAD["artifact"], robots="refused"))
    _, text, _ = decide(tmp_path, lead=lead)
    assert "Decision: pending" in text
    assert "robots is refused" in capsys.readouterr().out


def test_a_find_the_verify_lane_disputed_is_not_a_candidate_at_all(tmp_path, capsys):
    _, text, _ = decide(tmp_path, lead=LEAD, verify={"status": "disputed", "reason": "no"})
    assert "Decision: pending" in text
    assert "nothing to decide" in capsys.readouterr().out


def test_a_find_the_laptop_could_not_reprice_is_not_a_candidate_either(tmp_path):
    incoming, fleet, register = setup(tmp_path, lead=LEAD)
    (incoming / "new-source" / "store_price.json").write_text(
        json.dumps({"status": "no items shipped", "ee": None}), encoding="utf-8"
    )
    rule.main([str(incoming), "--fleet", str(fleet), "--register", str(register), "--write"])
    assert "Decision: pending" in register.read_text(encoding="utf-8")


def test_without_write_nothing_is_touched(tmp_path, capsys):
    incoming, fleet, register = setup(tmp_path, lead=LEAD)
    before = register.read_text(encoding="utf-8")
    rule.main([str(incoming), "--fleet", str(fleet), "--register", str(register)])
    assert register.read_text(encoding="utf-8") == before
    assert "would decide: new_source" in capsys.readouterr().out
