"""The ranking score, `S_i = k * p_i / t_i`, computed the way the reviewer computes it.

From his brief update of 2026-08-20: `p_i` is the percentage he awards a round and
`t_i` the elapsed time from the release of the benchmark package the round is measured
against to the receipt of the submission. Reconstructed on 2026-09-02 from the mail
archive, his two quoted scores fix the rule to the digit: `t_i` is the elapsed time in
his clock, rounded UP to whole days. Round 6 ran 5.19 days from the `merged260821`
release and he quotes 6.88, so `t_6 = 6`; round 7 ran 11.77 days from the same release
and he quotes 6.302372, so `t_7 = 12`. Calendar days give round 6 `t = 5` and 8.26, and
counting them from the current release floored to one day is how round 7's report came
to state S = 226.43 for a round he scored at 6.302372.

Pure arithmetic over timestamp strings. The rounds themselves live in `ark.baseline`;
this module only knows how to turn two stamps and a percentage into his number.
"""

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from math import ceil
from zoneinfo import ZoneInfo

from ark.baseline import SUBMISSION_SPEED_K

# Every stamp the score reads is in HIS clock, US Pacific, as his mail client writes it.
HIS_ZONE = ZoneInfo("America/Los_Angeles")
STAMP = "%Y-%m-%d %H:%M"

# The brief update that introduced the score, in his clock. Rounds received before it
# were never scored by him, so their S is a would-be figure and the report says so.
SCORE_RULE_SINCE = "2026-08-20 03:37"

# He quotes S_7 to six places.
PLACES = Decimal("0.000001")


def parse_stamp(stamp: str) -> datetime:
    """A `YYYY-MM-DD HH:MM` string in his clock as an aware datetime."""
    return datetime.strptime(stamp, STAMP).replace(tzinfo=HIS_ZONE)


def now_in_his_clock() -> str:
    """The current minute as he would stamp it, for a round not yet received."""
    return datetime.now(tz=HIS_ZONE).strftime(STAMP)


def elapsed_days(release_ts: str, receipt_ts: str) -> Decimal:
    """Fractional days between two stamps, both in his clock."""
    seconds = (parse_stamp(receipt_ts) - parse_stamp(release_ts)).total_seconds()
    return Decimal(seconds) / Decimal(86400)


def t_days(release_ts: str, receipt_ts: str) -> int:
    """`t_i`: the elapsed time rounded up to whole days, never below one.

    The floor only matters for a receipt inside the release minute, where his rule
    would otherwise divide by zero.
    """
    return max(1, ceil(elapsed_days(release_ts, receipt_ts)))


def score(p: Decimal, t: int) -> Decimal:
    """`S_i = k * p_i / t_i`, to the six places he quotes."""
    return (SUBMISSION_SPEED_K * p / Decimal(t)).quantize(PLACES)


def cumulative(scores: Iterable[Decimal]) -> Decimal:
    """`S_total`, the sum of per-round scores."""
    return sum(scores, Decimal(0))


def scored_under_rule(receipt_ts: str) -> bool:
    """Whether a round received at `receipt_ts` fell under his score rule at all."""
    return parse_stamp(receipt_ts) >= parse_stamp(SCORE_RULE_SINCE)
