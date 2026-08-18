"""Which baseline release is current, in one place.

The reviewer reissues the merged 1996-2001 corpus after each round he accepts, and
every one of those releases has to be loaded under its own marker namespace, because
the ingest ledger keys on the file name alone and a second `1996.txt` would otherwise
be skipped as already seen. Eight are now layered in the store: the originals,
`merged260727`, `merged260730`, `merged260802`, `merged260802-2`, `merged260810`,
`merged260815` and `merged260817-2`.

`merged260815` is the one that shows why this file matters. It arrived mid-round
carrying another contributor's UMN DRUM delivery, 4,063,995 records concentrated in
1999 and 2000, and it moved both sides of the ratio at once: the denominator up 34.06%
and our own increment down 32,880 EE to overlap. Measured against the release it
replaced the round read 2.1641%; against this one it reads 1.2204%. Neither number is
wrong, and only the second is the one the reviewer accepts against.

`merged260817-2` did the same thing twice over, and it is why a round's ACCEPTED
figures have to be recorded separately from the ones it was submitted with. Between
`merged260815` and the unshipped `merged260817` the corpus grew from 15,428,507 to
19,883,096 records on other contributors' work, and 230,393 of ours arrived inside that
growth. So phase 5 was submitted as 2,838,715 records and 1,697,224.86 EE, and accepted
as 2,608,322 and 1,566,229.7613. Both are true; only the second is credited.

Keeping the current one here rather than as a default spelled out at each call site
is not tidiness. Loading a round against a stale baseline is not an error anyone sees:
it silently reports as net-new a body of work the reviewer already holds, and it is
only caught when he merges and the numbers disagree. That happened once, between
2 and 7 August 2026, when `merged260802` sat unread on disk for five days while
`ark stats` overstated net-new by the 151,949 records he had already credited.

Point `CURRENT_*` at the new release when one arrives and every command follows.
Two flags are mandatory when loading a release before this file names it, because
`--marker-prefix` defaults to the marker below: `ark ingest-legacy` with only
`--legacy-dir` composes a marker that already exists and skips all six files behind
six reassuring "already ingested" lines.
"""

from decimal import Decimal
from pathlib import Path

# The release the store's baseline is defined against.
CURRENT_BASELINE_DIR = Path("feedback-phase-6/merged260817-2")
CURRENT_BASELINE_MARKER = "merged260817-2"

# The first moment anything in the current round could have been written, which is
# when the previous round's archive was cut (`submissions/phase-5/MANIFEST.txt`,
# `built 2026-08-17T09:34:55Z`). It lives beside the marker because a release and
# its round window are the same fact: the window opens where the shipped release
# closes. Kept apart, they drift, and a stale window re-reports the previous
# round's held candidates as this round's, silently and in our favour.
CURRENT_ROUND_SINCE = "2026-08-17 09:34:55+00"

# What to call the round now being collected, in Ivo's numbering. The report heading,
# the cumulative table's last row and the submission directory all take it from here,
# because they were three separate hardcoded "5"s and one of them was still saying 4
# a week into the round.
CURRENT_ROUND_LABEL = "6"

# The same files measured with the reviewer's own `equivalent_english_domains.py`.
# PAIRS is the RAW record count, not the validator-passing subset: his line 1 tracks
# the raw count, and quoting the valid one reads to him as records lost since his
# previous message. For `merged260802-2` the split was 10,415,768 raw against
# 10,404,200 valid, the difference being embedded ports and underscore labels.
REVIEWER_BASELINE_PAIRS = 22_491_418
REVIEWER_BASELINE_EE = Decimal("12077095.5404")

# Per-year equivalent-English of the same files, since the completion standard is
# stated against each year's own baseline rather than the whole-corpus total. Measured
# by running his own `equivalent_english_domains.py` over each `merged260817-2` file
# rather than by carrying reported increments forward, because a release absorbs
# several contributors' rounds and no per-year statement of ours covers it.
# The six sum to REVIEWER_BASELINE_EE exactly, which is the check that they are his
# numbers and not ours: he published only the total, 12,077,095.5404, and these six
# reproduce it to the digit.
REVIEWER_BASELINE_EE_BY_YEAR = {
    1996: Decimal("512261.2220"),
    1997: Decimal("1066414.0190"),
    1998: Decimal("1387485.6867"),
    1999: Decimal("2714773.8715"),
    2000: Decimal("3975913.5149"),
    2001: Decimal("2420247.2263"),
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
ORIGINAL_BASELINE_PAIRS = 8_224_963
ORIGINAL_BASELINE_EE = Decimal("4553314.7637")

# The rounds this project has SHIPPED, numbered as Ivo numbers them: 1, 3, 4, 5.
# This is the repository's own phase numbering, and the gap at 2 is real. Phase 2 was
# 17,418 pairs, was never sent as a scored round, and was rolled into phase 3.
#
# Only shipped rounds appear. Three interim reports were sent between them, on
# 2026-08-05, 08-06 and 08-12, and each was measured against the same baseline as the
# shipped round that followed, so each is already contained in one of these four rows.
# Ivo's instruction of 2026-08-17 is not to mention them; listing them would in any
# case invite the double-count this tuple exists to prevent.
#
# A cumulative claim is the one figure the store cannot regenerate: a round the
# reviewer has merged stops being net-new the moment he merges it.
#
# Round 1 carries a MEASURED equivalent-English rather than a quoted one, because the
# metric did not exist in July. Its record count is the reviewer's own confirmed
# figure ("the six yearly files grew from 8,224,963 to 9,654,487 records, adding
# 1,429,524 records (17.38%)", feedback of 2026-07-27), and the weight beside it is
# the difference between those same two releases under the fixed model. The two were
# computed independently and the record delta lands on his figure exactly, which is
# what makes the weight trustworthy.
#
# The merged260727 -> merged260730 step is NOT here and must never be added. Those
# 609,145 records are an external contributor's round, filed under
# `feedback-external-phase-2/`, and its feedback describes regional directory
# harvesting across eleven non-English countries, which is not this project's work.
# Every row carries the reviewer's ACCEPTED figures, which are not always the ones the
# round was submitted with. Phase 5 went out at 2,838,715 records and 1,697,224.86 EE
# against `merged260815`, and he credited 2,608,322 and 1,566,229.7613 because 230,393
# of those records had already reached the unshipped `merged260817` through other
# contributors. Quoting the submitted figure would overstate the cumulative by exactly
# that overlap, and the overlap is only ever visible in his reply.
SUBMITTED_ROUNDS = (
    # label, date, records, equivalent-English, baseline accepted against
    ("1", "2026-07-26", 1_429_524, Decimal("756559.2864"), "merged260715-2"),
    ("3", "2026-08-02", 151_949, Decimal("91814.6880"), "merged260730"),
    ("4", "2026-08-09", 946_266, Decimal("603401.7811"), "merged260802-2"),
    ("5", "2026-08-17", 2_608_322, Decimal("1566229.7613"), "merged260817"),
)


def _first_holding(candidates: tuple[Path, ...], must_contain: str) -> Path:
    """The first candidate directory that actually holds `must_contain`.

    **Addressing a file by where it happens to sit rather than by what it is has broken
    this project's own delivery three times.** `docs/notes.md` for 2026-08-17 records the
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
        "1996.txt",
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
                Path("feedback-phase-5") / "equivalent_english_domain_calculator",
                Path("feedback-phase-3") / "equivalent_english_domain_calculator",
            ),
            "equivalent_english_domains.py",
        )
        / "equivalent_english_domains.py"
    )
