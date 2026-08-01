"""CLI wiring: the app and its stub commands run and exit cleanly."""

from typer.testing import CliRunner

from ark.cli import app

runner = CliRunner()


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "seed" in result.output


def test_export_runs_after_init(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"]).exit_code == 0
    result = runner.invoke(app, ["export"])
    assert result.exit_code == 0


def test_seed_takes_positional_path(tmp_path, monkeypatch) -> None:
    # run in a temp cwd so the default data/ stores are created there, not in the repo
    monkeypatch.chdir(tmp_path)
    fixture = tmp_path / "seeds.txt"
    fixture.write_text("example.com\n", encoding="utf-8")
    assert runner.invoke(app, ["init"]).exit_code == 0
    # the natural invocation: ark seed <file>
    result = runner.invoke(app, ["seed", str(fixture), "--limit", "1"])
    assert result.exit_code == 0


def test_seed_rejects_missing_file() -> None:
    result = runner.invoke(app, ["seed", "no-such-file.txt"])
    assert result.exit_code != 0


def test_ingest_runs_on_cdx_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fixture = tmp_path / "sample.cdx"
    fixture.write_text(
        "com,example)/ 19970601120000 http://example.com:80/ text/html 200 B - - 9 f.arc.gz\n",
        encoding="utf-8",
    )
    assert runner.invoke(app, ["init"]).exit_code == 0
    result = runner.invoke(app, ["ingest", "early_web", str(fixture)])
    assert result.exit_code == 0


def test_ingest_rejects_unknown_source(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fixture = tmp_path / "sample.cdx"
    fixture.write_text("x\n", encoding="utf-8")
    result = runner.invoke(app, ["ingest", "no_such_source", str(fixture)])
    assert result.exit_code != 0


def test_rebuild_refuses_when_the_store_is_ahead_of_the_export(tmp_path, monkeypatch) -> None:
    """`ark rebuild` DROPS the store's tables before recreating them from
    Parquet. On a finished delivery that is the tier-2 reviewer path; during
    collection it silently discards everything ingested since the last export,
    and the maintenance loop keeps that window open almost all the time."""
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"]).exit_code == 0
    assert runner.invoke(app, ["export"]).exit_code == 0

    # one more ingest after the export, which is the hazard exactly
    import duckdb

    conn = duckdb.connect("data/ark.duckdb")
    conn.execute(
        "INSERT INTO ingested_file (source_name, file_name, sha256, record_rows) "
        "VALUES ('later', 'later.gz', 'abc', 1)"
    )
    conn.close()

    result = runner.invoke(app, ["rebuild", "output/provenance"])
    assert result.exit_code != 0
    assert "refusing to rebuild" in result.output


def test_rebuild_proceeds_when_the_export_is_current(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"]).exit_code == 0
    assert runner.invoke(app, ["export"]).exit_code == 0
    result = runner.invoke(app, ["rebuild", "output/provenance"])
    assert result.exit_code == 0, result.output
    assert "rebuilt from" in result.output
