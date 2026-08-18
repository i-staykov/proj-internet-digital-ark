"""What the cumulative-score rule implies about WHEN to submit, not what to collect.

Ding's feedback of 2026-08-18 states the scoring rule for the first time: a cumulative
score is the **direct sum** of the percentage increases awarded for each accepted
submission, each percentage measured against the benchmark **as it stood when that
submission arrived**. Submissions are processed strictly in arrival order and the
benchmark is reissued after every one.

That makes timing a lever independent of collection, and it points the opposite way from
the intuition that a bigger round is a better round. Two forces act on the denominator:

- **our own increment**, which dilutes only our own later submissions, and
- **other contributors' increments**, which dilute ours and are outside our control.

When the second dominates, splitting a fixed body of work into several early submissions
beats holding it for one large one, because each part is scored against a smaller
denominator. Our own dilution is second order at present: an increment of 13,898 EE
against a 12,077,096 EE benchmark moves the denominator by 0.12%.

**The rates below are measured; anything forward-looking is a model and says so.** The
release totals are the reviewer's own published line 2 and the per-round figures are the
ones he credited, so the others' share is a subtraction of two of his numbers rather than
an estimate of ours.
"""

from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal

from ark.baseline import REVIEWER_BASELINE_EE

# The reviewer's published equivalent-English total for each release, the date it arrived,
# and how much of the step INTO it was ours. Every figure is his: the release totals are
# his line 2 (`merged260810` and `merged260815` in docs/notes.md 2026-08-15,
# `merged260817` and `merged260817-2` in his feedback of 2026-08-18), and the ours column
# is his accepted credit rather than our submitted claim.
#
# **The ours column is stated rather than derived from dates, and that is the whole
# correctness of this file.** A round is scored AGAINST a release and merged INTO the next
# one, so keying on the round's own date puts phase 5's 1,566,230 EE inside
# `merged260817`, which is precisely the benchmark it was measured against and therefore
# cannot contain it. Doing that understates other contributors' rate by 3.6x, which is
# enough to reverse the conclusion.
#
# `merged260817` is ours-zero for the same reason it is interesting: 230,393 of our records
# had already reached it through other contributors, so they raised his denominator without
# ever being credited to us.
RELEASES = (
    ("merged260715-2", date(2026, 7, 15), Decimal("4553314.7637"), Decimal(0)),
    # rounds 1, 3 and 4, whose intermediate releases he published no total for
    ("merged260810", date(2026, 8, 10), Decimal("6226386.4245"), Decimal("1451775.7555")),
    # another contributor's UMN DRUM delivery, 4,063,995 records
    ("merged260815", date(2026, 8, 15), Decimal("8346839.3737"), Decimal(0)),
    ("merged260817", date(2026, 8, 17), Decimal("10510865.7791"), Decimal(0)),
    ("merged260817-2", date(2026, 8, 17), REVIEWER_BASELINE_EE, Decimal("1566229.7613")),
)


def measured_intervals() -> list[dict]:
    """Per-interval growth of the benchmark, split into ours and everybody else's."""
    out = []
    pairs = zip(RELEASES, RELEASES[1:], strict=False)
    for (_, lo, lo_ee, _), (label, hi, hi_ee, ours) in pairs:
        days = (hi - lo).days
        if days <= 0:
            # merged260817-2 falls on the same day as merged260817: it IS our phase-5
            # merge, so it carries no elapsed time and no third-party growth to attribute.
            continue
        others = hi_ee - lo_ee - ours
        out.append(
            {
                "to": label,
                "days": days,
                "growth": hi_ee - lo_ee,
                "ours": ours,
                "others": others,
                "others_per_day": others / days,
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--in-hand",
        type=Decimal,
        default=Decimal("13898.1827"),
        help="equivalent-English collected and submittable now",
    )
    ap.add_argument(
        "--per-day",
        type=Decimal,
        default=Decimal("13200"),
        help="our own collection rate, equivalent-English per day",
    )
    ap.add_argument("--horizon", type=int, default=7, help="days to model")
    args = ap.parse_args()

    intervals = measured_intervals()

    print("== MEASURED: how fast the benchmark grows, and whose work grows it ==\n")
    head = f"{'to release':<16}{'days':>5}{'growth EE':>15}"
    print(head + f"{'ours':>14}{'others':>14}{'others/day':>13}")
    for row in intervals:
        print(
            f"{row['to']:<16}{row['days']:>5}{row['growth']:>15,.0f}"
            f"{row['ours']:>14,.0f}{row['others']:>14,.0f}"
            f"{row['others_per_day']:>13,.0f}"
        )

    first, latest = intervals[0], intervals[-1]
    print(
        f"\nOthers' rate is ACCELERATING across the three intervals: "
        f"{first['others_per_day']:,.0f} -> {intervals[1]['others_per_day']:,.0f} "
        f"-> {latest['others_per_day']:,.0f} EE/day, the newest being "
        f"{latest['others_per_day'] / first['others_per_day']:,.0f}x the oldest."
    )
    print(f"Our own recent rate, for scale: {args.per_day:,.0f} EE/day.")

    rate = latest["others_per_day"]
    b0 = REVIEWER_BASELINE_EE
    print(f"\n== MODEL: holding {args.in_hand:,.0f} EE while others add {rate:,.0f} EE/day ==\n")
    print(f"{'submit in':<12}{'benchmark':>16}{'our %':>12}{'credit lost':>13}{'5% costs':>14}")
    today = args.in_hand / b0 * 100
    for d in range(args.horizon + 1):
        bench = b0 + rate * d
        pct = args.in_hand / bench * 100
        when = "now" if d == 0 else f"{d} day(s)"
        print(
            f"{when:<12}{bench:>16,.0f}{pct:>11.5f}%"
            f"{(pct / today - 1) * 100:>12.1f}%{bench * Decimal('0.05'):>14,.0f}"
        )

    print("\n== MODEL: the same work submitted daily, against held for one round ==\n")
    daily = sum(args.per_day / (b0 + rate * d) for d in range(1, args.horizon + 1)) * 100
    batched = (args.per_day * args.horizon) / (b0 + rate * args.horizon) * 100
    print(f"  submit every day for {args.horizon} days : {daily:.5f}% cumulative")
    print(f"  hold it and submit on day {args.horizon}      : {batched:.5f}% cumulative")
    print(f"  submitting often is worth {(daily / batched - 1) * 100:+.1f}%")
    print(
        "\nEverything after the first table is a MODEL on one assumed rate, not a\n"
        "measurement. The measured part is enough for the conclusion on its own: the\n"
        "denominator inflates far faster than we collect, so the credit for work already\n"
        "done decays every day it is held back."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
