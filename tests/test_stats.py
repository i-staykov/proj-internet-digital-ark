"""Scoreboard: net-new against his files, and cross-source corroboration."""

import duckdb
import pytest
from his_release import HIS_YEARS, WEB_METHOD, capture, stage, text

from ark import db, held
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.stats import collect_stats, format_stats

# the names his files hold beyond the staged release's own
HIS = {1996: ["foo.com", "mixed.com"], 1997: ["base.com"]}


@pytest.fixture(autouse=True)
def his(his_files, tmp_path, monkeypatch):
    """His release with `HIS` added, prepared; scratch stays in tmp."""
    stage(his_files.parent, {f"{y}.txt": text(sorted(HIS_YEARS[y] + n)) for y, n in HIS.items()})
    held.prepare(his_files)
    monkeypatch.setattr(db, "DB_TEMP_DIR", str(tmp_path / "duckdb_tmp"))
    return his_files


def _fresh_db() -> duckdb.DuckDBPyConnection:
    conn = connect(":memory:")
    init_db(conn)
    return conn


# The scoreboard applies the claim's screen, so an assignment in a fixture needs a web method
# and a capture of exactly its domain, or it is a candidate and counts nowhere.
WEB = WEB_METHOD


def _assign(
    conn,
    domain: str,
    source: int,
    year: int,
    etype: str,
    value: str | None = None,
    method: str = WEB,
) -> None:
    value = capture(domain, year) if value is None else value
    assign_year(
        conn, record_evidence(conn, domain, source, year, etype, value, acquisition_method=method)
    )


def _populated_db() -> duckdb.DuckDBPyConnection:
    conn = _fresh_db()
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    art = ensure_source(conn, "isc_survey", "timestamped")
    link = ensure_source(conn, "ukwa_link", "candidate_only")

    # a pair his 1997 file holds, cross-confirmed by two sources of ours (and a same-source
    # duplicate row that must NOT inflate the distinct-source count)
    add_candidate(conn, "base.com", cdx)
    assign_year(
        conn, record_evidence(conn, "base.com", cdx, 1997, "cdx_timestamp", "19970101000000")
    )
    record_evidence(conn, "base.com", cdx, 1997, "cdx_timestamp", "19970202000000")
    record_evidence(conn, "base.com", art, 1997, "artifact_listing", "isc-1997")
    # net-new pair, plus a candidate-only link_target row that must NOT corroborate
    add_candidate(conn, "new.com", cdx)
    _assign(conn, "new.com", cdx, 1998, "cdx_timestamp")
    record_evidence(conn, "new.com", link, 1998, "link_target", "graph-row")
    # a net-new year on a domain his 1996 file holds
    add_candidate(conn, "mixed.com", cdx)
    _assign(conn, "mixed.com", cdx, 1999, "cdx_timestamp")
    # net-new pair cross-confirmed by two master sources
    add_candidate(conn, "corr.com", cdx)
    _assign(conn, "corr.com", cdx, 2000, "cdx_timestamp")
    record_evidence(conn, "corr.com", art, 2000, "artifact_listing", "isc-2000")
    # unverified candidate
    add_candidate(conn, "cand.org", cdx)
    return conn


def test_collect_stats_counts() -> None:
    stats = collect_stats(_populated_db())
    assert stats["netnew_domains"] == 2
    assert stats["netnew_pairs_total"] == 3
    assert stats["netnew_pairs_by_year"] == {1998: 1, 1999: 1, 2000: 1}
    # the distinct names in his six files, his hostnames among them
    assert stats["baseline_domains"] == 7
    assert stats["total_domains"] == 5
    assert stats["total_pairs"] == 4
    assert stats["candidate_pool"] == 1


def test_two_outcomes_partition_the_netnew_total() -> None:
    """Discovery and completeness are disjoint and exhaustive over net-new pairs. The near miss
    is counting distinct domains over net-new pairs, which once reported 1,161,961 domains
    against a true 463,566: a domain his files already hold gaining a year is a new pair on
    an old domain.
    """
    stats = collect_stats(_populated_db())
    # his files hold new.com and corr.com in no year; mixed.com/1999 is a year filled on a
    # domain his 1996 file holds
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
    _assign(conn, "found.com", cdx, 1998, "cdx_timestamp")
    _assign(conn, "found.com", cdx, 1999, "cdx_timestamp")

    stats = collect_stats(conn)
    assert stats["netnew_domains"] == 1
    assert stats["discovery_pairs"] == 2
    assert stats["completeness_pairs"] == 0
    # two pairs' worth of score, one domain's worth of breadth
    assert stats["ee_discovery_pairs"] == 2 * stats["ee_netnew_domains"]


def test_corroboration_counts_distinct_master_sources() -> None:
    stats = collect_stats(_populated_db())
    assert stats["evidence_rows"] == 8
    assert list(stats["evidence_rows_by_type"].items()) == [
        ("cdx_timestamp", 5),
        ("artifact_listing", 2),
        ("link_target", 1),
    ]
    # base.com/1997 and corr.com/2000 each have two master sources of ours; the
    # same-source duplicate and the link_target row add no source: 6 over 4 pairs
    assert stats["avg_sources_per_pair"] == 1.5
    assert stats["corroborated_pairs"] == 2
    # base.com/1997, which his 1997 file holds
    assert stats["baseline_corroborated"] == 1
    assert stats["independently_corroborated_netnew"] == 1


def test_candidate_only_evidence_never_corroborates() -> None:
    conn = _fresh_db()
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    link = ensure_source(conn, "ukwa_link", "candidate_only")
    add_candidate(conn, "foo.com", cdx)
    _assign(conn, "foo.com", cdx, 1998, "cdx_timestamp")
    record_evidence(conn, "foo.com", link, 1998, "link_target", "graph-row")

    stats = collect_stats(conn)
    assert stats["corroborated_pairs"] == 0
    assert stats["avg_sources_per_pair"] == 1.0


def test_same_source_rows_count_once() -> None:
    conn = _fresh_db()
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    add_candidate(conn, "foo.com", cdx)
    _assign(conn, "foo.com", cdx, 1998, "cdx_timestamp")
    record_evidence(conn, "foo.com", cdx, 1998, "cdx_timestamp", "19980202000000")

    stats = collect_stats(conn)
    # two rows, one source: not corroborated
    assert stats["corroborated_pairs"] == 0
    assert stats["avg_sources_per_pair"] == 1.0


def test_netnew_pair_survives_another_year_his_files_hold() -> None:
    conn = _fresh_db()
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    add_candidate(conn, "foo.com", cdx)
    _assign(conn, "foo.com", cdx, 1998, "cdx_timestamp")

    stats = collect_stats(conn)
    # 1998 is net-new even though his 1996 file holds the domain
    assert stats["netnew_pairs_by_year"] == {1998: 1}
    assert stats["netnew_domains"] == 0


def test_scoreboard_counts_only_what_ships() -> None:
    """The brief once quoted 866 pairs that `ark export` drops, 479.4256 EE no round could
    be credited for. The scoreboard applies the shipping filter the export applies."""
    conn = _fresh_db()
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    add_candidate(conn, "real.com", cdx)
    _assign(conn, "real.com", cdx, 1998, "cdx_timestamp")
    # .info was delegated in 2001, so a 1996 pair predates its own TLD
    add_candidate(conn, "early.info", cdx)
    _assign(conn, "early.info", cdx, 1996, "cdx_timestamp")
    # the reverse-DNS tree never ships
    add_candidate(conn, "x.arpa", cdx)
    _assign(conn, "x.arpa", cdx, 1999, "cdx_timestamp")
    # a candidate under a TLD that did not exist in the window
    add_candidate(conn, "never.sucks", cdx)
    add_candidate(conn, "maybe.org", cdx)

    stats = collect_stats(conn)
    assert stats["netnew_pairs_by_year"] == {1998: 1}
    assert stats["netnew_domains"] == 1
    assert stats["discovery_pairs"] == 1
    assert stats["ee_netnew"] == stats["ee_discovery_pairs"] == stats["ee_netnew_domains"]
    assert stats["ee_assigned"] == stats["ee_netnew"]
    assert stats["candidate_pool"] == 1
    # the store still holds every row; only the scored figures narrow
    assert stats["total_pairs"] == 3
    assert stats["total_domains"] == 5


def test_format_stats_renders() -> None:
    out = format_stats(collect_stats(_populated_db()))
    assert "net-new domains" in out
    assert "1998: 1" in out
    assert "cross-source corroboration" in out
    assert "avg sources per assigned pair" in out
    assert "names in his files" in out and "merged260922" in out


def test_independent_corroboration_ignores_same_lineage_agreement() -> None:
    conn = connect(":memory:")
    init_db(conn)
    # three Internet-Archive-derived sources: the IA index, an IA dataset, and the
    # IA-donated Arquivo index. Agreement among them is coverage, not independent
    # confirmation.
    ia_sources = [
        ensure_source(conn, n, "timestamped") for n in ("ia_cdx", "early_web_cdx", "arquivo_ia")
    ]
    add_candidate(conn, "ia-only.com", ia_sources[0])
    for sid in ia_sources:
        assign_year(
            conn, record_evidence(conn, "ia-only.com", sid, 1998, "cdx_timestamp", "19980101000000")
        )

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
    """An unclassified source would silently become its own lineage. `_lineage_case_sql` falls
    through to the source name, so a new source nobody classified counts as independent of
    everything else and inflates the independent-corroboration headline. NCSA arrived that
    way: an editorial directory reported as its own body of observation, corroborating ODP.
    """
    from ark.sources import SOURCES
    from ark.stats import PROVENANCE_LINEAGE

    unclassified = {
        spec.source_name for spec in SOURCES.values() if spec.source_name not in PROVENANCE_LINEAGE
    }
    assert not unclassified, f"classify these in PROVENANCE_LINEAGE: {sorted(unclassified)}"


def test_the_scoreboard_counts_only_what_the_export_would_ship() -> None:
    """The figure and the claim must apply the same XIII screen.

    They did not until 2026-09-18: `export.py` filtered on the acquisition method and
    `stats.py` did not, so `docs/ROUND.md` reported 251,125 net-new registrable rows for
    2001 where the export wrote 3. A page that overstates the claim is worse than no
    page: it is the number the 5% gate is judged against.
    """
    conn = _fresh_db()
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    zone = ensure_source(conn, "registry_zone", "timestamped")

    # web evidence: enters the annual claim
    add_candidate(conn, "web.com", cdx)
    _assign(conn, "web.com", cdx, 1998, "cdx_timestamp")
    # a registry zone list captured from Wayback dates a DELEGATION, not a page, and is
    # 98% of our registrable net-new by EE. It is a candidate, and must not be counted.
    add_candidate(conn, "zone.com", zone)
    _assign(
        conn,
        "zone.com",
        zone,
        1998,
        "artifact_listing",
        "zone-1998",
        method="registry_zone_list_wayback_capture",
    )

    stats = collect_stats(conn)
    assert stats["netnew_pairs_total"] == 1, "the zone row is a candidate, not an annual record"
    assert stats["netnew_pairs_by_year"] == {1998: 1}
    assert stats["netnew_domains"] == 1


def test_his_files_decide_what_he_holds() -> None:
    """Held is the exact name in his files: his `www.rolled.com` holds no `rolled.com`."""
    conn = _fresh_db()
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    # his 1999 file holds www.rolled.com
    add_candidate(conn, "rolled.com", cdx)
    _assign(conn, "rolled.com", cdx, 1999, "cdx_timestamp")
    # his 1997 file holds base.com; 1998 is a year we fill
    add_candidate(conn, "base.com", cdx)
    _assign(conn, "base.com", cdx, 1997, "cdx_timestamp")
    _assign(conn, "base.com", cdx, 1998, "cdx_timestamp")

    stats = collect_stats(conn)
    assert stats["netnew_pairs_by_year"] == {1998: 1, 1999: 1}
    assert stats["netnew_domains"] == 1
    assert stats["discovery_pairs"] == 1
    assert stats["completeness_pairs"] == 1
    assert stats["total_domains"] == 2
    assert stats["total_pairs"] == 3
    assert stats["evidence_rows"] == 3
    assert stats["candidate_pool"] == 0


def test_a_capture_of_another_host_dates_nothing() -> None:
    """A shipped pair needs a capture of exactly its domain: `www.` is another name, which his
    files are diffed by, and a capture of it beside an exact one adds nothing."""
    conn = _fresh_db()
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    add_candidate(conn, "alias.com", cdx)
    _assign(conn, "alias.com", cdx, 1998, "cdx_timestamp", capture("www.alias.com", 1998))
    add_candidate(conn, "exact.com", cdx)
    _assign(conn, "exact.com", cdx, 1998, "cdx_timestamp")
    record_evidence(
        conn,
        "exact.com",
        cdx,
        1998,
        "cdx_timestamp",
        capture("www.exact.com", 1998),
        acquisition_method=WEB,
    )

    stats = collect_stats(conn)
    assert stats["netnew_pairs_by_year"] == {1998: 1}
    assert stats["netnew_domains"] == 1
    assert stats["total_pairs"] == 2


def test_a_candidate_his_files_hold_is_not_counted() -> None:
    """The pool is what `ark export` writes to `candidate_unverified.txt`: names we found and
    could not date, less every name his files hold, dated or candidate."""
    conn = _fresh_db()
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    for name in ("maybe.org", "held-candidate.com", "already-his.com"):
        add_candidate(conn, name, cdx)

    assert collect_stats(conn)["candidate_pool"] == 1


def test_no_prepared_release_is_refused(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(held, "his_dir", lambda: tmp_path / "gone")
    with pytest.raises(held.HeldError, match="ark intake"):
        collect_stats(_fresh_db())
