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
    uv run python scripts/round/round_figures.py --full
    uv run python scripts/round/round_figures.py --verify

By default it reads only the export's files and his release, never the store, so it runs
while a bank holds the writer. `--full` adds the store's own lines, read-only.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

import duckdb  # noqa: E402

from ark import export  # noqa: E402
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
YEARS = range(1996, 2002)
NETNEW = REPO / "output/netnew"
# `YYYY<TAB>registrable` for every pair the store dates that his year file lacks, sorted as a
# whole under LC_ALL=C. With his files and ours it is every name held in a year.
ATTESTED = NETNEW / "attested_registrables.txt"


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


def open_store(patience_s: int = 2700) -> duckdb.DuckDBPyConnection:
    """Wait out a bank rather than failing the whole measurement.

    The shared helper rather than a fourth hand-written retry loop, which is what this was:
    `ark.db.connect_read_only_patiently` exists precisely because the same loop had been
    written twice and omitted twice. 45 minutes of patience, not 10, because a bank that
    folds 500 sweep journals holds the writer for longer than that, which is exactly when the
    figures are wanted.
    """
    from ark.db import connect_read_only_patiently

    return connect_read_only_patiently(STORE, patience_s=patience_s)


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


def verify_with_his_calculator() -> dict:
    """Score the increment with his program, per year, and return his totals."""
    if not CALCULATOR.is_file():
        raise SystemExit(f"calculator not found at {CALCULATOR}")
    # Both halves come from the shipped files, the population the five fields count. A checker
    # that reads a different set from the thing it checks does not fail safe, it cries wolf,
    # and `just ship` refuses to package on it.
    per_year: dict[int, list[str]] = {}
    for year in YEARS:
        path = NETNEW / f"{year}.txt"
        if path.exists():
            per_year[year] = [
                line.strip() for line in path.read_text().splitlines() if line.strip()
            ]

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
    for year in YEARS:
        path = NETNEW / f"{year}_hostnames.txt"
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


def shipped_by_year(pattern: str) -> dict[int, tuple[int, Decimal]]:
    """Records and EE per year of a shipped annual file family, priced with his weight model.

    What he merges is the shipped files, so that is what the five fields count, both units,
    with no session window. A round's registrables since it opened is a store question,
    printed under `--full`, where the timestamps are.
    """
    weights = english_weights()
    by_year = {}
    for year in YEARS:
        records, year_ee = 0, Decimal(0)
        path = NETNEW / pattern.format(year=year)
        if path.exists():
            with path.open() as fh:
                for line in fh:
                    name = line.strip()
                    if name:
                        records += 1
                        year_ee += weights.get(name.rsplit(".", 1)[-1], Decimal(0))
        by_year[year] = (records, year_ee)
    return by_year


def summed(by_year: dict[int, tuple[int, Decimal]]) -> tuple[int, Decimal]:
    return sum(n for n, _ in by_year.values()), sum((e for _, e in by_year.values()), Decimal(0))


def hostname_increment() -> tuple[int, Decimal]:
    """Records and EE of the shipped hostname files."""
    return summed(shipped_by_year("{year}_hostnames.txt"))


def registrable_increment() -> tuple[int, Decimal]:
    """Records and EE of the shipped registrable additions."""
    return summed(shipped_by_year("{year}.txt"))


def candidate_potential() -> tuple[int, Decimal]:
    """Size of the shipped candidate pool, priced but NOT claimed.

    His section XI: "Report annual and active-candidate Equivalent-English contributions
    separately." Separately is the whole instruction. A candidate carries no in-window
    evidence, so this is what the pool would be worth if every name in it were later dated,
    which is a ceiling on future work and not a contribution to this round. It is printed
    under its own heading, in its own sentence, so it can never be read into the five fields.
    """
    weights = english_weights()
    path = REPO / "output/candidate_unverified.txt"
    if not path.exists():
        return 0, Decimal(0)
    names, ee = 0, Decimal(0)
    with path.open() as fh:
        for line in fh:
            name = line.strip()
            if name:
                names += 1
                ee += weights.get(name.rsplit(".", 1)[-1], Decimal(0))
    return names, ee


def candidate_track() -> dict:
    """The candidate-track claim as the export measured it, or an empty result.

    His 0906 update scores candidates separately and at the same rate as annual records,
    so this is the second of the two numbers a round is judged on and it belongs beside
    the first. The working pool in `candidates.txt` is not it: measured 2026-09-10 the
    two were 2,279,755 and 29,327.
    """
    path = NETNEW / "candidate_additions_summary.json"
    if not path.is_file():
        return {"candidates": 0, "equivalent_english": "0"}
    return json.loads(path.read_text(encoding="utf-8"))


def common_lines(sorted_a: Path, sorted_b: Path) -> set[str]:
    """Lines two LC_ALL=C sorted files share, streamed by `comm` rather than loaded."""
    out = subprocess.run(
        ["comm", "-12", str(sorted_a), str(sorted_b)],
        env={**os.environ, "LC_ALL": "C"},
        capture_output=True,
        check=True,
        encoding="utf-8",
    ).stdout
    return set(out.splitlines())


def www_alias_share() -> tuple[int, Decimal] | None:
    """How much of the hostname half is `www.<a name held that same year>`, or None.

    These rows ship: his section XI makes a base hostname and a distinct subdomain hostname
    each an annual record. The share is still reported every round, because it is the one
    number that says whether a corpus was worth reading: a bulk CDX index re-read at hostname
    grain is 99.5% to 100.0% alias, so it adds names without adding sites, while a corpus of
    URLs people typed is 22.2%. That difference is what picks the next corpus.

    Held that year means a line of his year file, of either shipped file for the year, or of
    the year's block of the attested list. None when the export wrote no attested list.
    """
    if not ATTESTED.is_file():
        return None
    held: set[str] = set()
    tagged: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for year in YEARS:
            hosts = NETNEW / f"{year}_hostnames.txt"
            with hosts.open(encoding="utf-8") as fh:
                bare = sorted({h.strip()[4:] for h in fh if h.startswith("www.")})
            if not bare:
                continue
            his = MERGED_BASELINE / f"{year}.txt"
            if not his.is_file():
                raise SystemExit(f"merged baseline not found at {his}")
            listing = Path(tmp) / f"www_{year}.txt"
            listing.write_text("".join(f"{n}\n" for n in bare), encoding="utf-8")
            for other in (his, NETNEW / f"{year}.txt", hosts):
                held |= {f"{year}\t{n}" for n in common_lines(listing, other)}
            tagged += [f"{year}\t{n}" for n in bare]
        if tagged:
            # The attested list is sorted as a whole, so the names tagged with their year
            # find every year's hits in one pass.
            listing = Path(tmp) / "www_tagged.txt"
            listing.write_text("".join(f"{t}\n" for t in tagged), encoding="utf-8")
            held |= common_lines(listing, ATTESTED)
    weights = english_weights()
    ee = sum((weights.get(t.rsplit(".", 1)[-1], Decimal(0)) for t in held), Decimal(0))
    return len(held), ee


def www_alias_seam(conn: duckdb.DuckDBPyConnection) -> tuple[int, Decimal]:
    """The same share over the store's hostname rows before the XIII screen.

    The predicate is imported from the export, so the figure cannot drift from the rule
    that produced it.
    """
    weights = english_weights()
    export.load_baseline_hostnames(conn)
    rows, ee = 0, Decimal(0)
    for year in YEARS:
        excluded = conn.execute(
            f"""
            SELECT DISTINCT hy.hostname FROM hostname_year hy
            WHERE hy.assigned_year = {year}
              AND {export.NOT_IN_BASELINE_HOSTNAME}
              AND NOT {export.NOT_WWW_ALIAS}
            """
        ).fetchall()
        rows += len(excluded)
        for (host,) in excluded:
            ee += weights.get(host.rsplit(".", 1)[-1], Decimal(0))
    return rows, ee


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--verify",
        action="store_true",
        help="re-score the increment with his calculator and fail on any disagreement",
    )
    ap.add_argument(
        "--full",
        action="store_true",
        help="also read the store: the round so far, the held count, by source, the www seam",
    )
    args = ap.parse_args()

    missing = [
        f"{year}{unit}.txt"
        for year in YEARS
        for unit in ("", "_hostnames")
        if not (NETNEW / f"{year}{unit}.txt").is_file()
    ]
    if missing:
        raise SystemExit(f"output/netnew lacks {', '.join(missing)}: run ark export --claim")
    # Both units count in the five fields: his calculator scores one distinct valid hostname
    # per year at full weight, so the increment is the union of the registrable files and the
    # hostname files. The split is printed beneath, registrables first, because he still asks
    # for those to be prioritized.
    r_years = shipped_by_year("{year}.txt")
    h_years = shipped_by_year("{year}_hostnames.txt")
    r_pairs, r_ee = summed(r_years)
    h_pairs, h_ee = summed(h_years)
    all_pairs, all_ee = r_pairs + h_pairs, r_ee + h_ee
    growth = all_ee / BASELINE_EE * 100

    print("The five fields, in his order\n")
    print(f"1. Total number of original domains 1996-2001 : {BASELINE_PAIRS:,}")
    print(f"2. Equivalent-English total                   : {BASELINE_EE:,.4f}")
    print(f"3. Increment                                  : {all_pairs:,} records")
    print(f"4. Equivalent-English increment               : {all_ee:,.4f}")
    print(f"5. Equivalent-English growth rate             : {growth:.6f}%")
    print(f"\n  registrable domains (additions/)  : {r_pairs:,} records  {r_ee:,.4f}")
    print(f"  hostnames (hostnames/)            : {h_pairs:,} records  {h_ee:,.4f}")
    www = www_alias_share()
    if www is None:
        print(
            f"    of which www.<held that year>   : not measured, output/netnew lacks "
            f"{ATTESTED.name}: run ark export --claim"
        )
    elif www[0] and h_ee:
        # Inside the hostname figure above, so the share is of the hostname half and reads
        # as a quality signal, not as a withheld alternative.
        www_rows, www_ee = www
        print(
            f"    of which www.<held that year>   : {www_rows:,} records  {www_ee:,.4f}"
            f"  ({www_ee / h_ee * 100:.1f}% of the hostname half)"
        )
    print(f"  registrable-only growth rate      : {r_ee / BASELINE_EE * 100:.6f}%")
    c_names, c_ee = candidate_potential()
    if c_names:
        # Reported separately because his XI says separately, and never added to anything.
        # The CLAIM is the net-new pool, not the working set: he scores the candidate track
        # at the same rate as the annual one, so it is the number that has to be watched.
        print(
            f"\n  candidate pool (candidates.txt), the working set: "
            f"{c_names:,} names, {c_ee:,.4f} EE if every one were later dated"
        )
    track = candidate_track()
    if track["candidates"]:
        # Its own name, never `ee`: `mean weight` under --full divides `ee` by `pairs`, so a
        # candidate EE bound to `ee` prints candidate EE over annual records under that label.
        track_ee = Decimal(track["equivalent_english"])
        print(
            f"  CANDIDATE TRACK CLAIM (candidate_additions.txt), scored separately at the "
            f"same rate: {track['candidates']:,} names, {track_ee:,.4f} EE, "
            f"{track_ee / BASELINE_EE * 100:.6f}% of the same denominator"
        )

    print("\n| Year | Records | Equivalent-English | Growth on that year's baseline |")
    print("|---|---|---|---|")
    for year in YEARS:
        n = r_years[year][0] + h_years[year][0]
        year_ee = r_years[year][1] + h_years[year][1]
        share = year_ee / BASELINE_EE_BY_YEAR[year] * 100
        print(f"| {year} | {n:,} | {year_ee:,.4f} | {share:.4f}% |")

    if args.full:
        conn = open_store()
        try:
            m = increment(conn)
            seam_rows, seam_ee = www_alias_seam(conn)
        finally:
            conn.close()
        pairs, ee = m["pairs"], m["ee"]
        print("\nfrom the store")
        print(
            f"  since this round opened ({SINCE[:16]}), registrables only: "
            f"{pairs:,} records  {ee:,.4f}"
        )
        if h_ee:
            print(
                f"  www.<held that year>, store rows before the XIII screen: {seam_rows:,} "
                f"records  {seam_ee:,.4f}  ({seam_ee / h_ee * 100:.1f}% of the hostname half)"
            )
        print(f"  distinct domains in the increment : {m['domains']:,}")
        print(f"  dated but held back, not counted  : {m['held']:,}")
        if pairs:
            mean = ee / pairs
            last_mean = LAST_EE / LAST_PAIRS
            print(
                f"  mean weight                       : {mean:.4f} "
                f"against last round's {last_mean:.4f}, {(mean / last_mean - 1) * 100:+.1f}%"
            )
            print(f"  equivalent-English against last round: {(ee / LAST_EE - 1) * 100:+.1f}%")
        print("\n  by source")
        for name, (n, source_ee) in sorted(m["by_source"].items(), key=lambda kv: -kv[1][0]):
            print(f"    {name:<24} {n:>8,}  {source_ee:>13,.4f}  mean {source_ee / n:.4f}")

    if not args.verify:
        print("\npass --verify to re-score this with his calculator before sending")
        return

    his = verify_with_his_calculator()
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
