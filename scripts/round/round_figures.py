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

    uv run python scripts/round/round_figures.py
    uv run python scripts/round/round_figures.py --verify

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

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

import duckdb  # noqa: E402

from ark.baseline import (  # noqa: E402
    CURRENT_ROUND_SINCE,
    REVIEWER_BASELINE_EE,
    REVIEWER_BASELINE_EE_BY_YEAR,
    REVIEWER_BASELINE_PAIRS,
    baseline_dir,
    calculator_path,
)
from ark.english_share import english_weights  # noqa: E402

STORE = Path("data/ark.duckdb")


# Both inputs come from `ark.baseline`, which owns the fact of which release is current
# and therefore owns finding it. This file used to carry its own resolver; a third caller
# needing the same answer is what moved it, and `tests/test_baseline_paths.py` pins it.
CALCULATOR = calculator_path()
MERGED_BASELINE = baseline_dir()

# The round window opens where the last shipped release closes, so it comes from
# `ark.baseline` rather than being retyped here. `increment()` does not actually
# need it: each of its queries carries NOT_BASELINE, so a pair the reviewer has
# merged drops out by itself. `held` does, and cannot be fixed the same way: a
# candidate is never in the baseline, so the time window is the only thing
# separating this round's held names from the last round's.
SINCE = CURRENT_ROUND_SINCE

# His merged 1996-2001 files after the last round was folded in, from `ark.baseline`
# so this script, `ark stats` and the ingest defaults cannot drift apart.
#
# BASELINE_PAIRS is the RAW record count, not the validator-passing subset, and the
# difference matters. Measured on `merged260802-2`, his calculator reported 10,415,768
# unique nonempty records of which 10,404,200 were valid, the other 11,568 being
# embedded ports and underscore labels that score zero. His line 1 tracks the raw
# count, so quoting the valid one reads to him as 11,568 records lost since his last
# message. The equivalent split for `merged260810` has not been re-measured; the raw
# count is `wc -l` and was verified, the valid subset was not.
BASELINE_PAIRS = REVIEWER_BASELINE_PAIRS
BASELINE_EE = REVIEWER_BASELINE_EE
BASELINE_EE_BY_YEAR = REVIEWER_BASELINE_EE_BY_YEAR

# What he credited for the previous round, used only for the comparison line.
# phase-4, merged into `merged260810` on 2026-08-10 and accepted in full.
LAST_PAIRS = 946_266
LAST_EE = Decimal("603401.7811")

# A pair the shared baseline already holds is not ours to report. `prior_reused` is
# the evidence type recording that a pair arrived with the baseline.
from ark.delegation import shipping_filter as _shipping_filter  # noqa: E402

SHIPPED = _shipping_filter("y.")

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
        WHERE y.verified_at >= TIMESTAMPTZ '{SINCE}' AND {NOT_BASELINE} AND {SHIPPED}
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
        WHERE y.verified_at >= TIMESTAMPTZ '{SINCE}' AND {NOT_BASELINE} AND {SHIPPED}
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


def already_in_his_files(per_year: dict[int, list[str]]) -> int:
    """Records we are about to report that his merged files already hold.

    The increment is defined by `verified_at` plus the absence of a `prior_reused`
    marker, and neither of those knows what he actually holds. Since `merged260802`
    was ingested this should now read zero, but the check stays: the moment he issues
    a release and it is not loaded, the store's idea of the baseline goes stale and
    net-new silently starts including work he already has. That is exactly what
    happened between 2 and 7 August, and it is the one error he would catch and we
    would not.
    """
    overlap = 0
    for year, ours in sorted(per_year.items()):
        path = MERGED_BASELINE / f"{year}.txt"
        if not path.is_file():
            raise SystemExit(f"merged baseline not found at {path}")
        with path.open(encoding="utf-8", errors="replace") as fh:
            his = {line.strip().lower() for line in fh if line.strip()}
        overlap += len(his & {d.lower() for d in ours})
    return overlap


def verify_with_his_calculator(conn: duckdb.DuckDBPyConnection) -> dict:
    """Score the increment with his program, per year, and return his totals."""
    if not CALCULATOR.is_file():
        raise SystemExit(f"calculator not found at {CALCULATOR}")
    rows = conn.execute(f"""
        SELECT y.assigned_year, y.domain FROM domain_year y
        WHERE y.verified_at >= TIMESTAMPTZ '{SINCE}' AND {NOT_BASELINE} AND {SHIPPED}
        ORDER BY 1, 2
    """).fetchall()
    per_year: dict[int, list[str]] = {}
    for year, domain in rows:
        per_year.setdefault(int(year), []).append(domain)

    totals = {
        "ee": Decimal(0),
        "valid": 0,
        "invalid": 0,
        "records": 0,
        "by_year": {},
        "overlap": 0,
    }
    # The hostname files are scored by the same program, so a hostname his validator
    # refuses is caught here and not by him.
    for year in range(1996, 2002):
        path = REPO / f"output/netnew/{year}_hostnames.txt"
        if path.exists():
            hosts = [h.strip() for h in path.read_text().splitlines() if h.strip()]
            per_year.setdefault(year, []).extend(hosts)
    totals["overlap"] = already_in_his_files(per_year)
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


def hostname_increment() -> tuple[int, Decimal]:
    """Records and EE of the shipped hostname files, priced with his weight model."""
    weights = english_weights()
    pairs, ee = 0, Decimal(0)
    for year in range(1996, 2002):
        path = REPO / f"output/netnew/{year}_hostnames.txt"
        if not path.exists():
            continue
        with path.open() as fh:
            for line in fh:
                host = line.strip()
                if host:
                    pairs += 1
                    ee += weights.get(host.rsplit(".", 1)[-1], Decimal(0))
    return pairs, ee


def www_alias_seam(conn: duckdb.DuckDBPyConnection) -> tuple[int, Decimal]:
    """Shipped hostnames that are `www.<a name already held in that same year>`.

    The ingest refuses `www.<parent registrable>` as the parent's own site under the name
    every crawler tries first. Nothing refuses the same alias one level down, and on
    2026-09-03 that was 61.0% of the hostname half: a CDX corpus re-read at hostname grain
    yields almost nothing else (nypw_firstcdx 100.0%, ukwa 99.5%), while a corpus of URLs
    people typed yields 27 to 38%. It is printed here rather than left to a pricing run,
    because a figure whose composition is disputed must not be quotable without it.
    """
    weights = english_weights()
    rows, ee = 0, Decimal(0)
    for year in range(1996, 2002):
        path = REPO / f"output/netnew/{year}_hostnames.txt"
        if not path.exists():
            continue
        hosts = [h.strip().lower() for h in path.read_text().splitlines() if h.strip()]
        bare = {h[4:] for h in hosts if h.startswith("www.")}
        if not bare:
            continue
        conn.execute("CREATE OR REPLACE TEMP TABLE seam_bare (name TEXT)")
        conn.executemany("INSERT INTO seam_bare VALUES (?)", [(b,) for b in bare])
        held = {
            r[0]
            for r in conn.execute(
                "SELECT b.name FROM seam_bare b JOIN domain_year dy "
                "ON dy.domain = b.name AND dy.assigned_year = ? "
                "UNION SELECT b.name FROM seam_bare b JOIN hostname_year hy "
                "ON hy.hostname = b.name AND hy.assigned_year = ?",
                [year, year],
            ).fetchall()
        }
        registrables = REPO / f"output/netnew/{year}.txt"
        if registrables.exists():
            held |= bare & {d.strip().lower() for d in registrables.read_text().splitlines()}
        his = MERGED_BASELINE / f"{year}.txt"
        if his.exists():
            with his.open(errors="replace") as fh:
                held |= {line.strip().lower() for line in fh} & bare
        for host in hosts:
            if host.startswith("www.") and host[4:] in held:
                rows += 1
                ee += weights.get(host.rsplit(".", 1)[-1], Decimal(0))
    return rows, ee


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
        seam_rows, seam_ee = www_alias_seam(conn)
        his = verify_with_his_calculator(conn) if args.verify else None
    finally:
        conn.close()

    pairs, ee = m["pairs"], m["ee"]
    if not pairs:
        raise SystemExit("nothing added since the submission: nothing to report")
    # Both output units count in the five fields since 2026-09-01: he accepted valid
    # hostnames as annual records and his calculator scores one distinct hostname per
    # year at full weight, so the increment is the union of the registrable files and
    # the hostname files. The split is printed beneath, registrables first, because he
    # still asks for those to be prioritized.
    h_pairs, h_ee = hostname_increment()
    all_pairs, all_ee = pairs + h_pairs, ee + h_ee
    growth = all_ee / BASELINE_EE * 100

    print("The five fields, in his order\n")
    print(f"1. Total number of original domains 1996-2001 : {BASELINE_PAIRS:,}")
    print(f"2. Equivalent-English total                   : {BASELINE_EE:,.4f}")
    print(f"3. Increment                                  : {all_pairs:,} records")
    print(f"4. Equivalent-English increment               : {all_ee:,.4f}")
    print(f"5. Equivalent-English growth rate             : {growth:.6f}%")
    print(f"\n  registrable domains (additions/)  : {pairs:,} records  {ee:,.4f}")
    print(f"  hostnames (hostnames/)            : {h_pairs:,} records  {h_ee:,.4f}")
    if h_ee:
        share = seam_ee / h_ee * 100
        print(
            f"    of which www.<held that year>   : {seam_rows:,} records  {seam_ee:,.4f}"
            f"  ({share:.1f}% of the hostname half)"
        )
        print(
            f"  increment without that seam       : {all_pairs - seam_rows:,} records  "
            f"{all_ee - seam_ee:,.4f}  ({(all_ee - seam_ee) / BASELINE_EE * 100:.6f}%)"
        )
    print(f"  registrable-only growth rate      : {ee / BASELINE_EE * 100:.6f}%")

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
    print(f"  records scored            : {his['records']:,}")
    print(f"  rejected by his validator : {his['invalid']:,}")
    print(f"  already in his merged files: {his['overlap']:,}")
    print(f"  his equivalent-English    : {his['ee']:,.4f}")
    print(f"  ours                      : {all_ee:,.4f}")
    difference = his["ee"] - all_ee
    print(f"  difference                : {difference:,.4f}")
    if difference != 0 or his["invalid"] or his["overlap"]:
        raise SystemExit(
            "his calculator disagrees, rejects records we counted, or the increment "
            "is not disjoint from what he holds: do not send these numbers"
        )
    print("  agreed exactly, he rejects none of them, and none are already his")


if __name__ == "__main__":
    main()
