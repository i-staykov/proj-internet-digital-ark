"""CLI wiring: the app and its stub commands run and exit cleanly."""

from typer.testing import CliRunner

from ark.cli import app

runner = CliRunner()


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "seed" in result.output


def test_export_stub_runs() -> None:
    result = runner.invoke(app, ["export"])
    assert result.exit_code == 0
