"""Merge this round's additions into the reviewer's baseline, and audit the arithmetic.

**D3 of the submission standard** (`docs/brief_amendments.md`): "the code and explanation
used to normalize, merge, and deduplicate the submitted annual files against the latest
baseline, including overlap counts, the accepted increment, and reconciliation checks."

Until 2026-08-17 the reviewer did this merge on his own side and shipped his audit of it
beside the next release. He now asks each contributor to produce it too, so his figure and
ours can be diffed rather than compared by eye. **The column names below are therefore his,
copied from `merge_stats_ivaylo_0817.csv`, and must not be improved.** A reconciliation whose
two sides use different words for the same quantity is not a reconciliation.

The one number that matters most is `already_in_baseline`. It is the overlap that turned
phase 5 from the 2,838,715 records it was submitted with into the 2,608,322 he credited,
and it is invisible from our own store: a pair only stops being ours when he merges someone
else's round that contains it.

Counting unit. He deduplicates the RAW LINE, lowercased, within a year. Not the registrable
domain, and not the validator-passing subset. Checked against his own audit: his 1996
`merged_unique` of 866,106 is exactly `wc -l` of his 1996.txt, and his 807,818 + 58,288 lands
on it. Counting registrable domains instead would understate every figure here by the 1.4M
lines that carry subdomains, and would silently disagree with his file.

Equivalent-English is measured by running HIS calculator over each file, never by our own
implementation, so the increment is his arithmetic on our data. `src/ark/english_share.py`
exists for ranking during collection; it has no vote here.

    uv run python scripts/round/merge_against_baseline.py
    uv run python scripts/round/merge_against_baseline.py --out output/merge --stamp 20260818

Read-only with respect to the store: it touches text files only, so it is safe while the
collectors are working and needs no write lock.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import duckdb  # noqa: E402

from ark.baseline import (  # noqa: E402
    CURRENT_BASELINE_MARKER,
    REVIEWER_BASELINE_EE,
    REVIEWER_BASELINE_EE_BY_YEAR,
    REVIEWER_BASELINE_PAIRS,
    _first_holding,
    baseline_dir,
    calculator_path,
)

YEARS = (1996, 1997, 1998, 1999, 2000, 2001)

# His own column names, in his own order. See the module docstring.
COLUMNS = (
    "year",
    "baseline_unique",
    "submitted_unique",
    "already_in_baseline",
    "accepted_new",
    "merged_unique",
    "equivalent_english_increment",
    "growth_pct_vs_year_baseline",
)


CALCULATOR = calculator_path()

# The round's own annual files. `ark export` writes them to `output/netnew/` and
# `package_delivery.sh` stages the same six as `additions/`, so the one name a reader
# of the archive knows is not the one the repository uses. Both are tried rather than
# either being right.
ADDITIONS = _first_holding(
    (
        Path("output/netnew"),
        Path("additions"),
        Path("../additions"),
        Path("output/additions"),
    ),
    "2001.txt",
)


def score(path: Path, work: Path) -> dict:
    """Run the reviewer's calculator over one file and return its summary verbatim."""
    out = work / f"score_{path.parent.name}_{path.stem}"
    subprocess.run(
        [sys.executable, str(CALCULATOR), str(path), "--output-dir", str(out)],
        check=True,
        capture_output=True,
    )
    return json.loads((out / "summary.json").read_text(encoding="utf-8"))


def merge_year(
    conn: duckdb.DuckDBPyConnection, baseline: Path, additions: Path, target: Path
) -> dict:
    """Union one year, deduplicated on the lowercased line, and count the overlap.

    DuckDB rather than Python sets because 2000.txt alone is 7.7M lines and the whole
    corpus is 22.5M: a set of that many short strings costs gigabytes for an operation
    that is a hash join. The connection is in-memory, so this takes no lock on the store.
    """
    conn.execute("DROP TABLE IF EXISTS b; DROP TABLE IF EXISTS a")
    conn.execute(
        "CREATE TABLE b AS SELECT DISTINCT lower(trim(col0)) AS d "
        "FROM read_csv(?, header=false, columns={'col0':'VARCHAR'}, quote='', delim=?) "
        "WHERE trim(col0) <> ''",
        [str(baseline), "\x07"],
    )
    if additions.is_file():
        conn.execute(
            "CREATE TABLE a AS SELECT DISTINCT lower(trim(col0)) AS d "
            "FROM read_csv(?, header=false, columns={'col0':'VARCHAR'}, quote='', delim=?) "
            "WHERE trim(col0) <> ''",
            [str(additions), "\x07"],
        )
    else:
        # A year with no additions is normal, not an error: the round may not have
        # reached it. It must still appear in the audit with zeros, because a missing
        # row reads as an omission rather than as nothing found.
        conn.execute("CREATE TABLE a (d VARCHAR)")

    baseline_unique = conn.execute("SELECT count(*) FROM b").fetchone()[0]
    submitted_unique = conn.execute("SELECT count(*) FROM a").fetchone()[0]
    already = conn.execute("SELECT count(*) FROM a WHERE d IN (SELECT d FROM b)").fetchone()[0]

    target.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(
        "COPY (SELECT d FROM b UNION SELECT d FROM a ORDER BY d) TO ? (HEADER false, DELIMITER ?)",
        [str(target), "\x07"],
    )
    merged_unique = sum(1 for _ in target.open(encoding="utf-8"))
    return {
        "baseline_unique": baseline_unique,
        "submitted_unique": submitted_unique,
        "already_in_baseline": already,
        "accepted_new": submitted_unique - already,
        "merged_unique": merged_unique,
    }


def reconcile(rows: list[dict], totals: dict) -> list[dict]:
    """Every identity that must hold by arithmetic rather than by measurement.

    These are the "reconciliation checks" of D3. Each one can only fail if the merge or
    the scoring is wrong, so a failure here is a defect and not a finding. They are
    returned rather than asserted so the audit file records that they were run and
    passed, which is the part a reviewer can check without rerunning anything.
    """
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(ok), "detail": detail})

    for r in rows:
        y = r["year"]
        add(
            f"{y}: baseline_unique + accepted_new == merged_unique",
            r["baseline_unique"] + r["accepted_new"] == r["merged_unique"],
            f"{r['baseline_unique']} + {r['accepted_new']} vs {r['merged_unique']}",
        )
        add(
            f"{y}: already_in_baseline + accepted_new == submitted_unique",
            r["already_in_baseline"] + r["accepted_new"] == r["submitted_unique"],
            f"{r['already_in_baseline']} + {r['accepted_new']} vs {r['submitted_unique']}",
        )

    per_year_sum = sum((Decimal(r["equivalent_english_increment"]) for r in rows), Decimal(0))
    add(
        "per-year equivalent-English increments sum to the headline increment",
        per_year_sum == Decimal(totals["equivalent_english_increment"]),
        f"{per_year_sum} vs {totals['equivalent_english_increment']}",
    )
    add(
        "baseline total + increment == post-merge total",
        Decimal(totals["baseline_equivalent_english_total"])
        + Decimal(totals["equivalent_english_increment"])
        == Decimal(totals["post_merge_equivalent_english_total"]),
        f"{totals['baseline_equivalent_english_total']} + "
        f"{totals['equivalent_english_increment']} vs "
        f"{totals['post_merge_equivalent_english_total']}",
    )
    # The two that catch a stale `src/ark/baseline.py`, which is the failure mode that
    # silently reports a round against a release the reviewer replaced days ago.
    add(
        "measured baseline record count matches src/ark/baseline.py",
        totals["baseline_records"] == REVIEWER_BASELINE_PAIRS,
        f"{totals['baseline_records']} vs {REVIEWER_BASELINE_PAIRS}",
    )
    add(
        "measured baseline equivalent-English matches src/ark/baseline.py",
        Decimal(totals["baseline_equivalent_english_total"]) == REVIEWER_BASELINE_EE,
        f"{totals['baseline_equivalent_english_total']} vs {REVIEWER_BASELINE_EE}",
    )
    for r in rows:
        expected = REVIEWER_BASELINE_EE_BY_YEAR.get(r["year"])
        if expected is not None:
            add(
                f"{r['year']}: measured baseline equivalent-English matches src/ark/baseline.py",
                Decimal(r["baseline_equivalent_english"]) == expected,
                f"{r['baseline_equivalent_english']} vs {expected}",
            )
    return checks


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", type=Path, default=baseline_dir())
    ap.add_argument("--additions", type=Path, default=ADDITIONS)
    ap.add_argument("--out", type=Path, default=Path("output/merge"))
    ap.add_argument("--stamp", default="", help="suffix for the audit filenames, e.g. 20260818")
    ap.add_argument("--keep-merged", action="store_true", help="keep the merged annual files")
    args = ap.parse_args()

    if not CALCULATOR.is_file():
        raise SystemExit(f"calculator not found at {CALCULATOR}")
    if not (args.baseline / "1996.txt").is_file():
        raise SystemExit(f"no baseline annual files under {args.baseline}")

    merged_dir = args.out / "merged"
    args.out.mkdir(parents=True, exist_ok=True)
    work = args.out / "scratch"
    work.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(":memory:")
    rows: list[dict] = []
    baseline_records = post_records = 0
    baseline_ee = post_ee = Decimal(0)

    for year in YEARS:
        b = args.baseline / f"{year}.txt"
        a = args.additions / f"{year}.txt"
        m = merged_dir / f"{year}.txt"
        counts = merge_year(conn, b, a, m)

        b_summary = score(b, work)
        m_summary = score(m, work)
        b_ee = Decimal(b_summary["equivalent_english_domains"])
        m_ee = Decimal(m_summary["equivalent_english_domains"])
        inc = m_ee - b_ee

        rows.append(
            {
                "year": year,
                **counts,
                "equivalent_english_increment": f"{inc:.4f}",
                "growth_pct_vs_year_baseline": f"{(inc / b_ee * 100):.6f}" if b_ee else "0",
                # Not in his CSV, kept in the JSON only, because the reconciliation
                # against `src/ark/baseline.py` needs the absolute figure and adding a
                # ninth column would stop the two CSVs lining up.
                "baseline_equivalent_english": f"{b_ee:.4f}",
                "post_merge_equivalent_english": f"{m_ee:.4f}",
                "baseline_invalid_records": b_summary["invalid_records"],
                "merged_invalid_records": m_summary["invalid_records"],
                "merged_model_unmatched_valid_records": m_summary["model_unmatched_valid_records"],
            }
        )
        baseline_records += counts["baseline_unique"]
        post_records += counts["merged_unique"]
        baseline_ee += b_ee
        post_ee += m_ee
        print(
            f"  {year}  baseline {counts['baseline_unique']:>9,}"
            f"  submitted {counts['submitted_unique']:>9,}"
            f"  overlap {counts['already_in_baseline']:>8,}  accepted {counts['accepted_new']:>9,}"
            f"  +{inc:,.4f} EE"
        )

    totals = {
        "baseline": str(args.baseline),
        "baseline_marker": CURRENT_BASELINE_MARKER,
        "additions": str(args.additions),
        "baseline_records": baseline_records,
        "post_merge_records": post_records,
        "accepted_new_records": sum(r["accepted_new"] for r in rows),
        "already_in_baseline_records": sum(r["already_in_baseline"] for r in rows),
        "submitted_records": sum(r["submitted_unique"] for r in rows),
        "baseline_equivalent_english_total": f"{baseline_ee:.4f}",
        "post_merge_equivalent_english_total": f"{post_ee:.4f}",
        "equivalent_english_increment": f"{(post_ee - baseline_ee):.4f}",
        "equivalent_english_growth_rate_pct": (
            f"{((post_ee - baseline_ee) / baseline_ee * 100):.6f}"
        ),
        "calculator": str(CALCULATOR),
    }
    checks = reconcile(rows, totals)
    failed = [c for c in checks if not c["passed"]]

    suffix = f"_{args.stamp}" if args.stamp else ""
    csv_path = args.out / f"merge_stats_ark{suffix}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    json_path = args.out / f"merge_audit_ark{suffix}.json"
    json_path.write_text(
        json.dumps({"totals": totals, "years": rows, "reconciliation": checks}, indent=1),
        encoding="utf-8",
    )

    print()
    print(f"  baseline    {baseline_records:>12,} records  {baseline_ee:>16,.4f} EE")
    print(f"  post-merge  {post_records:>12,} records  {post_ee:>16,.4f} EE")
    print(
        f"  increment   {totals['accepted_new_records']:>12,} records"
        f"  {post_ee - baseline_ee:>16,.4f} EE"
    )
    print(f"  growth rate {totals['equivalent_english_growth_rate_pct']}%")
    print(f"  overlap already in the baseline: {totals['already_in_baseline_records']:,} records")
    print()
    print(f"  reconciliation: {len(checks) - len(failed)}/{len(checks)} passed")
    for c in failed:
        print(f"    FAIL {c['check']}: {c['detail']}")
    print(f"  wrote {csv_path}")
    print(f"  wrote {json_path}")

    if not args.keep_merged:
        # The merged files are the reviewer's to produce, and shipping 1.4 GB of his own
        # corpus back to him is what the additions/ set exists to avoid. They are kept
        # only when asked for, so the audit can be checked against them.
        for year in YEARS:
            (merged_dir / f"{year}.txt").unlink(missing_ok=True)
        merged_dir.rmdir()
    for leftover in work.rglob("*"):
        if leftover.is_file():
            leftover.unlink()
    for leftover in sorted(work.rglob("*"), reverse=True):
        if leftover.is_dir():
            leftover.rmdir()
    work.rmdir()

    if failed:
        raise SystemExit(f"{len(failed)} reconciliation check(s) failed")


if __name__ == "__main__":
    main()
