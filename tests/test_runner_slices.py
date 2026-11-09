"""Slices cut and lent, artifacts pulled and banked (scripts/engines/runner_slices.py)."""

from __future__ import annotations

import datetime as dt
import fnmatch
import io
import json
import zipfile

from conftest import script

rs = script("engines/runner_slices.py")
trigger = script("harness/bank_trigger.py")
NOW = dt.datetime(2026, 11, 9, 12, 0, tzinfo=dt.UTC)
KEY = "co.uk 1000 {} 1996 2013"
SUB = "co.uk 100 40 1996 2013"
NAME = "slice_20261109T110000Z_0_r0"


def row(page: str, status: str, size: str = "1000") -> str:
    cols = ["20261109T100000Z", "co.uk", size, page, "1996", "2013", "all", status, "1", "9"]
    return "\t".join([*cols, "0", "0", "0", "0"])


def stage(tmp_path):
    """A bank host's data/ with its lanes installed: a counted suffix, a done page, an order."""
    data, register = tmp_path / "data", tmp_path / "docs/registers/runner"
    lane = data / "raw/cdx_walk/lane0"
    lane.mkdir(parents=True)
    (lane / "pages.json").write_text('{"co.uk": 12}')
    (lane / "done.txt").write_text(KEY.format(3) + "\n")
    (data / "queue").mkdir()
    order = {"units": {"co.uk all": {"p1": 1.0, "p2": 1.0, "s": 10, "n": 9}}}
    (data / "queue/cdx_order.json").write_text(json.dumps(order))
    register.mkdir(parents=True)
    (register / "cadence").write_text("# slices kept cut\n2\n")
    return data, register


def test_write_cuts_a_slice_of_pages_neither_done_nor_lent_and_lends_them(tmp_path, monkeypatch):
    data, register = stage(tmp_path)
    monkeypatch.setattr(rs, "PAGES", 4)
    (register / "slice_20261109T110000Z_0.txt").write_text(rs.HEAD + KEY.format(7) + " all\n")
    runner0 = data / "raw/cdx_walk/runner0"
    runner0.mkdir()
    (runner0 / "done.txt").write_text(KEY.format(9) + "\n")
    line = rs.write(data, register, NOW)
    assert line == "runner slices: 1 cut, 0 gone, 6 keys lent"
    new = register / "slice_20261109T120000Z_0.txt"
    text = new.read_text()
    assert text.startswith(rs.HEAD) and len(rs.lines(new)) == 4
    assert all(
        ln.startswith("co.uk 1000 ") and ln.endswith(" 1996 2013 all") for ln in rs.lines(new)
    )
    out = {int(k.split()[2]) for k in rs.keys(new)}
    assert out.isdisjoint({3, 7, 9}), "done, lent and a runner's answer stay out"
    lent = data / "raw/cdx_walk/runner/lent.txt"
    assert lent.read_text().startswith(rs.HEAD)
    assert rs.keys(lent) == rs.keys(new) | {KEY.format(7), KEY.format(9)}
    assert not (data / "raw/cdx_walk/runner/pending.txt").exists(), "the throwaway saves nothing"
    assert rs.write(data, register, NOW).startswith("runner slices: 0 cut"), "the cadence is met"


def test_write_drops_banked_and_stale_slices_and_stops_only_on_a_judged_refusal(tmp_path):
    data, register = stage(tmp_path)
    runner = data / "raw/cdx_walk/runner"
    (runner / "judge").mkdir(parents=True)
    (runner / "banked.txt").write_text(f"1\t{NAME}\n")
    for stem, page in (
        ("20261109T050000Z_0", 1),
        ("20261109T110000Z_0", 2),
        ("20261109T113000Z_0", 4),
    ):
        (register / f"slice_{stem}.txt").write_text(rs.HEAD + KEY.format(page) + " all\n")
    (runner / "judge/1_x.tsv").write_text("".join(row("1", "HTTP503") + "\n" for _ in range(5)))
    assert rs.write(data, register, NOW) == "runner slices: 1 cut, 2 gone, 11 keys lent"
    assert not (register / "STOP").exists(), "five requests are under the floor"
    assert not (register / "slice_20261109T050000Z_0.txt").exists(), "7 h old"
    assert not (register / "slice_20261109T110000Z_0.txt").exists(), "banked"
    assert (register / "slice_20261109T113000Z_0.txt").exists()
    assert not list((runner / "judge").glob("*")), "judged once"
    log = [row("1", "HTTP503")] * 20 + ["# pause 900 s: HTTP503"]
    (runner / "judge/2_y.tsv").write_text("\n".join(log) + "\n")
    assert (
        rs.write(data, register, NOW) == "runner slices: 0 cut, 2 gone, 0 keys lent, STOP written"
    )
    stop = register / "STOP"
    assert (
        stop.read_text() == rs.HEAD + "2_y: 1 pauses of 15 min or more, 0 of 20 requests answered\n"
    )
    assert rs.blocked(["# pause 1800 s: HTTP429"]).startswith("1 pauses of 15 min or more")
    assert rs.blocked(["# pause 60 s: HTTP503"] * 9) == "", (
        "a Retry-After is a throttle, not a refusal"
    )
    assert not list(register.glob("slice_*")) and rs.keys(runner / "lent.txt") == set()
    assert rs.write(data, register, NOW).endswith(", STOP"), "held until a PR lifts it"
    stop.unlink()
    assert rs.write(data, register, NOW) == "runner slices: 1 cut, 0 gone, 11 keys lent"
    assert not stop.exists(), "a judged log never latches STOP again"
    (register / "cadence").write_text("0\n")
    assert rs.write(data, register, NOW).startswith("runner slices: 0 cut, 1 gone"), "zeroed: off"
    assert not list(register.glob("slice_*"))
    assert rs.blocked([row("1", "ConnectionRefusedError")] * 18 + [row("2", "200")] * 2) == ""
    assert rs.blocked([row("1", "HTTP403")] * 19 + [row("2", "200")]) == "1 of 20 requests answered"


def test_dispatch_asks_one_job_while_a_slice_waits_and_no_run_is_live(tmp_path, monkeypatch):
    register = tmp_path / "docs/registers/runner"
    register.mkdir(parents=True)
    (register / "cadence").write_text("1\n")
    calls, runs = [], [{"status": "completed"}]

    def gh(*args, timeout):
        calls.append(args)
        return json.dumps(runs).encode()

    monkeypatch.setattr(rs, "gh", gh)
    assert rs.dispatch(register) == "runner dispatch: no slice" and calls == []
    (register / "slice_20261109T110000Z_0.txt").write_text(rs.HEAD + KEY.format(1) + " all\n")
    assert rs.dispatch(register) == "runner dispatch: a job asked"
    assert calls[0][:2] == ("run", "list") and "--json" in calls[0]
    assert calls[1] == ("workflow", "run", rs.WORKFLOW, "--repo", rs.GITHUB, "--ref", "live")
    runs.append({"status": "queued"})
    assert rs.dispatch(register) == "runner dispatch: 1 live, none asked" and len(calls) == 3
    (register / "STOP").write_text(rs.HEAD)
    assert rs.dispatch(register) == "runner dispatch: off"
    (register / "STOP").unlink()
    (register / "cadence").write_text("0\n")
    assert rs.dispatch(register) == "runner dispatch: off" and len(calls) == 3


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
