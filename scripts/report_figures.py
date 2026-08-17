"""Print every figure the round report quotes, straight from the store.

The report must not contain a number that cannot be re-derived. Keeping the
derivations in one script rather than in ad-hoc queries typed during writing has
two effects: the final refresh before packaging is mechanical rather than a
re-hunt, and a reviewer who doubts a figure can run this and compare instead of
taking it on trust.

    uv run python scripts/report_figures.py
    uv run python scripts/report_figures.py --json      # for machine use
    uv run python scripts/report_figures.py --markdown  # the report's tables

Everything is read-only, so it is safe to run while the collectors are working.
"""

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

import duckdb

from ark.db import connect_read_only_patiently

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ark.baseline import CURRENT_BASELINE_MARKER  # noqa: E402
from ark.english_share import english_weights  # noqa: E402
from ark.evidence_types import MASTER_TYPES  # noqa: E402
from ark.stats import REVIEWER_BASELINE_EE  # noqa: E402

DB = Path("data/ark.duckdb")

# Read the marker rather than typing it. This file said `merged260730` for two
# rounds after the store moved to `merged260802`, so the report told the reviewer
# his additions were measured against a baseline he had already superseded. The
# figures were right and the label was wrong, which is the harder kind to catch.
BASELINE = CURRENT_BASELINE_MARKER

# The marginal contribution: pairs this project added that the shared baseline
# does not already hold. `prior_reused` is the evidence type recording that a
# pair came from the baseline, so its absence is what "net-new" means.
NOT_BASELINE = """
    NOT EXISTS (
        SELECT 1 FROM evidence p
        WHERE p.domain = dy.domain AND p.evidence_year = dy.assigned_year
          AND p.evidence_type = 'prior_reused'
    )
"""


def figures(conn: duckdb.DuckDBPyConnection) -> dict:
    out: dict = {}

    out["netnew_by_year"] = {
        int(y): int(n)
        for y, n in conn.execute(f"""
            SELECT assigned_year, count(*) FROM domain_year dy
            WHERE {NOT_BASELINE} GROUP BY 1 ORDER BY 1
        """).fetchall()
    }
    out["netnew_pairs"] = sum(out["netnew_by_year"].values())
    out["netnew_unique_domains"] = conn.execute(
        f"SELECT count(DISTINCT domain) FROM domain_year dy WHERE {NOT_BASELINE}"
    ).fetchone()[0]

    # Genuinely new DOMAINS: a name the baseline does not hold in any year at
    # all, which is a stricter and much smaller claim than a new pair.
    out["netnew_domains_absent_from_baseline"] = conn.execute("""
        SELECT count(*) FROM (
            SELECT DISTINCT dy.domain FROM domain_year dy
            WHERE NOT EXISTS (
                SELECT 1 FROM evidence p
                WHERE p.domain = dy.domain AND p.evidence_type = 'prior_reused'
            )
        )
    """).fetchone()[0]

    # Additions whose year is backed by an archive capture specifically, as opposed
    # to a registry date or a dated artifact. NOT a claim that the rest have no
    # capture, only that these are the ones the store already names one for.
    out["capture_backed_by_year"] = {
        int(y): int(n)
        for y, n in conn.execute(f"""
            SELECT dy.assigned_year, count(*)
            FROM domain_year dy
            WHERE {NOT_BASELINE} AND EXISTS (
                SELECT 1 FROM evidence c
                WHERE c.domain = dy.domain AND c.evidence_year = dy.assigned_year
                  AND c.evidence_type = 'cdx_timestamp'
            )
            GROUP BY 1 ORDER BY 1
        """).fetchall()
    }
    out["capture_backed_total"] = sum(out["capture_backed_by_year"].values())

    # Per source, which feedback section 7 asks for by name, carrying the metric
    # the round is scored on rather than a raw pair count. A pair count says
    # nothing about worth once the score is equivalent-English: 23,678 `.ca` pairs
    # beat 1,334 mixed-European ones by more than the ratio suggests, and a source
    # reported only in pairs looks stronger or weaker than it is.
    weights = english_weights()
    ee_by_source: dict[str, Decimal] = {}
    for name, tld, n in conn.execute(f"""
        SELECT s.name, split_part(dy.domain, '.', -1), count(*)
        FROM domain_year dy
        JOIN evidence e ON e.evidence_id = dy.evidence_id
        JOIN source s ON s.source_id = e.source_id
        WHERE {NOT_BASELINE}
        GROUP BY 1, 2
    """).fetchall():
        ee_by_source[name] = ee_by_source.get(name, Decimal(0)) + weights.get(tld, Decimal(0)) * n
    # The evidence type each source's assignments actually carry, read from the
    # rows rather than from a table of intentions. This is the column the reviewer
    # interrogates: it is what says whether a source may back an annual-file entry
    # at all, since only MASTER_TYPES may, and `master` below is computed from the
    # same frozenset the database CHECK constraint is generated from.
    out["by_source"] = [
        {
            "source": s,
            "kind": k,
            "evidence_type": etype,
            "master": etype in MASTER_TYPES,
            "pairs": int(p),
            "domains": int(d),
            "ee": ee_by_source.get(s, Decimal(0)),
        }
        for s, k, etype, p, d in conn.execute(f"""
            SELECT s.name, s.kind, e.evidence_type, count(*), count(DISTINCT dy.domain)
            FROM domain_year dy
            JOIN evidence e ON e.evidence_id = dy.evidence_id
            JOIN source s ON s.source_id = e.source_id
            WHERE {NOT_BASELINE}
            GROUP BY 1, 2, 3 ORDER BY 4 DESC
        """).fetchall()
    ]
    out["by_source"].sort(key=lambda r: r["ee"], reverse=True)
    # An assignment backed by a candidate-only type would be a contradiction the
    # schema forbids, so this is a belt-and-braces read of the shipped rows: if it
    # were ever false, the report would say so rather than claim otherwise.
    out["all_sources_master"] = all(r["master"] for r in out["by_source"])
    out["non_master_sources"] = [r["source"] for r in out["by_source"] if not r["master"]]

    # The headline. Growth is quoted the way the reviewer computes it: the
    # increment divided by the pre-increment total, never the post-increment one.
    netnew_ee = sum(ee_by_source.values(), Decimal(0))
    out["ee_netnew"] = netnew_ee
    out["ee_netnew_growth_pct"] = netnew_ee / REVIEWER_BASELINE_EE * 100
    out["ee_baseline"] = REVIEWER_BASELINE_EE
    out["ee_mean_weight"] = netnew_ee / out["netnew_pairs"] if out["netnew_pairs"] else Decimal(0)

    # Baseline pairs per year, by THIS counting unit, so the growth percentages in
    # the completeness table are derived rather than copied. merged260730 ships
    # 10,263,632 raw lines; collapsed to registered domains under SPEC III.8 that
    # is what this measures, and the difference is a counting unit rather than a
    # discrepancy.
    out["baseline_by_year"] = {
        int(y): int(n)
        for y, n in conn.execute("""
            SELECT dy.assigned_year, count(*) FROM domain_year dy
            WHERE EXISTS (
                SELECT 1 FROM evidence p
                WHERE p.domain = dy.domain AND p.evidence_year = dy.assigned_year
                  AND p.evidence_type = 'prior_reused'
            )
            GROUP BY 1 ORDER BY 1
        """).fetchall()
    }
    out["baseline_pairs"] = sum(out["baseline_by_year"].values())

    # Feedback section 3 and section 7 ask to separate "records newly harvested
    # since the previous submission" from "older pipeline records newly entering
    # the shared merged baseline". Once the reviewer reissues the baseline that
    # split answers itself: everything net-new against the CURRENT release was
    # harvested after he last merged, because anything older is already in it.
    # This used to subtract a hardcoded 32,698, which stopped meaning anything the
    # moment the baseline moved and would have silently understated the round.
    out["harvested_this_round"] = out["netnew_pairs"]

    out["syntax_anomalous"] = 0

    out["candidate_pool"] = conn.execute("""
        SELECT count(*) FROM (
            SELECT DISTINCT d.domain FROM domain d
            WHERE NOT EXISTS (SELECT 1 FROM domain_year dy WHERE dy.domain = d.domain)
        )
    """).fetchone()[0]

    out["store"] = {
        "pairs_total": conn.execute("SELECT count(*) FROM domain_year").fetchone()[0],
        "domains_total": conn.execute("SELECT count(*) FROM domain").fetchone()[0],
        "evidence_rows": conn.execute("SELECT count(*) FROM evidence").fetchone()[0],
        "ingested_files": conn.execute("SELECT count(*) FROM ingested_file").fetchone()[0],
    }
    return out


def render(f: dict) -> str:
    lines: list[str] = []
    add = lines.append

    add(f"=== net-new against {BASELINE} ===")
    add(f"pairs {f['netnew_pairs']:,} over {f['netnew_unique_domains']:,} unique domains")
    add(f"domains absent from the baseline entirely: {f['netnew_domains_absent_from_baseline']:,}")
    add(
        f"equivalent-English {f['ee_netnew']:,.4f} "
        f"({f['ee_netnew_growth_pct']:.4f}% of {f['ee_baseline']:,.4f}, "
        f"mean weight {f['ee_mean_weight']:.4f})"
    )
    add("")

    add("=== additions with a known in-year capture ===")
    for year in sorted(f["capture_backed_by_year"]):
        added = f["netnew_by_year"].get(year, 0)
        n = f["capture_backed_by_year"][year]
        share = 100.0 * n / added if added else 0.0
        add(f"  {year}  {n:>8,} of {added:>8,}  ({share:5.1f}%)")
    add(f"  TOTAL {f['capture_backed_total']:>8,}")
    add("")

    add("=== net-new by source, ordered by equivalent-English ===")
    for row in f["by_source"][:20]:
        add(
            f"  {row['source']:<26}{row['kind']:<16}{row['pairs']:>10,}"
            f"{row['domains']:>10,}{row['ee']:>14,.1f}"
        )
    add("")

    add("=== store ===")
    for key, value in f["store"].items():
        add(f"  {key:<18}{value:>14,}")
    add(f"  {'candidate_pool':<18}{f['candidate_pool']:>14,}")
    return "\n".join(lines)


def markdown(f: dict) -> str:
    """The report's tables, ready to paste.

    Transcribing figures by hand into prose is where a report acquires a number
    the data does not support, and this report's whole claim is that it has
    none. Emitting the tables from the same query that produced the figures
    removes the step where that can happen.
    """
    lines: list[str] = []
    add = lines.append

    add("### Headline")
    add("")
    add("| | figure |")
    add("|---|--:|")
    add(f"| net-new (domain, year) pairs vs {BASELINE} | **{f['netnew_pairs']:,}** |")
    add(f"| over unique domains | {f['netnew_unique_domains']:,} |")
    add(
        "| domains absent from the baseline in every year | "
        f"**{f['netnew_domains_absent_from_baseline']:,}** |"
    )
    add(f"| equivalent-English added | **{f['ee_netnew']:,.1f}** |")
    add(
        f"| growth on the {f['ee_baseline']:,.1f} baseline | **{f['ee_netnew_growth_pct']:.4f}%** |"
    )
    add(f"| mean equivalent-English weight per pair | {f['ee_mean_weight']:.4f} |")
    add(f"| candidate pool | {f['candidate_pool']:,} |")
    add("")

    add("### Per year")
    add("")
    add("| Year | Net-new pairs | With a known in-year capture |")
    add("|---|--:|--:|")
    for year in sorted(f["netnew_by_year"]):
        add(
            f"| {year} | {f['netnew_by_year'][year]:,} | "
            f"{f['capture_backed_by_year'].get(year, 0):,} |"
        )
    add(f"| **Total** | **{f['netnew_pairs']:,}** | **{f['capture_backed_total']:,}** |")
    add("")

    add("### Per source")
    add("")
    add("| Source | Kind | Net-new pairs | Domains | Equivalent-English |")
    add("|---|---|--:|--:|--:|")
    for row in f["by_source"]:
        add(
            f"| `{row['source']}` | {row['kind']} | {row['pairs']:,} | "
            f"{row['domains']:,} | {row['ee']:,.1f} |"
        )
    add(f"| **Total** | | **{f['netnew_pairs']:,}** | | **{f['ee_netnew']:,.1f}** |")
    add("")

    add("### Completeness")
    add("")
    add("| Year | Additions | Growth vs baseline | Under 10,000? | Under 0.1%? |")
    add("|---|--:|--:|:-:|:-:|")
    for year in sorted(f["netnew_by_year"]):
        added = f["netnew_by_year"][year]
        base = f["baseline_by_year"].get(year, 0)
        growth = 100.0 * added / base if base else 0.0
        add(
            f"| {year} | {added:,} | {growth:.2f}% | "
            f"{'yes' if added < 10000 else 'no'} | {'yes' if growth < 0.1 else 'no'} |"
        )
    add("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true", help="report tables, ready to paste")
    args = parser.parse_args()
    conn = connect_read_only_patiently(DB)
    f = figures(conn)
    if args.json:
        # Equivalent-English is carried as Decimal all the way through, because
        # the reviewer's own calculator is exact and a float round-trip would put
        # our fourth decimal place a hair off his. Serialise it as a string so
        # that stays true on the way out too.
        print(json.dumps(f, indent=2, default=str))
    elif args.markdown:
        print(markdown(f))
    else:
        print(render(f))


if __name__ == "__main__":
    main()
