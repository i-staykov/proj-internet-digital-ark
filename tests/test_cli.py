"""CLI wiring: the app and its commands run and exit cleanly, and a fleet read banks as itself."""

import gzip
import importlib.util
import json
from functools import partial
from pathlib import Path

import duckdb
import pytest
import typer
from typer.testing import CliRunner

import ark
from ark import cli
from ark.bulk import ingest_files
from ark.checks import collect_checks
from ark.cli import app
from ark.db import init_db
from ark.hostnames import fleet_read_registrables_tag

runner = CliRunner()


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "seed" in result.output
    # the console script pyproject declares: ark = "ark:main"
    assert callable(ark.main)


def test_export_runs_after_init(tmp_path, monkeypatch, his_files) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"]).exit_code == 0
    result = runner.invoke(app, ["export"])
    assert result.exit_code == 0


def test_without_held_sets_export_and_rebuild_say_to_run_intake(tmp_path, monkeypatch) -> None:
    """One line naming the step, no traceback, and a rebuild refuses before it drops a table."""
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"]).exit_code == 0
    for args in (["export"], ["stats"], ["rebuild", "output/provenance"]):
        result = runner.invoke(app, args)
        assert result.exit_code == 1, args
        assert "run uv run ark intake" in result.output
        assert isinstance(result.exception, SystemExit)


def test_seed_takes_positional_path(tmp_path, monkeypatch, his_files) -> None:
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


def test_rebuild_refuses_when_the_store_is_ahead_of_the_export(
    tmp_path, monkeypatch, his_files
) -> None:
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


def test_rebuild_proceeds_when_the_export_is_current(tmp_path, monkeypatch, his_files) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"]).exit_code == 0
    assert runner.invoke(app, ["export", "--provenance"]).exit_code == 0
    result = runner.invoke(app, ["rebuild", "output/provenance"])
    assert result.exit_code == 0, result.output
    assert "rebuilt from" in result.output


def test_a_fleet_read_banks_both_halves_under_its_own_source(tmp_path, monkeypatch) -> None:
    """`ark ingest fleet_x_hostnames` banks the converter's registrables and the parts under the
    read's own source and method, so one unbank takes the read back. Another lead's part, or a
    file of neither half, exits 2 before anything banks."""
    rows = [
        ("http://example.com/", "19990301000000", "200"),
        ("http://www.example.com/", "19990301000000", "200"),
        ("http://shop.example.org/", "20000101000000", "200"),
        ("http://gone.com/", "19980101000000", "404"),
    ]
    (read := tmp_path / "read").mkdir()
    part = read / "fleetread_bulk_cdx_file__x_0001.jsonl.gz"
    lines = (json.dumps(dict(zip(("url", "timestamp", "status"), r, strict=True))) for r in rows)
    part.write_bytes(gzip.compress("\n".join(lines).encode() + b"\n"))
    engine = Path(__file__).resolve().parents[1] / "scripts/engines/cdx_suffix_convert.py"
    spec = importlib.util.spec_from_file_location("cdx_suffix_convert", engine)
    spec.loader.exec_module(convert := importlib.util.module_from_spec(spec))
    tag = fleet_read_registrables_tag("bulk_cdx_file", "x", "ab" * 32)
    out, state = tmp_path / "cdx", tmp_path / "state.tsv"
    convert.main(
        ["--glob", f"{read}/fleetread_*", "--tag", tag, "--out", str(out), "--state", str(state)]
    )
    registrables = out / f"cdx_suffix_{tag}.jsonl.gz"
    init_db(conn := duckdb.connect())
    monkeypatch.setattr(cli, "connect_patiently", lambda **_: conn)
    monkeypatch.setattr(cli, "ingest_files", partial(ingest_files, report_dir=tmp_path))
    for source, files in (("fleet_y_hostnames", [part]), ("fleet_x_hostnames", [part, engine])):
        with pytest.raises(typer.Exit) as refused:
            cli._ingest_fleet_read(source, files)
        assert refused.value.exit_code == 2 and not conn.execute("FROM evidence").fetchall()
    cli._ingest_fleet_read("fleet_x_hostnames", [registrables, part])
    join = "evidence e JOIN source s USING (source_id)"
    by = conn.execute(f"SELECT DISTINCT s.name, e.acquisition_method FROM {join}").fetchall()
    assert by == [("fleet_x_hostnames", "bulk_cdx_file")]
    # the registrable half dates example.com on its own stamp; a host dates only itself, and the
    # 404 dates nothing
    dated = "SELECT dy.domain, assigned_year, evidence_value FROM domain_year dy JOIN evidence"
    assert conn.execute(f"{dated} USING (evidence_id)").fetchall() == [
        ("example.com", 1999, "cdx capture 19990301000000 example.com")
    ]
    assert all(r["ok"] for r in collect_checks(conn, Path("no-such-export")))
