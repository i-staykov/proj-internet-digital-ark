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
