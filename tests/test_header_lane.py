"""The header lane unattended: seeding, back-off, strikes and a kill between log and bank."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
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
    big = [{"identifier": f"usenet-{t}.x", "item_size": 40_000_000} for t in "ab"]
    monkeypatch.setattr(m, "items", lambda *a: big)  # each top above the screen's sample
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
    assert m.start() == 7200 and "waits until" in last()
    monkeypatch.setattr(m, "screen", lambda *a: pytest.fail("asked inside a back-off"))
    assert m.start() > 7000 and last().startswith("header: backing off, waits until")
    (work / "log.tsv").write_text("")

    def down(*a):
        raise End("503", 9000)  # a 503's Retry-After is kept as a 429's is

    monkeypatch.setattr(m, "screen", down)
    assert m.start() == 9000
    assert not any(m.struck(r) for r in m.rows("log.tsv")) and m.left() == 2
    outage = sys.modules["sample_usenet_header_items"].outage
    codes = ("000", "cut", "503", "URLError", "404", "size")
    assert [outage(c) for c in codes] == [1, 1, 1, 1, 0, 0]
    # a back-off is slept out in the process, an hour at most between two starts
    waits, slept = [5000.0, 0], []
    monkeypatch.setattr(m, "start", lambda: waits.pop(0))
    monkeypatch.setattr(m.time, "sleep", slept.append)
    m.main()
    assert slept == [3600]


def test_the_floor_orders_tops_and_only_a_running_mean_under_50_excludes(lane):
    m, work, _ = lane
    (work / "seen.json").write_text("[]")
    (work / "tops.txt").write_text("poor\nmid\nnew\nold\nrich\nsour\nonce\n")
    per_gb = {"poor": 40, "mid": 100, "rich": 900, "sour": 900, "once": 900}
    screens = [f"{t}\t30000000\t9\t1\t1\t1\t{r * 0.03}\n" for t, r in per_gb.items()]
    (work / "screen.tsv").write_text("".join(screens) + "old\t0\t0\tbuild 2\n")
    batches = (("b1", "sour", 30.0), ("b2", "sour", 60.0), ("b3", "once", 0.0))
    (work / "log.tsv").write_text(
        "".join(f"{b}\t{t}\t{t}.x\tg.zip\t1000000000\t1\t1\t{ee}\n" for b, t, ee in batches)
        + "drop\trich\tb0\t290.0\t1000000000\n"  # one batch under the floor drops nothing
    )
    # at the floor or above, then the other screened, then the unscreened (a row cut short)
    assert m.todo() == ["rich", "once", "mid", "new", "old"]
    assert m.rates()["sour"] == 45.0 and m.rates()["once"] > 899


def test_a_top_within_the_sample_runs_whole_unscreened_and_a_screen_banks_its_sample(
    lane, monkeypatch
):
    m, work, _ = lane
    (work / "seen.json").write_text("[]")
    (work / "tops.txt").write_text("b\na\n")
    sizes = (("a", 30_000_000), ("b", 30_000_001))
    listed = [{"identifier": f"usenet-{t}.x", "item_size": n} for t, n in sizes]
    monkeypatch.setattr(m, "items", lambda *a: listed)
    screened, stamps = [], iter((".hl_1", "2"))

    def screen(work, top, todo, size, held, keep):
        screened.append(top)
        (keep / "url").mkdir(parents=True)
        return [top, 30000000, 9, 1, 1, 1, 0.0]

    monkeypatch.setattr(m, "screen", screen)
    monkeypatch.setattr(m, "listing", lambda item, held: [{"name": "g.mbox.zip", "size": "10"}])
    monkeypatch.setattr(m, "fetch", lambda url, dst, size, held: "200")
    monkeypatch.setattr(m, "build", lambda pool, out: out.mkdir(parents=True) or 0)
    monkeypatch.setattr(m, "price", lambda work, out: 0.0)
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    monkeypatch.setattr(m.time, "strftime", lambda *a: next(stamps))
    assert m.start() == 0 and screened == ["b"]
    assert [(r[0], r[1]) for r in m.rows("log.tsv")] == [("hl_2", "a"), ("ran", "a")]
    assert sorted(p.name for p in m.OUT.iterdir()) == ["hl_1", "hl_2"]


def test_a_top_drops_on_its_running_mean_not_on_its_first_batch(lane, monkeypatch):
    m, work, _ = lane
    asked, stamps = [], iter("123")
    (work / "seen.json").write_text("[]")
    (work / "tops.txt").write_text("a\n")
    (work / "screen.tsv").write_text("a\t30000000\t9\t1\t1\t1\t90.0\n")
    files = [{"name": f"{n}.mbox.zip", "size": "1000000000"} for n in "ghi"]  # a batch each
    monkeypatch.setattr(m, "listing", lambda item, held: files)
    monkeypatch.setattr(m, "fetch", lambda url, dst, size, held: asked.append(url) or "200")
    monkeypatch.setattr(m, "build", lambda pool, out: out.mkdir(parents=True) or 0)
    monkeypatch.setattr(m, "price", lambda work, out: 0.0)
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    monkeypatch.setattr(m.time, "strftime", lambda *a: next(stamps))
    assert m.start() == 0
    # the first batch at 0 EE reads on, the second puts the mean under 50: the third is not read
    assert [r[0] for r in m.rows("log.tsv")] == ["hl_1", "hl_2", "drop"]
    assert len(asked) == 2 and m.left() == 0


def running(m, work, monkeypatch, fetch, parallel=1) -> list[list[str]]:
    """Top a screened above the floor with two files, each batch priced at 0 EE; the log."""
    (work / "seen.json").write_text("[]")
    (work / "tops.txt").write_text("a\nb\n")
    (work / "screen.tsv").write_text("a\t30000000\t9\t1\t1\t1\t90.0\n")
    files = [{"name": f"{n}.mbox.zip", "size": "10"} for n in "gh"]
    monkeypatch.setattr(m, "PARALLEL", parallel)
    monkeypatch.setattr(m, "listing", lambda item, held: files)
    monkeypatch.setattr(m, "fetch", fetch)
    monkeypatch.setattr(m, "build", lambda pool, out: out.mkdir(parents=True) or 0)
    monkeypatch.setattr(m, "price", lambda work, out: 0.0)
    monkeypatch.setattr(m, "screen", lambda *a: pytest.fail("screened past an End"))
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    m.start()
    return m.rows("log.tsv")


def test_a_429_mid_batch_backs_off_and_judges_nothing(lane, monkeypatch):
    m, work, _ = lane
    End, asked = sys.modules["sample_usenet_header_items"].End, []

    def fetch(url, dst, size, held):
        held()
        asked.append(url)
        if len(asked) > 1:
            raise End("429")
        return "200"

    log = running(m, work, monkeypatch, fetch)
    # the partial batch lands as data, no drop row, and the 429 backs off
    assert len(asked) == 2 and [len(log[0]), log[-1][0]] == [8, "backoff"]
    assert "drop" not in {r[0] for r in log}


def test_two_files_download_at_once_and_one_429_stops_the_pool(lane, monkeypatch):
    m, work, _ = lane
    End, both = sys.modules["sample_usenet_header_items"].End, threading.Barrier(2)

    def fetch(url, dst, size, held):
        held()
        both.wait(timeout=10)  # passes only with both in flight
        if "/h." in url:
            raise End("429", 7200)
        return "200"

    log = running(m, work, monkeypatch, fetch, parallel=2)
    # the file that came whole is built and logged, the 429's is named in the back-off
    assert [r[3] for r in log if len(r) == 8] == ["g.mbox.zip"]
    assert log[-1][:3] + log[-1][4:] == ["backoff", "a", "429", "h.mbox.zip"]


def test_one_file_cut_three_starts_running_strikes_its_top_once(lane, monkeypatch):
    m, work, _ = lane
    End, asked = sys.modules["sample_usenet_header_items"].End, []

    def fetch(url, dst, size, held):
        held()  # the pool's gate: no request once a download ended the batch
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
    m.start()  # a start inside a back-off
    assert m.stalled() == ""


def test_a_failed_screen_extract_is_a_strike_and_a_top_without_a_file_a_row(lane, monkeypatch):
    m, work, _ = lane
    scr = sys.modules["screen_usenet_header_items"]
    meta, listed = [{"name": "g.mbox.zip", "size": "10"}], []
    monkeypatch.setattr(scr, "listing", lambda item, held: listed.append(item) or meta)
    monkeypatch.setattr(scr, "fetch", lambda *a: "200")
    monkeypatch.setattr(scr.time, "sleep", lambda s: None)
    built = SimpleNamespace(run=lambda *a, **k: SimpleNamespace(returncode=1, stdout=""))
    monkeypatch.setattr(scr, "subprocess", built)
    size = {"a.x": 9, "a.y": 7, "a": 1}
    assert scr.screen(work, "a", ["a.x", "a.y", "a"], size, m.held) == "build 1"
    assert listed == ["a", "a.x"]  # the top-level item, then the largest other
    monkeypatch.setattr(scr, "listing", lambda item, held: [])
    assert scr.screen(work, "a", ["a.x"], size, m.held) == ["a", 0, 0, 0, 0, 0, 0.0]
    (work / "seen.json").write_text("[]")
    (work / "tops.txt").write_text("a\n")
    monkeypatch.setattr(m, "screen", lambda *a: "build 1")
    m.start()
    assert not (work / "screen.tsv").exists()
    assert [r[:3] for r in m.rows("log.tsv") if m.struck(r)] == [["stop", "a", "screen"]]


def test_downloads_in_flight_count_against_the_floor_and_a_503_is_asked_once(tmp_path, monkeypatch):
    script("sources/usenet/run_usenet_header_items.py")
    s = sys.modules["sample_usenet_header_items"]
    asked, answers = [], ["200 ", "503 120"]

    def floor(path, more):
        asked.append(more)
        return ""

    def curl(cmd, **k):
        Path(cmd[cmd.index("-o") + 1]).write_bytes(b"x" * 10)
        return SimpleNamespace(returncode=0, stdout=answers.pop(0))

    monkeypatch.setattr(s, "below_floor", floor)
    monkeypatch.setattr(s, "subprocess", SimpleNamespace(run=curl))
    monkeypatch.setattr(s.time, "sleep", lambda secs: None)
    monkeypatch.setattr(s, "FLYING", {tmp_path / "other.zip": 500})
    assert s.fetch("u", tmp_path / "g.zip", 10) == "200"
    assert asked == [520] and s.FLYING == {tmp_path / "other.zip": 500}
    with pytest.raises(s.End) as end:
        s.fetch("u", tmp_path / "h.zip", 10)
    assert (end.value.code, end.value.retry, answers) == ("503", 120, [])
    assert not (tmp_path / "h.zip").exists()


def test_a_kill_after_the_log_lands_the_batch_and_drops_the_unlogged(lane):
    m, work, _ = lane
    (work / "seen.json").write_text("[]")
    (work / "tops.txt").write_text("")
    for name in ("hl_1", "hl_2"):
        (m.OUT / f".{name}").mkdir(parents=True)
    (work / "log.tsv").write_text("hl_1\ta\ta.x\tg.mbox.zip\t10\t1\t1\t9.0\n")
    m.start()
    assert sorted(p.name for p in m.OUT.iterdir()) == ["hl_1"]
