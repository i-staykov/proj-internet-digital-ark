"""The scoreboard: how much has been added on top of the baseline, and how
many sources back each assertion.

Everything is computed over the evidence table, which holds one row per
(domain, year) per source. A (domain, year) pair is net-new when it is
assigned but has no prior_reused (baseline) evidence; a domain is net-new
when it is assigned but has no baseline evidence at all. This is robust
regardless of which evidence row happened to make the assignment.

Corroboration is reported at two strengths, because they mean different things.

Cross-SOURCE corroboration counts distinct source rows behind an asserted pair.
It is the weaker figure: the supplied baseline, the Early Web CDX dataset and the
Arquivo `IA.cdxj` donation all trace back to the Internet Archive, so a pair
carrying all three is well covered but confirmed by one organisation's crawling.

Cross-PROVENANCE corroboration counts distinct collection lineages, grouping every
source that ultimately derives from the same body of observation. Two sources in
different lineages agreeing is genuine independent confirmation: a DNS survey and
a registry file have no common ancestor. That is the figure worth quoting, and it
is much smaller than the cross-source one.

Candidate-only evidence proves nothing and is excluded from both.
"""

import duckdb

from ark.evidence_types import MASTER_TYPES

BASELINE_TYPE = "prior_reused"

# Which body of observation each source ultimately derives from. Sources sharing a
# lineage cannot independently confirm one another, however many rows they carry:
# the baseline was built from Internet Archive holdings, Early Web IS an IA
# dataset, and Arquivo's `IA.cdxj` was donated by IA, so agreement among them is
# coverage rather than confirmation. A source absent from this map is treated as
# its own lineage, which is the conservative default for anything newly added.
PROVENANCE_LINEAGE = {
    "prior_task": "internet_archive",
    "early_web_cdx": "internet_archive",
    "arquivo_ia": "internet_archive",
    "ia_cdx": "internet_archive",
    "ia_cdx_bulk": "internet_archive",
    "page_expansion": "internet_archive",
    "page_directory": "internet_archive",
    "isc_survey": "dns_survey",
    "afnic_fr": "registry",
    "rdap": "registry",
    "rdap_snapshot": "registry",
    "ukwa_link_source": "uk_web_archive",
    "ukwa_link_target": "uk_web_archive",
    "arquivo_roteiro": "arquivo_pt",
    "odp": "editorial_directory",
    "internet_scout": "editorial_directory",
}
# only existence-proving evidence corroborates an assertion
_MASTER_TYPE_LIST = ", ".join(f"'{name}'" for name in sorted(MASTER_TYPES))


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
    # net-new domain: assigned, but carrying no baseline evidence anywhere
    netnew_domains = conn.execute(
        """
        SELECT count(DISTINCT dy.domain) FROM domain_year dy
        WHERE NOT EXISTS (
            SELECT 1 FROM evidence e WHERE e.domain = dy.domain AND e.evidence_type = ?
        )
        """,
        [BASELINE_TYPE],
    ).fetchone()[0]
    # net-new pair: assigned, but no baseline evidence for that (domain, year)
    pairs_by_year = dict(
        conn.execute(
            """
            SELECT dy.assigned_year, count(*)
            FROM domain_year dy
            WHERE NOT EXISTS (
                SELECT 1 FROM evidence e
                WHERE e.domain = dy.domain AND e.evidence_year = dy.assigned_year
                  AND e.evidence_type = ?
            )
            GROUP BY dy.assigned_year ORDER BY dy.assigned_year
            """,
            [BASELINE_TYPE],
        ).fetchall()
    )
    evidence_by_type = dict(
        conn.execute(
            "SELECT evidence_type, count(*) FROM evidence "
            "GROUP BY evidence_type ORDER BY count(*) DESC, evidence_type"
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
        "evidence_rows": sum(evidence_by_type.values()),
        "evidence_rows_by_type": evidence_by_type,
        **_corroboration(conn),
        **_independent_corroboration(conn),
    }


def _corroboration(conn: duckdb.DuckDBPyConnection) -> dict:
    """Distinct master-eligible sources behind each asserted pair."""
    avg_sources, corroborated, baseline_corroborated = conn.execute(
        f"""
        WITH pair_sources AS (
            SELECT e.domain, e.evidence_year,
                   count(DISTINCT e.source_id) AS n_sources,
                   count(*) FILTER (WHERE e.evidence_type = ?) > 0 AS has_baseline
            FROM evidence e
            JOIN domain_year dy
              ON dy.domain = e.domain AND dy.assigned_year = e.evidence_year
            WHERE e.evidence_type IN ({_MASTER_TYPE_LIST})
            GROUP BY e.domain, e.evidence_year
        )
        SELECT coalesce(round(avg(n_sources), 4), 0.0),
               count(*) FILTER (WHERE n_sources >= 2),
               count(*) FILTER (WHERE has_baseline AND n_sources >= 2)
        FROM pair_sources
        """,
        [BASELINE_TYPE],
    ).fetchone()
    return {
        "avg_sources_per_pair": avg_sources,
        "corroborated_pairs": corroborated,
        "baseline_corroborated": baseline_corroborated,
    }


def _lineage_case_sql(alias: str = "s.name") -> str:
    """SQL mapping a source name to its provenance lineage, unknown names to themselves."""
    whens = " ".join(
        f"WHEN '{name}' THEN '{lineage}'" for name, lineage in sorted(PROVENANCE_LINEAGE.items())
    )
    return f"CASE {alias} {whens} ELSE {alias} END"


def _independent_corroboration(conn: duckdb.DuckDBPyConnection) -> dict:
    """Pairs confirmed by two or more genuinely independent collection lineages."""
    lineage = _lineage_case_sql()
    independent, netnew_independent = conn.execute(
        f"""
        WITH pair_lineages AS (
            SELECT e.domain, e.evidence_year,
                   count(DISTINCT {lineage}) AS n_lineages,
                   count(*) FILTER (WHERE e.evidence_type = ?) > 0 AS has_baseline
            FROM evidence e
            JOIN source s ON s.source_id = e.source_id
            JOIN domain_year dy
              ON dy.domain = e.domain AND dy.assigned_year = e.evidence_year
            WHERE e.evidence_type IN ({_MASTER_TYPE_LIST})
            GROUP BY e.domain, e.evidence_year
        )
        SELECT count(*) FILTER (WHERE n_lineages >= 2),
               count(*) FILTER (WHERE n_lineages >= 2 AND NOT has_baseline)
        FROM pair_lineages
        """,
        [BASELINE_TYPE],
    ).fetchone()
    by_lineage = dict(
        conn.execute(
            f"""
            SELECT {lineage} AS lineage, count(*) FROM evidence e
            JOIN source s ON s.source_id = e.source_id
            GROUP BY 1 ORDER BY 2 DESC
            """
        ).fetchall()
    )
    return {
        "independently_corroborated_pairs": independent,
        "independently_corroborated_netnew": netnew_independent,
        "evidence_rows_by_lineage": by_lineage,
    }


def format_stats(stats: dict) -> str:
    lines = [
        "== scoreboard ==",
        f"net-new domains (not in baseline):  {stats['netnew_domains']:>12,}",
        f"net-new (domain, year) pairs:       {stats['netnew_pairs_total']:>12,}",
    ]
    for year, count in stats["netnew_pairs_by_year"].items():
        lines.append(f"    {year}: {count:,}")
    lines += [
        "== cross-source corroboration ==",
        f"evidence rows in store:             {stats['evidence_rows']:>12,}",
        f"avg sources per assigned pair:      {stats['avg_sources_per_pair']:>12.4f}",
        f"pairs with 2+ sources:              {stats['corroborated_pairs']:>12,}",
        f"    of which already in baseline:   {stats['baseline_corroborated']:>12,}",
        "== independent corroboration (2+ provenance lineages) ==",
        f"pairs confirmed independently:      {stats['independently_corroborated_pairs']:>12,}",
        f"    of which net-new:               {stats['independently_corroborated_netnew']:>12,}",
    ]
    for lineage, count in stats["evidence_rows_by_lineage"].items():
        lines.append(f"    {lineage}: {count:,}")
    lines += ["== evidence rows by type =="]
    for etype, count in stats["evidence_rows_by_type"].items():
        lines.append(f"    {etype}: {count:,}")
    lines += [
        "== context ==",
        f"baseline domains:                   {stats['baseline_domains']:>12,}",
        f"domains in store:                   {stats['total_domains']:>12,}",
        f"(domain, year) pairs in store:      {stats['total_pairs']:>12,}",
        f"candidate pool (unverified):        {stats['candidate_pool']:>12,}",
    ]
    return "\n".join(lines)
