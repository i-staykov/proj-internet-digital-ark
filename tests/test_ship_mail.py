"""The mail draft carries the due reminders and his record, and a rehearsal writes nothing."""

import importlib.util
import re
from datetime import date
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "ship_mail", Path(__file__).resolve().parents[1] / "scripts/round/ship_mail.py"
)
ship_mail = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ship_mail)

QUESTIONS = """| asked-on | question | status | remind-on |
|---|---|---|---|
| 2026-09-02 | Do both hold? | open (interim: yes) | phase-8 mail |
| 2026-08-01 | Answered one | answered ("yes") | 2026-08-09 |
| draft | Which release starts the clock? | open | 2026-09-30 |
| 2026-07-01 | Withdrawn one | withdrawn | phase-8 mail |
"""
ROUNDS = """| round | sent EE | awarded p_i | S_i computed | S_i quoted | note |
|---|---|---|---|---|---|
| 1 | n/a | 17.38 | 28.966667 | not quoted | record percentage |
| 2 | n/a | n/a | n/a | n/a | never scored |
| 6 | 713,481.4198 | 4.130718 | 6.884530 | 6.88 | matches |
| 7 | 1,458,263.2088 | 7.562846 | 6.302372 | 6.302372 | matches |
"""


@pytest.mark.parametrize(
    ("today", "due"),
    [
        (date(2026, 9, 3), ["Do both hold?"]),
        (date(2026, 9, 30), ["Do both hold?", "[DRAFT"]),
        (date(2026, 10, 1), ["Do both hold?", "[DRAFT"]),
    ],
    ids=["event-named-due-dated-not-yet", "dated-due-on-its-day", "dated-due-once-passed"],
)
def test_only_open_and_due_questions_are_reminded(today, due) -> None:
    lines = ship_mail.reminders(QUESTIONS, today)
    assert len(lines) == len(due), lines
    assert all(text in line for text, line in zip(due, lines, strict=True))


def test_the_record_is_summed_from_his_columns_found_by_name() -> None:
    lines = "\n".join(ship_mail.cumulative(ROUNDS))
    # 17.38 + 4.130718 + 7.562846, the three rows with a number in `awarded p_i`
    assert "29.073564% in total" in lines and "3 scored rounds (1, 6, 7)" in lines
    assert "RECORDS" in lines, "round 1 is not commensurable and the draft must say so"
    assert "6.88 + 6.302372 = 13.182372" in lines
    moved = re.sub(r"^(\|[^|]*\|)", r"\1 new |", ROUNDS, flags=re.M)
    assert "| round | new |" in moved
    assert ship_mail.cumulative(moved) == ship_mail.cumulative(ROUNDS)


def test_a_rehearsal_writes_nothing_and_write_saves_one_draft(tmp_path, capsys) -> None:
    archive = tmp_path / "delivery.tar.gz"
    archive.write_bytes(b"x")
    archive.with_suffix(".gz.sha256").write_text("abc123  delivery.tar.gz\n", encoding="utf-8")
    drafts = tmp_path / "drafts"
    argv = ["--today", "2026-09-03", "--out-dir", str(drafts), "--archive", str(archive)]
    files = {"questions": QUESTIONS, "rounds": ROUNDS, "body": "The five figures.\n"}
    for flag, text in files.items():
        (tmp_path / f"{flag}.md").write_text(text, encoding="utf-8")
        argv += [f"--{flag}", str(tmp_path / f"{flag}.md")]
    assert ship_mail.main(argv) == 0
    assert not drafts.exists(), "a rehearsal must not leave a draft behind"
    printed = capsys.readouterr().out
    assert "Do both hold?" in printed and "1 question(s) due" in printed
    assert ship_mail.main(["--write", *argv]) == 0
    [draft] = drafts.glob("*.md")
    text = draft.read_text(encoding="utf-8")
    assert "The five figures." in text
    assert "abc123" in text, "the checksum beside the archive belongs in the mail"
