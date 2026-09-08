"""ISC candidates are exact names, disjoint from every annual year and reviewer candidates."""

import csv
import json
from decimal import Decimal
from pathlib import Path

import pytest

from ark import export
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.english_share import weight_of
from ark.ingest import YEARS


@pytest.fixture
def collection(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    for year in YEARS:
        (baseline / f"{year}.txt").write_text("", encoding="utf-8")
    (baseline / "2001.txt").write_text("  ANNUAL.example.com  \nexample.com\n", encoding="utf-8")
    (baseline / "candidate_pool.txt").write_text(
        " POOL.example.com \npool.example.com\nwww.alias.example.com\n", encoding="utf-8"
    )
    monkeypatch.setattr(export, "baseline_dir", lambda: baseline)
    conn = connect(":memory:")
    init_db(conn)
    source = ensure_source(conn, export.ISC_SOURCE, "timestamped")
    web = ensure_source(conn, "web", "timestamped")
    for parent in ("example.com", "example.uk", "example.site"):
        add_candidate(conn, parent, source)
    eid = record_evidence(conn, "example.com", web, 2000, "cdx_timestamp", "20000101000000")
    assign_year(conn, eid)
    conn.execute(
        "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) "
        "VALUES ('local.example.com', 'example.com', 2000, ?)",
        [eid],
    )
    conn.execute(
        "INSERT INTO domain (domain, tld, discovered_source) VALUES ('annual.other.com', 'com', ?)",
        [web],
    )
    assign_year(
        conn,
        record_evidence(conn, "annual.other.com", web, 2001, "cdx_timestamp", "20010101000000"),
    )
    add_candidate(conn, "other.com", source)
    yield conn, source, baseline, tmp_path / "out"
    conn.close()


def observe(conn, source, hostname, year=1996, month="07", parent="example.com"):
    return record_evidence(
        conn,
        parent,
        source,
        year,
        "artifact_listing",
        f"isc survey {year}-{month} host {hostname}",
        f"http://nw.com/zone/{str(year)[2:]}{month}.hosts/com.gz",
        "isc_survey_host_listing",
    )


def write_collection(conn, out: Path):
    export.load_baseline_hostnames(conn)
    stats = {}
    export.export_isc_hostnames(conn, out, stats)
    export.export_isc_provenance(conn, out, stats)
    return stats


def test_reconciles_all_years_exact_names_and_preserves_each_observation(collection):
    conn, source, _, out = collection
    for host in (
        "keep.example.com",
        "pool.example.com",
        "annual.example.com",
        "local.example.com",
        "alias.example.com",
        "www.alias.example.com",
        "www.example.com",
        "bad_name.example.com",
        "example.com",
        "outside.other.com",
    ):
        observe(conn, source, host)
    observe(conn, source, "annual.other.com", parent="other.com")
    observe(conn, source, "keep.example.com", 1997)
    observe(conn, source, "keep.example.com", month="01")
    observe(conn, source, "keep.example.com", month="01")
    observe(conn, source, "keep.example.uk", parent="example.uk")
    observe(conn, source, "future.example.site", parent="example.site")
    stats = write_collection(conn, out)
    names = ["alias.example.com", "keep.example.com", "keep.example.uk", "www.example.com"]
    assert (out / "isc_candidates.txt").read_text().splitlines() == names
    assert (out / "1996-ISC.txt").read_text().splitlines() == names
    assert (out / "1997-ISC.txt").read_text() == "keep.example.com\n"
    assert stats["isc_candidates"] == 4
    assert stats["isc_provenance_rows"] == 6
    with (out / "isc_survey_provenance.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    assert {(r["hostname"], int(r["target_year"])) for r in rows} == {
        *((host, 1996) for host in names),
        ("keep.example.com", 1997),
    }
    assert {r["survey_edition"] for r in rows} == {"1996-01", "1996-07", "1997-07"}
    assert all(r["source_file"] == "com.gz" and all(r.values()) for r in rows)
    summary = json.loads((out / "isc_candidates_summary.json").read_text())
    assert summary["hostname_years"] == 5
    assert summary["candidates"] == 4
    assert Decimal(summary["equivalent_english"]) == sum(weight_of(h) for h in names)
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    assert write_collection(conn, out) == stats
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


@pytest.mark.parametrize("missing", ["candidate_pool.txt", "1998.txt"])
def test_missing_reviewer_input_refuses_candidate_claim(collection, missing):
    conn, source, baseline, out = collection
    observe(conn, source, "keep.example.com")
    (baseline / missing).unlink()
    with pytest.raises(FileNotFoundError, match="requires current baseline"):
        write_collection(conn, out)


@pytest.mark.parametrize("field", ["evidence_url", "acquisition_method", "evidence_value"])
def test_missing_required_provenance_refuses_export(collection, field):
    conn, source, _, out = collection
    eid = observe(conn, source, "keep.example.com")
    value = "host keep.example.com" if field == "evidence_value" else ""
    conn.execute(f"UPDATE evidence SET {field} = ? WHERE evidence_id = ?", [value, eid])
    with pytest.raises(ValueError, match="incomplete provenance"):
        write_collection(conn, out)
    assert not (out / "isc_candidates_summary.json").exists()


def test_empty_collection_has_header_and_zero_summary(collection):
    conn, _, _, out = collection
    stats = write_collection(conn, out)
    assert stats["isc_candidates"] == stats["isc_provenance_rows"] == 0
    summary = json.loads((out / "isc_candidates_summary.json").read_text())
    assert summary["equivalent_english"] == "0.0000"


def test_isc_export_does_not_change_annual_outputs_or_assignments(collection):
    conn, source, _, out = collection

    def write_all():
        export.export_all(
            conn,
            netnew_dir=out,
            candidates_path=out / "candidates.txt",
            masters_dir=out / "masters",
            report_dir=out / "reports",
            provenance_dir=out / "provenance",
        )
        paths = [out / f"{y}{suffix}.txt" for y in YEARS for suffix in ("", "_hostnames")]
        paths += list((out / "masters").glob("*.txt"))
        paths += [out / "evidence_manifest.csv", out / "hostnames_evidence_manifest.csv"]
        return {p: p.read_bytes() for p in paths}

    before = write_all()
    annual_query = (
        "SELECT * REPLACE (verified_at::VARCHAR AS verified_at) FROM domain_year ORDER BY ALL"
    )
    host_query = (
        "SELECT * REPLACE (verified_at::VARCHAR AS verified_at) FROM hostname_year ORDER BY ALL"
    )
    annual = conn.execute(annual_query).fetchall()
    hostname = conn.execute(host_query).fetchall()
    observe(conn, source, "keep.example.com")
    assert write_all() == before
    assert conn.execute(annual_query).fetchall() == annual
    assert conn.execute(host_query).fetchall() == hostname
