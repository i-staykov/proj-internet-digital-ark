"""Read-only integrity checks over the provenance store (Phase 6 QA).

Each check is a SQL query that must return zero offending rows. `ark check`
runs them all and exits non-zero if any fails, so it doubles as a release gate:
no annual result ships unless every invariant below holds.
"""

import duckdb

from ark.evidence_types import CANDIDATE_ONLY_TYPES

_CANDIDATE_LIST = ", ".join(f"'{t}'" for t in sorted(CANDIDATE_ONLY_TYPES))

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
]


def collect_checks(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    """Run every integrity check; return one result dict per check."""
    results = []
    for name, description, sql in CHECKS:
        offending = conn.execute(sql).fetchone()[0]
        results.append(
            {"name": name, "description": description, "offending": offending, "ok": offending == 0}
        )
    return results


def format_checks(results: list[dict]) -> str:
    lines = ["== integrity checks =="]
    for r in results:
        mark = "PASS" if r["ok"] else "FAIL"
        lines.append(f"  [{mark}] {r['name']}: {r['offending']:,} offending  ({r['description']})")
    failed = [r["name"] for r in results if not r["ok"]]
    lines.append("ALL PASS" if not failed else f"FAILED: {', '.join(failed)}")
    return "\n".join(lines)
