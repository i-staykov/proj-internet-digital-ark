"""The ranking score, `S_i = k * p_i / t_i`, under both of his definitions of `t_i`.

**The rule changed on 2026-09-03 and the two answers differ by 3.6x, so this module
computes both rather than choosing.**

*The benchmark rule*, his brief update of 2026-08-20, and the one he has actually scored
under: `t_i` is the elapsed time from the release of the benchmark package the round is
measured against to the receipt of the submission, in his clock, rounded UP to whole
days. Reconstructed on 2026-09-02 from the mail archive, his two quoted scores fix it to
the digit: round 6 ran 5.19 days from the `merged260821` release and he quotes 6.88, so
`t_6 = 6`; round 7 ran 11.77 days from the same release and he quotes 6.302372, so
`t_7 = 12`. Calendar days give round 6 `t = 5` and 8.26, and counting them from the
current release floored to one day is how round 7's report came to state S = 226.43.

*The assignment rule*, his 0903 update, verbatim: `t_i = max(1, receipt_date_i -
task_assignment_date_member)`, in whole calendar days, where the origin is the date the
participant FIRST received the task and "the clock does not reset when a new benchmark is
released or when the participant makes a later submission". Under it round 7 scores
1.759 rather than 6.302372, because the interval becomes 43 days rather than 12.

**What is not derivable from his documents is whether the revision re-scores the two
rounds he has already awarded.** "The definition of t_i is revised throughout" and "all
participants are scored using one stable, participant-specific time origin" read
retroactively; his awarded figures were computed the other way. Both totals are reported
until he answers, and the question is on `docs/questions.md`.

Pure arithmetic over timestamp strings. The rounds themselves live in `ark.baseline`;
this module only knows how to turn two stamps and a percentage into his number.
"""

from collections.abc import Iterable
from datetime import date, datetime
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

# The origin of the assignment rule: the date this participant first received the task.
# His brief is stamped 2026-07-21 18:07:04 and round 1's benchmark was released
# 2026-07-21 12:24, so that is the earliest date any record here supports. **It is not
# confirmed by Ivo and one day of error moves every S_i**, which is why it is a named
# constant rather than a literal in a formula.
TASK_ASSIGNED_DATE = "2026-07-21"


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
    """`t_i` under the BENCHMARK rule: elapsed days rounded up, never below one.

    The one he has scored under, kept because his two awarded figures reproduce from it
    and nothing else fits them. The floor only matters for a receipt inside the release
    minute, where his rule would otherwise divide by zero.
    """
    return max(1, ceil(elapsed_days(release_ts, receipt_ts)))


def t_days_assignment(receipt_ts: str, assigned: str = TASK_ASSIGNED_DATE) -> int:
    """`t_i` under the ASSIGNMENT rule of 2026-09-03: whole calendar days, min 1.

    Dates, not stamps: he says "measured in whole calendar days" and "the same official
    date records", so the time of day drops out. The origin is one fixed date per
    participant and never moves, which is why every day of delay now costs every future
    submission as well as this one.
    """
    days = (date.fromisoformat(receipt_ts[:10]) - date.fromisoformat(assigned)).days
    return max(1, days)


def score(p: Decimal, t: int) -> Decimal:
    """`S_i = k * p_i / t_i`, to the six places he quotes."""
    return (SUBMISSION_SPEED_K * p / Decimal(t)).quantize(PLACES)


def cumulative(scores: Iterable[Decimal]) -> Decimal:
    """`S_total`, the sum of per-round scores."""
    return sum(scores, Decimal(0))


def scored_under_rule(receipt_ts: str) -> bool:
    """Whether a round received at `receipt_ts` fell under his score rule at all."""
    return parse_stamp(receipt_ts) >= parse_stamp(SCORE_RULE_SINCE)
