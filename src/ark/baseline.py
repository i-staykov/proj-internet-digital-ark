"""Which baseline release is current, in one place.

The reviewer reissues the merged 1996-2001 corpus after each round he accepts, and
every one of those releases has to be loaded under its own marker namespace, because
the ingest ledger keys on the file name alone and a second `1996.txt` would otherwise
be skipped as already seen. Six are now layered in the store: the originals,
`merged260727`, `merged260730`, `merged260802`, `merged260802-2` and `merged260810`.

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
CURRENT_BASELINE_DIR = Path("feedback-phase-4/merged260810")
CURRENT_BASELINE_MARKER = "merged260810"

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
REVIEWER_BASELINE_PAIRS = 11_362_034
REVIEWER_BASELINE_EE = Decimal("6226386.4245")

# Per-year equivalent-English of the same files, since the completion standard is
# stated against each year's own baseline rather than the whole-corpus total. These
# are his `merged260802-2` totals plus the per-year increases he reported on
# 2026-08-10; the six sum to REVIEWER_BASELINE_EE exactly, and each year's increase
# over the previous total reproduces his stated growth rate to six decimals.
REVIEWER_BASELINE_EE_BY_YEAR = {
    1996: Decimal("452533.8352"),
    1997: Decimal("823616.0668"),
    1998: Decimal("810983.8031"),
    1999: Decimal("1244880.5113"),
    2000: Decimal("1092291.9241"),
    2001: Decimal("1802080.2840"),
}
