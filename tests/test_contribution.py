"""Contribution tables: the net-new pair and domain tests must stay distinct."""

import csv
from pathlib import Path

import pytest
from his_release import WEB_METHOD, capture, stage, text

from ark import held
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.export import export_all
from ark.stats import collect_stats


def _release(tmp_path: Path, files: dict[str, bytes] | None = None) -> Path:
    folder = stage(tmp_path / "release", files)
    held.prepare(folder)
    return folder


def _rows(conn, tmp_path: Path, baseline: Path, table: str) -> list[dict]:
    """The table as the export writes it: it builds the sets the table reads first."""
    reports = tmp_path / "reports"
    export_all(
        conn,
        netnew_dir=tmp_path / "netnew",
        candidates_path=tmp_path / "candidates.txt",
        report_dir=reports,
        provenance_dir=tmp_path / "provenance",
        baseline=baseline,
    )
    with (reports / table).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _web(conn, domain: str, source: int, year: int, kind: str, host: str = "") -> int:
    """A capture of exactly `host` (default `domain`), which the claim accepts."""
    value = capture(host or domain, year)
    return record_evidence(conn, domain, source, year, kind, value, acquisition_method=WEB_METHOD)


def _store(tmp_path: Path):
    """His 1997 file holds known.com; we add its 1999 pair, a new domain and a candidate."""
    conn = connect(":memory:")
    init_db(conn)
    baseline = _release(tmp_path, {"1997.txt": text(["already-his.com", "known.com"])})
    cdx = ensure_source(conn, "ia_cdx_bulk", "timestamped")
    isc = ensure_source(conn, "isc_survey", "timestamped")
    targets = ensure_source(conn, "ukwa_link_target", "candidate_only")
    for domain, source, year, kind in (
        ("known.com", cdx, 1999, "cdx_timestamp"),
        ("fresh.org", isc, 1996, "artifact_listing"),
    ):
        add_candidate(conn, domain, source)
        assign_year(conn, _web(conn, domain, source, year, kind))
    add_candidate(conn, "linked-only.com", targets)
    record_evidence(conn, "linked-only.com", targets, 1999, "link_target", "host_link_graph:1999")
    return conn, baseline


# conflating the pair and domain tests would zero netnew_pairs for every gap-filling source,
# and candidate-only evidence backs no pair, by design
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("ia_cdx_bulk", {"netnew_pairs": "1", "netnew_domains": "0"}),
        ("isc_survey", {"netnew_pairs": "1", "netnew_domains": "1"}),
        ("ukwa_link_target", {"candidate_domains": "1", "pairs_backed": "0"}),
    ],
    ids=["ia_cdx_bulk_gap_filling", "isc_survey_brand_new", "ukwa_link_target_candidate"],
)
def test_source_contribution_columns(tmp_path, source, expected) -> None:
    conn, baseline = _store(tmp_path)
    row = {r["source"]: r for r in _rows(conn, tmp_path, baseline, "source_contribution.csv")}
    assert {key: row[source][key] for key in expected} == expected


def test_netnew_pairs_reconciles_with_the_scoreboard(tmp_path) -> None:
    conn, baseline = _store(tmp_path)
    rows = _rows(conn, tmp_path, baseline, "source_contribution.csv")
    total = sum(int(r["netnew_pairs"]) for r in rows)
    assert total == 2 == collect_stats(conn, baseline)["netnew_pairs_total"]


def test_year_growth_uses_the_supplied_merge_stats_shape(tmp_path) -> None:
    """His year file, then our registrable and hostname lines, merged into `masters/`."""
    conn = connect(":memory:")
    init_db(conn)
    baseline = _release(tmp_path, {"1997.txt": text(["already-his.com", "base.com"])})
    cdx = ensure_source(conn, "ia_cdx_hostnames", "timestamped")
    add_candidate(conn, "added.com", cdx)
    assign_year(conn, _web(conn, "added.com", cdx, 1997, "cdx_timestamp"))
    conn.execute(
        "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) "
        "VALUES ('shop.added.com', 'added.com', 1997, ?)",
        [_web(conn, "added.com", cdx, 1997, "cdx_timestamp", "shop.added.com")],
    )
    # a survey listing earns no annual year under XIII, so the table must not count it
    isc = ensure_source(conn, "isc_survey", "timestamped")
    add_candidate(conn, "listed.com", isc)
    assign_year(conn, record_evidence(conn, "listed.com", isc, 1997, "artifact_listing", "1997-07"))

    rows = {r["year"]: r for r in _rows(conn, tmp_path, baseline, "year_growth.csv")}
    want = dict(base_unique="2", added_unique="2", merged_unique="4", growth_percent="100.0")
    assert rows["1997"] == rows["1997"] | want
    assert rows["1996"]["base_unique"] == str(held.load(baseline).counts["1996"])
    assert rows["1996"]["added_unique"] == "0"
