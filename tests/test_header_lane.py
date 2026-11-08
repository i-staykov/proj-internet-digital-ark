"""The header lane the tick starts (`run_usenet_header_items.py`): seeding, back-off, strikes and a
kill between log and bank."""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest
from conftest import script


@pytest.fixture
def lane(tmp_path, monkeypatch, capsys):
    m = script("sources/usenet/run_usenet_header_items.py")
    work = tmp_path / "queue"
    for name, path in (("WORK", work), ("POOL", work / "pool"), ("OUT", tmp_path / "raw")):
        monkeypatch.setattr(m, name, path)
    monkeypatch.setattr(m, "LOG", tmp_path / "lane.log")
    monkeypatch.setattr(m, "held", lambda: False)
    monkeypatch.setattr(m, "unread", lambda *a: ["a.x", "b.x"])
    monkeypatch.setattr(m, "items", lambda *a: [{"identifier": "usenet-a.x", "item_size": 9}])
    work.mkdir()
    return m, work, lambda: capsys.readouterr().out.strip().splitlines()[-1]


def test_an_unseeded_lane_counts_nothing_and_a_seeded_one_its_list(lane):
    m, work, _ = lane
    assert m.left() == 0
    (work / "seen.json").write_text("[]")
    assert m.left() == 1  # the first start writes tops.txt
    (work / "tops.txt").write_text("a\nb\n")
    assert m.left() == 2


def test_a_429_backs_off_across_starts_and_an_outage_strikes_nothing(lane, monkeypatch):
    m, work, last = lane
    (work / "seen.json").write_text("[]")
    (work / "tops.txt").write_text("a\nb\n")
    End = sys.modules["sample_usenet_header_items"].End

    def busy(*a):
        raise End("429", 7200)

    monkeypatch.setattr(m, "screen", busy)
    m.main()
    assert "waits until" in last() and m.waits() > m.time.time() + 7000
    monkeypatch.setattr(m, "screen", lambda *a: pytest.fail("asked inside a back-off"))
    m.main()
    assert last().startswith("header: backing off, waits until")
    (work / "log.tsv").write_text("")

    def down(*a):
        raise End("URLError")

    monkeypatch.setattr(m, "screen", down)
    m.main()
    assert not any(m.struck(r) for r in m.rows("log.tsv")) and m.left() == 2
    outage = sys.modules["sample_usenet_header_items"].outage
    codes = ("000", "cut", "503", "URLError", "404", "size")
    assert [outage(c) for c in codes] == [1, 1, 1, 1, 0, 0]


def running(m, work, monkeypatch, fetch) -> list[list[str]]:
    """Top a screened above the floor with two files, each batch priced at 0 EE; the log."""
    (work / "seen.json").write_text("[]")
    (work / "tops.txt").write_text("a\nb\n")
    (work / "screen.tsv").write_text("a\t30000000\t9\t1\t1\t1\t90.0\n")
    files = [{"name": f"{n}.mbox.zip", "size": "10"} for n in "gh"]
    monkeypatch.setattr(m, "listing", lambda item, held: files)
    monkeypatch.setattr(m, "fetch", fetch)
    monkeypatch.setattr(m, "build", lambda pool, out: out.mkdir(parents=True) or 0)
    monkeypatch.setattr(m, "price", lambda work, out: 0.0)
    monkeypatch.setattr(m, "screen", lambda *a: pytest.fail("screened past an End"))
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    m.main()
    return m.rows("log.tsv")


def test_a_429_mid_batch_backs_off_and_judges_nothing(lane, monkeypatch):
    m, work, _ = lane
    End, asked = sys.modules["sample_usenet_header_items"].End, []

    def fetch(url, dst, size, held):
        asked.append(url)
        if len(asked) > 1:
            raise End("429")
        return "200"

    log = running(m, work, monkeypatch, fetch)
    # the partial batch lands as data, no drop row, and the 429 backs off
    assert len(asked) == 2 and [len(log[0]), log[-1][0]] == [8, "backoff"]
    assert "drop" not in {r[0] for r in log}


def test_one_file_cut_three_starts_running_strikes_its_top_once(lane, monkeypatch):
    m, work, _ = lane
    End, asked = sys.modules["sample_usenet_header_items"].End, []

    def fetch(url, dst, size, held):
        asked.append(url.rsplit("/", 1)[1])
        raise End("503")

    monkeypatch.setattr(m, "waits", lambda: 0.0)  # each start past its back-off
    for _start in range(5):
        log = running(m, work, monkeypatch, fetch)
    assert [r[2:] for r in log if m.struck(r)] == [["g.mbox.zip", "outage"]]
    assert asked == ["g.mbox.zip"] * 3 + ["h.mbox.zip"] * 2  # the next file from the fourth


def test_a_day_without_progress_reads_stalled_at_its_top(lane, monkeypatch, tmp_path):
    m, work, _ = lane
    (work / "seen.json").write_text("[]")
    (work / "tops.txt").write_text("a\n")
    monkeypatch.setattr(m, "SCRIPT", work / "seen.json")
    os.utime(work / "seen.json", (0, 0))
    assert m.stalled() == "stalled at a"
    (work / "log.tsv").write_text("backoff\ta\t429\t29991231T000000Z\t\n")
    m.main()  # a start inside a back-off
    assert m.stalled() == ""


def test_a_failed_screen_extract_is_a_strike_and_an_empty_pool_a_row(lane, monkeypatch):
    m, work, _ = lane
    scr = sys.modules["screen_usenet_header_items"]
    meta = [{"name": "g.mbox.zip", "size": "10"}]
    monkeypatch.setattr(scr, "listing", lambda item, held: meta)
    monkeypatch.setattr(scr, "fetch", lambda *a: "200")
    monkeypatch.setattr(scr.time, "sleep", lambda s: None)
    built = SimpleNamespace(run=lambda *a, **k: SimpleNamespace(returncode=1, stdout=""))
    monkeypatch.setattr(scr, "subprocess", built)
    size = {"a.x": 9}
    assert scr.screen(work, "a", ["a.x"], size, m.held) == "build 1"
    monkeypatch.setattr(scr, "listing", lambda item, held: [])
    assert scr.screen(work, "a", ["a.x"], size, m.held)[3] == "build 1"
    (work / "seen.json").write_text("[]")
    (work / "tops.txt").write_text("a\n")
    monkeypatch.setattr(m, "screen", lambda *a: "build 1")
    m.main()
    assert not (work / "screen.tsv").exists()
    assert [r[:3] for r in m.rows("log.tsv") if m.struck(r)] == [["stop", "a", "screen"]]


def test_a_kill_after_the_log_lands_the_batch_and_drops_the_unlogged(lane):
    m, work, _ = lane
    (work / "seen.json").write_text("[]")
    (work / "tops.txt").write_text("")
    for name in ("hl_1", "hl_2"):
        (m.OUT / f".{name}").mkdir(parents=True)
    (work / "log.tsv").write_text("hl_1\ta\ta.x\tg.mbox.zip\t10\t1\t1\t9.0\n")
    m.main()
    assert sorted(p.name for p in m.OUT.iterdir()) == ["hl_1"]
