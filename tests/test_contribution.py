"""Contribution tables: the net-new pair and domain tests must stay distinct."""

import csv
from pathlib import Path

import duckdb
from his_release import WEB_METHOD, capture, stage, text

from ark import held
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.export import export_all
from ark.stats import collect_stats


def _store() -> duckdb.DuckDBPyConnection:
    conn = connect(":memory:")
    init_db(conn)
    return conn


def _release(tmp_path: Path, files: dict[str, bytes] | None = None) -> Path:
    folder = stage(tmp_path / "release", files)
    held.prepare(folder)
    return folder


def _write(conn: duckdb.DuckDBPyConnection, tmp_path: Path, baseline: Path) -> Path:
    """The tables as the export writes them: it builds the sets they read first."""
    reports = tmp_path / "reports"
    export_all(
        conn,
        netnew_dir=tmp_path / "netnew",
        candidates_path=tmp_path / "candidates.txt",
        report_dir=reports,
        provenance_dir=tmp_path / "provenance",
        baseline=baseline,
    )
    return reports


def _rows(path):
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _web(conn, domain: str, source: int, year: int, kind: str = "cdx_timestamp") -> int:
    """A capture of exactly `domain`, which the claim accepts."""
    value = capture(domain, year)
    return record_evidence(conn, domain, source, year, kind, value, acquisition_method=WEB_METHOD)


def test_a_gap_filling_source_shows_new_pairs_but_no_new_domains(tmp_path) -> None:
    conn = _store()
    prior = ensure_source(conn, "prior_task", "timestamped")
    cdx = ensure_source(conn, "ia_cdx_bulk", "timestamped")
    # his file already holds this domain, for 1997 only
    baseline = _release(tmp_path, {"1997.txt": text(["already-his.com", "known.com"])})
    add_candidate(conn, "known.com", prior)
    assign_year(conn, record_evidence(conn, "known.com", prior, 1997, "prior_reused", "1997.txt"))
    # the archive then evidences 1999, which is a new PAIR on a known DOMAIN
    assign_year(conn, _web(conn, "known.com", cdx, 1999))

    reports = _write(conn, tmp_path, baseline)
    by_source = {r["source"]: r for r in _rows(reports / "source_contribution.csv")}

    # conflating the two tests would zero this column and hide the whole
    # contribution of every gap-filling source
    assert by_source["ia_cdx_bulk"]["netnew_pairs"] == "1"
    assert by_source["ia_cdx_bulk"]["netnew_domains"] == "0"
    # his rows are not ours to report
    assert by_source["prior_task"]["evidence_rows"] == "0"
    assert by_source["prior_task"]["pairs_backed"] == "0"
    conn.close()


def test_a_brand_new_domain_counts_in_both_columns(tmp_path) -> None:
    conn = _store()
    isc = ensure_source(conn, "isc_survey", "timestamped")
    add_candidate(conn, "fresh.org", isc)
    assign_year(conn, _web(conn, "fresh.org", isc, 1996, "artifact_listing"))

    reports = _write(conn, tmp_path, _release(tmp_path))
    row = {r["source"]: r for r in _rows(reports / "source_contribution.csv")}["isc_survey"]
    assert row["netnew_pairs"] == "1" and row["netnew_domains"] == "1"
    conn.close()


def test_netnew_pairs_reconciles_with_the_scoreboard(tmp_path) -> None:
    conn = _store()
    prior = ensure_source(conn, "prior_task", "timestamped")
    isc = ensure_source(conn, "isc_survey", "timestamped")
    cdx = ensure_source(conn, "ia_cdx_bulk", "timestamped")
    baseline = _release(tmp_path, {"1997.txt": text(["already-his.com", "known.com"])})
    add_candidate(conn, "known.com", prior)
    assign_year(conn, record_evidence(conn, "known.com", prior, 1997, "prior_reused", "1997.txt"))
    assign_year(conn, _web(conn, "known.com", cdx, 1999))
    add_candidate(conn, "fresh.org", isc)
    assign_year(conn, _web(conn, "fresh.org", isc, 1996, "artifact_listing"))

    reports = _write(conn, tmp_path, baseline)
    total = sum(int(r["netnew_pairs"]) for r in _rows(reports / "source_contribution.csv"))

    # every net-new pair is attributed to exactly the source whose evidence backs it, and the
    # pairs are the lines the export wrote
    assert total == 2
    assert total == collect_stats(conn, baseline)["netnew_pairs_total"]
    conn.close()


def test_candidate_domains_are_attributed_to_their_discovering_source(tmp_path) -> None:
    conn = _store()
    targets = ensure_source(conn, "ukwa_link_target", "candidate_only")
    add_candidate(conn, "linked-only.com", targets)
    record_evidence(conn, "linked-only.com", targets, 1999, "link_target", "host_link_graph:1999")

    reports = _write(conn, tmp_path, _release(tmp_path))
    row = {r["source"]: r for r in _rows(reports / "source_contribution.csv")}["ukwa_link_target"]
    assert row["candidate_domains"] == "1"
    # candidate-only evidence backs no pair, by design
    assert row["pairs_backed"] == "0"
    conn.close()


def test_year_growth_uses_the_supplied_merge_stats_shape(tmp_path) -> None:
    """Each year from line counts: his year file, then our registrable and hostname files,
    which packaging merges into `masters/<year>.txt`."""
    conn = _store()
    prior = ensure_source(conn, "prior_task", "timestamped")
    isc = ensure_source(conn, "isc_survey", "timestamped")
    baseline = _release(tmp_path, {"1997.txt": text(["already-his.com", "base.com"])})
    add_candidate(conn, "base.com", prior)
    assign_year(conn, record_evidence(conn, "base.com", prior, 1997, "prior_reused", "1997.txt"))
    cdx = ensure_source(conn, "ia_cdx_hostnames", "timestamped")
    add_candidate(conn, "added.com", cdx)
    assign_year(conn, _web(conn, "added.com", cdx, 1997))
    shop = record_evidence(
        conn,
        "added.com",
        cdx,
        1997,
        "cdx_timestamp",
        capture("shop.added.com", 1997),
        acquisition_method=WEB_METHOD,
    )
    conn.execute(
        "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) "
        "VALUES ('shop.added.com', 'added.com', 1997, ?)",
        [shop],
    )
    # a survey listing earns no annual year under XIII, so it is in neither
    # `masters/` nor `additions/` and the table must not count it
    add_candidate(conn, "listed.com", isc)
    assign_year(conn, record_evidence(conn, "listed.com", isc, 1997, "artifact_listing", "1997-07"))

    rows = {r["year"]: r for r in _rows(_write(conn, tmp_path, baseline) / "year_growth.csv")}

    # his two lines, and our registrable and hostname line
    assert rows["1997"]["base_unique"] == "2"
    assert rows["1997"]["added_unique"] == "2"
    assert rows["1997"]["merged_unique"] == "4"
    assert rows["1997"]["growth_percent"] == "100.0"
    assert rows["1996"]["base_unique"] == str(held.load(baseline).counts["1996"])
    assert rows["1996"]["added_unique"] == "0"
    conn.close()
