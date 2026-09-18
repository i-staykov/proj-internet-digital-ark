"""Which baseline release is current, in one place.

**The figures live in `data/baseline.json`; this module only loads them.** Point the
JSON at the new release and every command follows. `docs/registers/releases.md` names
every release the reviewer has issued.

Each release loads under its OWN marker namespace: the ingest ledger keys on file name
alone, so a second `1996.txt` is skipped as already seen. `ark ingest-legacy` with only
`--legacy-dir` reuses the marker below and skips all six files behind reassuring
"already ingested" lines, so pass `--marker-prefix` when loading a release the JSON does
not yet name. Loading a round against a stale baseline is silent: it reports as net-new
work the reviewer already holds, and only surfaces when he merges and disagrees.
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

# Resolved from this file, never from the working directory: the delivery unpacks the
# repository tree into `source/`, so the JSON sits beside `src/` there exactly as here.
_DATA = json.loads(
    (Path(__file__).resolve().parents[2] / "data" / "baseline.json").read_text(encoding="utf-8")
)
_CURRENT = _DATA["current"]

# The release the store's baseline is defined against.
CURRENT_BASELINE_DIR = Path(_CURRENT["directory"])
CURRENT_BASELINE_MARKER = _CURRENT["marker"]

# When the previous round's archive was cut, so the earliest anything in this round
# could have been written. Beside the marker because the window opens where the shipped
# release closes; kept apart they drift and re-report held candidates in our favour.
CURRENT_ROUND_SINCE = _CURRENT["round_since"]

# What to call the round now being collected, in Ivo's numbering. The report heading,
# the cumulative table's last row and the submission directory all read it from here.
CURRENT_ROUND_LABEL = _CURRENT["round_label"]

# The current release's stamp for the time-weighted score, in his clock like the round
# rows. An unsent round defaults its receipt to now, not to its eventual send time.
CURRENT_BASELINE_RELEASED = _CURRENT["released_at"]

# The same files measured with the reviewer's own `equivalent_english_domains.py`.
# PAIRS is his RAW record count, never the validator-passing subset.
REVIEWER_BASELINE_PAIRS = _CURRENT["reviewer_pairs"]
REVIEWER_BASELINE_EE = Decimal(_CURRENT["reviewer_ee"])

# Per-year equivalent-English, because the completion standard is stated against each
# year's own baseline. Always MEASURED by running his calculator over each file of the
# release, never by carrying our reported increments forward: a release absorbs several
# contributors' rounds, so the denominator can move without our increment moving.
REVIEWER_BASELINE_EE_BY_YEAR = {
    int(year): Decimal(value) for year, value in _CURRENT["reviewer_ee_by_year"].items()
}

# The corpus before this project's FIRST submission: `merged260715-2`, shipped as
# `legacy-data/`. **Not the cumulative denominator.** Ivo's instruction is to quote the
# cumulative contribution against the CURRENT corpus, `REVIEWER_BASELINE_EE`. Kept
# because it is the only release predating every contribution, so phase 1's measured
# increment stays checkable.
ORIGINAL_BASELINE_PAIRS = _DATA["original"]["pairs"]
ORIGINAL_BASELINE_EE = Decimal(_DATA["original"]["ee"])

# The rounds this project has SHIPPED, each row carrying the reviewer's ACCEPTED
# figures, not the ones it was submitted with. Ordered as the JSON lists them: label,
# date, records, equivalent-English, baseline accepted against, awarded %, benchmark
# released, submission received (the last two "YYYY-MM-DD HH:MM" in his clock, which
# `ark.figures` turns into t_i). A cumulative claim is the one figure the store cannot
# regenerate, because a merged round stops being net-new, so these rows are read and
# never recomputed. `docs/registers/rounds.md` is the ledger.
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


class AwardedScore(NamedTuple):
    """A ranking score the reviewer stated himself, with the divisor he used."""

    percent: Decimal
    divisor: int
    score: Decimal


def awarded_score_of(label: str) -> AwardedScore | None:
    """His own `S_i` for a round, where he has quoted one, else None.

    **Recorded because it does not reproduce.** Round 8 he wrote as
    `S = 10 x (18.769714 / 33) = 5.687792`, and 33 is neither reading of `t_i` we put to
    him. His figures are stored as quoted facts, like the awarded percentages, and
    `figures.score` stays the model of the rule we can defend.
    """
    for row in _DATA["rounds"]:
        if row["label"] == label and "awarded_score" in row:
            return AwardedScore(
                Decimal(row["awarded_percent"]),
                int(row["awarded_score_divisor"]),
                Decimal(row["awarded_score"]),
            )
    return None


# Round 1's percentage was awarded on RECORDS, so it is not commensurable with the
# equivalent-English percentages of later rounds. Summed with them anyway, on Ivo's
# instruction, and every place that prints the sum says so.
ROUND_ONE_IS_RECORD_BASED = _DATA["round_one_is_record_based"]

# `k` in the RANKING score `S_i = k * (p_i / t_i)`, which is not the cumulative
# percentage and is what decides positions. It makes speed worth as much as size, so
# round length is Ivo's call; `docs/registers/rounds.md` works the arithmetic through.
SUBMISSION_SPEED_K = _DATA["speed_k"]

# The annual file every candidate directory must hold to be the baseline: the earliest
# year the reviewer's corpus covers, so the probe follows the JSON rather than a literal.
_EARLIEST_YEAR_FILE = f"{min(REVIEWER_BASELINE_EE_BY_YEAR)}.txt"


def _first_holding(candidates: tuple[Path, ...], must_contain: str) -> Path:
    """The first candidate directory that actually holds `must_contain`.

    Address a baseline file by WHAT it is, never by where it sits. The repository keeps
    the baseline under git-ignored `feedback-phase-N/`, which `git archive` cannot carry;
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
                Path("feedback/feedback-phase-6/equivalent_english_domain_calculator"),
                Path("feedback/feedback-phase-3/equivalent_english_domain_calculator"),
            ),
            "equivalent_english_domains.py",
        )
        / "equivalent_english_domains.py"
    )
