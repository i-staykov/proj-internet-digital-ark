"""Slices cut and lent, artifacts pulled and banked (scripts/engines/runner_slices.py)."""

from __future__ import annotations

import datetime as dt
import fnmatch
import io
import json
import threading
import zipfile
from types import SimpleNamespace

import pytest
from conftest import script

rs = script("engines/runner_slices.py")
trigger = script("harness/bank_trigger.py")
NOW = dt.datetime(2026, 11, 9, 12, 0, tzinfo=dt.UTC)
KEY = "co.uk 1000 {} 1996 2013"
SUB = "co.uk 100 40 1996 2013"
NAME = "slice_20261109T110000Z_0_r0"


def row(page: str, status: str, size: str = "1000", at: str = "20261109T100000Z") -> str:
    cols = [at, "co.uk", size, page, "1996", "2013", "all", status, "1", "9"]
    return "\t".join([*cols, "0", "0", "0", "0"])


def stage(tmp_path):
    """A bank host's data/ with its lanes installed: a counted suffix, a done page, an order."""
    data, register = tmp_path / "data", tmp_path / "docs/registers/runner"
    lane = data / "raw/cdx_walk/lane0"
    lane.mkdir(parents=True)
    (lane / "pages.json").write_text('{"co.uk": 24}')
    (lane / "done.txt").write_text(KEY.format(3) + "\n")
    (data / "queue").mkdir()
    order = {"units": {"co.uk all": {"p1": 1.0, "p2": 2.0, "s": 10, "n": 9}}}  # above ask-gap
    (data / "queue/cdx_order.json").write_text(json.dumps(order))
    register.mkdir(parents=True)
    (register / "cadence").write_text("# slices kept cut\n2\n")
    (register / "long").write_text("1\n")
    return data, register


def test_write_cuts_each_lane_its_slices_of_pages_neither_done_nor_lent(tmp_path, monkeypatch):
    data, register = stage(tmp_path)
    monkeypatch.setattr(rs, "PAGES", 4)
    (data / "raw/cdx_walk/lane0/pages.json").write_text('{"co.uk": 48}')  # a fourth holds both
    (register / "slice_20261109T110000Z_0.txt").write_text(rs.HEAD + KEY.format(7) + " all\n")
    runner0 = data / "raw/cdx_walk/runner0"
    runner0.mkdir()
    (runner0 / "done.txt").write_text(KEY.format(9) + "\n")
    line = rs.write(data, register, NOW)
    assert line == "runner slices: 2 cut, 0 gone, 10 keys lent"
    new = register / "slice_20261109T120000Z_0.txt"
    long = register / "long_20261109T120000Z_0.txt"
    text = new.read_text()
    assert text.startswith(rs.HEAD) and len(rs.lines(new)) == len(rs.lines(long)) == 4
    assert all(
        ln.startswith("co.uk 1000 ") and ln.endswith(" 1996 2013 all") for ln in rs.lines(new)
    )
    out = {int(k.split()[2]) for k in rs.keys(new) | rs.keys(long)}
    assert len(out) == 8 and out.isdisjoint({3, 7, 9}), "done, lent and a runner's answer stay out"
    lent = data / "raw/cdx_walk/runner/lent.txt"
    assert lent.read_text().startswith(rs.HEAD)
    assert rs.keys(lent) == rs.keys(new) | rs.keys(long) | {KEY.format(7), KEY.format(9)}
    assert not (data / "raw/cdx_walk/runner/pending.txt").exists(), "the throwaway saves nothing"
    assert rs.write(data, register, NOW).startswith("runner slices: 0 cut"), "the knobs are met"
    assert rs.ARTIFACT.match("long_20261109T120000Z_0_r1")[2] == "1", "banked as runner1"


def test_size_scales_a_slice_by_the_lane_s_rate_over_its_last_banked_log(tmp_path, monkeypatch):
    log = tmp_path / "log.tsv"
    assert rs.size(log, 3300) == 300, "none banked: the floor"
    first = [row("1", "200"), row("2", "200", at="20261109T100140Z")]
    last = [
        row("3", "200"),
        row("4", "HTTP403", at="20261109T100500Z"),
        row("5", "200", at="20261109T101000Z"),
        row("6", "HTTP504", at="20261109T101640Z"),
        "# pause 60 s: HTTP503",
    ]
    log.write_text("\n".join(["# artifact 1 a_r0", *first, "# artifact 2 b_r0", *last]) + "\n")
    assert rs.size(log, 3300) == 300, "13 at 3 answered a 1000 s: under the floor"
    monkeypatch.setattr(rs, "PAGES", 4)
    assert rs.size(log, 3300) == 13 and rs.size(log, 21600) == 81
    log.write_text("\n".join(["# artifact 1 a_r0", *first, "# artifact 3 c_r0", row("7", "200")]))
    assert rs.size(log, 3300) == 4, "one row spans nothing"
    log.write_text(
        "\n".join(["# artifact 4 d_r1", row("8", "200"), row("9", "200", at="20261109T100001Z")])
    )
    assert rs.size(log, 21600) == 2700, "two rows a second apart: capped at one start an INTERVAL"


def test_a_slice_leaves_the_lanes_their_share_above_the_ask_tier(tmp_path, monkeypatch):
    data, _register = stage(tmp_path)
    monkeypatch.setattr(rs, "PAGES", 10)
    lane, runner = data / "raw/cdx_walk/lane0", data / "raw/cdx_walk/runner"
    runner.mkdir()
    (lane / "pages.json").write_text('{"co.uk": 20, "me.uk": 8}')
    units = {"co.uk all": {"p2": 33.0, "s": 450, "n": 9}, "me.uk all": {"p2": 1.0, "s": 50, "n": 9}}
    units["ask-gap ask"] = {"p2": 2.8, "s": 2.0, "n": 5000}
    (data / "queue/cdx_order.json").write_text(json.dumps({"units": units}))
    want = [rs.PAGES] * 2
    assert rs.cut(data, runner, want) == [], "unmeasured, 10 s a start: every page under ask-gap"
    (lane / "log.tsv").write_text("# order 3 priced, 0 exploring, 21 s a start\n")
    slices = rs.cut(data, runner, want)
    assert [len(s) for s in slices] == [4] and {t[0] for t in slices[0]} == {"co.uk"}, (
        "a fourth of the 19 co.uk pages above the tier; me.uk sits under it; no question"
    )


def test_a_slice_of_questions_banks_and_prices_like_a_lane_s(tmp_path, monkeypatch):
    """Pages scarce above the ask tier: the slice carries ask-gap's head, which no lane asks while
    it is lent; the job walks it in its order, and its rows price as a lane's, kind by kind."""
    order, yields = script("engines/cdx_walk_order.py"), script("agents/lane_yield.py")
    data, register = stage(tmp_path)
    monkeypatch.setattr(rs, "PAGES", 6)
    (register / "cadence").write_text("1\n")
    (register / "long").write_text("0\n")
    lane0 = data / "raw/cdx_walk/lane0"
    (lane0 / "pages.json").write_text('{"co.uk": 9}')  # 8 above the tier, a fourth lent
    (lane0 / "done.txt").write_text(KEY.format(3) + "\nask-gap 1 q0.com 1996 2013\n")
    (data / "queue/pool_questions.tsv").write_text("".join(f"gap\tq{n}.com\n" for n in range(10)))
    units = json.loads((data / "queue/cdx_order.json").read_text())["units"]
    units["ask-gap ask"] = {"p1": 0.01, "p2": 2.82, "n": 8651, "s": 2.0}  # under co.uk a start
    (data / "queue/cdx_order.json").write_text(json.dumps({"units": units}))
    assert rs.write(data, register, NOW) == "runner slices: 1 cut, 0 gone, 6 keys lent"
    slice_ = register / "slice_20261109T120000Z_0.txt"
    tasks = [rs.walker.decode(ln)[0] for ln in rs.lines(slice_)]
    assert [t[2] for t in tasks[2:]] == ["q1.com", "q2.com", "q3.com", "q4.com"], "q0 is done"
    assert [t[5] for t in tasks[:2]] == ["all", "all"], "the pages first"

    def answer(task, a, sink):  # a host's root, 1999 and 2005
        host = task[2] if task[5] == "ask" else f"h{task[2]}.co.uk"
        for ts in ("19990101000000", "20050101000000"):
            sink(f"k {ts} http://{host}/ 200".encode())
        return "200", True, 1.0, 1, None

    def walk(a) -> list[tuple]:
        lane, asked = rs.walker.load(a), []
        while (task := lane.take()) is not None:
            asked.append(task)
            lane.settle(task, *lane.ask(task))
        return asked

    monkeypatch.setattr(rs.walker, "fetch", answer)
    a = SimpleNamespace(lane=0, lanes=1, data=data, state_dir=lane0, slice=None, questions=False)
    a.max_transient, a.workers, a.min_interval = 0, 3, 10
    lent = rs.keys(data / "raw/cdx_walk/runner/lent.txt")
    assert {rs.walker.key_of(t) for t in walk(a)}.isdisjoint(lent), "no lane asks a lent key"
    job = tmp_path / "job/raw"
    b = SimpleNamespace(lane=0, lanes=1, data=job.parent, state_dir=job / "cdx_walk/lane0")
    b.slice, b.questions, b.max_transient, b.workers, b.min_interval = slice_, True, 0, 2, 10
    b.state_dir.mkdir(parents=True)
    assert walk(b) == tasks, "the job walks the slice in its order"
    blob = zipped({str(p.relative_to(job)): p.read_bytes() for p in job.rglob("*") if p.is_file()})
    listing = json.dumps({"artifacts": [art(1, "slice_20261109T120000Z_0_r0")]}).encode()
    monkeypatch.setattr(rs, "gh", lambda *call, timeout: blob if "zip" in call[1] else listing)
    assert rs.pull(data).startswith("runner slices: 1 artifacts banked")
    (data / "baseline.json").write_text('{"current": {"directory": "his", "marker": "m"}}')
    monkeypatch.setattr(order, "DATA", data)
    order.main()
    priced = json.loads((data / "queue/cdx_order.json").read_text())["units"]
    assert priced["ask-gap ask"]["n"] == 9, "the job's answers price the tier beside the lane's"
    out, hour = tmp_path / "productivity.tsv", dt.datetime.now(dt.UTC) + dt.timedelta(hours=1)
    yields.write(out, data, f"{hour:%Y-%m-%dT%H00}", hours=48)
    rows = {tuple(r[1:4]): (int(r[5]), float(r[7]) / int(r[5])) for r in yields.read(out)}
    for kind, n in (("page", 2), ("ask-gap", 4)):
        for w in yields.WINDOWS:
            (answered, each), lane = rows["runner0", kind, w], rows["lane0", kind, w][1]
            assert answered == n and each == pytest.approx(lane, abs=0.01) and each > 0


def test_a_slice_s_blocked_questions_are_booked_done_and_write_no_stop(tmp_path, monkeypatch):
    """IA answers an excluded domain's question 403 every time (laws): six in a row and one left
    last are booked done unpaused, so the bank writes no STOP and lends none again; past
    `EXCLUDED` in a row with no 200 between, a question's 403 is the address's wall again."""
    data, register = stage(tmp_path)
    names = [f"x{n}.com" for n in range(6)] + ["ok.com", "x6.com"]
    tasks = [("ask-gap", 1, d, 1996, 2013, "ask") for d in names]
    slice_ = register / "slice_20261109T110000Z_0.txt"
    slice_.write_text(rs.HEAD + "".join(rs.walker.encode(t, ()) + "\n" for t in tasks))

    def answer(task, a, sink):
        if task[2] != "ok.com":
            return "HTTP403", False, 0.5, 0, None
        sink(b"k 20050101000000 http://ok.com/ 200")
        return "200", True, 1.0, 1, None

    monkeypatch.setattr(rs.walker, "fetch", answer)
    monkeypatch.setattr(rs.walker, "STOP", threading.Event())
    job = tmp_path / "job/raw"
    b = SimpleNamespace(lane=0, lanes=1, data=job.parent, state_dir=job / "cdx_walk/lane0")
    b.slice, b.questions, b.max_transient, b.workers, b.min_interval = slice_, True, 0, 2, 10
    b.state_dir.mkdir(parents=True)
    lane = rs.walker.load(b)
    while not rs.walker.STOP.is_set() and (task := lane.take()) is not None:
        lane.settle(task, *lane.ask(task))
    assert not rs.walker.STOP.is_set() and lane.refusal_end == 0, "no pause"
    assert rs.keys(b.state_dir / "done.txt") == {rs.walker.key_of(t) for t in tasks}
    blob = zipped({str(p.relative_to(job)): p.read_bytes() for p in job.rglob("*") if p.is_file()})
    listing = json.dumps({"artifacts": [art(1, NAME)]}).encode()
    monkeypatch.setattr(rs, "gh", lambda *call, timeout: blob if "zip" in call[1] else listing)
    assert rs.pull(data).startswith("runner slices: 1 artifacts banked")
    pool = "".join(f"gap\t{d}\n" for d in [*names, "y.com"])
    (data / "queue/pool_questions.tsv").write_text(pool)
    assert "STOP" not in rs.write(data, register, NOW) and not (register / "STOP").exists()
    cut = [rs.walker.decode(ln)[0] for f in rs.slices(register) for ln in rs.lines(f)]
    assert {t[2] for t in cut if t[5] == "ask"} == {"y.com"}, "no done question is lent again"
    lane.excluded, z = rs.walker.EXCLUDED, ("ask-gap", 1, "z.com", 1996, 2013, "ask")
    lane.settle(z, *lane.ask(z))
    assert lane.refusal_end > 0 and rs.walker.key_of(z) not in lane.done, "the cap's 403 is a wall"


def test_write_drops_banked_and_stale_slices_and_stops_only_on_a_judged_refusal(tmp_path):
    data, register = stage(tmp_path)
    runner = data / "raw/cdx_walk/runner"
    (runner / "judge").mkdir(parents=True)
    (runner / "banked.txt").write_text(f"1\t{NAME}\n")
    for stem, page in (
        ("slice_20261109T050000Z_0", 1),
        ("slice_20261109T110000Z_0", 2),
        ("slice_20261109T113000Z_0", 4),
        ("long_20261109T050000Z_0", 5),
        ("long_20261108T050000Z_0", 6),
    ):
        (register / f"{stem}.txt").write_text(rs.HEAD + KEY.format(page) + " all\n")
    (runner / "judge/1_x.tsv").write_text("".join(row("1", "HTTP503") + "\n" for _ in range(5)))
    assert rs.write(data, register, NOW) == "runner slices: 1 cut, 3 gone, 5 keys lent"
    assert not (register / "STOP").exists(), "five requests are under the floor"
    assert not (register / "slice_20261109T050000Z_0.txt").exists(), "7 h old"
    assert not (register / "slice_20261109T110000Z_0.txt").exists(), "banked"
    assert not (register / "long_20261108T050000Z_0.txt").exists(), "31 h old"
    assert [f.name[:5] for f in rs.slices(register)] == ["long_", "slice", "slice"], "7 h, 30 m"
    assert not list((runner / "judge").glob("*")), "judged once"
    log = [row("1", "HTTP503")] * 20 + ["# pause 900 s: HTTP503"]
    (runner / "judge/2_y.tsv").write_text("\n".join(log) + "\n")
    assert (
        rs.write(data, register, NOW) == "runner slices: 0 cut, 3 gone, 0 keys lent, STOP written"
    )
    stop = register / "STOP"
    assert (
        stop.read_text() == rs.HEAD + "2_y: 1 pauses of 15 min or more, 0 of 20 requests answered\n"
    )
    assert rs.blocked(["# pause 1800 s: HTTP429"]).startswith("1 pauses of 15 min or more")
    assert rs.blocked(["# pause 60 s: HTTP503"] * 9) == "", (
        "a Retry-After is a throttle, not a refusal"
    )
    assert not rs.slices(register) and rs.keys(runner / "lent.txt") == set()
    assert rs.write(data, register, NOW).endswith(", STOP"), "held until a PR lifts it"
    stop.unlink()
    assert rs.write(data, register, NOW) == "runner slices: 1 cut, 0 gone, 5 keys lent"
    assert not stop.exists(), "a judged log never latches STOP again"
    (register / "cadence").write_text("0\n")
    (register / "long").write_text("0\n")
    assert rs.write(data, register, NOW).startswith("runner slices: 0 cut, 1 gone"), "zeroed: off"
    assert not rs.slices(register)
    assert rs.blocked([row("1", "ConnectionRefusedError")] * 18 + [row("2", "200")] * 2) == ""
    assert rs.blocked([row("1", "HTTP403")] * 19 + [row("2", "200")]) == "1 of 20 requests answered"


def test_dispatch_asks_each_workflow_one_job_while_its_slice_waits_and_no_run_is_live(
    tmp_path, monkeypatch
):
    register = tmp_path / "docs/registers/runner"
    register.mkdir(parents=True)
    (register / "cadence").write_text("1\n")
    calls, runs = [], [{"status": "completed"}]

    def gh(*args, timeout):
        calls.append(args)
        return json.dumps(runs).encode()

    monkeypatch.setattr(rs, "gh", gh)
    assert rs.dispatch(register) == "runner dispatch: slice no slice, long off" and calls == []
    (register / "slice_20261109T110000Z_0.txt").write_text(rs.HEAD + KEY.format(1) + " all\n")
    assert rs.dispatch(register) == "runner dispatch: slice asked, long off"
    hosted = rs.LANES["slice"].workflow
    listing = ("run", "list", "--repo", rs.GITHUB, "--workflow", hosted, "--limit", "5")
    assert calls[0] == (*listing, "--json", "status")
    assert calls[1] == ("workflow", "run", hosted, "--repo", rs.GITHUB, "--ref", "live")
    (register / "long").write_text("1\n")
    (register / "long_20261109T110000Z_0.txt").write_text(rs.HEAD + KEY.format(2) + " all\n")
    runs.append({"status": "queued"})
    assert rs.dispatch(register) == "runner dispatch: slice 1 live, long 1 live"
    assert len(calls) == 4 and calls[3][5] == rs.LANES["long"].workflow
    (register / "STOP").write_text(rs.HEAD)
    assert rs.dispatch(register) == "runner dispatch: slice off, long off" and len(calls) == 4


def zipped(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, body in members.items():
            zf.writestr(name, body)
    return buf.getvalue()


def art(aid: int, name: str, head: str = "live", own: bool = True) -> dict:
    run = {"repository_id": 7, "head_repository_id": 7 if own else 8, "head_branch": head}
    return {"id": aid, "name": name, "expired": False, "workflow_run": run}


def test_pull_banks_an_own_live_artifact_once_through_the_allowlist(tmp_path, monkeypatch):
    data = tmp_path / "data"
    core, ext = data / "raw/cdx_suffix", data / "raw/extended/ia_cdx_hostnames"
    ext.mkdir(parents=True)
    journal = "walk_co.uk_ps1000_p1_1996-2013.jsonl.gz"
    (ext / journal).write_bytes(b"kept")
    state = "cdx_walk/lane0/"
    walked = {
        state + "log.tsv": (row("1", "200") + "\n" + row("4", "200") + "\n").encode(),
        state + "done.txt": f"{KEY.format(1)}\n{KEY.format(4)}\n{SUB}\n".encode(),
        state + "pending.txt": f"{SUB} all\tcut\t{KEY.format(4)}\tk5\n".encode(),
        "cdx_suffix/" + journal: b"new",
        "extended/ia_cdx_hostnames/" + journal: b"again",
        "cdx_suffix/evil.sh": b"x",
        "../evil.txt": b"x",
        "cdx_walk/lane0/pages.json": b"{}",
    }
    zips = {
        "1": zipped(walked),
        "5": zipped({state + "log.tsv": b"# order 0 priced, 1 exploring\n"}),
    }
    listing = [
        art(1, NAME),
        art(2, "slice_20261109T110000Z_1_r0", own=False),
        art(3, "slice_20261109T110000Z_2_r0", head="main"),
        art(4, "ci-logs"),
        art(5, "slice_20261109T113000Z_0_r1"),
    ]
    calls = []

    def gh(*args, timeout):
        calls.append(args[1])
        if args[1].endswith("/zip"):
            return zips[args[1].split("/")[-2]]
        return json.dumps({"artifacts": listing}).encode()

    monkeypatch.setattr(rs, "gh", gh)
    assert rs.pull(data) == "runner slices: 2 artifacts banked, 3 members dropped"
    assert (core / journal).read_bytes() == b"new" and (ext / journal).read_bytes() == b"kept"
    assert not (data / "raw/cdx_suffix/evil.sh").exists() and not (tmp_path / "evil.txt").exists()
    runner0 = data / "raw/cdx_walk/runner0"
    assert rs.keys(runner0 / "done.txt") == {KEY.format(1), SUB}, (
        "a cut parent still owed is not done"
    )
    log = (runner0 / "log.tsv").read_text().splitlines()
    assert log == [f"# artifact 1 {NAME}", row("1", "200"), row("4", "200")]
    assert (data / "raw/cdx_walk/runner1/log.tsv").read_text().startswith("# artifact 5 ")
    assert any(fnmatch.fnmatch("data/raw/cdx_walk/runner1/log.tsv", g) for g in trigger.FOLD)
    assert not any(fnmatch.fnmatch("data/raw/cdx_walk/runner/log.tsv", g) for g in trigger.FOLD)
    judge = data / "raw/cdx_walk/runner/judge"
    assert sorted(p.name for p in judge.glob("*")) == [
        f"1_{NAME}.tsv",
        "5_slice_20261109T113000Z_0_r1.tsv",
    ]
    assert rs.lines(data / "raw/cdx_walk/runner/banked.txt") == [
        f"1\t{NAME}",
        "5\tslice_20261109T113000Z_0_r1",
    ]
    assert not list((data / "raw/cdx_walk/runner").glob("pull_*"))
    assert rs.pull(data) == "runner slices: 0 artifacts banked, 0 members dropped"
    assert [c for c in calls if c.endswith("/zip")] == [
        f"repos/{rs.GITHUB}/actions/artifacts/{i}/zip" for i in (1, 5)
    ]
    assert (runner0 / "log.tsv").read_text().splitlines() == log, "banked once"
