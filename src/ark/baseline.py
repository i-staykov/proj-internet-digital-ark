"""Which baseline release is current, in one place.

**The figures live in `data/baseline.json`; this module only loads them.** Point the JSON
at the new release and every command follows. `docs/registers/releases.md` lists them.

`ark intake` checks the release the JSON names and writes the held sets every diff against
him reads (`ark.held`). Diffing against a stale release is silent: it reports work the
reviewer already holds as net-new.
"""

import json
from decimal import Decimal
from pathlib import Path

# Resolved from this file, never from the working directory: the delivery unpacks the
# repository tree into `source/`, so the JSON sits beside `src/` there exactly as here.
_DATA = json.loads(
    (Path(__file__).resolve().parents[2] / "data" / "baseline.json").read_text(encoding="utf-8")
)
_CURRENT = _DATA["current"]

# The release the store's baseline is defined against.
CURRENT_BASELINE_DIR = Path(_CURRENT["directory"])
CURRENT_BASELINE_MARKER = _CURRENT["marker"]

# When the previous round's archive was cut, so the earliest anything in this round could
# have been written. Beside the marker because the window opens where the shipped release
# closes; kept apart they drift and re-report held candidates in our favour.
CURRENT_ROUND_SINCE = _CURRENT["round_since"]

# What to call the round now being collected, in the project's numbering. The report
# heading, the cumulative table's last row and the submission directory all read it here.
CURRENT_ROUND_LABEL = _CURRENT["round_label"]

# The current release's stamp for the time-weighted score, in his clock like the round
# rows. An unsent round defaults its receipt to now, not to its eventual send time.
CURRENT_BASELINE_RELEASED = _CURRENT["released_at"]

# The same files measured with the reviewer's own `equivalent_english_domains.py`.
# PAIRS is his RAW record count, never the validator-passing subset.
REVIEWER_BASELINE_PAIRS = _CURRENT["reviewer_pairs"]
REVIEWER_BASELINE_EE = Decimal(_CURRENT["reviewer_ee"])

# Per-year equivalent-English, the completion standard being stated against each year's own
# baseline. Always MEASURED by running his calculator over each file of the release, never
# by carrying our increments forward: a release absorbs several contributors' rounds, so the
# denominator moves without our increment moving.
REVIEWER_BASELINE_EE_BY_YEAR = {
    int(year): Decimal(value) for year, value in _CURRENT["reviewer_ee_by_year"].items()
}

# His 2002 to 2013 files of the same release, the extended baseline, measured the same way and
# kept apart so every core figure keeps meaning 1996 to 2001. Zero when a release has none.
EXTENDED_YEARS = range(2002, 2014)
REVIEWER_EXTENDED_PAIRS = _CURRENT["reviewer_extended_pairs"]
REVIEWER_EXTENDED_EE = Decimal(_CURRENT["reviewer_extended_ee"])
REVIEWER_EXTENDED_EE_BY_YEAR = {
    int(year): Decimal(value) for year, value in _CURRENT["reviewer_extended_ee_by_year"].items()
}

# The gate: this much EE growth in one part, 1996 to 2001 over REVIEWER_BASELINE_EE or 2002 to
# 2013 over REVIEWER_EXTENDED_EE. The parts are never summed.
GATE_PCT = Decimal(5)
GATE_EE = {
    "1996-2001": REVIEWER_BASELINE_EE * GATE_PCT / 100,
    "2002-2013": REVIEWER_EXTENDED_EE * GATE_PCT / 100,
}

# The corpus before this project's FIRST submission, `merged260715-2`, shipped as
# `legacy-data/`. **Not the cumulative denominator**: the cumulative contribution is
# quoted against the CURRENT corpus, `REVIEWER_BASELINE_EE`. Kept as the
# only release predating every contribution, so phase 1's increment stays checkable.
ORIGINAL_BASELINE_PAIRS = _DATA["original"]["pairs"]
ORIGINAL_BASELINE_EE = Decimal(_DATA["original"]["ee"])

# The rounds this project has SHIPPED, each row carrying the reviewer's ACCEPTED figures,
# not the ones submitted. As the JSON lists them: label, date, records, equivalent-English,
# baseline accepted against, awarded %, benchmark released, submission received (the last
# two "YYYY-MM-DD HH:MM" in his clock, which `ark.figures` turns into t_i). A cumulative
# claim is the one figure the store cannot regenerate, a merged round stopping being
# net-new, so these rows are read and never recomputed. Ledger: `docs/registers/rounds.md`.
SUBMITTED_ROUNDS = tuple(
    (
        row["label"],
        row["date"],
        row["records"],
        Decimal(row["equivalent_english"]),
        row["baseline"],
        Decimal(row["awarded_percent"]),
        row["benchmark_released"],
        row["submission_received"],
    )
    for row in _DATA["rounds"]
)


# `k` in the RANKING score `S_i = k * (p_i / t_i)`, which is not the cumulative
# percentage and is what decides positions. It makes speed worth as much as size;
# `docs/registers/rounds.md` works the arithmetic of round length through.
SUBMISSION_SPEED_K = _DATA["speed_k"]

# The annual file every candidate directory must hold to be the baseline: the earliest
# year the reviewer's corpus covers, so the probe follows the JSON rather than a literal.
_EARLIEST_YEAR_FILE = f"{min(REVIEWER_BASELINE_EE_BY_YEAR)}.txt"


def _first_holding(candidates: tuple[Path, ...], must_contain: str) -> Path:
    """The first candidate directory that actually holds `must_contain`.

    Address a baseline file by WHAT it is, never by where it sits. The repository keeps
    the baseline under git-ignored `ding/`, which `git archive` cannot carry;
    the delivery puts the same files at `baseline/<marker>/`, one level up from the
    `source/` tree the code runs from. A hardcoded path breaks `just reproduce` for
    everyone but us, so the resolution lives here rather than in each caller.
    """
    for base in candidates:
        if (base / must_contain).is_file():
            return base
    return candidates[0]


def baseline_dir() -> Path:
    """Where the current baseline's annual files actually are, repository or delivery."""
    return _first_holding(
        (
            CURRENT_BASELINE_DIR,
            Path("..") / "baseline" / CURRENT_BASELINE_MARKER,
            Path("baseline") / CURRENT_BASELINE_MARKER,
            Path("..") / "baseline" / CURRENT_BASELINE_DIR.name,
            Path("baseline") / CURRENT_BASELINE_DIR.name,
        ),
        _EARLIEST_YEAR_FILE,
    )


def calculator_path() -> Path:
    """The reviewer's own scorer, repository or delivery.

    Ordering matters here in a way it does not for the baseline: a round can hold two
    releases at once, and the current one must win.
    """
    return (
        _first_holding(
            (
                CURRENT_BASELINE_DIR.parent / "equivalent_english_domain_calculator",
                Path("..") / "equivalent_english_domain_calculator",
                Path("equivalent_english_domain_calculator"),
                Path("ding/feedback-phase-6/equivalent_english_domain_calculator"),
                Path("ding/feedback-phase-3/equivalent_english_domain_calculator"),
            ),
            "equivalent_english_domains.py",
        )
        / "equivalent_english_domains.py"
    )
