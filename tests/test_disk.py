"""The collectors' floor sits above the bank's by the export's dip; a writer's log stays bounded."""

from ark import disk


def test_the_collectors_floor_is_the_banks_plus_the_budget_and_the_dip(monkeypatch):
    monkeypatch.setenv("ARK_FREE_SPACE_GIB", "50")
    monkeypatch.setenv("ARK_WRITE_BUDGET_GIB", "20")
    monkeypatch.setattr(disk, "EXPORT_DIP_GIB", 3.5)
    assert disk.collector_floor() == int(73.5 * disk.GIB)
    monkeypatch.setattr(disk, "free", lambda p: 80 * disk.GIB)
    assert disk.below_floor(disk.STORE) == ""
    assert disk.below_floor(disk.STORE, 7 * disk.GIB) == (
        "80.0 GiB free, under the collectors' floor of 80.5"
    )


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
