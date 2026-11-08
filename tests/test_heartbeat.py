"""The tick's row, the VM's alerts and the daily heartbeat (scripts/harness/heartbeat.py)."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/harness/heartbeat.py"
GIB = 1024**3


@pytest.fixture
def hb(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("heartbeat", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (tmp_path / "data/logs").mkdir(parents=True)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "LOGS", tmp_path / "data/logs")
    monkeypatch.setattr(mod, "TICKS", tmp_path / "data/logs/ticks.tsv")
    monkeypatch.setattr(mod, "DISK", tmp_path / "data/logs/disk.tsv")
    monkeypatch.setattr(mod, "STATE", tmp_path / "state")
    monkeypatch.setattr(mod, "REBOOT", tmp_path / "reboot-required")
    monkeypatch.setenv("ARK_FREE_SPACE_GIB", "0.001")
    monkeypatch.setenv("ARK_WRITE_BUDGET_GIB", "0.001")
    mod.issues, mod.calls, mod.expiry = [], [], "2099-01-01 00:00:00 UTC"

    def gh(*args):
        mod.calls.append(args)
        if args[:2] == ("api", "-i"):
            return 0, f"HTTP/2 200\ngithub-authentication-token-expiration: {mod.expiry}\n\n{{}}"
        if args[:2] == ("issue", "list"):
            return 0, json.dumps(mod.issues)
        return 0, ""

    monkeypatch.setattr(mod, "gh", gh)
    return mod


def stamp(at: dt.datetime) -> str:
    return at.strftime("%Y%m%dT%H%MZ")


def run(hb, tmp_path, at: str, sync_rc=0, check_rc=0, sync="bank: nothing arrived", check="ok"):
    (tmp_path / "sync.out").write_text(sync + "\n")
    (tmp_path / "check.out").write_text(check + "\nunattended: ok\n")
    args = [at, str(time.time()), str(sync_rc), str(check_rc)]
    return hb.main([*args, str(tmp_path / "sync.out"), str(tmp_path / "check.out")])


def made(hb, verb: str) -> list[str]:
    return [
        c[c.index("--title") + 1] if verb == "create" else c[2]
        for c in hb.calls
        if c[:2] == ("issue", verb)
    ]


def test_verdicts(hb, tmp_path):
    t0 = time.time() - 5
    assert hb.verdict(0, "held\n", t0)[0] == "held"
    assert (
        hb.verdict(0, "a sync is already running\n  here: ... This one stops\n", t0)[0] == "refused"
    )
    assert hb.verdict(1, "boom\n", t0) == ("refused", "sync exit 1: boom")
    assert hb.verdict(0, "bank: nothing arrived\n", t0) == ("idle", "bank: nothing arrived")
    (tmp_path / "data/logs/bank_stamp.json").write_text("{}")
    assert hb.verdict(0, "", t0) == ("banked", "banked")
    (tmp_path / "data/logs/bank_red.json").write_text("{}")
    assert hb.verdict(1, "bank: BANK RED since x step y\n", t0) == (
        "red",
        "bank: BANK RED since x step y",
    )


def test_rows_kept_ninety_days(hb):
    now = dt.datetime(2026, 11, 7, 6, 5, tzinfo=dt.UTC)
    old = [stamp(now - dt.timedelta(days=91)), "idle", "1", "x"]
    hb.append(old, now - dt.timedelta(days=91))
    kept = hb.append([stamp(now), "banked", "2", "banked"], now)
    assert [r[0] for r in kept] == [stamp(now)]
    assert hb.TICKS.read_text().count("\n") == 1


def test_lane_stalls_only_with_work_queued(hb, tmp_path):
    now = dt.datetime.now(dt.UTC)
    lane = tmp_path / "data/raw/cdx_walk/lane0"
    lane.mkdir(parents=True)
    row = "\t".join(
        ["com.sg", "100", "5", "1996", "2013", "all", "200", "1", "1.0", "9", "9", "1", "0"]
    )
    old = stamp(now - dt.timedelta(hours=7)).replace("Z", "00Z")
    (lane / "log.tsv").write_text(f"{old}\t{row}\n# exit {old} pending=0\n")
    assert hb.lane(0, now, {"lane0": "2026-11-07: page 1 of 1 answered"}) == (
        False,
        "lane0: 2026-11-07: page 1 of 1 answered",
    )
    (lane / "pending.txt").write_text("task\n")
    assert hb.lane(0, now, {})[0] is True
    (lane / "pending.txt").write_text("")
    (lane / "log.tsv").write_text(f"{old}\t{row}\n")  # no exit row: still walking
    assert hb.lane(0, now, {})[0] is True
    (tmp_path / "state").mkdir()
    (tmp_path / "state/pause-platform").write_text("")
    assert hb.lane(0, now, {})[0] is None
    assert hb.lane(1, now, {}) == (None, "lane1: not walked here")


def test_each_cause_opens_once_and_reopens(hb, tmp_path):
    now = dt.datetime.now(dt.UTC)
    earlier = stamp(now - dt.timedelta(days=2))
    torn = "2026-11-0\tidle\t1\n"
    hb.TICKS.write_text(f"{torn}{earlier}\trefused\t1\tsync exit 1\n")
    shrinking(hb, now.date(), 100.0, 3.0)
    (tmp_path / "data/logs/bank_red.json").write_text("{}")
    lane = tmp_path / "data/raw/cdx_walk/lane2"
    lane.mkdir(parents=True)
    (lane / "log.tsv").write_text("")
    (lane / "pending.txt").write_text("task\n")
    hb.expiry = (now + dt.timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S UTC")
    hb.REBOOT.write_text("")
    (tmp_path / "data/logs/.reboot_seen").write_text("")
    os.utime(tmp_path / "data/logs/.reboot_seen", (time.time() - 25 * 3600,) * 2)
    at = now.strftime("%Y%m%dT0505Z")
    run(hb, tmp_path, at, 1, 1, sync="bank: BANK RED since x", check="FAIL lane1: stopped")
    titles = made(hb, "create")
    assert sorted(titles) == sorted(
        f"vm-alert: {c}"
        for c in (
            "check lane1",
            "BANK RED",
            "lane2 stalled",
            "no agent success in 24 h",
            "disk under 14 days",
            "gh token under 14 days",
            "no Claude pre-flight ok in 24 h",
            "no offsite listing in 24 h",
            "reboot pending 24 h",
        )
    )
    # the red gone and a refused tick before: open ones stay single, a closed one reopens
    (tmp_path / "data/logs/bank_red.json").unlink()
    hb.TICKS.write_text(f"{earlier}\trefused\t1\tsync exit 1\n")
    hb.issues = [{"number": i, "title": t, "state": "OPEN"} for i, t in enumerate(titles)]
    hb.issues[0]["state"] = "CLOSED"
    hb.calls.clear()
    run(hb, tmp_path, at, 1, 1, sync="boom", check="FAIL lane1: stopped")
    assert made(hb, "create") == ["vm-alert: two refused ticks"]
    assert made(hb, "reopen") == ["0"]


def ledger_row(at: dt.datetime, outcome: str, five="0.0", seven="0.0") -> str:
    return "\t".join([stamp(at), "work", "m", "1", "1", "1", "0.1", five, seven, "9", outcome])


def test_preflight_and_offsite_read_their_records(hb, tmp_path):
    now = dt.datetime.now(dt.UTC)
    ledger = tmp_path / "data/logs/agent_runs.tsv"
    assert hb.preflight(now) == (False, "claude token: no pre-flight ok")
    old, fresh = now - dt.timedelta(hours=25), now - dt.timedelta(hours=2)
    rows = [
        "stamp\tmode\tmodel\tturns\ttokens_in\ttokens_out\tcost_usd\tfive_hour_pct\tseven_day_pct\tseconds\toutcome",
        ledger_row(old, "success:over-cap", "2.0", "33.0"),
        ledger_row(fresh, "paced:backing off until x"),  # before the pre-flight: no windows
        ledger_row(fresh, "preflight-failed:401"),
        "torn\trow",
        ledger_row(now, "held"),
    ]
    ledger.write_text("\n".join(rows) + "\n")
    ok, line = hb.preflight(now)
    assert (ok, line) == (False, f"claude token: pre-flight ok at {stamp(old)}")
    answered = ("paced:seven-day window at 40%", "rate-limited:x", "error_max_turns", "failed:1")
    for outcome in answered:
        rows.insert(-1, ledger_row(fresh, outcome, "0.0", "40.0"))
        ledger.write_text("\n".join(rows) + "\n")
        assert hb.preflight(now) == (True, f"claude token: pre-flight ok at {stamp(fresh)}")
        rows.pop(-2)
    ledger.write_text("\n".join(rows[:1] + rows[2:]) + "\n")
    assert hb.preflight(now) == (False, "claude token: no pre-flight ok, last row held")

    listed = tmp_path / "data/logs/.offsite_listed"
    assert hb.offsite(now) == (False, "offsite: never listed")
    listed.write_text("not a stamp\n")
    assert hb.offsite(now) == (False, "offsite: never listed")
    listed.write_text(stamp(old) + "\n")
    assert hb.offsite(now) == (False, f"offsite: listed at {stamp(old)}")
    listed.write_text(stamp(fresh) + "\n")
    assert hb.offsite(now) == (True, f"offsite: listed at {stamp(fresh)}")

    ledger.write_text("\n".join(rows) + "\n")
    run(hb, tmp_path, now.strftime("%Y%m%dT0505Z"))
    assert "vm-alert: no Claude pre-flight ok in 24 h" in made(hb, "create")
    assert "vm-alert: no offsite listing in 24 h" not in made(hb, "create")


def shrinking(hb, today: dt.date, free: float, a_day: float) -> None:
    """Eight daily readings ending today at `free` GiB, falling `a_day`; the floor at 70."""
    hb.DISK.write_text(
        "".join(
            f"{today - dt.timedelta(days=n)}\t{free + n * a_day:.1f}\n" for n in range(7, -1, -1)
        )
    )
    hb.space = lambda root: (0, [f"space data: {free:.1f} GiB free, need 70.0 GiB (50 floor)"])


def test_days_to_floor_from_the_daily_readings(hb):
    today = dt.date(2026, 11, 8)
    shrinking(hb, today, 100.0, 1.0)
    assert hb.disk(today) == (30.0, "disk: 100.0 GiB free, need 70.0, 30 days to floor")
    shrinking(hb, today, 100.0, -1.0)
    assert hb.disk(today) == (None, "disk: 100.0 GiB free, need 70.0, not shrinking")
    hb.DISK.write_text(f"{today}\t100.0\n")
    assert hb.disk(today)[1].endswith("1 reading, no 7-day rate yet")
    # the day's reading is its first tick's
    hb.DISK.unlink()
    hb.record(today, 99.0)
    hb.record(today, 98.0)
    assert hb.DISK.read_text() == f"{today}\t99.0\n"


def test_heartbeat_once_at_six(hb, tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/ROUND.md").write_text("x\nGATE. 1996-2001 : a\nGATE. 2002-2013 : b\n")
    (tmp_path / "data/logs/agent_runs.tsv").write_text(
        "\t".join(
            [
                stamp(dt.datetime.now(dt.UTC)),
                "work",
                "m",
                "1",
                "1",
                "1",
                "0.1",
                "2.0",
                "33.0",
                "9",
                "success:over-cap",
            ]
        )
        + "\n"
    )
    now = dt.datetime.now(dt.UTC)
    (tmp_path / "data/logs/.offsite_listed").write_text(stamp(now) + "\n")
    run(hb, tmp_path, now.strftime("%Y%m%dT0505Z"))
    assert not [c for c in hb.calls if c[:2] == ("issue", "create")] and not hb.DISK.exists()
    run(hb, tmp_path, now.strftime("%Y%m%dT0605Z"))
    assert hb.DISK.read_text().startswith(f"{now.date()}\t")
    body = next(c for c in hb.calls if c[:2] == ("issue", "create"))
    text = body[body.index("--body") + 1]
    lines = text.splitlines()
    assert lines[1:3] == ["GATE. 1996-2001 : a", "GATE. 2002-2013 : b"]
    assert "unattended: ok" in lines and "hold: none" in lines
    assert any(ln.startswith("ticks in 24 h: 0 banked, 0 refused") for ln in lines)
    assert any(ln.startswith("agent: 1 runs, 1 succeeded, windows 2.0% of 5 h") for ln in lines)
    hb.issues = [{"number": 7, "title": "VM heartbeat", "state": "OPEN"}]
    hb.calls.clear()
    run(hb, tmp_path, now.strftime("%Y%m%dT0605Z"))
    assert not [c for c in hb.calls if c[1] in ("comment", "create")]
    os.remove(tmp_path / "data/logs/.heartbeat_day")
    run(hb, tmp_path, now.strftime("%Y%m%dT0605Z"))
    assert [c[2] for c in hb.calls if c[:2] == ("issue", "comment")] == ["7"]


def test_a_body_failing_the_scan_is_replaced(hb):
    assert hb.clean("plain words", "x") == "plain words"
    assert hb.clean("a dash " + chr(0x2014) + " here", "x").startswith(
        "(the body failed the public scan"
    )
