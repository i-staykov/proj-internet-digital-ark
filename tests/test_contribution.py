"""Contribution tables: the net-new pair and domain tests must stay distinct."""

import csv

import duckdb

from ark.contribution import write_contribution_tables
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.stats import collect_stats


def _store() -> duckdb.DuckDBPyConnection:
    conn = connect(":memory:")
    init_db(conn)
    return conn


def _rows(path):
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_a_gap_filling_source_shows_new_pairs_but_no_new_domains(tmp_path) -> None:
    conn = _store()
    prior = ensure_source(conn, "prior_task", "timestamped")
    cdx = ensure_source(conn, "ia_cdx_bulk", "timestamped")
    # the baseline already knew this domain, for 1997 only
    add_candidate(conn, "known.com", prior)
    assign_year(conn, record_evidence(conn, "known.com", prior, 1997, "prior_reused", "1997.txt"))
    # the archive then evidences 1999, which is a new PAIR on a known DOMAIN
    assign_year(
        conn, record_evidence(conn, "known.com", cdx, 1999, "cdx_timestamp", "19990101000000")
    )

    write_contribution_tables(conn, tmp_path)
    by_source = {r["source"]: r for r in _rows(tmp_path / "source_contribution.csv")}

    # conflating the two tests would zero this column and hide the whole
    # contribution of every gap-filling source
    assert by_source["ia_cdx_bulk"]["netnew_pairs"] == "1"
    assert by_source["ia_cdx_bulk"]["netnew_domains"] == "0"
    conn.close()


def test_a_brand_new_domain_counts_in_both_columns(tmp_path) -> None:
    conn = _store()
    isc = ensure_source(conn, "isc_survey", "timestamped")
    add_candidate(conn, "fresh.org", isc)
    assign_year(conn, record_evidence(conn, "fresh.org", isc, 1996, "artifact_listing", "1996-07"))

    write_contribution_tables(conn, tmp_path)
    row = {r["source"]: r for r in _rows(tmp_path / "source_contribution.csv")}["isc_survey"]
    assert row["netnew_pairs"] == "1" and row["netnew_domains"] == "1"
    conn.close()


def test_netnew_pairs_reconciles_with_the_scoreboard(tmp_path) -> None:
    conn = _store()
    prior = ensure_source(conn, "prior_task", "timestamped")
    isc = ensure_source(conn, "isc_survey", "timestamped")
    cdx = ensure_source(conn, "ia_cdx_bulk", "timestamped")
    add_candidate(conn, "known.com", prior)
    assign_year(conn, record_evidence(conn, "known.com", prior, 1997, "prior_reused", "1997.txt"))
    assign_year(
        conn, record_evidence(conn, "known.com", cdx, 1999, "cdx_timestamp", "19990101000000")
    )
    add_candidate(conn, "fresh.org", isc)
    assign_year(conn, record_evidence(conn, "fresh.org", isc, 1996, "artifact_listing", "1996-07"))

    write_contribution_tables(conn, tmp_path)
    total = sum(int(r["netnew_pairs"]) for r in _rows(tmp_path / "source_contribution.csv"))

    # every net-new pair is attributed to exactly the source whose evidence backs it
    assert total == collect_stats(conn)["netnew_pairs_total"]
    conn.close()


def test_candidate_domains_are_attributed_to_their_discovering_source(tmp_path) -> None:
    conn = _store()
    targets = ensure_source(conn, "ukwa_link_target", "candidate_only")
    add_candidate(conn, "linked-only.com", targets)
    record_evidence(conn, "linked-only.com", targets, 1999, "link_target", "host_link_graph:1999")

    write_contribution_tables(conn, tmp_path)
    row = {r["source"]: r for r in _rows(tmp_path / "source_contribution.csv")}["ukwa_link_target"]
    assert row["candidate_domains"] == "1"
    # candidate-only evidence backs no pair, by design
    assert row["pairs_backed"] == "0"
    conn.close()


def test_year_growth_uses_the_supplied_merge_stats_shape(tmp_path) -> None:
    conn = _store()
    prior = ensure_source(conn, "prior_task", "timestamped")
    isc = ensure_source(conn, "isc_survey", "timestamped")
    add_candidate(conn, "base.com", prior)
    assign_year(conn, record_evidence(conn, "base.com", prior, 1997, "prior_reused", "1997.txt"))
    add_candidate(conn, "added.com", isc)
    assign_year(conn, record_evidence(conn, "added.com", isc, 1997, "artifact_listing", "1997-07"))

    write_contribution_tables(conn, tmp_path)
    rows = {r["year"]: r for r in _rows(tmp_path / "year_growth.csv")}

    assert rows["1997"]["base_unique"] == "1"
    assert rows["1997"]["added_unique"] == "1"
    assert rows["1997"]["merged_unique"] == "2"
    assert rows["1997"]["growth_percent"] == "100.0"
    conn.close()
