"""CLI wiring: the console script loads, export, stats and rebuild refuse without his held sets,
seed takes its file, rebuild refuses a store ahead of its export, a fleet read banks as itself."""

import gzip
import importlib.util
import json
from functools import partial
from importlib.metadata import entry_points
from pathlib import Path

import duckdb
import pytest
import typer
from typer.testing import CliRunner

from ark import cli
from ark.bulk import ingest_files
from ark.checks import collect_checks
from ark.cli import app
from ark.db import init_db
from ark.hostnames import fleet_read_registrables_tag

runner = CliRunner()


def test_without_held_sets_export_and_rebuild_say_to_run_intake(tmp_path, monkeypatch) -> None:
    """One line naming the step, no traceback, and a rebuild refuses before it drops a table."""
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"]).exit_code == 0
    for args in (["export"], ["stats"], ["rebuild", "output/provenance"]):
        result = runner.invoke(app, args)
        assert (result.exit_code, type(result.exception)) == (1, SystemExit), args
        assert "run uv run ark intake" in result.output


def test_rebuild_refuses_when_the_store_is_ahead_of_the_export(tmp_path, monkeypatch, his_files):
    """`ark rebuild` DROPS the store's tables before recreating them from Parquet, so an ingest
    since the last export would be discarded silently; with none since, it rebuilds."""
    (script,) = entry_points(group="console_scripts", name="ark")  # every `uv run ark` loads it
    assert callable(script.load())
    monkeypatch.chdir(tmp_path)
    cdx = tmp_path / "sample.cdx"
    cdx.write_text("com,example)/ 19970601120000 http://example.com:80/ text/html 200 B - - 9 f\n")
    (seeds := tmp_path / "seeds.txt").write_text("example.com\n")
    assert runner.invoke(app, ["init"]).exit_code == 0
    assert runner.invoke(app, ["seed", str(seeds), "--limit", "1"]).exit_code == 0
    assert runner.invoke(app, ["seed", "no-such-file.txt"]).exit_code == 2  # a usage error
    assert runner.invoke(app, ["ingest", "no_such_source", str(cdx)]).exit_code != 0
    assert runner.invoke(app, ["export", "--provenance"]).exit_code == 0
    result = runner.invoke(app, ["rebuild", "output/provenance"])
    assert result.exit_code == 0 and "rebuilt from" in result.output, result.output
    assert runner.invoke(app, ["ingest", "early_web", str(cdx)]).exit_code == 0
    result = runner.invoke(app, ["rebuild", "output/provenance"])
    assert result.exit_code != 0 and "refusing to rebuild" in result.output


def test_a_fleet_read_banks_both_halves_under_its_own_source(tmp_path, monkeypatch) -> None:
    """`ark ingest fleet_x_hostnames` banks the converter's registrables and the parts under the
    read's own source and method, so one unbank takes the read back. Another lead's part, or a
    file of neither half, exits 2 before anything banks."""
    rows = [("http://example.com/", "19990301000000", "200"),
            ("http://www.example.com/", "19990301000000", "200"),
            ("http://shop.example.org/", "20000101000000", "200"),
            ("http://gone.com/", "19980101000000", "404")]  # fmt: skip
    (read := tmp_path / "read").mkdir()
    part = read / "fleetread_bulk_cdx_file__x_0001.jsonl.gz"
    lines = (json.dumps(dict(zip(("url", "timestamp", "status"), r, strict=True))) for r in rows)
    part.write_bytes(gzip.compress("\n".join(lines).encode() + b"\n"))
    engine = Path(__file__).resolve().parents[1] / "scripts/engines/cdx_suffix_convert.py"
    spec = importlib.util.spec_from_file_location("cdx_suffix_convert", engine)
    spec.loader.exec_module(convert := importlib.util.module_from_spec(spec))
    tag = fleet_read_registrables_tag("bulk_cdx_file", "x", "ab" * 32)
    out, state = str(tmp_path / "cdx"), str(tmp_path / "state.tsv")
    convert.main(["--glob", f"{read}/fleetread_*", "--tag", tag, "--out", out, "--state", state])
    registrables = tmp_path / "cdx" / f"cdx_suffix_{tag}.jsonl.gz"
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
