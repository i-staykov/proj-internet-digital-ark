"""The scoreboard: how much have we added on top of the provided baseline.

A (domain, year) pair is net-new when its evidence is anything other than
prior_reused. A domain is net-new when it has verified years but never
appears in the baseline at all.
"""

import duckdb

BASELINE_TYPE = "prior_reused"


def collect_stats(conn: duckdb.DuckDBPyConnection) -> dict:
    baseline_domains = conn.execute(
        "SELECT count(DISTINCT domain) FROM evidence WHERE evidence_type = ?",
        [BASELINE_TYPE],
    ).fetchone()[0]
    total_domains = conn.execute("SELECT count(*) FROM domain").fetchone()[0]
    total_pairs = conn.execute("SELECT count(*) FROM domain_year").fetchone()[0]
    candidate_pool = conn.execute(
        "SELECT count(*) FROM domain d WHERE NOT EXISTS "
        "(SELECT 1 FROM domain_year dy WHERE dy.domain = d.domain)"
    ).fetchone()[0]
    netnew_domains = conn.execute(
        """
        SELECT count(DISTINCT dy.domain) FROM domain_year dy
        WHERE dy.domain NOT IN (
            SELECT DISTINCT domain FROM evidence WHERE evidence_type = ?
        )
        """,
        [BASELINE_TYPE],
    ).fetchone()[0]
    pairs_by_year = dict(
        conn.execute(
            """
            SELECT dy.assigned_year, count(*)
            FROM domain_year dy
            JOIN evidence e ON dy.evidence_id = e.evidence_id
            WHERE e.evidence_type != ?
            GROUP BY dy.assigned_year ORDER BY dy.assigned_year
            """,
            [BASELINE_TYPE],
        ).fetchall()
    )
    return {
        "baseline_domains": baseline_domains,
        "total_domains": total_domains,
        "total_pairs": total_pairs,
        "candidate_pool": candidate_pool,
        "netnew_domains": netnew_domains,
        "netnew_pairs_by_year": pairs_by_year,
        "netnew_pairs_total": sum(pairs_by_year.values()),
    }


def format_stats(stats: dict) -> str:
    lines = [
        "== scoreboard ==",
        f"net-new domains (not in baseline):  {stats['netnew_domains']:>10,}",
        f"net-new (domain, year) pairs:       {stats['netnew_pairs_total']:>10,}",
    ]
    for year, count in stats["netnew_pairs_by_year"].items():
        lines.append(f"    {year}: {count:,}")
    lines += [
        "== context ==",
        f"baseline domains:                   {stats['baseline_domains']:>10,}",
        f"domains in store:                   {stats['total_domains']:>10,}",
        f"(domain, year) pairs in store:      {stats['total_pairs']:>10,}",
        f"candidate pool (unverified):        {stats['candidate_pool']:>10,}",
    ]
    return "\n".join(lines)
