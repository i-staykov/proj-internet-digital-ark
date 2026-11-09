"""The collectors' floor sits above the bank's by the export's dip; a writer's log stays bounded."""

import itertools
import subprocess

import pytest
from conftest import script

from ark import disk


def test_the_collectors_floor_is_what_the_bank_requires_plus_the_dip(tmp_path, monkeypatch):
    monkeypatch.setenv("ARK_FREE_SPACE_GIB", "50")
    monkeypatch.setenv("ARK_WRITE_BUDGET_GIB", "20")
    monkeypatch.setattr(disk, "EXPORT_DIP_GIB", 3.5)
    assert disk.collector_floor(tmp_path) == int(73.5 * disk.GIB)
    monkeypatch.setattr(disk, "free", lambda p: 80 * disk.GIB)
    assert disk.below_floor(tmp_path, root=tmp_path) == ""
    assert disk.below_floor(tmp_path, 7 * disk.GIB, root=tmp_path) == (
        "80.0 GiB free, under the collectors' floor of 80.5"
    )
    # the budget is never under the store's own size, as `space` has it
    monkeypatch.setattr(disk, "GIB", 1)
    (tmp_path / disk.STORE).parent.mkdir()
    (tmp_path / disk.STORE).write_bytes(b"x" * 30)
    assert disk.collector_floor(tmp_path) == 53 + 30
    monkeypatch.setenv("ARK_WRITE_BUDGET_GIB", "")
    with pytest.raises(ValueError):
        disk.settings()


def test_the_cron_line_carries_the_floor_local_env_sets(monkeypatch):
    jobs = script("engines/cdx_walk_jobs.py")
    monkeypatch.setattr(jobs, "local_env", lambda k: {"ARK_FREE_SPACE_GIB": "60"}.get(k, ""))
    assert "cd " in jobs.cron(0) and " ARK_FREE_SPACE_GIB=60 flock -n " in jobs.cron(0)
    assert "ARK_WRITE_BUDGET_GIB" not in jobs.cron(0)


def test_a_log_over_the_limit_is_cut_in_place_to_whole_lines(tmp_path):
    log = tmp_path / "lane0.log"
    log.write_text("".join(f"row {n:06d}\n" for n in range(3000)))
    inode = log.stat().st_ino
    with open(log, "a") as shell:  # a `>>` redirect, open across the trim
        assert disk.trim(log, limit=20_000, keep=5_000)
        shell.write("after\n")
    lines = log.read_text().splitlines()
    assert lines[0].startswith("row ") and lines[-2:] == ["row 002999", "after"]
    assert 4_000 < log.stat().st_size <= 5_010 and log.stat().st_ino == inode
    assert not disk.trim(log, limit=20_000, keep=5_000)
    assert not disk.trim(tmp_path / "absent.log")


def test_watch_runs_the_command_and_keeps_the_least_free_space(tmp_path, monkeypatch):
    reads = itertools.chain([90, 80, 70, 85], itertools.repeat(88))
    monkeypatch.setattr(disk, "free", lambda p: next(reads))
    cmd = ["python3", "-c", "import time; time.sleep(0.5); raise SystemExit(3)"]
    rc, start, least = disk.watch(cmd, tmp_path, every=0.01)
    assert (rc, start, least) == (3, 90, 70)


def test_the_ship_export_appends_its_dip_and_exits_as_the_export(tmp_path):
    log = tmp_path / "export_dip.tsv"
    run = subprocess.run(["python3", disk.__file__, str(log), "python3", "-c", "exit(4)"])
    row = log.read_text().rstrip("\n").split("\t")
    assert run.returncode == 4 and len(row) == 6 and row[4] == "4" and float(row[3]) >= 0
