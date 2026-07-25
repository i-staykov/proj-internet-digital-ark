"""Prune whois_creation evidence down to the creation year alone.

An earlier standard read a WHOIS/RDAP creation date as evidence for every
in-window year of an inferred registration interval. Brief III.6 only blesses
"the annual file for the target year in which the creation date falls" and
requires later years to carry evidence "tied to that specific year", so this
script deletes the interval rows a source wrote for years other than its
creation year, plus the annual assignments that rested on them.

Safety: dry run unless --apply. It aborts rather than guess if a creation year
cannot be parsed, or if a doomed assignment could be re-pointed at other
master evidence (that case needs re-pointing, not deletion, and does not
currently occur).

    uv run python scripts/restrict_whois_creation_to_creation_year.py rdap
    uv run python scripts/restrict_whois_creation_to_creation_year.py rdap --apply
"""

import argparse
from pathlib import Path

import duckdb

# per source, a SQL expression reading the creation year out of evidence_value
CREATION_YEAR_SQL = {
    # "rdap creation 1998"
    "rdap": r"TRY_CAST(regexp_extract(evidence_value, 'creation ([0-9]{4})', 1) AS INT)",
    # "registered 29-12-1999..active"
    "afnic_fr": r"TRY_CAST(regexp_extract(evidence_value, '-([0-9]{4})\.\.', 1) AS INT)",
}

CANDIDATE_ONLY = "'link_target'"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=sorted(CREATION_YEAR_SQL))
    parser.add_argument("--db", type=Path, default=Path("data/ark.duckdb"))
    parser.add_argument("--apply", action="store_true", help="Actually delete (default: dry run).")
    args = parser.parse_args()

    creation_year = CREATION_YEAR_SQL[args.source]
    conn = duckdb.connect(str(args.db), read_only=not args.apply)
    row = conn.execute("SELECT source_id FROM source WHERE name = ?", [args.source]).fetchone()
    if row is None:
        print(f"no such source in the store: {args.source}")
        return 1
    source_id = row[0]

    def scalar(sql: str) -> int:
        return conn.execute(sql).fetchone()[0]

    mine = f"FROM evidence WHERE source_id = {source_id}"
    doomed = f"{mine} AND {creation_year} IS DISTINCT FROM evidence_year"

    unparseable = scalar(f"SELECT count(*) {mine} AND {creation_year} IS NULL")
    if unparseable:
        print(f"ABORT: {unparseable:,} {args.source} rows have no parseable creation year")
        return 1

    evidence_before = scalar(f"SELECT count(*) {mine}")
    evidence_doomed = scalar(f"SELECT count(*) {doomed}")

    # an assignment resting on a doomed row survives only if other master
    # evidence for the same (domain, year) can carry it instead
    repointable = scalar(f"""
        SELECT count(*) FROM domain_year dy
        WHERE dy.evidence_id IN (SELECT evidence_id {doomed})
          AND EXISTS (
            SELECT 1 FROM evidence e2
            WHERE e2.domain = dy.domain AND e2.evidence_year = dy.assigned_year
              AND e2.evidence_id <> dy.evidence_id
              AND e2.evidence_type NOT IN ({CANDIDATE_ONLY})
              AND e2.evidence_id NOT IN (SELECT evidence_id {doomed})
          )
    """)
    if repointable:
        print(f"ABORT: {repointable:,} assignments could be re-pointed, not deleted")
        return 1

    pairs_before = scalar("SELECT count(*) FROM domain_year")
    pairs_doomed = scalar(
        f"SELECT count(*) FROM domain_year WHERE evidence_id IN (SELECT evidence_id {doomed})"
    )
    domains_emptied = scalar(f"""
        SELECT count(*) FROM (
            SELECT dy.domain FROM domain_year dy
            GROUP BY dy.domain
            HAVING count(*) = count_if(dy.evidence_id IN (SELECT evidence_id {doomed}))
        )
    """)

    print(f"source {args.source} (source_id {source_id})")
    print(f"  evidence rows   {evidence_before:,} -> {evidence_before - evidence_doomed:,}")
    print(f"  assigned pairs  {pairs_before:,} -> {pairs_before - pairs_doomed:,}")
    print(f"  domains left with no assigned year: {domains_emptied:,} (they stay candidates)")

    if not args.apply:
        print("dry run: nothing written. re-run with --apply to delete.")
        return 0

    # two transactions on purpose: DuckDB validates the domain_year -> evidence
    # foreign key against the pre-commit index, so dropping both ends at once
    # trips the constraint. Assignments must go first and be committed; evidence
    # with no assignment is a normal state, the reverse is what the wall forbids.
    for statement in (
        f"DELETE FROM domain_year WHERE evidence_id IN (SELECT evidence_id {doomed})",
        f"DELETE FROM evidence WHERE evidence_id IN (SELECT evidence_id {doomed})",
    ):
        conn.execute("BEGIN TRANSACTION")
        conn.execute(statement)
        conn.execute("COMMIT")

    left = scalar(f"SELECT count(*) {mine} AND {creation_year} IS DISTINCT FROM evidence_year")
    print(f"applied. interval rows remaining for {args.source}: {left:,} (expected 0)")
    return 0 if left == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
