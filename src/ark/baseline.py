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
CURRENT_BASELINE_DIR = Path("feedback/feedback-phase-8/Domain_Data_Collection_Task/merged260902-3")
CURRENT_BASELINE_MARKER = "merged260902-3"

# The first moment anything in the current round could have been written, which is
# when the previous round's archive was cut (`submissions/phase-7/MANIFEST.txt`,
# `built 2026-09-02T12:14:46Z`). It lives beside the marker because a release and
# its round window are the same fact: the window opens where the shipped release
# closes. Kept apart, they drift, and a stale window re-reports the previous
# round's held candidates as this round's, silently and in our favour.
CURRENT_ROUND_SINCE = "2026-09-02 12:14:46+00"

# What to call the round now being collected, in Ivo's numbering. The report heading,
# the cumulative table's last row and the submission directory all take it from here,
# because they were three separate hardcoded "5"s and one of them was still saying 4
# a week into the round.
CURRENT_ROUND_LABEL = "8"

# The same files measured with the reviewer's own `equivalent_english_domains.py`.
# PAIRS is the RAW record count, not the validator-passing subset: his line 1 tracks
# the raw count, and quoting the valid one reads to him as records lost since his
# previous message. For `merged260802-2` the split was 10,415,768 raw against
# 10,404,200 valid, the difference being embedded ports and underscore labels.
REVIEWER_BASELINE_PAIRS = 39_237_288
REVIEWER_BASELINE_EE = Decimal("20714526.9732")

# Per-year equivalent-English of the same files, since the completion standard is
# stated against each year's own baseline rather than the whole-corpus total. Measured
# by running his own `equivalent_english_domains.py` over each `merged260902-3` file
# rather than by carrying reported increments forward, because a release absorbs
# several contributors' rounds and no per-year statement of ours covers it.
#
# **`merged260902-3` is `merged260902-2` plus our accepted phase 7**: 36,698,388 +
# 2,538,900 = 39,237,288 records, verified line by line on 2026-09-02, and its EE of
# 20,714,526.9732 is his 19,258,068.8703 plus our 1,456,458.1029 to the digit.
# `merged260902-2` itself was never released; its totals exist only in his mail.
#
# **`merged260902` followed one day later with +2,823,477 records and +1,469,347 EE**, of
# which 2001 alone took +1,249,752 EE (12.89M records): the same platform-hostname wave,
# still landing. The 5% trigger is now 961,996.8 EE. The paragraph below describes the
# 0901 step and stays because it is what changed the scale.
#
# **`merged260901` was the platform-hostname release, and it changed the game's scale.**
# One day after `merged260830` it adds +4,690,367 records at 2001 alone (5.85M to
# 10.54M), +740,322 at 2000 and +320,801 at 1999, almost entirely third-level hostnames
# under mass-hosting platforms: the very workflow Ding's 0901 update added to the brief.
# Overlap with our unsubmitted round is tiny, 26,667 of 513,758 net-new 2001 pairs
# (5.2%), because we collect registrable domains and this wave collects hostnames. So
# the denominator grew +3,239,135 EE (+22.3%) while barely touching our increment, and
# the 5% trigger moved from 726,573 to 888,529 EE. Figures from his own calculator run
# over each file of the release.
REVIEWER_BASELINE_EE_BY_YEAR = {
    1996: Decimal("583717.4598"),
    1997: Decimal("1229302.1248"),
    1998: Decimal("1703250.1788"),
    1999: Decimal("3383015.2270"),
    2000: Decimal("5856084.1034"),
    2001: Decimal("7959157.8794"),
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

# The rounds this project has SHIPPED, numbered as Ivo numbers them: 1, 3, 4, 5, 6, 7.
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
    # label, date, records, equivalent-English, baseline accepted against, awarded %,
    # benchmark released, submission received (both "YYYY-MM-DD HH:MM" in his clock)
    #
    # Column 6 is the percentage HE awarded, quoted from his feedback, because the
    # cumulative record is the direct arithmetic sum of those percentages and not a ratio
    # anything here can recompute: each was taken against the baseline of the day it
    # arrived, and those baselines are gone. Sources, in order:
    # round 1  feedback of 2026-07-27, "adding 1,429,524 records (17.38%)". A RECORD
    #          percentage: the equivalent-English metric came after it. Ivo's decision of
    #          2026-09-02 is to carry it in the cumulative record anyway, flagged as such.
    # round 3  feedback of 2026-08-03, "91,814.6880, equal to 1.659986% of the merged260730
    #          baseline of 5,531,053.6089".
    # round 4  feedback of 2026-08-10, "increased by 603,401.7811 ... a 10.730988% increase
    #          over merged260802-2".
    # round 5  feedback of 2026-08-18, credited 2,608,322 records and 1,566,229.7613 EE at
    #          14.901054%, against the 2,838,715 and 1,697,224.86 that were sent.
    # round 6  feedback of 2026-08-27, credited 1,684,903 records and 562,099.5294 EE at
    #          4.130718% against `merged260826`, from the 1,929,655 and 713,481.4198 that
    #          were sent against `merged260821`.
    # round 7  feedback of 2026-09-02, credited 2,538,900 records and 1,456,458.1029 EE at
    #          7.562846% against `merged260902-2`, from the 2,541,429 and 1,458,263.2088 that
    #          were sent; S_7 = 6.302372, so t_7 = 12 days, from the 2026-08-21 release.
    #
    # Columns 7 and 8 are the two timestamps the time-weighted score divides by, to the
    # minute and in HIS clock, US Pacific, because the brief requires one zone for all
    # participants: when his mail released the benchmark package a round was measured
    # against, and when his client stamped the mail carrying the submission. Reconstructed
    # on 2026-09-02 from the mail archive and checked against this repository's commit times
    # on five rounds. `ark.figures` turns them into t_i as the elapsed time rounded UP to
    # whole days, the one rule that reproduces both scores he has quoted: round 6 ran 5.19
    # days from the 2026-08-21 11:19 release and he quotes 6.88 (t = 6); round 7 ran 11.77
    # days from the same release and he quotes 6.302372 (t = 12). Rounds 1 to 5 predate the
    # rule and carry their stamps for the record only.
    (
        "1",
        "2026-07-26",
        1_429_524,
        Decimal("756559.2864"),
        "merged260715-2",
        Decimal("17.38"),
        "2026-07-21 12:24",
        "2026-07-26 18:30",
    ),
    (
        "3",
        "2026-08-02",
        151_949,
        Decimal("91814.6880"),
        "merged260730",
        Decimal("1.659986"),
        "2026-07-31 17:25",
        "2026-08-01 19:42",
    ),
    (
        "4",
        "2026-08-09",
        946_266,
        Decimal("603401.7811"),
        "merged260802-2",
        Decimal("10.730988"),
        "2026-08-03 05:36",
        "2026-08-09 07:58",
    ),
    (
        "5",
        "2026-08-17",
        2_608_322,
        Decimal("1566229.7613"),
        "merged260817",
        Decimal("14.901054"),
        "2026-08-15 10:27",
        "2026-08-17 03:03",
    ),
    (
        "6",
        "2026-08-27",
        1_684_903,
        Decimal("562099.5294"),
        "merged260826",
        Decimal("4.130718"),
        "2026-08-21 11:19",
        "2026-08-26 15:51",
    ),
    (
        "7",
        "2026-09-02",
        2_538_900,
        Decimal("1456458.1029"),
        "merged260902-2",
        Decimal("7.562846"),
        "2026-08-21 11:19",
        "2026-09-02 05:50",
    ),
)

# Round 1's percentage was awarded on records, so it is not commensurable with the
# equivalent-English percentages of every later round. It is summed with them anyway,
# on Ivo's instruction of 2026-09-02, and every place that prints the sum says so.
ROUND_ONE_IS_RECORD_BASED = "1"

# The current round's release stamp, for the same arithmetic: his mail of 2026-09-02
# carrying `merged260902-3` (the phase-7 feedback zip), in his clock like the rows above.
# The receipt stamp is filled at send time and defaults to now in his clock, so an unsent
# round reads as if it went out this minute rather than scoring itself faster than it will.
CURRENT_BASELINE_RELEASED = "2026-09-02 10:31"

# The competition RANKING score, which is not the cumulative percentage and is the number
# that decides positions. From the brief update of 2026-08-20: `S_i = k * (p_i / t_i)` with
# `k = 10`, `p_i` the awarded percentage and `t_i` the elapsed days from the release of the
# benchmark a submission is measured against to its receipt. `S_total` is the sum.
#
# **This makes speed worth as much as size, and the arithmetic is brutal.** Round 6 took six
# days from `merged260821` to receipt and awarded 4.130718%, so `S_6 = 10 * 4.130718 / 6 =
# 6.88`, which is the figure he quotes back. The same 4.13% delivered in two days would have
# scored 20.65. Three separate 1.4% rounds at two days each would score 21.0 against the
# 6.88 one 4.13% round actually earned.
#
# So the round length is a scoring decision, not a logistics one, and it belongs to Ivo.
SUBMISSION_SPEED_K = 10


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
                Path("feedback/feedback-phase-6/equivalent_english_domain_calculator"),
                Path("feedback/feedback-phase-3/equivalent_english_domain_calculator"),
            ),
            "equivalent_english_domains.py",
        )
        / "equivalent_english_domains.py"
    )
