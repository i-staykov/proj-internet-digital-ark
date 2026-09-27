"""The reviewer's per-item "extraction method" is `evidence.acquisition_method`.

The column is nullable, so nothing structural forces it; what forces it is that the bulk loader
stamps it unconditionally with whatever the source's `SourceSpec` declares. These tests drive it
into a temp store beside a release of his, run the export and read the shipped files back.
"""

import duckdb
from his_release import stage
from typer.testing import CliRunner

from ark import held
from ark.cli import app
from ark.export import NETNEW_DIR
from ark.provenance import PROVENANCE_DIR
from ark.sources import SOURCES

runner = CliRunner()

CDX_LINE = "com,example)/ 19970601120000 http://example.com:80/ text/html 200 B - - 9 f.arc.gz\n"


def test_every_registered_source_declares_an_extraction_method() -> None:
    missing = [key for key, spec in SOURCES.items() if not spec.acquisition_method]
    assert missing == []


def test_every_exported_evidence_row_names_its_extraction_method(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    release = stage(tmp_path / "release")
    monkeypatch.setattr(held, "his_dir", lambda: release)
    cdx = tmp_path / "sample.cdx"
    cdx.write_text(CDX_LINE, encoding="utf-8")

    assert runner.invoke(app, ["init"]).exit_code == 0
    intake_run = runner.invoke(app, ["intake", "--baseline", str(release)])
    assert intake_run.exit_code == 0, intake_run.output
    bulk_run = runner.invoke(app, ["ingest", "early_web", str(cdx)])
    assert bulk_run.exit_code == 0, bulk_run.output
    assert runner.invoke(app, ["export", "--provenance"]).exit_code == 0

    reader = duckdb.connect(":memory:")
    parquet = PROVENANCE_DIR / "evidence.parquet"
    total, blank, methods = reader.execute(
        "SELECT count(*), "
        "count(*) FILTER (WHERE acquisition_method IS NULL OR acquisition_method = ''), "
        "count(DISTINCT acquisition_method) FROM read_parquet(?)",
        [str(parquet)],
    ).fetchone()
    # every row he receives names how it was acquired
    assert total == 1
    assert blank == 0
    assert methods == 1

    stored = duckdb.connect("data/ark.duckdb", read_only=True)
    kinds = stored.execute(
        "SELECT count(*), count(*) FILTER (WHERE acquisition_method IS NULL "
        "OR acquisition_method = '') FROM evidence"
    ).fetchone()
    stored.close()
    assert kinds == (1, 0), "his release writes no row, and ours stamps the method"

    manifest = NETNEW_DIR / "evidence_manifest.csv"
    rows = reader.execute(
        "SELECT acquisition_method FROM read_csv_auto(?, header = true)", [str(manifest)]
    ).fetchall()
    assert rows == [("bulk_cdx_file",)]
    reader.close()
