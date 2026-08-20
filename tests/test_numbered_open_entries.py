"""A numbered OPEN heading must not read as a decided one.

Ivo's rewrite of 2026-08-20 numbers the entries `(O1)` upward at the end of the
heading, because both this cycle and `test_the_live_triage_entry_agrees_with_itself`
match on a heading's opening words. Equality against the still-pending set then
failed, and the cycle told him to close an entry that was still waiting on him.
Acting on that would have stranded the journal the approval gate protects.
"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dc", ROOT / "scripts" / "discover_cycle.py")
dc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dc)


DOC = """# Decisions

## OPEN

### Approve, refuse or downgrade internic_zone / artifact_listing  (O1)

Body.

### Triage the newly found sources: 60 found  (O4)

**60 source(s) found and not yet priced**.

---

## CLOSED
"""


def _titles(tmp_path):
    doc = tmp_path / "key-decisions.md"
    doc.write_text(DOC, encoding="utf-8")
    return doc


def test_a_numbered_heading_still_matches_its_pending_class(tmp_path, monkeypatch) -> None:
    doc = _titles(tmp_path)
    monkeypatch.setattr(dc, "DECISIONS_DOC", doc)
    still_pending = {"internic_zone / artifact_listing"}
    stale = [
        title
        for title in dc.key_decisions.open_titles(doc)
        if "Approve, refuse or downgrade " in title
        and not any(needle in title for needle in still_pending)
    ]
    assert stale == [], f"a numbered heading was read as decided: {stale}"


def test_a_numbered_triage_heading_is_still_recognised(tmp_path) -> None:
    doc = _titles(tmp_path)
    titles = dc.key_decisions.open_titles(doc)
    assert any(dc.TRIAGE_HEADING in title for title in titles)
    assert not any(title == dc.TRIAGE_HEADING for title in titles), (
        "the numbered form is the one that needs covering; equality would pass trivially"
    )
