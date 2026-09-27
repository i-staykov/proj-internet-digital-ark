"""The scoreboard: what we add to his files, and how well our rows attest it.

A pair is net-new when it ships and his file for its year lacks the exact name; a domain is
net-new when it has a net-new pair and his files hold it in no year. `held` diffs both by
`comm`, as `ark export` does, so the net-new pairs are the lines of `output/netnew/<year>.txt`.
Only our rows count: one of his rows in the store holds nothing and corroborates nothing.

Corroboration is reported at two strengths. Cross-SOURCE counts distinct source rows and is
the weaker figure, because several sources share one collector. Cross-PROVENANCE counts
distinct collection LINEAGES, so a DNS survey agreeing with a registry file is genuine
independent confirmation: that is the figure worth quoting, and it is much smaller.
Candidate-only evidence proves nothing and is excluded from both.
"""

import tempfile
from decimal import Decimal
from pathlib import Path

import duckdb

from ark import db, held
from ark.baseline import REVIEWER_BASELINE_EE
from ark.delegation import shipping_filter
from ark.english_share import english_weights
from ark.evidence_types import HIS_TYPE, MASTER_TYPES

# The scoreboard counts what ships, not what the store holds: `ark export` drops `.arpa`
# names and pairs dated before their TLD was delegated, 866 pairs (479.4256 EE) that no
# round can be credited for.
_SHIPPED = shipping_filter("dy.")
_SHIPPED_CANDIDATE = shipping_filter("d.", with_year=False)

# Growth is the increment over the reviewer's PRE-increment total, his convention. Which
# release that is lives in `ark.baseline`, so this and the release `held` diffs against
# cannot drift. Never subtract an already-credited constant here: diffing against his
# merged release makes net-new right by construction, and a constant needing a hand edit
# when he merges fails silently, in our favour.

# Which body of observation each source derives from. Sources sharing a lineage cannot
# confirm one another however many rows they carry, so filing a source in an existing
# family costs a corroboration statistic and is the conservative trade. A source absent
# from this map is treated as its own lineage, which is conservative for anything new.
PROVENANCE_LINEAGE = {
    "prior_task": "internet_archive",
    "early_web_cdx": "internet_archive",
    "arquivo_ia": "internet_archive",
    "ia_cdx": "internet_archive",
    "ia_cdx_bulk": "internet_archive",
    "nypw_firstcdx": "internet_archive",
    "nypw_timemaps": "internet_archive",
    "nypw_timemaps_nonok": "internet_archive",
    "dartmouth_bfs_seed": "internet_archive",
    "dartmouth_nber_captures": "internet_archive",
    "page_expansion": "internet_archive",
    "page_directory": "internet_archive",
    "isc_survey": "dns_survey",
    "isc_survey_hostnames": "dns_survey",
    "afnic_fr": "registry",
    "domain_creation_bulk": "registry",
    "internic_zone": "registry",
    "internic_zone_hostnames": "registry",
    "internic_zone_hostnames_1999": "registry",
    "ripe_nserver_hostnames": "registry",
    "ia_cdx_hostnames": "internet_archive",
    "arquivo_ia_hostnames": "arquivo_pt",
    "early_web_cdx_hostnames": "internet_archive",
    "usfedgov_extract_hostnames": "internet_archive",
    "poland_pl_extract_hostnames": "internet_archive",
    "iedr_register": "registry",
    "us_domain_delegated": "registry",
    "ripe_dbase_1999": "registry",
    "ripe_dbase_changed": "registry",
    "ripe_dbase_split_2004": "registry",
    "namewinner_expiring": "registry",
    # A BROKER, deliberately not the `registry` family `namewinner_expiring` sits in: a
    # registrar is the operator of record, a marketplace knows a name only because its
    # owner submitted it for sale, so a broker listing and a zone file are two witnesses.
    "urlmerchant_inventory": "broker_inventory",
    "urlmerchant_inventory_mention": "broker_inventory",
    "can_domain_registry_notices": "registry",
    "cctld_register_listing_inbody": "registry",
    # A person transcribed registry whois records: the field read is the registry's.
    "early_bulk_whois_snapshot": "registry",
    "junkfilter_dated_blocklist": "blocklist",
    "junkfilter_mention": "blocklist",
    "chastity_list_blacklist": "blocklist",
    "chastity_list_hostnames": "blocklist",
    "chastity_list_mention": "blocklist",
    # A free-DNS operator reading out its own BIND config. The capture only fixes when
    # the file existed, it did not produce the names.
    "granitecanyon_zone_rejects": "hosted_dns",
    "granitecanyon_zone_mention": "hosted_dns",
    "cctld_register_listing_capture": "registry",
    "cctld_register_listing_mention": "registry",
    "mynic_my_change_report": "registry",
    "coza_deletion_listing": "registry",
    "fac_single_audit": "federal_filing",
    "fac_single_audit_mention": "federal_filing",
    # This robot did its own fetching in 2001 and owes the archive nothing, so `crawl`
    # rather than `internet_archive`.
    "squidguard_2001_blacklist": "crawl",
    "squidguard_2001_hostnames": "crawl",
    "jpnic_register": "registry",
    "rdap": "registry",
    "rdap_snapshot": "registry",
    "ukwa_link_source": "uk_web_archive",
    "ukwa_geoindex": "uk_web_archive",
    "ukwa_link_target": "uk_web_archive",
    "ukwa_link_target_bare": "uk_web_archive",
    "arquivo_roteiro": "arquivo_pt",
    "usenet_announce": "usenet",
    "usenet_mention": "usenet",
    "tucows_catalogue": "software_catalogue",
    "tucows_mention": "software_catalogue",
    "trade_press": "trade_press",
    "trade_press_mention": "trade_press",
    "attrition_defacement": "defacement_mirror",
    # A registry dump that happened to travel over Usenet. Under `usenet` a Usenet
    # announcement and a registry record would look like one observation; as its own
    # family it would corroborate AFNIC as if independently collected.
    "uucp_map_registry": "registry",
    "uucp_map_creation": "registry",
    "uucp_map_mention": "registry",
    "dk_hostmaster_dk_zonen_domains_txt_wayback_2001": "registry",
    "udrp_proceedings": "dispute_docket",
    "rtfm_faq": "usenet",
    "rtfm_faq_mention": "usenet",
    "usenet_address": "usenet",
    "usenet_address_mention": "usenet",
    "usenet_bare": "usenet",
    "usenet_bare_mention": "usenet",
    "usenet_whois_paste": "usenet",
    "usenet_whois_paste_mention": "usenet",
    "enron_email": "corporate_email",
    "enron_email_mention": "corporate_email",
    "enron_body_url_hostnames": "corporate_email",
    "jeb_bush_gubernatorial_email": "corporate_email",
    "jeb_bush_gubernatorial_email_mention": "corporate_email",
    # Safe as its own family only because the collector skips newsgroup-gatewayed lists,
    # which carry the messages the Usenet corpus already holds.
    "maillist_archive": "mailing_list",
    "maillist_archive_mention": "mailing_list",
    "maillist_body_url_hostnames": "mailing_list",
    # Two readings of one spool, not two witnesses: hosts people TYPED into posts, and
    # the ones news servers WROTE into the same posts' headers.
    "usenet_body_url_hostnames": "usenet",
    "usenet_header_fqdn_hostnames": "usenet",
    "odp": "editorial_directory",
    "internet_scout": "editorial_directory",
    "ncsa_whats_new": "editorial_directory",
}
# only existence-proving evidence of ours corroborates an assertion
_MASTER_TYPE_LIST = ", ".join(f"'{name}'" for name in sorted(MASTER_TYPES - {HIS_TYPE}))


def collect_stats(conn: duckdb.DuckDBPyConnection, baseline: Path | None = None) -> dict:
    """The scoreboard, diffed against his release in `baseline` (his current one by default)."""
    his = held.load(baseline)
    held.our_domain_year(conn)
    held.our_domains(conn)
    held.claim_pairs(conn)
    Path(db.DB_TEMP_DIR).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=db.DB_TEMP_DIR) as tmp:
        work = Path(tmp)
        held.netnew(conn, his, work)
        held.held_any(conn, his, work)
        held.held_pairs(conn, his, work)
        _unverified(conn, his, work)

    def one(sql: str) -> int:
        return conn.execute(sql).fetchone()[0]

    pairs_by_year = dict(
        conn.execute("SELECT year, count(*) FROM netnew_pair GROUP BY 1 ORDER BY 1").fetchall()
    )
    evidence_by_type = dict(
        conn.execute(
            f"SELECT evidence_type, count(*) FROM evidence e WHERE {held.ours('e')} "
            "GROUP BY evidence_type ORDER BY count(*) DESC, evidence_type"
        ).fetchall()
    )
    return {
        **_equivalent_english(conn),
        "his_release": his.marker,
        "baseline_domains": his.counts["all"],
        "total_domains": one(f"SELECT count(*) FROM domain d WHERE {held.we_know('d')}"),
        "total_pairs": one("SELECT count(*) FROM our_domain_year"),
        "candidate_pool": one("SELECT count(*) FROM unverified"),
        # net-new domain: a net-new pair on a name his files hold in no year
        "netnew_domains": one(
            "SELECT count(DISTINCT domain) FROM netnew_pair "
            "WHERE domain NOT IN (SELECT name FROM held_any)"
        ),
        "netnew_pairs_by_year": pairs_by_year,
        "netnew_pairs_total": sum(pairs_by_year.values()),
        "evidence_rows": sum(evidence_by_type.values()),
        "evidence_rows_by_type": evidence_by_type,
        **_corroboration(conn),
        **_independent_corroboration(conn),
    }


def _unverified(conn: duckdb.DuckDBPyConnection, his: held.Held, work: Path) -> None:
    """`unverified(name)`: the names `ark export` writes to `candidate_unverified.txt`, found by
    us and dated by no pair of ours, less every name his files hold, dated or candidate."""
    found, not_candidate = work / "unverified_found.txt", work / "unverified_other.txt"
    held.dump(
        conn,
        f"""SELECT d.domain FROM domain d
            WHERE NOT EXISTS (SELECT 1 FROM our_domain_year dy WHERE dy.domain = d.domain)
              AND {held.we_know("d")} AND {_SHIPPED_CANDIDATE}
            ORDER BY 1""",
        found,
    )
    held.minus(found, his.candidates, not_candidate)
    held.minus(not_candidate, his.all, work / "unverified.txt")
    held.read_names(conn, "unverified", work / "unverified.txt")


def _corroboration(conn: duckdb.DuckDBPyConnection) -> dict:
    """Distinct master-eligible sources behind each asserted pair."""
    avg_sources, corroborated, baseline_corroborated = conn.execute(
        f"""
        WITH pair_sources AS (
            SELECT e.domain, e.evidence_year, count(DISTINCT e.source_id) AS n_sources
            FROM evidence e
            JOIN our_domain_year dy
              ON dy.domain = e.domain AND dy.assigned_year = e.evidence_year
            WHERE e.evidence_type IN ({_MASTER_TYPE_LIST})
            GROUP BY e.domain, e.evidence_year
        )
        SELECT coalesce(round(avg(n_sources), 4), 0.0),
               count(*) FILTER (WHERE n_sources >= 2),
               count(*) FILTER (WHERE h.domain IS NOT NULL AND n_sources >= 2)
        FROM pair_sources p
        LEFT JOIN held_pair h ON h.domain = p.domain AND h.year = p.evidence_year
        """
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
            SELECT e.domain, e.evidence_year, count(DISTINCT {lineage}) AS n_lineages
            FROM evidence e
            JOIN source s ON s.source_id = e.source_id
            JOIN our_domain_year dy
              ON dy.domain = e.domain AND dy.assigned_year = e.evidence_year
            WHERE e.evidence_type IN ({_MASTER_TYPE_LIST})
            GROUP BY e.domain, e.evidence_year
        )
        SELECT count(*) FILTER (WHERE n_lineages >= 2),
               count(*) FILTER (WHERE n_lineages >= 2 AND h.domain IS NULL)
        FROM pair_lineages p
        LEFT JOIN held_pair h ON h.domain = p.domain AND h.year = p.evidence_year
        """
    ).fetchone()
    by_lineage = dict(
        conn.execute(
            f"""
            SELECT {lineage} AS lineage, count(*) FROM evidence e
            JOIN source s ON s.source_id = e.source_id
            WHERE {held.ours("e")}
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
    """The reviewer's metric, the one the round is scored on.

    Each figure is a count elsewhere in this scoreboard re-weighted by the English
    page-language share of the domain's right-most TLD, so a pair count no longer says
    what a tranche is worth. The candidate figure is an UPPER BOUND: it assumes every
    candidate is real and earns exactly one year, and much of the pool is neither.
    """
    weights = english_weights()

    def weigh(rows: list[tuple[str, int]]) -> Decimal:
        return sum((weights.get(tld, Decimal(0)) * n for tld, n in rows), Decimal(0))

    # **The pairs the export writes**, or this figure describes a claim we would not send.
    # Rows the claim's screen refuses are not lost: they are candidates, counted below.
    netnew = conn.execute(
        "SELECT split_part(domain, '.', -1) AS tld, count(*) FROM netnew_pair GROUP BY 1"
    ).fetchall()
    assigned = conn.execute(
        f"""
        SELECT split_part(dy.domain, '.', -1) AS tld, count(*) FROM our_domain_year dy
        WHERE {_SHIPPED}
        GROUP BY 1
        """
    ).fetchall()
    candidates = conn.execute(
        "SELECT split_part(name, '.', -1) AS tld, count(*) FROM unverified GROUP BY 1"
    ).fetchall()

    # The reviewer's priority (d): an unknown domain and a filled year on a domain he
    # already has are different results and both stay visible. `known` is per DOMAIN, not
    # per pair, so the two branches partition the net-new pairs exactly. Counting distinct
    # domains over net-new pairs reports 1,161,961 against a true 463,566.
    split = conn.execute(
        """
        SELECT split_part(domain, '.', -1) AS tld,
               domain IN (SELECT name FROM held_any) AS known, count(*)
        FROM netnew_pair GROUP BY 1, 2
        """
    ).fetchall()
    discovery = [(tld, n) for tld, known, n in split if not known]
    completeness = [(tld, n) for tld, known, n in split if known]
    # Breadth in the scored unit: one count per newly discovered domain rather
    # than one per pair, so a domain found in four years is one discovery.
    netnew_domain_tlds = conn.execute(
        """
        SELECT split_part(domain, '.', -1) AS tld, count(DISTINCT domain) FROM netnew_pair
        WHERE domain NOT IN (SELECT name FROM held_any)
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
        f"net-new domains (not in his files): {stats['netnew_domains']:>12,}",
        f"net-new (domain, year) pairs:       {stats['netnew_pairs_total']:>12,}",
        f"net-new equivalent-English:         {stats['ee_netnew']:>16,.4f}",
        f"    mean weight per pair:           {stats['ee_netnew_mean_weight']:>16.4f}",
        f"    growth on the {REVIEWER_BASELINE_EE:,.4f} baseline: "
        f"{stats['ee_netnew_growth_pct']:.4f}%",
        f"    (measured against {stats['his_release']}, so this is the uncredited",
        "     increment: everything the reviewer has already merged is excluded)",
    ]
    for year, count in stats["netnew_pairs_by_year"].items():
        lines.append(f"    {year}: {count:,}")
    lines += [
        "== the two outcomes, counted separately ==",
        "  discovery: domains his files hold in no year",
        f"    domains:                          {stats['netnew_domains']:>12,}",
        f"    equivalent-English, one per domain:{stats['ee_netnew_domains']:>15,.4f}",
        f"    pairs they carry:                 {stats['discovery_pairs']:>12,}",
        f"    equivalent-English of those pairs: {stats['ee_discovery_pairs']:>15,.4f}",
        "  completeness: years filled on domains his files hold",
        f"    pairs:                            {stats['completeness_pairs']:>12,}",
        f"    equivalent-English:               {stats['ee_completeness_pairs']:>15,.4f}",
        "== cross-source corroboration ==",
        f"our evidence rows:                  {stats['evidence_rows']:>12,}",
        f"avg sources per assigned pair:      {stats['avg_sources_per_pair']:>12.4f}",
        f"pairs with 2+ sources:              {stats['corroborated_pairs']:>12,}",
        f"    of which his files hold:        {stats['baseline_corroborated']:>12,}",
        "== independent corroboration (2+ provenance lineages) ==",
        f"pairs confirmed independently:      {stats['independently_corroborated_pairs']:>12,}",
        f"    of which net-new:               {stats['independently_corroborated_netnew']:>12,}",
    ]
    for lineage, count in stats["evidence_rows_by_lineage"].items():
        lines.append(f"    {lineage}: {count:,}")
    lines += ["== our evidence rows by type =="]
    for etype, count in stats["evidence_rows_by_type"].items():
        lines.append(f"    {etype}: {count:,}")
    lines += [
        "== context ==",
        f"names in his files:                 {stats['baseline_domains']:>12,}",
        f"our domains:                        {stats['total_domains']:>12,}",
        f"our (domain, year) pairs:           {stats['total_pairs']:>12,}",
        f"equivalent-English, all assigned:   {stats['ee_assigned']:>16,.4f}",
        f"candidate pool (unverified):        {stats['candidate_pool']:>12,}",
        f"    equivalent-English if every one earned a year, an UPPER BOUND: "
        f"{stats['ee_candidate_upper_bound']:,.0f}",
        "    (the pool is mostly Usenet names no other source attests, including",
        "     addresses munged against harvesters, so the realised figure is far lower)",
    ]
    return "\n".join(lines)
