"""The round's own pages: the verdict mail parsed into one row of `rounds.md`, the mail draft
a rehearsal never writes, and the shipped saturation ledger, byte for byte the register."""

import re
import sys
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
from conftest import script

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"


rounds = script("round/rounds.py", "rounds_page")
ship_mail = script("round/ship_mail.py", "ship_mail")
ledger = script("round/saturation_ledger.py", "saturation_ledger")


COLUMNS = (
    "round|sent records|sent EE|sent %|credited records|credited EE|awarded p_i|against|"
    "released|received|days|t_i|S_i computed|S_i quoted|note"
).split("|")


TABLE = [COLUMNS, ["---"] * 15] + [[label] + ["old"] * 14 for label in ("1", "6", "7", "9")]
PAGE = "\n".join(
    ["# Rounds", "", "Prose above the table.", ""]
    + ["| " + " | ".join(row) + " |" for row in TABLE]
    + ["", "Prose below it.", ""]
)
SIX, SEVEN = ((FIXTURES / f"verdict_round{n}.txt").read_text() for n in (6, 7))
WANT_6 = {"total_records": D("25467416"), "total_ee": D("13607793.2733"), "growth": D("4.130718")}
WANT_6 |= {"increment_records": D("1684903"), "increment_ee": D("562099.5294")}
WANT_6 |= {"marker": "merged260826"}
WANT_7 = {"increment_records": D("2538900"), "increment_ee": D("1456458.1029")}
WANT_7 |= {"growth": D("7.562846"), "candidate_growth": D("0.225249")}
WANT_7 |= {"quoted_score": D("6.302372"), "marker": "merged260902-2"}
ROUND_7 = ["2,538,900", "1,456,458.1029", "7.562846", "merged260902-2 (not received)"]
ROUND_7 += ["2026-08-21 11:19", "2026-09-02 05:50", "11.77", "12", "6.302372", "6.302372"]


def _row(text: str, label: str) -> list[str]:
    return next(rounds.cells_of(ln) for ln in text.splitlines() if ln.startswith(f"| {label} |"))


@pytest.fixture
def run(tmp_path, monkeypatch):
    """Run `rounds.py` on a copy of the page, with no feedback tree unless one is given."""
    page = tmp_path / "rounds.md"
    page.write_text(PAGE, encoding="utf-8")

    def go(label: str, received: str, mail: str = "", **extra) -> str:
        mail = str(FIXTURES / (mail or f"verdict_round{label}.txt"))
        argv = ["rounds.py", "--mail", mail, "--round", label, "--received", received]
        for flag, value in ({"page": page, "feedback": tmp_path / "feedback"} | extra).items():
            argv += [f"--{flag}", str(value)]
        monkeypatch.setattr(sys, "argv", argv)
        rounds.main()
        return page.read_text(encoding="utf-8")

    return go


@pytest.mark.parametrize(
    ("mail", "want", "absent"),
    [
        (SIX, WANT_6, ("quoted_score", "candidate_growth")),
        (re.sub(r"^\d\. | domain-year records", "", SIX, flags=re.M), WANT_6, ()),
        (SEVEN, WANT_7, ()),
    ],
    ids=["round-6-no-pool-line-no-score", "unnumbered-no-record-suffix", "round-7-pool-and-score"],
)
def test_the_mail_parses_to_his_figures(mail, want, absent) -> None:
    parsed = rounds.parse_mail(mail)
    assert {key: parsed[key] for key in want} == want
    assert not set(absent) & set(parsed)


@pytest.mark.parametrize(
    ("label", "received", "at", "cells", "warned"),
    [
        ("7", "2026-09-02 05:50", 4, ROUND_7, ()),
        ("6", "2026-08-26 15:51", 10, ["5.19", "6", "6.884530", "not quoted"], ()),
        ("7", "2026-09-03 05:50", 12, ["5.817574"], ("WARNING", "6.302372", "5.817574")),
    ],
    ids=["round-7-gives-his-6.302372", "round-6-gives-6.884530", "disagreeing-score-warns"],
)
def test_one_row_is_written_and_every_other_line_is_left(
    run, capsys, label, received, at, cells, warned
):
    after = run(label, received)
    assert _row(after, label)[at : at + len(cells)] == cells
    out = capsys.readouterr().out
    assert all(text in out for text in warned) and ("WARNING" in out) == bool(warned)
    changed = [a for a, b in zip(PAGE.split("\n"), after.split("\n"), strict=True) if a != b]
    assert [rounds.cells_of(line)[0] for line in changed] == [label]


def test_a_new_round_goes_in_order_and_an_absent_marker_is_not_received(run, tmp_path):
    after = run("8", "2026-09-03 05:50", mail="verdict_round7.txt", note="new")
    labels = [rounds.cells_of(ln)[0] for ln in after.splitlines() if ln.startswith("| ")]
    assert labels == ["round", "---", "1", "6", "7", "8", "9"]
    assert (_row(after, "8")[1], _row(after, "8")[14]) == ("pending", "new")
    assert _row(run("6", "2026-08-26 15:51"), "6")[7] == "merged260826 (not received)"
    (tmp_path / "feedback/phase-6/merged260826").mkdir(parents=True)
    assert _row(run("6", "2026-08-26 15:51"), "6")[7] == "merged260826"


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
def test_only_open_and_due_questions_are_reminded(today, due):
    lines = ship_mail.reminders(QUESTIONS, today)
    assert len(lines) == len(due) and all(t in ln for t, ln in zip(due, lines, strict=True))


def test_his_record_is_summed_from_his_columns_found_by_name():
    lines = "\n".join(ship_mail.cumulative(ROUNDS))
    # 17.38 + 4.130718 + 7.562846, the three rows with a number in `awarded p_i`
    assert "29.073564% in total" in lines and "3 scored rounds (1, 6, 7)" in lines
    assert "RECORDS" in lines, "round 1 is not commensurable and the draft must say so"
    assert "6.88 + 6.302372 = 13.182372" in lines
    moved = re.sub(r"^(\|[^|]*\|)", r"\1 new |", ROUNDS, flags=re.M)
    assert "| round | new |" in moved, "the columns are found by name"
    assert ship_mail.cumulative(moved) == ship_mail.cumulative(ROUNDS)


def test_a_rehearsal_writes_nothing_and_write_saves_one_draft(tmp_path, capsys) -> None:
    archive = tmp_path / "delivery.tar.gz"
    archive.write_bytes(b"x")
    archive.with_suffix(".gz.sha256").write_text("abc123  delivery.tar.gz\n")
    drafts = tmp_path / "drafts"
    argv = ["--today", "2026-09-03", "--out-dir", str(drafts), "--archive", str(archive)]
    for flag, text in {"questions": QUESTIONS, "rounds": ROUNDS, "body": "The figures.\n"}.items():
        (tmp_path / f"{flag}.md").write_text(text)
        argv += [f"--{flag}", str(tmp_path / f"{flag}.md")]
    assert ship_mail.main(argv) == 0
    assert not drafts.exists(), "a rehearsal must not leave a draft behind"
    assert "1 question(s) due" in capsys.readouterr().out
    assert ship_mail.main(["--write", *argv]) == 0
    [draft] = drafts.glob("*.md")
    text = draft.read_text()
    assert all(s in text for s in ("The figures.", "Do both hold?", "abc123")), "body, due, sha"


REGISTER = FIXTURES / "register"
SOURCES, CLOSED = ((REGISTER / name).read_text() for name in ("sources.md", "sources-closed.md"))


def is_the_expected_ledger(tmp_path: Path, sources: str = SOURCES, closed: str = CLOSED) -> bool:
    """The exporter over two register pages. The fixture is stored with LF so git cannot
    rewrite it; the CSV module writes CRLF, the artifact's real shape."""
    (tmp_path / "sources.md").write_text(sources)  # the `reference` column names the page
    (tmp_path / "sources-closed.md").write_text(closed)
    out = tmp_path / "ledger.csv"
    argv = ["saturation_ledger.py", "--out", str(out), "--sources", str(tmp_path / "sources.md")]
    argv += ["--closed", str(tmp_path / "sources-closed.md"), "--contribution", str(tmp_path / "x")]
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(sys, "argv", argv)
        assert ledger.main() == 0
    return out.read_bytes() == (REGISTER / "expected_ledger.csv").read_bytes().replace(
        b"\n", b"\r\n"
    )


def _reorder(page: str, order: list[int]) -> str:
    lines = []
    for line in page.splitlines():
        cells = line.strip().strip("|").split("|")
        if line.startswith("|") and len(cells) == len(order):
            line = "|" + "|".join(cells[i] for i in order) + "|"
        lines.append(line)
    return "\n".join(lines) + "\n"


def test_the_ledger_is_byte_for_byte_what_the_register_says_in_any_column_order(tmp_path):
    """Cells are found by header name, so a shuffled page, or a column the exporter has never
    heard of prepended where a positional reader goes wrong, gives the same bytes."""
    assert is_the_expected_ledger(tmp_path)
    shuffled = _reorder(SOURCES, [10, 6, 0, 9, 3, 1, 7, 2, 8, 4, 5])
    assert shuffled != SOURCES, "the fixture was not actually reordered"
    assert is_the_expected_ledger(tmp_path, shuffled, _reorder(CLOSED, [4, 2, 0, 3, 1]))
    grown = []
    for line in SOURCES.splitlines():
        if line.startswith("|"):
            body = line.strip().strip("|")
            added = "---" if not set(line) - set("|-: ") else "top"
            line = f"| {'priority' if body.split('|')[0].strip() == 'source' else added} |{body}|"
        grown.append(line)
    assert is_the_expected_ledger(tmp_path, "\n".join(grown) + "\n")


def test_a_missing_column_is_named_and_a_closed_rows_verdict_is_its_reasons_closed_word():
    page = "| source | version or date | net-new EE (date) | quality issues |\n|---|---|---|---|\n"
    found = r"source_link.*Headers found: source, version or date, net-new EE \(date\), quality"
    with pytest.raises(ValueError, match=found):
        ledger.rows_from_register(page + "| a | 2026-09-01 | 12 EE | none |\n")
    text = CLOSED + (
        "| not_a_source | 2026-09-01 | 0 EE | REJECTED. FIND, not a source. |  |\n"
        "| aged_out | 2026-09-19, retired | 0 EE | RETIRED: never priced; retired unmeasured |  |\n"
    )
    _, rejected, retired = ledger.rows_from_register(text, "docs/registers/sources-closed.md")
    assert rejected["status"] == "rejected" and not rejected["decision"].startswith("retain")
    assert (retired["status"], retired["decision"]) == ("retired", "retired unmeasured")
