"""The verdict-mail parser writes the ledger row and never reads his score off the mail.

The two fixtures are his template: round 6 without the candidate-pool line or a quoted
score, round 7 with both. Their lines 1 and 2 are his database, not this project's, and
round 7's pair is derived from the growth rate rather than quoted, since only lines 3 to
5 reach the page. What the tests pin is that S and t come out of `ark.figures` and match
the two figures he has quoted, and that writing one row does not touch another.
"""

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
PAGE = ROOT / "docs/rounds.md"


def _load():
    spec = importlib.util.spec_from_file_location("rounds_page", ROOT / "scripts/round/rounds.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rounds = _load()


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _row(text: str, label: str) -> list[str]:
    for line in text.splitlines():
        if line.startswith("|") and _cells(line)[0] == label:
            return _cells(line)
    raise AssertionError(f"no row for round {label}")


def _run(monkeypatch, page: Path, mail: Path, label: str, received: str, **extra) -> None:
    argv = [
        "rounds.py",
        "--mail",
        str(mail),
        "--round",
        label,
        "--received",
        received,
        "--page",
        str(page),
    ]
    for flag, value in extra.items():
        argv += [f"--{flag.replace('_', '-')}", str(value)]
    monkeypatch.setattr(sys, "argv", argv)
    rounds.main()


@pytest.fixture
def page(tmp_path) -> Path:
    copy = tmp_path / "rounds.md"
    copy.write_text(PAGE.read_text(encoding="utf-8"), encoding="utf-8")
    return copy


def test_the_fixtures_parse_to_his_five_figures() -> None:
    six = rounds.parse_mail((FIXTURES / "verdict_round6.txt").read_text())
    assert six["total_records"] == Decimal("25467416")
    assert six["total_ee"] == Decimal("13607793.2733")
    assert six["increment_records"] == Decimal("1684903")
    assert six["increment_ee"] == Decimal("562099.5294")
    assert six["growth"] == Decimal("4.130718")
    assert six["marker"] == "merged260826"
    assert "quoted_score" not in six and "candidate_growth" not in six

    seven = rounds.parse_mail((FIXTURES / "verdict_round7.txt").read_text())
    assert seven["increment_records"] == Decimal("2538900")
    assert seven["increment_ee"] == Decimal("1456458.1029")
    assert seven["growth"] == Decimal("7.562846")
    assert seven["candidate_growth"] == Decimal("0.225249")
    assert seven["quoted_score"] == Decimal("6.302372")
    assert seven["marker"] == "merged260902-2"


def test_numbering_and_the_record_suffix_are_optional() -> None:
    parsed = rounds.parse_mail(
        "Original domain-year total: 25,467,416\n"
        "Equivalent-English total: 13,607,793.2733\n"
        "Increment: 1,684,903\n"
        "Equivalent-English increment: 562,099.5294\n"
        "Equivalent-English growth rate: 4.130718%\n"
    )
    assert parsed["increment_records"] == Decimal("1684903")
    assert parsed["growth"] == Decimal("4.130718")


def test_round_7_reproduces_his_6_302372(monkeypatch, page, capsys) -> None:
    _run(monkeypatch, page, FIXTURES / "verdict_round7.txt", "7", "2026-09-02 05:50")
    row = _row(page.read_text(), "7")
    assert row[4:7] == ["2,538,900", "1,456,458.1029", "7.562846"]
    assert row[8:14] == [
        "2026-08-21 11:19",
        "2026-09-02 05:50",
        "11.77",
        "12",
        "6.302372",
        "6.302372",
    ]
    assert "WARNING" not in capsys.readouterr().out


def test_round_6_gives_6_884530(monkeypatch, page) -> None:
    _run(monkeypatch, page, FIXTURES / "verdict_round6.txt", "6", "2026-08-26 15:51")
    row = _row(page.read_text(), "6")
    assert row[10:14] == ["5.19", "6", "6.884530", "not quoted"]


def test_a_quoted_score_that_disagrees_is_a_warning_not_a_cell(monkeypatch, page, capsys) -> None:
    """His clock is the record of what he scored; ours is the record of the rule."""
    _run(monkeypatch, page, FIXTURES / "verdict_round7.txt", "7", "2026-09-03 05:50")
    out = capsys.readouterr().out
    assert "WARNING" in out and "6.302372" in out and "5.817574" in out
    assert _row(page.read_text(), "7")[12] == "5.817574"


def test_a_marker_with_no_directory_is_not_received(monkeypatch, page, tmp_path) -> None:
    feedback = tmp_path / "feedback"
    feedback.mkdir()
    _run(
        monkeypatch,
        page,
        FIXTURES / "verdict_round6.txt",
        "6",
        "2026-08-26 15:51",
        feedback=feedback,
    )
    assert _row(page.read_text(), "6")[7] == "merged260826 (not received)"

    (feedback / "phase-6" / "merged260826").mkdir(parents=True)
    _run(
        monkeypatch,
        page,
        FIXTURES / "verdict_round6.txt",
        "6",
        "2026-08-26 15:51",
        feedback=feedback,
    )
    assert _row(page.read_text(), "6")[7] == "merged260826"


def test_updating_one_row_leaves_the_others_byte_identical(monkeypatch, page) -> None:
    before = page.read_text().splitlines()
    _run(monkeypatch, page, FIXTURES / "verdict_round7.txt", "7", "2026-09-02 05:50")
    after = page.read_text().splitlines()
    assert len(before) == len(after)
    changed = [i for i, (a, b) in enumerate(zip(before, after, strict=True)) if a != b]
    assert [_cells(after[i])[0] for i in changed] == ["7"]


def test_a_round_the_page_lacks_is_inserted_in_order(monkeypatch, page) -> None:
    _run(monkeypatch, page, FIXTURES / "verdict_round7.txt", "8", "2026-09-03 05:50", note="new")
    labels = [_cells(line)[0] for line in page.read_text().splitlines() if line.startswith("| ")]
    assert labels[-1] == "8"
    row = _row(page.read_text(), "8")
    assert row[1] == "pending" and row[14] == "new"
