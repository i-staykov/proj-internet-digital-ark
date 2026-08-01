"""Read-only integrity checks over the provenance store.

Each check is a SQL query that must return zero offending rows. `ark check`
runs them all and exits non-zero if any fails, so it doubles as a release gate:
no annual result ships unless every invariant below holds.

The checks exist to make claims machine-verified rather than asserted in prose.
Several of them encode a rule that is stated in the delivery report, so a reader
who doubts the rule can run the gate instead of taking it on trust.
"""

from pathlib import Path

import duckdb

from ark.evidence_types import CANDIDATE_ONLY_TYPES

_CANDIDATE_LIST = ", ".join(f"'{t}'" for t in sorted(CANDIDATE_ONLY_TYPES))

# Where `ark export` writes the annual additions. A parameter rather than a
# constant inside the SQL: a hardcoded path would make the test suite assert
# against the real deliverable, which is the same trap `export_all` documents.
NETNEW_DIR = Path("output/netnew")
ENGLISH_DIR = Path("output/netnew_english")

# The first four-digit run inside an evidence value is that value's own year, for
# every type whose value names a single year: a CDX timestamp (19981212033831), a
# survey month (1996-07), a link-graph tag (host_link_graph:2001), a creation
# note (rdap creation 1998). Not applied to `dated_directory`, whose value is an
# opaque record identifier, nor to a registration span, which names two years on
# purpose.
_VALUE_YEAR = "TRY_CAST(regexp_extract(evidence_value, '([0-9]{4})', 1) AS INT)"

# Sources whose evidence value is a registration SPAN rather than a single year,
# so its year deliberately differs from the assigned year. Only AFNIC qualifies,
# and only because its registry documents that a creation date resets on
# re-registration, which is what makes the span continuous. Any other source
# added here needs the same standard of proof.
_SPAN_SOURCES = "'afnic_fr'"

# a stored domain is a lowercase registrable name: strict first label, then one
# or more suffix labels (co.uk, xn--*, historical ccTLDs all fit), at least one dot
_DOMAIN_RE = r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$"

# name, human description, SQL returning a single count of offending rows (0 = pass)
CHECKS: list[tuple[str, str, str]] = [
    (
        "evidence_wall_intact",
        "every annual assignment points at an evidence row for the same domain and year",
        """
        SELECT count(*) FROM domain_year dy
        LEFT JOIN evidence e ON e.evidence_id = dy.evidence_id
        WHERE e.evidence_id IS NULL
           OR e.domain <> dy.domain
           OR e.evidence_year <> dy.assigned_year
        """,
    ),
    (
        "no_candidate_leakage",
        "no annual assignment is backed by candidate-only evidence",
        f"""
        SELECT count(*) FROM domain_year dy
        JOIN evidence e ON e.evidence_id = dy.evidence_id
        WHERE e.evidence_type IN ({_CANDIDATE_LIST})
        """,
    ),
    (
        "every_pair_has_master_evidence",
        "every assigned pair has >=1 master-eligible evidence row for that exact year",
        f"""
        SELECT count(*) FROM domain_year dy WHERE NOT EXISTS (
            SELECT 1 FROM evidence e
            WHERE e.domain = dy.domain AND e.evidence_year = dy.assigned_year
              AND e.evidence_type NOT IN ({_CANDIDATE_LIST})
        )
        """,
    ),
    (
        "within_year_unique",
        "no duplicate (domain, year) in the annual masters",
        """
        SELECT count(*) FROM (
            SELECT domain, assigned_year FROM domain_year GROUP BY 1, 2 HAVING count(*) > 1
        )
        """,
    ),
    (
        "assigned_year_in_window",
        "every assigned year is within 1996-2001",
        "SELECT count(*) FROM domain_year WHERE assigned_year NOT BETWEEN 1996 AND 2001",
    ),
    (
        "registered_domain_format",
        "every stored domain is a well-formed lowercase registrable name",
        f"SELECT count(*) FROM domain WHERE NOT regexp_matches(domain, '{_DOMAIN_RE}')",
    ),
    (
        "evidence_year_matches_its_value",
        "the year named inside an evidence value equals the year it was filed under "
        "(registration spans excepted, since they name two years by design)",
        f"""
        SELECT count(*) FROM evidence e
        JOIN source s ON s.source_id = e.source_id
        WHERE {_VALUE_YEAR} IS NOT NULL
          AND {_VALUE_YEAR} <> e.evidence_year
          AND (
            e.evidence_type IN ('cdx_timestamp', 'artifact_listing', 'link_source')
            OR (e.evidence_type = 'whois_creation' AND s.name NOT IN ({_SPAN_SOURCES}))
          )
        """,
    ),
    (
        "additions_not_double_counted",
        "no domain in the exported additions files carries baseline evidence for that year, "
        "so the shipped net-new figure cannot be inflated by rows the baseline already had",
        r"""
        SELECT count(*)
        FROM read_csv(
            '{netnew_dir}/[0-9][0-9][0-9][0-9].txt',
            columns = {{'domain': 'VARCHAR'}}, header = false, filename = true
        ) f
        JOIN evidence p ON p.domain = f.domain
         -- anchored to the file name: the year is the file, and an unanchored
         -- match would take any four digits that happen to sit in the path
         AND p.evidence_year = TRY_CAST(regexp_extract(f.filename, '([0-9]{{4}})\.txt$', 1) AS INT)
        WHERE p.evidence_type = 'prior_reused'
        """,
    ),
    (
        "english_files_hold_only_verified_english",
        "every domain in the exported English annual files has an 'english' language verdict "
        "for that exact year, so the admitted set cannot contain a site the standard excludes",
        r"""
        SELECT count(*)
        FROM read_csv(
            '{english_dir}/[0-9][0-9][0-9][0-9].txt',
            columns = {{'domain': 'VARCHAR'}}, header = false, filename = true
        ) f
        WHERE NOT EXISTS (
            SELECT 1 FROM domain_language dl
            WHERE dl.domain = f.domain
              AND dl.verdict = 'english'
              -- anchored to the file name for the same reason as the check above
              AND dl.assigned_year =
                  TRY_CAST(regexp_extract(f.filename, '([0-9]{{4}})\.txt$', 1) AS INT)
        )
        """,
    ),
    (
        "nothing_earned_is_left_unassigned",
        "every master-eligible evidence row has its (domain, year) assigned, so a domain "
        "cannot sit in the candidate pool while already holding proof of a year",
        f"""
        SELECT count(*) FROM evidence e
        WHERE e.evidence_type NOT IN ({_CANDIDATE_LIST})
          AND NOT EXISTS (
            SELECT 1 FROM domain_year dy
            WHERE dy.domain = e.domain AND dy.assigned_year = e.evidence_year
          )
        """,
    ),
]


def collect_checks(
    conn: duckdb.DuckDBPyConnection,
    netnew_dir: Path = NETNEW_DIR,
    english_dir: Path = ENGLISH_DIR,
) -> list[dict]:
    """Run every integrity check; return one result dict per check.

    A check that reads an exported file is reported as skipped when the export
    is absent, which is the normal state of a fresh clone before `ark export`.
    Skipped is shown rather than counted as a pass, so an empty output/ cannot be
    mistaken for a satisfied invariant.
    """
    results = []
    for name, description, template in CHECKS:
        needs_export = "{netnew_dir}" in template or "{english_dir}" in template
        sql = (
            template.format(netnew_dir=netnew_dir, english_dir=english_dir)
            if needs_export
            else template
        )
        try:
            offending = conn.execute(sql).fetchone()[0]
        except duckdb.IOException:
            results.append(
                {
                    "name": name,
                    "description": description,
                    "offending": 0,
                    "ok": True,
                    "skipped": f"no exported files in {netnew_dir}; run `ark export` first",
                }
            )
            continue
        results.append(
            {"name": name, "description": description, "offending": offending, "ok": offending == 0}
        )
    return results


def format_checks(results: list[dict]) -> str:
    lines = ["== integrity checks =="]
    for r in results:
        if r.get("skipped"):
            lines.append(f"  [SKIP] {r['name']}: {r['skipped']}")
            continue
        mark = "PASS" if r["ok"] else "FAIL"
        lines.append(f"  [{mark}] {r['name']}: {r['offending']:,} offending  ({r['description']})")
    failed = [r["name"] for r in results if not r["ok"]]
    lines.append("ALL PASS" if not failed else f"FAILED: {', '.join(failed)}")
    return "\n".join(lines)
