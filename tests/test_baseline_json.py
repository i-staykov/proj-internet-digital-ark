"""The baseline figures live in `data/baseline.json` alone, and `ark.baseline` only loads them."""

import ast
import json
import re
from decimal import Decimal
from pathlib import Path

from ark import baseline

ROOT = Path(__file__).resolve().parents[1]
DECIMALS = ("equivalent_english", "awarded_percent")
ROUND = ("label", "date", "records", DECIMALS[0], "baseline", DECIMALS[1], "benchmark_released")


def test_the_module_holds_no_figure_of_its_own() -> None:
    """No run of two digits in its code: a comment or docstring may name a year, code may not."""
    tree = ast.parse(Path(baseline.__file__).read_text(encoding="utf-8"))
    prose = {id(node.value) for node in ast.walk(tree) if isinstance(node, ast.Expr)}
    code = [node for node in ast.walk(tree) if id(node) not in prose]
    words = [(n.lineno, n.value) for n in code if isinstance(n, ast.Constant)]
    words += [(n.lineno, n.id) for n in code if isinstance(n, ast.Name)]
    offenders = [word for word in words if re.search(r"\d\d", str(word[1]))]
    assert not offenders, f"numbers hardcoded in {baseline.__file__}: {offenders}"


def test_the_json_ships_rewrites_byte_for_byte_and_is_every_constant() -> None:
    """It ships past `/data/*`, keeps its bytes through intake's re-dump, and is every constant."""
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "!/data/baseline.json" in ignore and "/data/" not in ignore
    text = (ROOT / "data/baseline.json").read_text(encoding="utf-8")
    assert json.dumps(data := json.loads(text), indent=2, ensure_ascii=False) + "\n" == text
    current, ee = data["current"], data["current"]["reviewer_ee"]
    assert baseline.CURRENT_BASELINE_MARKER == current["marker"]
    assert str(baseline.CURRENT_BASELINE_DIR) == current["directory"]
    assert baseline.CURRENT_BASELINE_RELEASED == current["released_at"]
    assert baseline.CURRENT_ROUND_SINCE == current["round_since"]
    assert baseline.CURRENT_ROUND_LABEL == current["round_label"]
    assert baseline.REVIEWER_BASELINE_PAIRS == current["reviewer_pairs"]
    # Decimal("9.5294") keeps the digits the reviewer reads, unconverted and unrounded.
    assert baseline.REVIEWER_BASELINE_EE == Decimal(ee) and str(baseline.REVIEWER_BASELINE_EE) == ee
    assert baseline.REVIEWER_BASELINE_EE_BY_YEAR == {
        int(year): Decimal(value) for year, value in current["reviewer_ee_by_year"].items()
    }
    assert baseline.ORIGINAL_BASELINE_PAIRS == data["original"]["pairs"]
    assert baseline.ORIGINAL_BASELINE_EE == Decimal(data["original"]["ee"])
    assert baseline.ROUND_ONE_IS_RECORD_BASED == data["round_one_is_record_based"]
    assert baseline.SUBMISSION_SPEED_K == data["speed_k"]
    for row, entry in zip(baseline.SUBMITTED_ROUNDS, data["rounds"], strict=True):
        keys = (*ROUND, "submission_received")
        assert row == tuple(Decimal(entry[k]) if k in DECIMALS else entry[k] for k in keys)
        assert (str(row[3]), str(row[5])) == tuple(entry[k] for k in DECIMALS)
