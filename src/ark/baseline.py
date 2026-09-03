"""Which baseline release is current, in one place.

The reviewer reissues the merged 1996-2001 corpus after each round he accepts, and
every one of those releases has to be loaded under its own marker namespace, because
the ingest ledger keys on the file name alone and a second `1996.txt` would otherwise
be skipped as already seen. Several are now layered in the store; `docs/releases.md`
is the table of every release he has named.

`merged260815` is the one that shows why this file matters. It arrived mid-round
carrying another contributor's UMN DRUM delivery, 4,063,995 records concentrated in
1999 and 2000, and it moved both sides of the ratio at once: the denominator up 34.06%
and our own increment down 32,880 EE to overlap. Measured against the release it
replaced the round read 2.1641%; against this one it reads 1.2204%. Neither number is
wrong, and only the second is the one the reviewer accepts against.

`merged260817-2` did the same thing twice over, and it is why a round's ACCEPTED
figures have to be recorded separately from the ones it was submitted with. Between
`merged260815` and the unshipped `merged260817` the corpus grew on other contributors'
work while ours arrived inside that growth, so a round was submitted with one pair of
figures and credited with another. Both are true; only the second is credited.

Keeping the current one here rather than as a default spelled out at each call site
is not tidiness. Loading a round against a stale baseline is not an error anyone sees:
it silently reports as net-new a body of work the reviewer already holds, and it is
only caught when he merges and the numbers disagree. That happened once, between
2 and 7 August 2026, when `merged260802` sat unread on disk for five days while
`ark stats` overstated net-new by the records he had already credited.

**The figures themselves live in `data/baseline.json` and this module only loads them.**
A hand-edited constant block is the one place an intake can be silently wrong, and it
was one release behind on the day that was written. Point the JSON at the new release
and every command follows. Two flags are mandatory when loading a release before the
JSON names it, because `--marker-prefix` defaults to the marker below: `ark ingest-legacy`
with only `--legacy-dir` composes a marker that already exists and skips all six files
behind six reassuring "already ingested" lines.
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

# The first moment anything in the current round could have been written, which is
# when the previous round's archive was cut. It lives beside the marker because a
# release and its round window are the same fact: the window opens where the shipped
# release closes. Kept apart, they drift, and a stale window re-reports the previous
# round's held candidates as this round's, silently and in our favour.
CURRENT_ROUND_SINCE = _CURRENT["round_since"]

# What to call the round now being collected, in Ivo's numbering. The report heading,
# the cumulative table's last row and the submission directory all take it from here,
# because they were three separate hardcoded round numbers and one of them was still a
# round behind a week into the round.
CURRENT_ROUND_LABEL = _CURRENT["round_label"]

# The current release's stamp, for the time-weighted score: the mail that carried it,
# in his clock like the round rows. The receipt stamp is filled at send time and
# defaults to now in his clock, so an unsent round reads as if it went out this minute
# rather than scoring itself faster than it will.
CURRENT_BASELINE_RELEASED = _CURRENT["released_at"]

# The same files measured with the reviewer's own `equivalent_english_domains.py`.
# PAIRS is the RAW record count, not the validator-passing subset: his line 1 tracks
# the raw count, and quoting the valid one reads to him as records lost since his
# previous message. For one release the split was 10,415,768 raw against 10,404,200
# valid, the difference being embedded ports and underscore labels.
REVIEWER_BASELINE_PAIRS = _CURRENT["reviewer_pairs"]
REVIEWER_BASELINE_EE = Decimal(_CURRENT["reviewer_ee"])

# Per-year equivalent-English of the same files, since the completion standard is
# stated against each year's own baseline rather than the whole-corpus total. Measured
# by running his own `equivalent_english_domains.py` over each file of the release
# rather than by carrying reported increments forward, because a release absorbs
# several contributors' rounds and no per-year statement of ours covers it.
#
# The current release was checked line by line on 2026-09-02 as the previous one plus our
# accepted round: 36,698,388 + 2,538,900 = 39,237,288 records, and its 20,714,526.9732 EE
# is his 19,258,068.8703 plus our 1,456,458.1029 to the digit. That previous merge was
# never released; its totals exist only in his mail, which is why the check is recorded.
#
# The scale moved under us at the end of August 2026: the platform-hostname releases
# added millions of third-level hostnames under mass-hosting platforms at 2001, which
# is the workflow the reviewer's own brief update had just described. Overlap with our
# unsubmitted round was tiny, because we collect registrable domains and that wave
# collects hostnames, so the denominator grew while our increment barely moved and the
# 5% trigger jumped with it. `docs/releases.md` carries the per-release counts.
REVIEWER_BASELINE_EE_BY_YEAR = {
    int(year): Decimal(value) for year, value in _CURRENT["reviewer_ee_by_year"].items()
}

# The corpus as it stood before this project's FIRST submission: `merged260715-2`,
# which ships as `legacy-data/`. Measured with the reviewer's own calculator and its
# unchanged weight model, which reproduces his published line 2 for every later
# release to the digit.
#
# **Not the cumulative denominator.** Ivo's instruction of 2026-08-17 is to quote the
# cumulative contribution against the CURRENT corpus, `REVIEWER_BASELINE_EE`, which is
# the number he is scored on. Kept because it is the only release predating every
# contribution and is what makes phase 1's measured increment checkable.
ORIGINAL_BASELINE_PAIRS = _DATA["original"]["pairs"]
ORIGINAL_BASELINE_EE = Decimal(_DATA["original"]["ee"])

# The rounds this project has SHIPPED, each row carrying the reviewer's ACCEPTED
# figures rather than the ones it was submitted with. Ordered as the JSON lists them:
# label, date, records, equivalent-English, baseline accepted against, awarded %,
# benchmark released, submission received (the last two "YYYY-MM-DD HH:MM" in his
# clock, US Pacific, which `ark.figures` turns into t_i).
#
# `docs/rounds.md` is the ledger: which rounds exist and why, where each awarded
# percentage is quoted from, what must never be added to it, and the whole-day reading
# of t_i that reproduces both scores he has quoted. A cumulative claim is the one
# figure the store cannot regenerate, because a round the reviewer has merged stops
# being net-new the moment he merges it, so the rows are read and never recomputed.
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

# The round whose percentage was awarded on records, so it is not commensurable with
# the equivalent-English percentages of every later round. It is summed with them
# anyway, on Ivo's instruction of 2026-09-02, and every place that prints the sum says so.
ROUND_ONE_IS_RECORD_BASED = _DATA["round_one_is_record_based"]

# `k` in the competition RANKING score `S_i = k * (p_i / t_i)`, which is not the
# cumulative percentage and is the number that decides positions. From the brief update
# of 2026-08-20. It makes speed worth as much as size; `docs/rounds.md` works the
# arithmetic through and says why the round length is Ivo's decision, not a logistics one.
SUBMISSION_SPEED_K = _DATA["speed_k"]

# The annual file every candidate directory must hold to be the baseline: the earliest
# year the reviewer's corpus covers, so the probe follows the JSON rather than a literal.
_EARLIEST_YEAR_FILE = f"{min(REVIEWER_BASELINE_EE_BY_YEAR)}.txt"


def _first_holding(candidates: tuple[Path, ...], must_contain: str) -> Path:
    """The first candidate directory that actually holds `must_contain`.

    **Addressing a file by where it happens to sit rather than by what it is has broken
    this project's own delivery three times.** The git log for 2026-08-17 records the
    first two: the calculator path hardcoded to `feedback-phase-3/`, then the merged
    baseline one step later. The third was found on 2026-08-18 by auditing the delivery
    against D1, and is the worst of them, because it breaks the reproduction route the
    archive tells a reviewer to run.

    The repository keeps the baseline under `feedback-phase-N/`, which is **git-ignored**,
    so `git archive HEAD` cannot carry it and no fresh extraction has that path. The
    archive puts the same six files at `baseline/<marker>/`, one level up from the
    `source/` directory the code runs from. `ark ingest-legacy` defaulted to the
    repository path with no fallback, so `just reproduce` died at its first stage with
    "missing year files in feedback-phase-6/merged260817-2" for anybody but us.

    So the resolution lives here, in the module that owns the fact of which release is
    current, rather than in each caller. Two callers already had their own copy.
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
