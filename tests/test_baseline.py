"""The baseline, the calculator and the English-share table the score is made of. A delivery
keeps his release at `baseline/<marker>/` beside `source/`, since `git archive` cannot carry the
git-ignored repository path. His calculator decides every figure quoted to him and ours ranks
candidates in a loop, so the two tables must agree, and his brief freezes his."""

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from ark import baseline
from ark.english_share import english_weights

ROOT = Path(__file__).resolve().parents[1]
VENDORED = ROOT / "src/ark/data/tld_english_share.json"
# Measured, never transcribed. A new value is either a standard he formally reissued, recorded
# in `docs/brief/brief_amendments.md`, or a defect under every figure ever quoted.
EXPECTED_SHA256 = "480d86bc287ef2c2bc80be62ecffe6eecba950dddf07bb9d3f15e6c2c268eb07"
# The one reader of the vendored table, and this file, which parses his model to check ours.
SHARE_HOLDERS = {"src/ark/english_share.py", "tests/test_baseline.py"}
# A TLD key followed by a share, however wrapped: `"com": 0.6321`, `"com": Decimal("0.6321")`.
_SHARE_ENTRY = re.compile(
    r"""["'](?P<tld>[a-z]{2,})["']\s*:\s*(?:Decimal\()?["']?(?P<share>0\.\d+)"""
)


def test_the_baseline_and_the_calculator_are_found_from_an_unpacked_delivery(tmp_path, monkeypatch):
    (source := tmp_path / "source").mkdir()
    monkeypatch.chdir(source)
    # With neither, the first candidate comes back for the caller to report with its path.
    assert baseline.baseline_dir() == baseline.CURRENT_BASELINE_DIR
    (merged := tmp_path / "baseline" / baseline.CURRENT_BASELINE_MARKER).mkdir(parents=True)
    for year in range(1996, 2002):
        (merged / f"{year}.txt").write_text("example.com\n")
    (tmp_path / "equivalent_english_domain_calculator").mkdir()
    (tmp_path / "equivalent_english_domain_calculator/equivalent_english_domains.py").touch()
    assert baseline.baseline_dir().resolve() == merged.resolve()
    assert baseline.calculator_path().is_file()
    # The repository layout still wins when both are there.
    (source / baseline.CURRENT_BASELINE_DIR).mkdir(parents=True)
    (source / baseline.CURRENT_BASELINE_DIR / "1996.txt").touch()
    assert baseline.baseline_dir() == baseline.CURRENT_BASELINE_DIR


def test_every_constant_loads_its_own_key_with_his_digits() -> None:
    """Every gate percentage divides by his EE, and a float on the way changes his digits; the
    label names the round and its phase directory, and round_since opens the round's window."""
    data = json.loads((ROOT / "data/baseline.json").read_text(encoding="utf-8"))
    by_year = baseline.REVIEWER_BASELINE_EE_BY_YEAR
    loaded = {
        "marker": baseline.CURRENT_BASELINE_MARKER,
        "directory": baseline.CURRENT_BASELINE_DIR,
        "released_at": baseline.CURRENT_BASELINE_RELEASED,
        "round_since": baseline.CURRENT_ROUND_SINCE,
        "round_label": baseline.CURRENT_ROUND_LABEL,
        "reviewer_pairs": baseline.REVIEWER_BASELINE_PAIRS,
        "reviewer_ee": baseline.REVIEWER_BASELINE_EE,
        "reviewer_ee_by_year": {str(year): ee for year, ee in by_year.items()},
        "reviewer_extended_pairs": baseline.REVIEWER_EXTENDED_PAIRS,
        "reviewer_extended_ee": baseline.REVIEWER_EXTENDED_EE,
        "reviewer_extended_ee_by_year": {
            str(year): ee for year, ee in baseline.REVIEWER_EXTENDED_EE_BY_YEAR.items()
        },
    }
    # As text, so a Decimal shows the digits he reads and a float shows its own.
    assert json.loads(json.dumps(loaded, default=str)) == data["current"]
    keys = ("label", "date", "records", "equivalent_english", "baseline", "awarded_percent")
    keys += ("benchmark_released", "submission_received")
    rounds = json.loads(json.dumps(baseline.SUBMITTED_ROUNDS, default=str))
    assert rounds == [[row[key] for key in keys] for row in data["rounds"]]
    assert str(baseline.ORIGINAL_BASELINE_EE) == data["original"]["ee"]
    # The 2002 to 2013 part's denominator is his EE for those years, 2014 on never in it.
    extended = sum(baseline.REVIEWER_EXTENDED_EE_BY_YEAR.values(), Decimal(0))
    assert baseline.REVIEWER_EXTENDED_EE == extended
    years = sorted(baseline.REVIEWER_EXTENDED_EE_BY_YEAR)
    assert years == list(baseline.EXTENDED_YEARS) == list(range(2002, 2014))


def test_the_vendored_table_is_pinned_by_content() -> None:
    assert hashlib.sha256(VENDORED.read_bytes()).hexdigest() == EXPECTED_SHA256


def test_our_table_agrees_with_his_model_on_every_tld() -> None:
    """Skipped rather than failed when his git-ignored package is absent: the pin holds then."""
    model = baseline.calculator_path().parent / "q2_tld_top_langs.json"
    if not model.is_file():
        pytest.skip(f"the reviewer's model is not on disk at {model}")
    raw = json.loads(model.read_text(encoding="utf-8"))
    his = {
        str(tld).lower(): Decimal(str(pct)) / Decimal("100")
        for tld, lang, pct in zip(raw["tld"], raw["lang"], raw["perc_of_tld"], strict=True)
        if tld and lang == "eng"
    }
    ours = english_weights()
    assert set(his) == set(ours), (
        sorted(set(his) - set(ours))[:5],
        sorted(set(ours) - set(his))[:5],
    )
    assert not {t: (his[t], ours[t]) for t in his if his[t] != ours[t]}


def test_no_second_copy_of_the_table_exists() -> None:
    """Every weight in code comes from `english_weights()`, or the pin guards nothing: no
    literal maps a TLD to its share, and no private parse of his JSON reads `perc_of_tld`."""
    weights, copies = english_weights(), []
    for top in ("src", "scripts", "tests", "probes", "hooks"):
        for path in sorted((ROOT / top).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if rel in SHARE_HOLDERS:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "perc_of_tld" in text:
                copies.append(f"{rel} parses the model itself")
            for hit in _SHARE_ENTRY.finditer(text):
                if weights.get(hit["tld"]) == Decimal(hit["share"]):
                    copies.append(f"{rel} spells .{hit['tld']} = {hit['share']}")
    assert not copies, "import english_weights instead: " + "; ".join(copies)
