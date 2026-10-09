"""The ranking score, `S_i = k * p_i / t_i`, with `t_i` in whole calendar days.

`t_i` counts whole calendar days from the task assignment, `TASK_ASSIGNED_DATE`, never below
one, and never resets (`t_days_assignment`): his round 8 and 9 divisors, 33 and 39, put the
assignment there. `t_days` is the benchmark clock, release to receipt rounded up, which his
round 6 and 7 scores fit; `rounds.py` fills `S_i computed` with it. Stamps are in his clock,
US Pacific. Pure arithmetic over timestamp strings; the rounds live in `ark.baseline`.
"""

from datetime import date, datetime
from decimal import Decimal
from math import ceil
from zoneinfo import ZoneInfo

from ark.baseline import SUBMISSION_SPEED_K

# Every stamp the score reads is in HIS clock, US Pacific, as his mail client writes it.
HIS_ZONE = ZoneInfo("America/Los_Angeles")
STAMP = "%Y-%m-%d %H:%M"

# He quotes S_7 to six places; from round 11 on, growth to ten and S to nine.
PLACES = Decimal("0.000001")

# The origin of the assignment rule, read out of his own arithmetic, not our receipts:
# he scored round 8 as 10 x (18.769714 / 33), so the divisor 33
# puts the origin here. One day of error moves every S_i.
TASK_ASSIGNED_DATE = "2026-08-02"


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

    The floor only matters for a receipt inside the release minute, which would divide
    by zero.
    """
    return max(1, ceil(elapsed_days(release_ts, receipt_ts)))


def t_days_assignment(receipt_ts: str, assigned: str = TASK_ASSIGNED_DATE) -> int:
    """`t_i` under the ASSIGNMENT rule: whole calendar days, min 1.

    Dates, not stamps: "measured in whole calendar days", so time of day drops out.
    """
    days = (date.fromisoformat(receipt_ts[:10]) - date.fromisoformat(assigned)).days
    return max(1, days)


def score(p: Decimal, t: int, places: Decimal = PLACES) -> Decimal:
    """`S_i = k * p_i / t_i`, to the six places he quotes unless told otherwise."""
    return (SUBMISSION_SPEED_K * p / Decimal(t)).quantize(places)


def score_line(p: Decimal, t: int) -> str:
    """One part's S at his round 11 digits, `S = 10 x (28.8813137522 / 67) = 4.310643844`."""
    growth = p.quantize(Decimal("1E-10"))
    return f"S = {SUBMISSION_SPEED_K} x ({growth:f} / {t}) = {score(growth, t, Decimal('1E-9')):f}"
