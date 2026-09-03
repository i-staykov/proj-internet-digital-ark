"""The mail draft carries the reminders and the record, and a rehearsal writes nothing.

The rehearsal property is the one worth a test: `just ship` is rehearsed on evenings when
nothing has been decided, and a rehearsal that wrote a draft would leave a half-figured mail
in the drafts folder for somebody to send.
"""

import importlib.util
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("ship_mail", ROOT / "scripts/round/ship_mail.py")
assert _spec and _spec.loader
ship_mail = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ship_mail)

QUESTIONS = """# Questions

| asked-on | question | status | remind-on |
|---|---|---|---|
| 2026-09-02 | Do both hold? | open (interim: yes) | phase-8 mail |
| 2026-08-01 | Answered one | answered ("yes") | 2026-08-09 |
| draft | Which release starts the clock? | open | 2026-09-30 |
| 2026-07-01 | Withdrawn one | withdrawn | phase-8 mail |
"""

ROUNDS = """# Rounds

| round | sent EE | awarded p_i | S_i computed | S_i quoted | note |
|---|---|---|---|---|---|
| 1 | n/a | 17.38 | 28.966667 | not quoted | record percentage |
| 2 | n/a | n/a | n/a | n/a | never scored |
| 6 | 713,481.4198 | 4.130718 | 6.884530 | 6.88 | matches |
| 7 | 1,458,263.2088 | 7.562846 | 6.302372 | 6.302372 | matches |
"""


def test_only_open_and_due_questions_are_reminded() -> None:
    lines = ship_mail.reminders(QUESTIONS, date(2026, 9, 3))
    assert len(lines) == 1, lines
    assert "Do both hold?" in lines[0]
    # The 2026-09-30 row is open and not yet due; the other two are not open.
    assert not any("clock" in line for line in lines)


def test_a_remind_date_that_has_passed_falls_due() -> None:
    lines = ship_mail.reminders(QUESTIONS, date(2026, 10, 1))
    assert len(lines) == 2
    assert "[DRAFT" in lines[1], "a row nobody has approved says so in the mail"


def test_a_remind_on_naming_an_event_is_due_at_the_next_mail() -> None:
    assert ship_mail.is_due("phase-8 mail", date(1996, 1, 1))
    assert ship_mail.is_due("2026-09-03", date(2026, 9, 3))
    assert not ship_mail.is_due("2026-09-04", date(2026, 9, 3))


def test_the_cumulative_record_is_summed_from_his_own_columns() -> None:
    lines = "\n".join(ship_mail.cumulative(ROUNDS))
    # 17.38 + 4.130718 + 7.562846, the three rows with a number in `awarded p_i`.
    assert "29.073564% in total" in lines
    assert "3 scored rounds (1, 6, 7)" in lines
    assert "RECORDS" in lines, "round 1 is not commensurable and the draft must say so"
    assert "6.88 + 6.302372 = 13.182372" in lines


def test_a_column_inserted_before_the_figures_does_not_shift_the_reading() -> None:
    lines = []
    for line in ROUNDS.splitlines():
        if line.startswith("|"):
            head, rest = line.split("|", 2)[1], line.split("|", 2)[2]
            line = f"|{head}| new |{rest}" if "---" not in head else f"|{head}|---|{rest}"
        lines.append(line)
    moved = "\n".join(lines)
    assert "| round | new |" in moved
    assert ship_mail.cumulative(moved) == ship_mail.cumulative(ROUNDS)


def test_a_rehearsal_prints_the_draft_and_writes_nothing(tmp_path: Path, capsys) -> None:
    out_dir = tmp_path / "drafts"
    questions = tmp_path / "questions.md"
    questions.write_text(QUESTIONS, encoding="utf-8")
    rounds = tmp_path / "rounds.md"
    rounds.write_text(ROUNDS, encoding="utf-8")
    code = ship_mail.main(
        [
            "--questions",
            str(questions),
            "--rounds",
            str(rounds),
            "--body",
            str(tmp_path / "absent.md"),
            "--out-dir",
            str(out_dir),
            "--today",
            "2026-09-03",
        ]
    )
    assert code == 0
    assert not out_dir.exists(), "a rehearsal must not leave a draft behind"
    printed = capsys.readouterr().out
    assert "Do both hold?" in printed
    assert "1 question(s) due" in printed


def test_write_saves_one_dated_draft(tmp_path: Path) -> None:
    out_dir = tmp_path / "drafts"
    body = tmp_path / "body.md"
    body.write_text("The five figures.\n", encoding="utf-8")
    questions = tmp_path / "questions.md"
    questions.write_text(QUESTIONS, encoding="utf-8")
    rounds = tmp_path / "rounds.md"
    rounds.write_text(ROUNDS, encoding="utf-8")
    archive = tmp_path / "delivery.tar.gz"
    archive.write_bytes(b"x")
    archive.with_suffix(".gz.sha256").write_text("abc123  delivery.tar.gz\n", encoding="utf-8")
    assert (
        ship_mail.main(
            [
                "--write",
                "--questions",
                str(questions),
                "--rounds",
                str(rounds),
                "--body",
                str(body),
                "--out-dir",
                str(out_dir),
                "--archive",
                str(archive),
                "--today",
                "2026-09-03",
            ]
        )
        == 0
    )
    drafts = list(out_dir.glob("*.md"))
    assert len(drafts) == 1
    text = drafts[0].read_text(encoding="utf-8")
    assert "The five figures." in text
    assert "abc123" in text, "the checksum beside the archive belongs in the mail"


def test_the_real_pages_parse() -> None:
    """The shipped pages, not a fixture: a column rename in either would go unnoticed."""
    assert ship_mail.rows((ROOT / "docs/questions.md").read_text(encoding="utf-8"), "asked-on")
    record = ship_mail.cumulative((ROOT / "docs/rounds.md").read_text(encoding="utf-8"))
    assert any("scored rounds" in line for line in record)
