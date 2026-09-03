"""The reviewer's per-item "extraction method" is `evidence.acquisition_method`.

The column is nullable in the schema, so nothing structural forces it. What
forces it is that both production writers stamp it unconditionally: the
baseline loader with `prior_task`, the bulk loader with whatever the source's
`SourceSpec` declares. These tests drive both writers into a temp store, run the
export, and read the shipped files back, so a writer that stops stamping the
method is caught here rather than by the reviewer.
"""

import duckdb
from typer.testing import CliRunner

from ark.cli import app
from ark.export import NETNEW_DIR
from ark.ingest import YEARS
from ark.provenance import PROVENANCE_DIR
from ark.sources import SOURCES

runner = CliRunner()

CDX_LINE = "com,example)/ 19970601120000 http://example.com:80/ text/html 200 B - - 9 f.arc.gz\n"


def test_every_registered_source_declares_an_extraction_method() -> None:
    missing = [key for key, spec in SOURCES.items() if not spec.acquisition_method]
    assert missing == []


def test_every_exported_evidence_row_names_its_extraction_method(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    for year in YEARS:
        (legacy / f"{year}.txt").write_text("base.org\n", encoding="utf-8")
    cdx = tmp_path / "sample.cdx"
    cdx.write_text(CDX_LINE, encoding="utf-8")

    assert runner.invoke(app, ["init"]).exit_code == 0
    legacy_run = runner.invoke(app, ["ingest-legacy", "--legacy-dir", str(legacy)])
    assert legacy_run.exit_code == 0, legacy_run.output
    bulk_run = runner.invoke(app, ["ingest", "early_web", str(cdx)])
    assert bulk_run.exit_code == 0, bulk_run.output
    assert runner.invoke(app, ["export"]).exit_code == 0

    reader = duckdb.connect(":memory:")
    parquet = PROVENANCE_DIR / "evidence.parquet"
    total, blank, methods = reader.execute(
        "SELECT count(*), "
        "count(*) FILTER (WHERE acquisition_method IS NULL OR acquisition_method = ''), "
        "count(DISTINCT acquisition_method) FROM read_parquet(?)",
        [str(parquet)],
    ).fetchone()
    # seven rows: six baseline years and one capture, from the two writers
    assert total == 7
    assert blank == 0
    assert methods == 2

    manifest = NETNEW_DIR / "evidence_manifest.csv"
    rows = reader.execute(
        "SELECT acquisition_method FROM read_csv_auto(?, header = true)", [str(manifest)]
    ).fetchall()
    assert rows == [("bulk_cdx_file",)]
    reader.close()
