"""Legacy ingest: canonicalization, dedup, provenance rows, idempotent re-run."""

from pathlib import Path

import duckdb

from ark.db import connect, init_db
from ark.ingest import YEARS, ingest_legacy, ingest_year_file

FIXTURE_LINES = [
    "example.com",
    "www.example.com",
    "EXAMPLE.COM",
    "$garbage$",
    "",
    "other.org",
]


def _fresh_db() -> duckdb.DuckDBPyConnection:
    conn = connect(":memory:")
    init_db(conn)
    return conn


def _write_fixture(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_ingest_year_file_counts_and_rows(tmp_path: Path) -> None:
    conn = _fresh_db()
    fixture = tmp_path / "1996.txt"
    _write_fixture(fixture, FIXTURE_LINES)
    report = tmp_path / "mismatches.txt"

    stats = ingest_year_file(conn, fixture, 1996, report_path=report)

    assert stats["lines"] == 6
    assert stats["ok"] == 4
    # www./uppercase variants both canonicalize to example.com
    assert stats["changed"] == 2
    assert stats["rejected"] == 1
    assert stats["blank"] == 1
    assert stats["unique_domains"] == 2
    assert stats["year_rows"] == 2

    domains = {row[0] for row in conn.execute("SELECT domain FROM domain").fetchall()}
    assert domains == {"example.com", "other.org"}
    # every baseline year row points at prior_reused evidence
    linked = conn.execute(
        "SELECT count(*) FROM domain_year dy JOIN evidence e ON dy.evidence_id = e.evidence_id "
        "WHERE e.evidence_type = 'prior_reused'"
    ).fetchone()[0]
    assert linked == 2
    report_text = report.read_text(encoding="utf-8")
    assert "$garbage$" in report_text
    assert "www.example.com -> example.com" in report_text


def test_ingest_year_file_is_idempotent(tmp_path: Path) -> None:
    conn = _fresh_db()
    fixture = tmp_path / "1997.txt"
    _write_fixture(fixture, ["example.com"])
    report = tmp_path / "mismatches.txt"

    first = ingest_year_file(conn, fixture, 1997, report_path=report)
    second = ingest_year_file(conn, fixture, 1997, report_path=report)

    assert first["skipped"] is False
    assert second["skipped"] is True
    assert conn.execute("SELECT count(*) FROM domain_year").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM evidence").fetchone()[0] == 1


def test_ingest_legacy_all_years(tmp_path: Path) -> None:
    conn = _fresh_db()
    for year in YEARS:
        _write_fixture(tmp_path / f"{year}.txt", [f"site-{year}.com", "shared.org"])
    (tmp_path / "merge_stats_new0714.csv").write_text(
        "year,base_unique\n1996,2\n", encoding="utf-8"
    )

    all_stats = ingest_legacy(conn, tmp_path, report_path=tmp_path / "mismatches.txt")

    assert len(all_stats) == 6
    years = conn.execute("SELECT DISTINCT assigned_year FROM domain_year ORDER BY 1").fetchall()
    assert [row[0] for row in years] == list(YEARS)
    # shared.org is one domain with six year rows, one per file
    shared_years = conn.execute(
        "SELECT count(*) FROM domain_year WHERE domain = 'shared.org'"
    ).fetchone()[0]
    assert shared_years == 6
    assert conn.execute("SELECT count(*) FROM prior_merge_stats").fetchone()[0] == 1
