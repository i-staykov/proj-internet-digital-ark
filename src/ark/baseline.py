"""Which baseline release is current, in one place.

The reviewer reissues the merged 1996-2001 corpus after each round he accepts, and
every one of those releases has to be loaded under its own marker namespace, because
the ingest ledger keys on the file name alone and a second `1996.txt` would otherwise
be skipped as already seen. Seven are now layered in the store: the originals,
`merged260727`, `merged260730`, `merged260802`, `merged260802-2`, `merged260810` and
`merged260815`.

`merged260815` is the one that shows why this file matters. It arrived mid-round
carrying another contributor's UMN DRUM delivery, 4,063,995 records concentrated in
1999 and 2000, and it moved both sides of the ratio at once: the denominator up 34.06%
and our own increment down 32,880 EE to overlap. Measured against the release it
replaced the round read 2.1641%; against this one it reads 1.2204%. Neither number is
wrong, and only the second is the one the reviewer accepts against.

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
CURRENT_BASELINE_DIR = Path("feedback-phase-5/merged260815")
CURRENT_BASELINE_MARKER = "merged260815"

# The first moment anything in the current round could have been written, which is
# when the previous round's archive was cut (`submissions/phase-4/MANIFEST.txt`,
# `built 2026-08-09T13:51:03Z`). It lives beside the marker because a release and
# its round window are the same fact: the window opens where the shipped release
# closes. Kept apart, they drift, and a stale window re-reports the previous
# round's held candidates as this round's, silently and in our favour.
CURRENT_ROUND_SINCE = "2026-08-09 13:51:03+00"

# The same files measured with the reviewer's own `equivalent_english_domains.py`.
# PAIRS is the RAW record count, not the validator-passing subset: his line 1 tracks
# the raw count, and quoting the valid one reads to him as records lost since his
# previous message. For `merged260802-2` the split was 10,415,768 raw against
# 10,404,200 valid, the difference being embedded ports and underscore labels.
REVIEWER_BASELINE_PAIRS = 15_428_507
REVIEWER_BASELINE_EE = Decimal("8346839.3737")

# Per-year equivalent-English of the same files, since the completion standard is
# stated against each year's own baseline rather than the whole-corpus total. Measured
# by running his own `equivalent_english_domains.py` over each `merged260815` file
# rather than by carrying his reported increments forward, because this release came
# from another contributor's merge and no per-year statement of ours was involved.
# The six sum to REVIEWER_BASELINE_EE exactly.
REVIEWER_BASELINE_EE_BY_YEAR = {
    1996: Decimal("453162.0038"),
    1997: Decimal("833557.1096"),
    1998: Decimal("926521.2816"),
    1999: Decimal("1750212.8600"),
    2000: Decimal("2580907.2067"),
    2001: Decimal("1802478.9120"),
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
SUBMITTED_ROUNDS = (
    # label, date, records, equivalent-English, baseline measured against
    ("1", "2026-07-26", 1_429_524, Decimal("756559.2864"), "merged260715-2"),
    ("3", "2026-08-02", 151_949, Decimal("91814.6880"), "merged260730"),
    ("4", "2026-08-09", 946_266, Decimal("603401.7811"), "merged260802-2"),
)
