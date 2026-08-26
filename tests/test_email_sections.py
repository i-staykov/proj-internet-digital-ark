"""The round's email prose comes from a tracked file, not from typing into the draft.

`private/email-draft.md` is regenerated from its template on every fill, so prose typed
straight into the draft is destroyed by the next run. That happened once and the email
had to be rewritten from a copy kept elsewhere, which is the whole reason
`docs/email-sections.md` exists.
"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("fill_report", ROOT / "scripts" / "fill_report.py")
fill_report = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fill_report)

STUB = "<!-- ROUND [ROUND]: write this one. -->"


def test_sections_are_read_in_file_order(tmp_path) -> None:
    path = tmp_path / "s.md"
    path.write_text(
        "# head\n\nintro\n\n## opening\n\nfirst block\n\n## substance\n\nsecond block\n"
    )
    assert fill_report.written_sections(path) == ["first block", "second block"]


def test_a_missing_file_is_not_an_error(tmp_path) -> None:
    assert fill_report.written_sections(tmp_path / "absent.md") == []


def test_each_stub_is_satisfied_by_the_matching_section(tmp_path, monkeypatch) -> None:
    sections = tmp_path / "s.md"
    sections.write_text("## a\n\nALPHA\n\n## b\n\nBETA\n")
    monkeypatch.setattr(fill_report, "EMAIL_SECTIONS", sections)
    template = tmp_path / "t.md"
    template.write_text(f"top\n{STUB}\nmid\n{STUB}\nend\n")
    target = tmp_path / "out.md"
    remaining = fill_report.fill(template, target, {"ROUND": "6"}, check=False, stubs_fatal=True)
    assert remaining == [], remaining
    body = target.read_text()
    assert "ALPHA" in body and "BETA" in body
    assert "<!-- ROUND" not in body


def test_an_unsatisfied_stub_is_still_reported(tmp_path, monkeypatch) -> None:
    """Two stubs and one section must not silently look finished."""
    sections = tmp_path / "s.md"
    sections.write_text("## only\n\nONE\n")
    monkeypatch.setattr(fill_report, "EMAIL_SECTIONS", sections)
    template = tmp_path / "t.md"
    template.write_text(f"top\n{STUB}\nmid\n{STUB}\nend\n")
    remaining = fill_report.fill(
        template, tmp_path / "out.md", {"ROUND": "6"}, check=False, stubs_fatal=True
    )
    assert any("UNWRITTEN_ROUND_SECTIONS" in r for r in remaining), remaining


def test_the_live_sections_file_covers_the_live_email_template() -> None:
    """The real files, because a mismatch here is what makes a round's email hand-work."""
    template = ROOT / "private" / "email.template.md"
    if not template.is_file():
        return  # private/ is git-ignored; a fresh clone has no template
    stubs = len(fill_report.UNWRITTEN_SECTION.findall(template.read_text()))
    assert len(fill_report.written_sections()) >= stubs, (
        f"{stubs} stub(s) in the email template but fewer sections in "
        f"{fill_report.EMAIL_SECTIONS}, so the draft will need hand-work"
    )
