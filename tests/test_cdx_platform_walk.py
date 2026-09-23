"""The platform walker follows the resume key to the end and never marks a failed walk done."""

from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "cdx_platform_walk", ROOT / "scripts/engines/cdx_platform_walk.py"
)
walk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(walk)


def _args(tmp_path: Path, **kw) -> SimpleNamespace:
    base = dict(
        deadline=9999999999,
        out=tmp_path / "out",
        state_dir=tmp_path / "state",
        limit=3,
        delay=0,
        timeout=5,
        rotate=25,
    )
    base.update(kw)
    base["out"].mkdir(exist_ok=True)
    base["state_dir"].mkdir(exist_ok=True)
    return SimpleNamespace(**base)


def _fake(monkeypatch, tmp_path, answers):
    monkeypatch.setattr(walk, "PAUSE_FLAG", tmp_path / "pause-platform")
    slept, asked = [], []
    monkeypatch.setattr(walk.time, "sleep", slept.append)
    calls = iter(answers)

    def fetch(params, timeout):
        asked.append(dict(params))
        return next(calls)

    monkeypatch.setattr(walk, "fetch", fetch)
    return slept, asked


def _rows(out: Path) -> list[dict]:
    rows = []
    for journal in sorted(out.glob("suffix_a_net_rk_*.jsonl.gz")):
        with gzip.open(journal, "rt") as fh:
            rows += [json.loads(line) for line in fh]
    return rows


def test_a_page_with_more_ends_in_a_blank_line_and_the_key():
    rows, key = walk.split_page("http://x.a.net/ 19990101000000 200\n\nnet,a,x)/ 1999\n")
    assert rows == [["http://x.a.net/", "19990101000000", "200"]] and key == "net,a,x)/ 1999"
    assert walk.split_page("http://x.a.net/ 19990101000000 200\n") == (
        [["http://x.a.net/", "19990101000000", "200"]],
        None,
    )


def test_the_walk_follows_the_key_dedupes_and_marks_done(tmp_path, monkeypatch):
    page1 = (
        "http://x.a.net:80/ 19990101000000 200\n"
        "http://x.a.net/p.html 19990601000000 301\n"
        "http://other.com/ 19990101000000 200\n"
        "\nKEY1\n"
    )
    page2 = "http://y.a.net/ 20010101000000 200\nhttp://x.a.net/ 20000101000000 200\n"
    answers = [("200", page1, None), ("200", page2, None), ("200", page2, None)]
    _, asked = _fake(monkeypatch, tmp_path, answers)
    args = _args(tmp_path)
    assert walk.Walk("a.net", args).run().startswith("done: 2 pages, 3 host-years")
    assert "resumeKey" not in asked[0] and asked[1]["resumeKey"] == asked[2]["resumeKey"] == "KEY1"
    assert asked[0]["fl"] == "original,timestamp,statuscode" and "collapse" not in asked[0]
    assert [(r["url"], r["timestamp"]) for r in _rows(args.out)] == [
        ("http://x.a.net:80/", "19990101000000"),
        ("http://y.a.net/", "20010101000000"),
        ("http://x.a.net/", "20000101000000"),
    ]
    assert (args.state_dir / "a_net.done").exists()
    assert not list(args.out.glob("*.part"))


def test_a_resumed_page_without_a_key_is_asked_again_before_done(tmp_path, monkeypatch):
    short = ("200", "http://x.a.net/ 19990101000000 200\n", None)
    more = ("200", "http://z.a.net/ 19990101000000 200\n\nKEY2\n", None)
    answers = [("200", "\nKEY1\n", None), short, more, ("200", "", None), ("200", "", None)]
    _, asked = _fake(monkeypatch, tmp_path, answers)
    args = _args(tmp_path)
    assert walk.Walk("a.net", args).run().startswith("done")
    assert [p.get("resumeKey") for p in asked] == [None, "KEY1", "KEY1", "KEY2", "KEY2"]
    assert {r["url"] for r in _rows(args.out)} == {"http://x.a.net/", "http://z.a.net/"}


def test_a_refusal_parks_the_platform(tmp_path, monkeypatch):
    _fake(monkeypatch, tmp_path, [("HTTP403", "", None)])
    args = _args(tmp_path)
    assert "parked" in walk.Walk("a.net", args).run()
    assert (args.state_dir / "a_net.refused").exists()
    assert not (args.state_dir / "a_net.done").exists()


def test_a_journal_left_by_a_killed_run_is_promoted(tmp_path, monkeypatch):
    args = _args(tmp_path)
    left = args.out / "suffix_a_net_rk_20260923T080000Z_00000.jsonl.gz.part"
    with gzip.open(left, "wt") as fh:
        fh.write('{"url": "http://x.a.net/", "timestamp": "19990101000000", "status": "200"}\n')
    walk.Walk("a.net", args)
    assert not left.exists() and left.with_name(left.name[: -len(".part")]).exists()


def test_retry_after_takes_seconds_or_a_date_and_never_goes_negative():
    assert walk.retry_after("42") == 42.0
    assert walk.retry_after("-5") == 0.0
    assert walk.retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0
    assert walk.retry_after("soon") is None and walk.retry_after(None) is None


def test_a_page_that_keeps_failing_is_resumable_and_never_done(tmp_path, monkeypatch):
    answers = [("200", "http://x.a.net/ 19990101000000 200\n\nKEY1\n", None)]
    answers += [("ERR:TimeoutError", "", None)] * 3
    _fake(monkeypatch, tmp_path, answers)
    args = _args(tmp_path)
    assert "resumable" in walk.Walk("a.net", args).run()
    assert not (args.state_dir / "a_net.done").exists()
    state = json.loads((args.state_dir / "a_net.state.json").read_text())
    assert state["resume_key"] == "KEY1" and state["pages"] == 1
    # a new process picks up the saved key
    _, asked = _fake(monkeypatch, tmp_path, [("200", "", None), ("200", "", None)])
    assert walk.Walk("a.net", args).run().startswith("done")
    assert asked[0]["resumeKey"] == "KEY1"


def test_retry_after_is_slept_and_five_throttles_stop_the_client(tmp_path, monkeypatch):
    slept, _ = _fake(monkeypatch, tmp_path, [("HTTP429", "", 42.0), ("200", "", None)])
    assert walk.Walk("a.net", _args(tmp_path)).run().startswith("done")
    assert 42.0 in slept
    _fake(monkeypatch, tmp_path, [("REFUSED", "", None)] * 5)
    with pytest.raises(SystemExit):
        walk.Walk("b.net", _args(tmp_path)).run()


def test_a_giant_that_keeps_timing_out_is_parked_not_the_lane(tmp_path, monkeypatch):
    args = _args(tmp_path)
    for run in range(3):
        slept, _ = _fake(monkeypatch, tmp_path, [("HTTP504", "", None)] * 3)
        outcome = walk.Walk("a.net", args).run()
        assert ("parked" in outcome) == (run == 2)
        assert 60.0 in slept
    assert (args.state_dir / "a_net.refused").exists()


def test_lanes_split_the_seeds_disjointly():
    seeds = [f"p{i}.net" for i in range(60)]
    lanes = [[s for s in seeds if walk.mine(s, k, 3)] for k in range(3)]
    assert sorted(sum(lanes, [])) == sorted(seeds) and all(lanes)
