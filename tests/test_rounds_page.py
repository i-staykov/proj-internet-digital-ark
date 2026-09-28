"""The verdict-mail parser writes one ledger row, and S and t come from `ark.figures`."""

import importlib.util
import re
import sys
from decimal import Decimal as D
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"
_spec = importlib.util.spec_from_file_location(
    "rounds_page", Path(__file__).resolve().parents[1] / "scripts/round/rounds.py"
)
rounds = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rounds)

COLUMNS = (
    "round|sent records|sent EE|sent %|credited records|credited EE|awarded p_i|against|"
    "released|received|days|t_i|S_i computed|S_i quoted|note"
).split("|")


def _line(cells) -> str:
    return "| " + " | ".join(cells) + " |"


PAGE = "\n".join(
    ["# Rounds", "", "Prose above the table.", "", _line(COLUMNS), _line(["---"] * len(COLUMNS))]
    + [_line([label] + ["old"] * (len(COLUMNS) - 1)) for label in ("1", "6", "7", "9")]
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
        extra = {"page": page, "feedback": tmp_path / "feedback", **extra}
        for flag, value in extra.items():
            argv += [f"--{flag.replace('_', '-')}", str(value)]
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
) -> None:
    after = run(label, received)
    assert _row(after, label)[at : at + len(cells)] == cells
    out = capsys.readouterr().out
    assert all(text in out for text in warned) and ("WARNING" in out) == bool(warned)
    changed = [a for a, b in zip(PAGE.split("\n"), after.split("\n"), strict=True) if a != b]
    assert [rounds.cells_of(line)[0] for line in changed] == [label]


def test_a_marker_with_no_directory_is_not_received(run, tmp_path) -> None:
    assert _row(run("6", "2026-08-26 15:51"), "6")[7] == "merged260826 (not received)"
    (tmp_path / "feedback" / "phase-6" / "merged260826").mkdir(parents=True)
    assert _row(run("6", "2026-08-26 15:51"), "6")[7] == "merged260826"


def test_a_round_the_page_lacks_is_inserted_in_order(run) -> None:
    after = run("8", "2026-09-03 05:50", mail="verdict_round7.txt", note="new")
    labels = [rounds.cells_of(ln)[0] for ln in after.splitlines() if ln.startswith("| ")]
    assert labels == ["round", "---", "1", "6", "7", "8", "9"]
    row = _row(after, "8")
    assert row[1] == "pending" and row[14] == "new"
