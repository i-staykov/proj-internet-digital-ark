"""Per-source and per-year contribution tables, as machine-readable CSVs, written to the
audit directory that ships in the delivery archive.

`source_contribution.csv` answers "what did each source actually buy?", which decides
whether a source is worth expanding. Evidence rows are reported separately from assigned
pairs because the gap is the point: millions of rows and almost no new pairs makes a
corroboration source rather than a growth source, which is a finding.

`year_growth.csv` answers "how much did each annual file grow?", in the column shape of the
supplied `merge_stats` file. `candidate_unique_not_merged` is deliberately not reproduced:
it assumes candidates are attributable to a year, and here a candidate has no year at all.
The pool is reported as a whole instead.
"""

import csv
import tempfile
from pathlib import Path

import duckdb

from ark import held
from ark.ingest import YEARS
from ark.stats import _lineage_case_sql

DEFAULT_REPORT_DIR = Path("data/reports")

# Reads what `export_all` builds first: `netnew_pair` and `held_any`.
_SOURCE_SQL = f"""
WITH per_source AS (
    SELECT s.name AS source,
           {_lineage_case_sql()} AS lineage,
           min(e.evidence_type) AS evidence_type,
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
-- A pair is net-new when it is a line of a shipped annual file, which includes a
-- domain he holds gaining a year his file lacks. A domain is net-new only when no year
-- file of his names it. Conflating them silently zeroes every gap-filling source, since
-- those add years to domains he already holds.
-- `netnew_pair` is the shipped registrable lines, each with the row it cites, so a
-- per-source figure a reviewer reads here equals what he counts in
-- `additions/evidence_manifest.csv`.
netnew AS (
    SELECT s.name AS source,
           count(*) AS netnew_pairs,
           count(DISTINCT n.domain) FILTER (WHERE h.name IS NULL) AS netnew_domains
    FROM netnew_pair n
    LEFT JOIN held_any h ON h.name = n.domain
    JOIN evidence e ON e.evidence_id = n.evidence_id
    JOIN source s ON s.source_id = e.source_id
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

YEAR_COLUMNS = ["year", "base_unique", "added_unique", "merged_unique", "growth_percent"]


def _year_rows(his: held.Held, netnew_dir: Path) -> list[tuple[int, int, int, int]]:
    """Each year from line counts: his year file, then our registrable and hostname files.
    Each of ours had his year file taken out by `comm`, and packaging merges the three into
    `masters/<year>.txt`, so `merged_unique` is its `wc -l` as long as ours share no line."""
    rows = []
    with tempfile.TemporaryDirectory(prefix="ark-growth-") as tmp:
        for year in YEARS:
            ours = netnew_dir / f"{year}.txt", netnew_dir / f"{year}_hostnames.txt"
            if held.intersect(*ours, Path(tmp) / f"{year}.txt"):
                raise ValueError(f"{ours[0]} and {ours[1]} share a line")
            base = his.counts[str(year)]
            added = sum(held.lines(path) for path in ours)
            rows.append((year, base, added, base + added))
    return rows


def write_contribution_tables(
    conn: duckdb.DuckDBPyConnection, report_dir: Path, his: held.Held, netnew_dir: Path
) -> dict[str, int]:
    """Write both contribution tables and report how many rows each holds."""
    report_dir.mkdir(parents=True, exist_ok=True)

    source_rows = conn.execute(_SOURCE_SQL).fetchall()
    source_path = report_dir / "source_contribution.csv"
    with source_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(SOURCE_COLUMNS)
        writer.writerows(source_rows)

    year_rows = _year_rows(his, netnew_dir)
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
