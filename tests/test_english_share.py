"""Our vendored weight table must be the reviewer's, and it must be pinned.

Two implementations of the metric exist here on purpose: his
`equivalent_english_domains.py` decides every figure quoted to him, and
`src/ark/english_share.py` ranks two million candidates in a loop during collection, which
shelling out per file cannot do. The whole arrangement rests on them agreeing, and until
2026-08-18 that agreement was a sentence in a docstring with nothing checking it.

It is not a theoretical risk. His validator requires a letters-only TLD and ours had no
validity rule at all, so seventeen `xn--` records scored zero for him and full weight for
us, and `round_figures.py --verify` refused the round over the resulting 0.3150
discrepancy. That was the shape of a disagreement between the two sides; a silently
different weight would be the same class of bug and harder to see.

His brief also requires the table to be frozen: "the same fixed Common Crawl-derived TLD
English-share weight table must be used for the baseline and every submission being
compared", and it "must not be changed between submissions unless a revised standard is
formally issued for all comparisons". So the pin below is a requirement, not tidiness.
"""

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from ark.baseline import calculator_path
from ark.english_share import english_weights

ROOT = Path(__file__).resolve().parents[1]
VENDORED = ROOT / "src" / "ark" / "data" / "tld_english_share.json"

# The files allowed to hold a share by any route other than `english_weights()`.
# Anything else that needs a weight imports it, so one edit to the table cannot
# leave a second copy behind. A new entry needs a reason as good as these.
SHARE_HOLDERS = {
    "src/ark/english_share.py": "the one reader of the vendored table",
    "tests/test_english_share.py": "spells the quoted figures in order to check them",
    "scripts/output_unit_pack/registrable_unit.py": "ships standalone beside his model file",
    "scripts/pricing/measure_host_unit.py": "reads HIS file on purpose, to separate the weight "
    "question from the unit question",
}
# A TLD key followed by a share, however the value is wrapped: `"com": 0.6321`,
# `"com": "0.6321"`, `"com": Decimal("0.6321")`.
_SHARE_ENTRY = re.compile(
    r"""["'](?P<tld>[a-z]{2,})["']\s*:\s*(?:Decimal\()?["']?(?P<share>0\.\d+)"""
)
# The column name of his model: its presence means a file parses the JSON itself.
_MODEL_COLUMN = "perc_of_tld"

# The frozen table, by content. If this changes, either the reviewer has formally reissued
# the standard, in which case update it and say so in `docs/brief_amendments.md`, or
# something has edited the model and every figure this project has ever quoted is wrong.
# Measured, not transcribed. `src/ark/english_share.py` records only the first twelve
# characters in prose, and writing the rest from memory produced a wrong pin that this
# test caught on its first run. The prefix matching is what confirms it is the same file
# the docstring describes.
EXPECTED_SHA256 = "480d86bc287ef2c2bc80be62ecffe6eecba950dddf07bb9d3f15e6c2c268eb07"


def test_the_vendored_table_is_pinned_by_content() -> None:
    actual = hashlib.sha256(VENDORED.read_bytes()).hexdigest()
    assert actual == EXPECTED_SHA256, (
        "the vendored weight model changed. His brief freezes it across submissions, so "
        "either he has formally reissued the standard (update this pin and record it in "
        f"docs/brief_amendments.md) or this is a defect. Now: {actual}"
    )


def test_the_known_weights_are_what_the_project_quotes_everywhere() -> None:
    """The handful of weights that appear in prose across the repository and the report."""
    w = english_weights()
    for tld, expected in {
        "au": "0.9904",
        "gov": "0.9825",
        "uk": "0.9813",
        "edu": "0.9717",
        "us": "0.9261",
        "ca": "0.8365",
        "org": "0.7101",
        "com": "0.6321",
        "net": "0.4530",
        "info": "0.3648",
        "nl": "0.1629",
        "de": "0.1324",
        "pl": "0.1070",
        "br": "0.0934",
    }.items():
        assert w[tld] == Decimal(expected), f".{tld} reads {w[tld]}, prose says {expected}"


def test_our_table_agrees_with_his_model_on_every_tld() -> None:
    """The load-bearing check, run whenever his package is on disk.

    Skipped rather than failed when it is absent, because his package is git-ignored and a
    fresh clone has no copy. The pin above is what holds in that case, which is why both
    tests exist rather than only this one.
    """
    model = calculator_path().parent / "q2_tld_top_langs.json"
    if not model.is_file():
        pytest.skip(f"the reviewer's model is not on disk at {model}")

    raw = json.loads(model.read_text(encoding="utf-8"))
    his: dict[str, Decimal] = {}
    for tld, lang, pct in zip(raw["tld"], raw["lang"], raw["perc_of_tld"], strict=True):
        if tld and lang == "eng":
            his[str(tld).lower()] = Decimal(str(pct)) / Decimal("100")

    ours = english_weights()
    assert set(his) == set(ours), (
        f"his model has {len(his)} English-weighted TLDs and ours has {len(ours)}; "
        f"only in his: {sorted(set(his) - set(ours))[:5]}, "
        f"only in ours: {sorted(set(ours) - set(his))[:5]}"
    )
    disagree = {t: (his[t], ours[t]) for t in his if his[t] != ours[t]}
    assert not disagree, f"the two implementations weight these differently: {disagree}"


def test_no_second_copy_of_the_table_exists() -> None:
    """Every weight in code comes from `english_weights()`, or the pin above guards nothing.

    Two copies are caught: a literal that maps a TLD to its share, and a private parse of
    his JSON, which is how `build_pool_candidates.py` carried its own table until 2026-09.
    """
    weights = english_weights()
    copies: list[str] = []
    for top in ("src", "scripts", "tests", "probes", "hooks"):
        for path in sorted((ROOT / top).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if rel in SHARE_HOLDERS:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if _MODEL_COLUMN in text:
                copies.append(f"{rel} parses the model itself")
            for hit in _SHARE_ENTRY.finditer(text):
                if weights.get(hit["tld"]) == Decimal(hit["share"]):
                    copies.append(f"{rel} spells .{hit['tld']} = {hit['share']}")
    assert not copies, "import english_weights instead: " + "; ".join(copies)
