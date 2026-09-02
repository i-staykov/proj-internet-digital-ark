"""The ranking score reproduces the two figures the reviewer has quoted, to the digit.

He quotes S_6 = 6.88 and S_7 = 6.302372. Exactly one rule fits both: t_i is the elapsed
time from the release of the benchmark package to receipt, in his clock, rounded up to
whole days. The report shipped round 7 at S = 226.43 by counting calendar days from the
current release and flooring to one; these tests pin the rule that replaced it and record
why the alternatives were rejected.
"""

import importlib.util
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from ark.baseline import CURRENT_BASELINE_RELEASED, SUBMITTED_ROUNDS
from ark.figures import (
    cumulative,
    elapsed_days,
    now_in_his_clock,
    parse_stamp,
    score,
    scored_under_rule,
    t_days,
)

ROOT = Path(__file__).resolve().parents[1]
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
ROWS = {r[0]: r for r in SUBMITTED_ROUNDS}


def _score(label: str) -> tuple[int, Decimal]:
    _, _, _, _, _, p, released, received = ROWS[label]
    t = t_days(released, received)
    return t, score(p, t)


def test_round_6_reproduces_his_6_88() -> None:
    t, s = _score("6")
    assert t == 6
    assert s == Decimal("6.884530")
    assert s.quantize(Decimal("0.01")) == Decimal("6.88")


def test_round_7_reproduces_his_6_302372_exactly() -> None:
    t, s = _score("7")
    assert t == 12
    assert s == Decimal("6.302372")


def test_elapsed_is_fractional_and_t_rounds_up() -> None:
    e = elapsed_days("2026-08-21 11:19", "2026-08-26 15:51")
    assert e.quantize(Decimal("0.0001")) == Decimal("5.1889")
    assert t_days("2026-08-21 11:19", "2026-08-26 15:51") == 6
    assert elapsed_days("2026-08-21 11:19", "2026-09-02 05:50").quantize(
        Decimal("0.01")
    ) == Decimal("11.77")


def test_calendar_days_were_rejected_because_they_miss_round_6() -> None:
    """Calendar days from the release give t = 5 and S = 8.26, not the 6.88 he quotes."""
    _, _, _, _, _, p, released, received = ROWS["6"]
    calendar = (date.fromisoformat(received[:10]) - date.fromisoformat(released[:10])).days
    assert calendar == 5
    assert score(p, calendar) == Decimal("8.261436")
    assert score(p, calendar).quantize(Decimal("0.01")) != Decimal("6.88")


def test_a_clock_from_the_brief_update_was_rejected_because_it_misses_round_7() -> None:
    """Counting from the 2026-08-20 03:37 update gives round 7 t = 14 (or 13 by calendar)."""
    p = ROWS["7"][5]
    assert t_days("2026-08-20 03:37", "2026-09-02 05:50") == 14
    assert score(p, 14) != Decimal("6.302372")
    assert score(p, 13) != Decimal("6.302372")


def test_cumulative_is_the_sum_of_the_rounds_he_scored() -> None:
    scored = [_score(label)[1] for label in ("6", "7")]
    assert cumulative(scored) == Decimal("13.186902")
    assert cumulative([]) == Decimal(0)


def test_the_rule_covers_rounds_6_and_7_only() -> None:
    assert [r[0] for r in SUBMITTED_ROUNDS if scored_under_rule(r[7])] == ["6", "7"]


def test_a_receipt_inside_the_release_minute_still_divides_by_one() -> None:
    assert t_days("2026-09-02 10:31", "2026-09-02 10:31") == 1


def test_rows_carry_minute_stamps_in_his_clock() -> None:
    for r in SUBMITTED_ROUNDS:
        assert STAMP.match(r[6]) and STAMP.match(r[7]), r[0]
        assert parse_stamp(r[7]) > parse_stamp(r[6]), r[0]
    assert ROWS["6"][6] == "2026-08-21 11:19"
    assert ROWS["7"][6] == "2026-08-21 11:19"
    assert STAMP.match(CURRENT_BASELINE_RELEASED)
    assert STAMP.match(now_in_his_clock())


def test_fill_report_has_no_day_arithmetic_of_its_own() -> None:
    source = (ROOT / "scripts/round/fill_report.py").read_text(encoding="utf-8")
    for token in ("date.today", "fromisoformat", "timedelta", ".days"):
        assert token not in source, token


def test_fill_report_quotes_his_sum_and_labels_the_rest(monkeypatch) -> None:
    spec = importlib.util.spec_from_file_location(
        "fill_report_for_figures", ROOT / "scripts/round/fill_report.py"
    )
    fill_report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fill_report)
    monkeypatch.setattr(fill_report, "now_in_his_clock", lambda: "2026-09-03 10:00")
    text = fill_report.cumulative({}, Decimal("1.5"))
    assert "**S = 13.186902**" in text
    assert "6: 4.130718% / 6d = 6.884530" in text
    assert "7: 7.562846% / 12d = 6.302372" in text
    assert "would add 15.000000 at t = 1" in text
    assert "Rounds 1, 3, 4 and 5 predate the rule" in text
    assert "5: 14.901054% / 2d = 74.505270" in text
    sentence = fill_report.cumulative_sentence({}, Decimal("1.5"))
    assert "13.186902 (6.884530 + 6.302372)" in sentence
