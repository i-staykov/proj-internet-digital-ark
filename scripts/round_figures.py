"""Print the round's figures in the five fields the reviewer asked for.

He set the reporting format on 6 August and it is not the same shape as our own
report: lines 1 and 2 are the state of HIS merged database before our increment,
lines 3 and 4 are what we add, and line 5 is 4 divided by 2. Keeping his
convention in code rather than in someone's head is the only way the growth rate
stays comparable between rounds, because the obvious alternative, dividing by the
post-increment total, is wrong by about 2% of itself and looks right.

Lines 1 and 2 are constants: they are his database, measured once with his own
calculator over his merged annual files and confirmed by him. They move only when
he merges a round.

`--verify` re-runs the increment through his `equivalent_english_domains.py`, one
file per year, and fails if the answer differs from ours. That check is the reason
the increment can be quoted to him as measured rather than as claimed, and it also
catches records his validator rejects and ours does not, which is a live risk every
time a source widens: a rejected record scores zero for him and full weight for us.

    uv run python scripts/round_figures.py
    uv run python scripts/round_figures.py --verify

Read-only, so it is safe to run while the collectors are working.
"""

import argparse
import json
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402

from ark.english_share import english_weights  # noqa: E402

STORE = Path("data/ark.duckdb")
CALCULATOR = Path(
    "feedback-phase-3/equivalent_english_domain_calculator/equivalent_english_domains.py"
)

# The engines started against the store at 20:09 UTC on 3 August, the first moment
# anything in this round could have been written.
SINCE = "2026-08-03 18:09:00+00"

# His merged 1996-2001 files after the last round was folded in, measured with his
# calculator and reported to him on 4 August without objection. His own message
# quotes the PRE-merge pair, 10,263,632 and 5,531,053.6089, so do not copy those.
BASELINE_PAIRS = 10_404_200
BASELINE_EE = Decimal("5622984.6434")

# Per-year equivalent-English of the same merged files, needed because the
# completion standard is stated against each year's own baseline.
BASELINE_EE_BY_YEAR = {
    1996: Decimal("436608.5583"),
    1997: Decimal("785802.0843"),
    1998: Decimal("698408.2027"),
    1999: Decimal("1081431.7776"),
    2000: Decimal("932153.5050"),
    2001: Decimal("1688580.5155"),
}

# What he credited for the previous round, used only for the comparison line.
LAST_PAIRS = 151_949
LAST_EE = Decimal("91814.6880")

# A pair the shared baseline already holds is not ours to report. `prior_reused` is
# the evidence type recording that a pair arrived with the baseline.
NOT_BASELINE = """
    NOT EXISTS (
        SELECT 1 FROM evidence p
        WHERE p.domain = y.domain AND p.evidence_year = y.assigned_year
          AND p.evidence_type = 'prior_reused'
    )
"""


def open_store(attempts: int = 40, pause: float = 15.0) -> duckdb.DuckDBPyConnection:
    """Wait out the maintain loop rather than failing the whole measurement."""
    for remaining in range(attempts, 0, -1):
        try:
            return duckdb.connect(str(STORE), read_only=True)
        except duckdb.IOException:
            if remaining == 1:
                raise
            time.sleep(pause)
    raise RuntimeError("unreachable")


def increment(conn: duckdb.DuckDBPyConnection) -> dict:
    weights = english_weights()
    rows = conn.execute(f"""
        SELECT s.name, split_part(y.domain, '.', -1) AS tld,
               y.assigned_year, count(*) AS pairs
        FROM domain_year y
        JOIN evidence e ON e.evidence_id = y.evidence_id
        JOIN source s ON s.source_id = e.source_id
        WHERE y.verified_at >= TIMESTAMPTZ '{SINCE}' AND {NOT_BASELINE}
        GROUP BY 1, 2, 3
    """).fetchall()

    by_source: dict[str, list] = {}
    by_year: dict[int, list] = {}
    for name, tld, year, pairs in rows:
        ee = weights.get(tld, Decimal(0)) * pairs
        for bucket, key in ((by_source, name), (by_year, int(year))):
            slot = bucket.setdefault(key, [0, Decimal(0)])
            slot[0] += pairs
            slot[1] += ee

    domains = conn.execute(f"""
        SELECT count(DISTINCT y.domain) FROM domain_year y
        WHERE y.verified_at >= TIMESTAMPTZ '{SINCE}' AND {NOT_BASELINE}
    """).fetchone()[0]

    # Dated by one source but not yet corroborated, so not in an annual file. Same
    # definition as the 119,055 quoted last round, so the two are comparable.
    held = conn.execute(f"""
        SELECT count(DISTINCT e.domain) FROM evidence e
        JOIN source s ON s.source_id = e.source_id
        WHERE s.name = 'usenet_mention' AND e.ingested_at >= TIMESTAMPTZ '{SINCE}'
          AND NOT EXISTS (SELECT 1 FROM domain_year y WHERE y.domain = e.domain)
    """).fetchone()[0]

    return {
        "by_source": by_source,
        "by_year": by_year,
        "pairs": sum(v[0] for v in by_year.values()),
        "ee": sum((v[1] for v in by_year.values()), Decimal(0)),
        "domains": domains,
        "held": held,
    }


def verify_with_his_calculator(conn: duckdb.DuckDBPyConnection) -> dict:
    """Score the increment with his program, per year, and return his totals."""
    if not CALCULATOR.is_file():
        raise SystemExit(f"calculator not found at {CALCULATOR}")
    rows = conn.execute(f"""
        SELECT y.assigned_year, y.domain FROM domain_year y
        WHERE y.verified_at >= TIMESTAMPTZ '{SINCE}' AND {NOT_BASELINE}
        ORDER BY 1, 2
    """).fetchall()
    per_year: dict[int, list[str]] = {}
    for year, domain in rows:
        per_year.setdefault(int(year), []).append(domain)

    totals = {"ee": Decimal(0), "valid": 0, "invalid": 0, "records": 0, "by_year": {}}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for year, domains in sorted(per_year.items()):
            listing = work / f"increment_{year}.txt"
            listing.write_text("\n".join(domains) + "\n", encoding="utf-8")
            results = work / f"results_{year}"
            subprocess.run(
                [sys.executable, str(CALCULATOR), str(listing), "--output-dir", str(results)],
                check=True,
                capture_output=True,
            )
            summary = json.loads((results / "summary.json").read_text(encoding="utf-8"))
            ee = Decimal(summary["equivalent_english_domains"])
            totals["ee"] += ee
            totals["valid"] += summary["unique_valid_domains"]
            totals["invalid"] += summary["invalid_records"]
            totals["records"] += summary["unique_nonempty_records"]
            totals["by_year"][year] = ee
    return totals


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--verify",
        action="store_true",
        help="re-score the increment with his calculator and fail on any disagreement",
    )
    args = ap.parse_args()

    conn = open_store()
    try:
        m = increment(conn)
        his = verify_with_his_calculator(conn) if args.verify else None
    finally:
        conn.close()

    pairs, ee = m["pairs"], m["ee"]
    if not pairs:
        raise SystemExit("nothing added since the submission: nothing to report")
    growth = ee / BASELINE_EE * 100

    print("The five fields, in his order\n")
    print(f"1. Total number of original domains 1996-2001 : {BASELINE_PAIRS:,}")
    print(f"2. Equivalent-English total                   : {BASELINE_EE:,.4f}")
    print(f"3. Increment                                  : {pairs:,} records")
    print(f"4. Equivalent-English increment               : {ee:,.4f}")
    print(f"5. Equivalent-English growth rate             : {growth:.6f}%")

    mean = ee / pairs
    last_mean = LAST_EE / LAST_PAIRS
    print(f"\ndistinct domains in the increment : {m['domains']:,}")
    print(f"dated but held back, not counted  : {m['held']:,}")
    print(
        f"mean weight                       : {mean:.4f} "
        f"against last round's {last_mean:.4f}, {(mean / last_mean - 1) * 100:+.1f}%"
    )
    print(f"equivalent-English against last round: {(ee / LAST_EE - 1) * 100:+.1f}%")

    print("\n| Year | Records | Equivalent-English | Growth on that year's baseline |")
    print("|---|---|---|---|")
    for year in sorted(m["by_year"]):
        n, year_ee = m["by_year"][year]
        share = year_ee / BASELINE_EE_BY_YEAR[year] * 100
        print(f"| {year} | {n:,} | {year_ee:,.4f} | {share:.4f}% |")

    print("\nby source")
    for name, (n, source_ee) in sorted(m["by_source"].items(), key=lambda kv: -kv[1][0]):
        print(f"  {name:<24} {n:>8,}  {source_ee:>13,.4f}  mean {source_ee / n:.4f}")

    if his is None:
        print("\npass --verify to re-score this with his calculator before sending")
        return

    print("\nverified with his equivalent_english_domains.py")
    print(f"  records scored   : {his['records']:,}")
    print(f"  rejected by his validator : {his['invalid']:,}")
    print(f"  his equivalent-English    : {his['ee']:,.4f}")
    print(f"  ours                      : {ee:,.4f}")
    difference = his["ee"] - ee
    print(f"  difference                : {difference:,.4f}")
    if difference != 0 or his["invalid"]:
        raise SystemExit(
            "his calculator disagrees, or rejects records we counted: "
            "do not send these numbers until the cause is understood"
        )
    print("  agreed exactly, and he rejects none of them")


if __name__ == "__main__":
    main()
