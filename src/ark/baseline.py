"""Which baseline release is current, in one place.

The reviewer reissues the merged 1996-2001 corpus after each round he accepts, and
every one of those releases has to be loaded under its own marker namespace, because
the ingest ledger keys on the file name alone and a second `1996.txt` would otherwise
be skipped as already seen. Four are now layered in the store: the originals,
`merged260727`, `merged260730` and `merged260802`.

Keeping the current one here rather than as a default spelled out at each call site
is not tidiness. Loading a round against a stale baseline is not an error anyone sees:
it silently reports as net-new a body of work the reviewer already holds, and it is
only caught when he merges and the numbers disagree. That has already cost this
project once, when `merged260802` sat unread on disk for five days while `ark stats`
quietly overstated net-new by the 151,949 records he had credited on 2 August.

Point `CURRENT_*` at the new release when one arrives and every command follows.
"""

from decimal import Decimal
from pathlib import Path

# The release the store's baseline is defined against.
CURRENT_BASELINE_DIR = Path("feedback-phase-3/merged260802-2")
CURRENT_BASELINE_MARKER = "merged260802-2"

# The same files measured with the reviewer's own `equivalent_english_domains.py`,
# reported to him on 4 August without objection. PAIRS is the RAW record count, not
# the validator-passing subset: his line 1 tracks the raw count, and quoting the valid
# one reads to him as 11,568 records lost since his previous message.
REVIEWER_BASELINE_PAIRS = 10_415_768
REVIEWER_BASELINE_EE = Decimal("5622984.6434")

# Per-year equivalent-English of the same files, since the completion standard is
# stated against each year's own baseline rather than the whole-corpus total.
REVIEWER_BASELINE_EE_BY_YEAR = {
    1996: Decimal("436608.5583"),
    1997: Decimal("785802.0843"),
    1998: Decimal("698408.2027"),
    1999: Decimal("1081431.7776"),
    2000: Decimal("932153.5050"),
    2001: Decimal("1688580.5155"),
}
