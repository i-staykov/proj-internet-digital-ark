"""The baseline figures live in `data/baseline.json`, and nowhere else.

A hand-edited constant block is the one place an intake can be silently wrong: the
module carried a release it was no longer pointed at, and nothing failed. So the test
is mechanical on both sides. Nothing in the module's code may carry a number of two or
more digits, which is what a stale figure looks like, and every name the module exposes
must still be exactly what the JSON says.
"""

import io
import json
import re
import tokenize
from decimal import Decimal
from pathlib import Path

from ark import baseline

SOURCE = Path("src/ark/baseline.py")
DATA = Path("data/baseline.json")

MULTI_DIGIT = re.compile(r"\d\d+")


def _is_docstring(tokens: list[tokenize.TokenInfo], index: int) -> bool:
    """A string that is a statement on its own, which is a docstring here."""
    before = tokenize.INDENT, tokenize.NEWLINE, tokenize.NL, tokenize.ENCODING
    previous = next(
        (t for t in reversed(tokens[:index]) if t.type not in (tokenize.DEDENT, tokenize.COMMENT)),
        None,
    )
    following = next(
        (t for t in tokens[index + 1 :] if t.type not in (tokenize.COMMENT, tokenize.NL)),
        None,
    )
    starts = previous is None or previous.type in before
    ends = following is not None and following.type == tokenize.NEWLINE
    return starts and ends


def _code_tokens(source: str) -> list[tokenize.TokenInfo]:
    """The module minus comments and docstrings: prose may name a year, code may not."""
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    return [
        tok
        for i, tok in enumerate(tokens)
        if tok.type != tokenize.COMMENT
        and not (tok.type == tokenize.STRING and _is_docstring(tokens, i))
    ]


def test_the_module_holds_no_figure_of_its_own() -> None:
    """No two-digit run in the code, so every number reaches it through the JSON."""
    offenders = [
        (tok.start[0], tok.string)
        for tok in _code_tokens(SOURCE.read_text(encoding="utf-8"))
        if MULTI_DIGIT.search(tok.string)
    ]
    assert not offenders, f"numbers hardcoded in {SOURCE}: {offenders}"


def test_every_constant_round_trips_from_the_json() -> None:
    """The names importers use are the JSON's values, unconverted and unrounded."""
    data = json.loads(DATA.read_text(encoding="utf-8"))
    current = data["current"]

    assert baseline.CURRENT_BASELINE_MARKER == current["marker"]
    assert str(baseline.CURRENT_BASELINE_DIR) == current["directory"]
    assert baseline.CURRENT_BASELINE_RELEASED == current["released_at"]
    assert baseline.CURRENT_ROUND_SINCE == current["round_since"]
    assert baseline.CURRENT_ROUND_LABEL == current["round_label"]
    assert baseline.REVIEWER_BASELINE_PAIRS == current["reviewer_pairs"]
    assert baseline.REVIEWER_BASELINE_EE == Decimal(current["reviewer_ee"])
    assert baseline.REVIEWER_BASELINE_EE_BY_YEAR == {
        int(year): Decimal(ee) for year, ee in current["reviewer_ee_by_year"].items()
    }
    assert baseline.ORIGINAL_BASELINE_PAIRS == data["original"]["pairs"]
    assert baseline.ORIGINAL_BASELINE_EE == Decimal(data["original"]["ee"])
    assert baseline.ROUND_ONE_IS_RECORD_BASED == data["round_one_is_record_based"]
    assert baseline.SUBMISSION_SPEED_K == data["speed_k"]

    assert len(baseline.SUBMITTED_ROUNDS) == len(data["rounds"])
    for row, entry in zip(baseline.SUBMITTED_ROUNDS, data["rounds"], strict=True):
        assert row == (
            entry["label"],
            entry["date"],
            entry["records"],
            Decimal(entry["equivalent_english"]),
            entry["baseline"],
            Decimal(entry["awarded_percent"]),
            entry["benchmark_released"],
            entry["submission_received"],
        )


def test_the_decimals_keep_their_written_precision() -> None:
    """`Decimal("...9.5294")` and `Decimal(9.5294)` differ, and the reviewer reads the digits."""
    data = json.loads(DATA.read_text(encoding="utf-8"))
    assert str(baseline.REVIEWER_BASELINE_EE) == data["current"]["reviewer_ee"]
    for row, entry in zip(baseline.SUBMITTED_ROUNDS, data["rounds"], strict=True):
        assert str(row[3]) == entry["equivalent_english"]
        assert str(row[5]) == entry["awarded_percent"]


def test_the_json_is_tracked_and_not_ignored() -> None:
    """`.gitignore` excludes `/data/*`, and this one file is re-included by name."""
    assert DATA.is_file()
    ignore = Path(".gitignore").read_text(encoding="utf-8").splitlines()
    assert "!/data/baseline.json" in ignore
    assert "/data/" not in ignore, "an excluded directory cannot re-include a file inside it"
