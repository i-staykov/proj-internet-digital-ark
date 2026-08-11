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

from decimal import Decimal

import duckdb

from ark.baseline import CURRENT_BASELINE_MARKER, REVIEWER_BASELINE_EE
from ark.english_share import english_weights
from ark.evidence_types import MASTER_TYPES

BASELINE_TYPE = "prior_reused"

# Growth is the increment divided by the reviewer's PRE-increment total, which is his
# convention and not the same as dividing by the post-increment one. Which release
# that is lives in `ark.baseline`, so this figure and the ingest defaults cannot drift
# apart.
#
# A hardcoded ALREADY_CREDITED_EE stood here briefly, subtracting the round he had
# already merged, because `merged260802` was sitting unread on disk and net-new
# therefore overstated by exactly that round. Ingesting it makes net-new right by
# construction. A constant needing a hand edit every time he merges is the worse bug
# of the two: it fails silently, and it fails in our favour.

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
    # NYPW is a sample of the Internet Archive's own CDX, so a pair it confirms
    # alongside early_web_cdx or a Wayback query has ONE lineage, not two. Filing
    # it here rather than as its own family keeps the independent-corroboration
    # count honest, which is the whole point of that measure.
    "nypw_firstcdx": "internet_archive",
    "page_expansion": "internet_archive",
    "page_directory": "internet_archive",
    "isc_survey": "dns_survey",
    "afnic_fr": "registry",
    "rdap": "registry",
    "rdap_snapshot": "registry",
    "ukwa_link_source": "uk_web_archive",
    "ukwa_link_target": "uk_web_archive",
    "arquivo_roteiro": "arquivo_pt",
    # Usenet is its own lineage: the archive is a Giganews donation of posts,
    # entirely independent of any web crawl, so a pair it confirms alongside a
    # Wayback capture is genuine cross-lineage corroboration.
    "usenet_announce": "usenet",
    "usenet_mention": "usenet",
    # Tucows is a software catalogue, independent of both web crawls and Usenet
    "tucows_catalogue": "software_catalogue",
    "tucows_mention": "software_catalogue",
    # Scanned trade press. Its own lineage: the observation is a printed page in a
    # magazine, which is independent of every crawl, of Usenet and of the software
    # catalogue. Filing it anywhere else would understate genuine cross-lineage
    # corroboration, and giving it no entry at all would silently make it its own
    # family anyway, which is the failure this table exists to prevent.
    "trade_press": "trade_press",
    "trade_press_mention": "trade_press",
    # UUCP maps are a registry dump that happened to travel over Usenet. The
    # lineage is the registry, not the newsgroup: filing them under `usenet` would
    # let a Usenet announcement and a registry record for the same pair look like
    # one body of observation, and filing them as their own family would let them
    # corroborate AFNIC as if independently collected. They are registry data.
    # A defacement mirror is its own body of observation: neither a web crawl, nor
    # Usenet, nor a registry. Its operators saw the host serving because they broke
    # into it or watched someone else do so, which is independent of every other
    # source here, so a pair it confirms alongside a capture is genuine
    # cross-lineage corroboration.
    "attrition_defacement": "defacement_mirror",
    "uucp_map_registry": "registry",
    "uucp_map_creation": "registry",
    "uucp_map_mention": "registry",
    # A domain-dispute docket is its own body of observation too: the arbitration
    # provider knows the name was registered because a complaint was filed against
    # it and the registrar confirmed the registration. That is neither a crawl, nor
    # Usenet, nor the registry's own published data, so a pair UDRP confirms
    # alongside an RDAP creation date is genuine cross-lineage corroboration rather
    # than one organisation agreeing with itself.
    "udrp_proceedings": "dispute_docket",
    # rtfm FAQs travelled over Usenet and are the same body of observation, so
    # they share its lineage: a FAQ and an announcement post confirming the same
    # pair is one source of evidence, not two.
    "rtfm_faq": "usenet",
    "rtfm_faq_mention": "usenet",
    # Addresses recovered from the same Usenet messages. Same body of
    # observation, so the same lineage: an announcement post and a body address
    # in that post confirming one pair is one observation, not two.
    "usenet_address": "usenet",
    "usenet_address_mention": "usenet",
    # Bare hosts in the body of the same posts. Same messages again, so the same
    # lineage: three readings of one artifact are one observation, not three.
    "usenet_bare": "usenet",
    "usenet_bare_mention": "usenet",
    # Corporate email is its own body of observation, independent of every crawl,
    # of Usenet and of the registries.
    "enron_email": "corporate_email",
    "enron_email_mention": "corporate_email",
    # Public pipermail list archives. Its own family, and the claim is only safe
    # because the collector skips the newsgroup-gatewayed lists: a gatewayed list
    # carries the same messages the Usenet corpus already holds, so counting it
    # here would make one body of observation look like two lineages.
    "maillist_archive": "mailing_list",
    "maillist_archive_mention": "mailing_list",
    "odp": "editorial_directory",
    "internet_scout": "editorial_directory",
    "ncsa_whats_new": "editorial_directory",
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
        **_equivalent_english(conn),
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


def _equivalent_english(conn: duckdb.DuckDBPyConnection) -> dict:
    """The reviewer's metric, which is the one the round is actually scored on.

    Every figure here is a count somewhere else in this scoreboard re-weighted by
    the English page-language share of each domain's right-most TLD, so 10,000 `.de`
    pairs are worth less than 1,500 `.uk` ones and a pair count no longer says what
    a tranche is worth. Growth is quoted against the reviewer's merged baseline the
    way he computes it: increment divided by the PRE-increment total.

    The candidate figure is deliberately labelled an upper bound. It assumes every
    held name is real and earns exactly one year, and a large share of the pool is
    neither: Usenet posters munged their addresses against harvesters, so it carries
    names like `mqegamrfaj.mil` and `nospam@...` that no capture will ever confirm.
    """
    weights = english_weights()

    def weigh(rows: list[tuple[str, int]]) -> Decimal:
        return sum((weights.get(tld, Decimal(0)) * n for tld, n in rows), Decimal(0))

    netnew = conn.execute(
        f"""
        SELECT split_part(dy.domain, '.', -1) AS tld, count(*) FROM domain_year dy
        WHERE NOT EXISTS (
            SELECT 1 FROM evidence e WHERE e.domain = dy.domain
              AND e.evidence_year = dy.assigned_year AND e.evidence_type = '{BASELINE_TYPE}')
        GROUP BY 1
        """
    ).fetchall()
    assigned = conn.execute(
        "SELECT split_part(domain, '.', -1) AS tld, count(*) FROM domain_year GROUP BY 1"
    ).fetchall()
    candidates = conn.execute(
        """
        SELECT split_part(d.domain, '.', -1) AS tld, count(*) FROM domain d
        WHERE NOT EXISTS (SELECT 1 FROM domain_year dy WHERE dy.domain = d.domain)
        GROUP BY 1
        """
    ).fetchall()

    # The reviewer's priority (d): a genuinely unknown domain and a filled year on
    # a domain he already has are different results, and he asked for both to stay
    # visible. `has_baseline` is per DOMAIN, not per pair, so the two branches
    # partition the net-new pairs exactly and neither can be read off the other.
    # Counting distinct domains over net-new pairs instead once reported 1,161,961
    # domains against a true 463,566.
    split = conn.execute(
        f"""
        WITH nn AS (
            SELECT dy.domain, dy.assigned_year,
                   EXISTS (SELECT 1 FROM evidence b
                           WHERE b.domain = dy.domain
                             AND b.evidence_type = '{BASELINE_TYPE}') AS known
            FROM domain_year dy
            WHERE NOT EXISTS (
                SELECT 1 FROM evidence e WHERE e.domain = dy.domain
                  AND e.evidence_year = dy.assigned_year
                  AND e.evidence_type = '{BASELINE_TYPE}')
        )
        SELECT split_part(domain, '.', -1) AS tld, known, count(*)
        FROM nn GROUP BY 1, 2
        """
    ).fetchall()
    discovery = [(tld, n) for tld, known, n in split if not known]
    completeness = [(tld, n) for tld, known, n in split if known]
    # Breadth in the scored unit: one count per newly discovered domain rather
    # than one per pair, so a domain found in four years is one discovery.
    netnew_domain_tlds = conn.execute(
        f"""
        SELECT split_part(dy.domain, '.', -1) AS tld, count(DISTINCT dy.domain)
        FROM domain_year dy
        WHERE NOT EXISTS (
            SELECT 1 FROM evidence e WHERE e.domain = dy.domain
              AND e.evidence_type = '{BASELINE_TYPE}')
        GROUP BY 1
        """
    ).fetchall()

    netnew_ee, netnew_n = weigh(netnew), sum(n for _, n in netnew)
    return {
        "ee_netnew": netnew_ee,
        "ee_netnew_pairs": netnew_n,
        "ee_netnew_mean_weight": netnew_ee / netnew_n if netnew_n else Decimal(0),
        "ee_netnew_growth_pct": netnew_ee / REVIEWER_BASELINE_EE * 100,
        "ee_assigned": weigh(assigned),
        "ee_candidate_upper_bound": weigh(candidates),
        "ee_discovery_pairs": weigh(discovery),
        "discovery_pairs": sum(n for _, n in discovery),
        "ee_completeness_pairs": weigh(completeness),
        "completeness_pairs": sum(n for _, n in completeness),
        "ee_netnew_domains": weigh(netnew_domain_tlds),
    }


def format_stats(stats: dict) -> str:
    lines = [
        "== scoreboard ==",
        f"net-new domains (not in baseline):  {stats['netnew_domains']:>12,}",
        f"net-new (domain, year) pairs:       {stats['netnew_pairs_total']:>12,}",
        f"net-new equivalent-English:         {stats['ee_netnew']:>16,.4f}",
        f"    mean weight per pair:           {stats['ee_netnew_mean_weight']:>16.4f}",
        f"    growth on the {REVIEWER_BASELINE_EE:,.4f} baseline: "
        f"{stats['ee_netnew_growth_pct']:.4f}%",
        f"    (measured against {CURRENT_BASELINE_MARKER}, so this is the uncredited",
        "     increment: everything the reviewer has already merged is excluded)",
    ]
    for year, count in stats["netnew_pairs_by_year"].items():
        lines.append(f"    {year}: {count:,}")
    lines += [
        "== the two outcomes, counted separately ==",
        "  discovery: domains the baseline holds in no year",
        f"    domains:                          {stats['netnew_domains']:>12,}",
        f"    equivalent-English, one per domain:{stats['ee_netnew_domains']:>15,.4f}",
        f"    pairs they carry:                 {stats['discovery_pairs']:>12,}",
        f"    equivalent-English of those pairs: {stats['ee_discovery_pairs']:>15,.4f}",
        "  completeness: years filled on domains the baseline already holds",
        f"    pairs:                            {stats['completeness_pairs']:>12,}",
        f"    equivalent-English:               {stats['ee_completeness_pairs']:>15,.4f}",
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
        f"equivalent-English, all assigned:   {stats['ee_assigned']:>16,.4f}",
        f"candidate pool (unverified):        {stats['candidate_pool']:>12,}",
        f"    equivalent-English if every one earned a year, an UPPER BOUND: "
        f"{stats['ee_candidate_upper_bound']:,.0f}",
        "    (the pool is mostly Usenet names no other source attests, including",
        "     addresses munged against harvesters, so the realised figure is far lower)",
    ]
    return "\n".join(lines)
