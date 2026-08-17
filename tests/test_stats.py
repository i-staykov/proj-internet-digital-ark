"""Scoreboard: net-new vs the baseline, and cross-source corroboration."""

import duckdb

from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.stats import collect_stats, format_stats


def _fresh_db() -> duckdb.DuckDBPyConnection:
    conn = connect(":memory:")
    init_db(conn)
    return conn


def _assign(conn, domain: str, source: int, year: int, etype: str, value: str) -> None:
    assign_year(conn, record_evidence(conn, domain, source, year, etype, value))


def _populated_db() -> duckdb.DuckDBPyConnection:
    conn = _fresh_db()
    prior = ensure_source(conn, "prior_task", "timestamped")
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    art = ensure_source(conn, "isc_survey", "timestamped")
    link = ensure_source(conn, "ukwa_link", "candidate_only")

    # baseline pair, cross-confirmed by a second master source (and a same-source
    # duplicate row that must NOT inflate the distinct-source count)
    add_candidate(conn, "base.com", prior)
    _assign(conn, "base.com", prior, 1997, "prior_reused", "1997.txt")
    record_evidence(conn, "base.com", cdx, 1997, "cdx_timestamp", "19970101000000")
    record_evidence(conn, "base.com", cdx, 1997, "cdx_timestamp", "19970202000000")
    # net-new pair, plus a candidate-only link_target row that must NOT corroborate
    add_candidate(conn, "new.com", cdx)
    _assign(conn, "new.com", cdx, 1998, "cdx_timestamp", "19980101000000")
    record_evidence(conn, "new.com", link, 1998, "link_target", "graph-row")
    # one baseline year, one net-new year on the same domain
    add_candidate(conn, "mixed.com", prior)
    _assign(conn, "mixed.com", prior, 1996, "prior_reused", "1996.txt")
    _assign(conn, "mixed.com", cdx, 1999, "cdx_timestamp", "19990101000000")
    # net-new pair cross-confirmed by two master sources (no baseline)
    add_candidate(conn, "corr.com", cdx)
    _assign(conn, "corr.com", cdx, 2000, "cdx_timestamp", "20000101000000")
    record_evidence(conn, "corr.com", art, 2000, "artifact_listing", "isc-2000")
    # unverified candidate
    add_candidate(conn, "cand.org", cdx)
    return conn


def test_collect_stats_counts() -> None:
    stats = collect_stats(_populated_db())
    assert stats["netnew_domains"] == 2
    assert stats["netnew_pairs_total"] == 3
    assert stats["netnew_pairs_by_year"] == {1998: 1, 1999: 1, 2000: 1}
    assert stats["baseline_domains"] == 2
    assert stats["total_domains"] == 5
    assert stats["total_pairs"] == 5
    assert stats["candidate_pool"] == 1


def test_two_outcomes_partition_the_netnew_total() -> None:
    """Discovery and completeness are disjoint and exhaustive over net-new pairs.

    Written because the near miss here is counting distinct domains over net-new
    pairs, which once reported 1,161,961 domains against a true 463,566: a domain
    the baseline already holds gaining a year is a new pair on an old domain.
    """
    stats = collect_stats(_populated_db())
    # new.com and corr.com carry no baseline evidence; mixed.com/1999 is a year
    # filled on a domain the baseline already holds
    assert stats["discovery_pairs"] == 2
    assert stats["completeness_pairs"] == 1
    assert stats["discovery_pairs"] + stats["completeness_pairs"] == stats["netnew_pairs_total"]
    assert stats["ee_discovery_pairs"] + stats["ee_completeness_pairs"] == stats["ee_netnew"]
    # breadth is one count per domain, so it is not the discovery pair total
    assert stats["ee_netnew_domains"] == stats["ee_discovery_pairs"]


def test_a_discovered_domain_with_two_years_is_one_discovery() -> None:
    """Breadth counts the domain once however many years it earns."""
    conn = _fresh_db()
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    add_candidate(conn, "found.com", cdx)
    _assign(conn, "found.com", cdx, 1998, "cdx_timestamp", "19980101000000")
    _assign(conn, "found.com", cdx, 1999, "cdx_timestamp", "19990101000000")

    stats = collect_stats(conn)
    assert stats["netnew_domains"] == 1
    assert stats["discovery_pairs"] == 2
    assert stats["completeness_pairs"] == 0
    # two pairs' worth of score, one domain's worth of breadth
    assert stats["ee_discovery_pairs"] == 2 * stats["ee_netnew_domains"]


def test_corroboration_counts_distinct_master_sources() -> None:
    stats = collect_stats(_populated_db())
    assert stats["evidence_rows"] == 9
    assert list(stats["evidence_rows_by_type"].items()) == [
        ("cdx_timestamp", 5),
        ("prior_reused", 2),
        ("artifact_listing", 1),
        ("link_target", 1),
    ]
    # base.com/1997 and corr.com/2000 each have two master sources; the
    # same-source duplicate and the link_target row add no source
    assert stats["avg_sources_per_pair"] == 1.4
    assert stats["corroborated_pairs"] == 2
    assert stats["baseline_corroborated"] == 1


def test_candidate_only_evidence_never_corroborates() -> None:
    conn = _fresh_db()
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    link = ensure_source(conn, "ukwa_link", "candidate_only")
    add_candidate(conn, "foo.com", cdx)
    _assign(conn, "foo.com", cdx, 1998, "cdx_timestamp", "19980101000000")
    record_evidence(conn, "foo.com", link, 1998, "link_target", "graph-row")

    stats = collect_stats(conn)
    assert stats["corroborated_pairs"] == 0
    assert stats["avg_sources_per_pair"] == 1.0


def test_same_source_rows_count_once() -> None:
    conn = _fresh_db()
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    add_candidate(conn, "foo.com", cdx)
    _assign(conn, "foo.com", cdx, 1998, "cdx_timestamp", "19980101000000")
    record_evidence(conn, "foo.com", cdx, 1998, "cdx_timestamp", "19980202000000")

    stats = collect_stats(conn)
    # two rows, one source: not corroborated
    assert stats["corroborated_pairs"] == 0
    assert stats["avg_sources_per_pair"] == 1.0


def test_netnew_pair_survives_unrelated_baseline_year() -> None:
    conn = _fresh_db()
    prior = ensure_source(conn, "prior_task", "timestamped")
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    add_candidate(conn, "foo.com", prior)
    _assign(conn, "foo.com", prior, 1996, "prior_reused", "1996.txt")
    _assign(conn, "foo.com", cdx, 1998, "cdx_timestamp", "19980101000000")

    stats = collect_stats(conn)
    # 1998 is net-new even though the domain is in the baseline for 1996
    assert stats["netnew_pairs_by_year"] == {1998: 1}
    assert stats["netnew_domains"] == 0


def test_format_stats_renders() -> None:
    out = format_stats(collect_stats(_populated_db()))
    assert "net-new domains" in out
    assert "1998: 1" in out
    assert "cross-source corroboration" in out
    assert "avg sources per assigned pair" in out


def test_independent_corroboration_ignores_same_lineage_agreement() -> None:
    conn = connect(":memory:")
    init_db(conn)
    # three Internet-Archive-derived sources: the baseline itself, an IA dataset,
    # and the IA-donated Arquivo index. Agreement among them is coverage, not
    # independent confirmation.
    ia_sources = [
        ensure_source(conn, n, "timestamped") for n in ("prior_task", "early_web_cdx", "arquivo_ia")
    ]
    add_candidate(conn, "ia-only.com", ia_sources[0])
    for sid, etype in zip(
        ia_sources, ("prior_reused", "cdx_timestamp", "cdx_timestamp"), strict=True
    ):
        assign_year(conn, record_evidence(conn, "ia-only.com", sid, 1998, etype, "19980101000000"))

    # a domain confirmed by a DNS survey and a registry file: different lineages
    isc = ensure_source(conn, "isc_survey", "timestamped")
    afnic = ensure_source(conn, "afnic_fr", "timestamped")
    add_candidate(conn, "two-lineage.fr", isc)
    assign_year(
        conn, record_evidence(conn, "two-lineage.fr", isc, 1997, "artifact_listing", "1997-07")
    )
    record_evidence(
        conn, "two-lineage.fr", afnic, 1997, "whois_creation", "registered 01-01-1997..active"
    )

    stats = collect_stats(conn)

    # three sources agree on the IA-only pair, so the weak figure counts it ...
    assert stats["corroborated_pairs"] == 2
    # ... but only the cross-lineage pair is independently confirmed
    assert stats["independently_corroborated_pairs"] == 1
    assert stats["evidence_rows_by_lineage"]["internet_archive"] == 3
    conn.close()


def test_an_unmapped_source_is_its_own_lineage() -> None:
    conn = connect(":memory:")
    init_db(conn)
    # conservative default: something newly added is not assumed to share a lineage
    a = ensure_source(conn, "brand_new_source", "timestamped")
    b = ensure_source(conn, "isc_survey", "timestamped")
    add_candidate(conn, "x.com", a)
    assign_year(conn, record_evidence(conn, "x.com", a, 1999, "cdx_timestamp", "19990101000000"))
    record_evidence(conn, "x.com", b, 1999, "artifact_listing", "1999-07")

    assert collect_stats(conn)["independently_corroborated_pairs"] == 1
    conn.close()


def test_every_source_has_an_explicit_provenance_lineage() -> None:
    """An unclassified source would silently become its own lineage.

    `_lineage_case_sql` falls through to the source name, so a new source that
    nobody classified counts as independent of everything else and inflates the
    independent-corroboration headline. NCSA arrived that way: an editorial
    directory reported as its own body of observation, corroborating ODP.
    """
    from ark.sources import SOURCES
    from ark.stats import PROVENANCE_LINEAGE

    unclassified = {
        spec.source_name for spec in SOURCES.values() if spec.source_name not in PROVENANCE_LINEAGE
    }
    assert not unclassified, f"classify these in PROVENANCE_LINEAGE: {sorted(unclassified)}"
