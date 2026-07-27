"""Per-source and per-year contribution tables, as machine-readable CSVs.

Two tables, because two questions get asked of this project.

`source_contribution.csv` answers "what did each source actually buy?", which is
what decides whether a source is worth expanding. It reports evidence rows
separately from assigned pairs, because the gap between them is the point: a
source can contribute millions of rows and almost no new pairs, which makes it a
corroboration source rather than a growth source, and that is a finding rather
than a disappointment.

`year_growth.csv` answers "how much did each annual file grow?", in the column
shape of the `merge_stats` file supplied with the task, so the two can be read
side by side. One column of that shape is deliberately not reproduced:
`candidate_unique_not_merged` assumes candidates are attributable to a year,
and in this model a candidate has no year at all, which is what makes it a
candidate. The pool is reported as a whole instead.

Both are written to the audit directory that ships in the delivery archive.
"""

import csv
from pathlib import Path

import duckdb

from ark.ingest import YEARS
from ark.stats import BASELINE_TYPE, _lineage_case_sql

DEFAULT_REPORT_DIR = Path("data/reports")

_SOURCE_SQL = f"""
WITH per_source AS (
    SELECT s.name AS source,
           {_lineage_case_sql()} AS lineage,
           any_value(e.evidence_type) AS evidence_type,
           count(e.evidence_id) AS evidence_rows,
           count(DISTINCT e.domain) AS domains_touched
    -- Driven from `source`, not from `evidence`: a source that only ever fed the
    -- candidate pool has no evidence rows at all, and an inner join silently drops
    -- it, so the candidate column could not be reconciled with the reported pool.
    FROM source s
    LEFT JOIN evidence e ON e.source_id = s.source_id
    GROUP BY s.name
),
backed AS (
    SELECT s.name AS source, count(*) AS pairs_backed
    FROM domain_year dy
    JOIN evidence e ON e.evidence_id = dy.evidence_id
    JOIN source s ON s.source_id = e.source_id
    GROUP BY s.name
),
-- A net-new PAIR and a net-new DOMAIN are different tests and must not share one.
-- A pair is net-new when the baseline held no evidence for that (domain, year),
-- which includes a baseline domain gaining a year it did not have. A domain is
-- net-new only when the baseline held nothing for it at all. Conflating them
-- silently zeroes every gap-filling source, since those add years to domains the
-- baseline already knew.
netnew AS (
    SELECT s.name AS source,
           count(*) FILTER (
             WHERE NOT EXISTS (
               SELECT 1 FROM evidence p
               WHERE p.domain = dy.domain AND p.evidence_year = dy.assigned_year
                 AND p.evidence_type = '{BASELINE_TYPE}'
             )
           ) AS netnew_pairs,
           count(DISTINCT dy.domain) FILTER (
             WHERE NOT EXISTS (
               SELECT 1 FROM evidence p
               WHERE p.domain = dy.domain AND p.evidence_type = '{BASELINE_TYPE}'
             )
           ) AS netnew_domains
    FROM domain_year dy
    JOIN evidence e ON e.evidence_id = dy.evidence_id
    JOIN source s ON s.source_id = e.source_id
    WHERE e.evidence_type <> '{BASELINE_TYPE}'
    GROUP BY s.name
),
candidates AS (
    SELECT s.name AS source, count(*) AS candidate_domains
    FROM domain d
    JOIN source s ON s.source_id = d.discovered_source
    WHERE NOT EXISTS (SELECT 1 FROM domain_year dy WHERE dy.domain = d.domain)
    GROUP BY s.name
),
files AS (
    SELECT source_name AS source, count(*) AS files_ingested
    FROM ingested_file GROUP BY source_name
)
SELECT p.source, p.lineage, p.evidence_type,
       coalesce(f.files_ingested, 0) AS files_ingested,
       p.evidence_rows, p.domains_touched,
       coalesce(b.pairs_backed, 0) AS pairs_backed,
       coalesce(n.netnew_domains, 0) AS netnew_domains,
       coalesce(n.netnew_pairs, 0) AS netnew_pairs,
       coalesce(c.candidate_domains, 0) AS candidate_domains
FROM per_source p
LEFT JOIN backed b ON b.source = p.source
LEFT JOIN netnew n ON n.source = p.source
LEFT JOIN candidates c ON c.source = p.source
LEFT JOIN files f ON f.source = p.source
ORDER BY netnew_pairs DESC, evidence_rows DESC, p.source
"""

SOURCE_COLUMNS = [
    "source",
    "lineage",
    "evidence_type",
    "files_ingested",
    "evidence_rows",
    "domains_touched",
    "pairs_backed",
    "netnew_domains",
    "netnew_pairs",
    "candidate_domains",
]

_YEAR_SQL = f"""
SELECT y.year,
       count(*) FILTER (WHERE b.domain IS NOT NULL) AS base_unique,
       count(*) FILTER (WHERE b.domain IS NULL) AS added_unique,
       count(*) AS merged_unique
FROM (SELECT unnest($years) AS year) y
JOIN domain_year dy ON dy.assigned_year = y.year
LEFT JOIN (
    SELECT DISTINCT domain, evidence_year FROM evidence
    WHERE evidence_type = '{BASELINE_TYPE}'
) b ON b.domain = dy.domain AND b.evidence_year = dy.assigned_year
GROUP BY y.year ORDER BY y.year
"""

YEAR_COLUMNS = ["year", "base_unique", "added_unique", "merged_unique", "growth_percent"]


def write_contribution_tables(
    conn: duckdb.DuckDBPyConnection,
    report_dir: Path = DEFAULT_REPORT_DIR,
) -> dict[str, int]:
    """Write both contribution tables and report how many rows each holds."""
    report_dir.mkdir(parents=True, exist_ok=True)

    source_rows = conn.execute(_SOURCE_SQL).fetchall()
    source_path = report_dir / "source_contribution.csv"
    with source_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(SOURCE_COLUMNS)
        writer.writerows(source_rows)

    year_rows = conn.execute(_YEAR_SQL, {"years": list(YEARS)}).fetchall()
    year_path = report_dir / "year_growth.csv"
    with year_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(YEAR_COLUMNS)
        for year, base, added, merged in year_rows:
            # growth against the baseline the year started from, which is what the
            # supplied merge_stats reports; undefined rather than infinite when a
            # year had no baseline at all
            growth = round(100.0 * added / base, 6) if base else ""
            writer.writerow([year, base, added, merged, growth])

    return {"source_rows": len(source_rows), "year_rows": len(year_rows)}
