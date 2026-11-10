"""The cdx run's row (scripts/agents/lane_yield.py)."""

from __future__ import annotations

import json

from conftest import script

yield_ = script("agents/lane_yield.py")
DATE = "2026-11-07"


def row(stamp: str, sfx: str, page: str, kind: str, status: str, secs: str, complete="1") -> str:
    cols = [stamp, sfx, "1" if kind == "ask" else "1000", page, "1996", "2013", kind]
    return "\t".join([*cols, status, complete, secs, "0", "0", "0", "0"])


def stage(tmp_path):
    lane = tmp_path / "raw/cdx_walk/lane0"
    lane.mkdir(parents=True)
    (lane / "log.tsv").write_text(
        "\n".join(
            [
                "# order 2 priced, 0 exploring",
                row("20261106T235900Z", "co.uk", "1", "all", "HTTP503", "10"),
                "# pause 60 s: HTTP503",  # 10 s of it fall into the date
                row("20261107T000100Z", "co.uk", "2", "p1", "200", "100"),
                row("20261107T000200Z", "co.uk", "3", "all", "200", "50", "0"),
                row("20261107T000300Z", "co.uk", "4", "all", "HTTP504", "60"),
                "# pause 30 s: HTTP504",
                row("20261107T000350Z", "co.uk", "5", "all", "ConnectTimeout", "4"),
                "# pause 30 s: ConnectTimeout",  # overlaps the 504's pause: 36 s, not 60
                row("20261107T000500Z", "ask-gap", "example.co.uk", "ask", "200", "5"),
                row("20261108T000000Z", "co.uk", "6", "all", "200", "5"),
                "",
            ]
        )
    )
    core, ext = "raw/cdx_suffix/", "raw/extended/ia_cdx_hostnames/"
    journals = {
        core + "walk_co.uk_ps1000_p2_1996-2013.jsonl.gz": 2.5,
        ext + "walk_co.uk_ps1000_p2_1996-2013.jsonl.gz": 40.0,
        core + "walk_co.uk_ps1000_p3_1996-2013_cut_20261107T000200Z.jsonl.gz": 1.5,
        core + "walk_ask-gap_ps1_pexample.co.uk_1996-2013.jsonl.gz": 0.013,
    }
    (tmp_path / "queue").mkdir()
    (tmp_path / "queue/cdx_order.priced.json").write_text(json.dumps({"journals": journals}))
    return tmp_path / "productivity.tsv"


def test_a_day_is_counted_priced_by_window_and_split_by_kind(tmp_path):
    out = stage(tmp_path)
    assert yield_.write(out, tmp_path, DATE) == 4
    rows = yield_.read(out)
    # the lane's wall: 00:00 (the pause running in) to 00:05:05, 305 s
    assert rows[0][:9] == [DATE, "lane0", "ask-gap", "1996-2001", "1", "1", "0", "0.01", "0.00004"]
    assert rows[2][:9] == [DATE, "lane0", "page", "1996-2001", "4", "3", "46", "4.00", "0.01311"]
    assert rows[3][:9] == [DATE, "lane0", "page", "2002-2013", "4", "3", "46", "40.00", "0.13115"]
    assert all(r[9:] == ["", "", ""] for r in rows)
    assert yield_.lines(out)["lane0"].startswith(
        f"{DATE}: ask-gap 1 of 1 answered, 0 s paused, 0.01 EE 1996-2001 at 0.00004 a second, "
    )
    # the header lane's row: what the bank's header candidates gained, tick to tick
    tick = "{}\tbanked\t9\tbanked\t300.0000\t{}\n"
    ticks = tick.format("20261106T2305Z", "100.5") + "20261107T0005Z\tidle\t9\tno output\n"
    ticks += tick.format("20261107T2305Z", "180.5") + tick.format("20261108T0005Z", "200.5")
    (tmp_path / "ticks.tsv").write_text(ticks)
    assert yield_.write(out, tmp_path, DATE) == 5
    banked = ["header", "banked", "1996-2001", "", "", "", "0.00", "", "", "", "100.00"]
    assert yield_.read(out)[0] == [DATE, *banked] and "header" not in yield_.lines(out)


def test_a_rerun_replaces_the_date_and_the_band_is_the_previous_seven_rows(tmp_path):
    out = stage(tmp_path)
    earlier = [
        "\t".join([f"2026-11-0{d}", "lane0", "page", "2002-2013", "1", "1", "0", "1", r, "", ""])
        for d, r in zip(range(1, 7), ("0.5", "0.1", "0.4", "0.2", "0.3", "0.9"), strict=True)
    ]
    out.write_text("\t".join(yield_.HEADER) + "\n" + "\n".join(earlier) + "\n")
    yield_.write(out, tmp_path, DATE)
    yield_.write(out, tmp_path, DATE)
    rows = yield_.read(out)
    assert [r[0] for r in rows] == [r.split("\t")[0] for r in earlier] + [DATE] * 4
    assert rows[-1][3:-1] == ["2002-2013", "4", "3", "46", "40.00", "0.13115", "0.10000", "0.90000"]
    assert rows[-2][9:] == ["", "", ""]  # 1996-2001 has no earlier row, a walk no candidate_ee
    assert yield_.lines(out)["lane0"].endswith("a second (band 0.10000 to 0.90000)")
    out.write_text(out.read_text() + "2026-11-08\tlane1\tpage\t1996-2001\t1\t1\t0\t1\t0.5\t\t\n")
    assert yield_.lines(out)["lane0"].startswith(DATE)  # each lane's own last date
    assert yield_.LEVERS.exists() and json.loads(yield_.LEVERS.read_text())["version"] == 1


def test_a_window_row_counts_its_hours_beside_the_date_and_bands_on_its_hour(tmp_path):
    out = stage(tmp_path)
    key = f"{DATE}T0100"
    hours = (("04", "01", "0.2"), ("05", "01", "0.3"), ("06", "01", "0.4"), ("06", "05", "9"))
    earlier = [
        f"2026-11-{d}T{hh}00\tlane0\tpage\t2002-2013\t1\t1\t0\t1\t{r}\t\t" for d, hh, r in hours
    ]
    out.write_text("\t".join(yield_.HEADER) + "\n" + "\n".join(earlier) + "\n")
    yield_.write(out, tmp_path, DATE)
    date_rows = [ln for ln in out.read_text().splitlines() if ln.startswith(DATE + "\t")]
    assert yield_.write(out, tmp_path, key, hours=2) == 4
    rows = yield_.read(out)
    # 23:00 to 01:00: the 503 row and its whole pause join the date's; wall 23:59:00 to 00:05:05
    assert rows[-2][:9] == [key, "lane0", "page", "1996-2001", "5", "3", "96", "4.00", "0.01096"]
    assert rows[-1][3:-1] == ["2002-2013", "5", "3", "96", "40.00", "0.10959", "0.20000", "0.40000"]
    assert [ln for ln in out.read_text().splitlines() if ln.startswith(DATE + "\t")] == date_rows
    assert yield_.write(out, tmp_path, DATE) == 4 and len(yield_.read(out)) == 12
    assert yield_.lines(out)["lane0"].startswith(DATE + ": ")
    assert yield_.lines(out)["lane0"].endswith("a second")  # the daily band ignores the hours
    # the hours are priced by the tick at or after the key's hour, banked or idle; else no row
    ticks = tmp_path / "ticks.tsv"
    assert yield_.unpriced(ticks, key) == "last tick none"
    for stamp, verdict in (("20261107T0005Z", "banked"), ("20261107T0105Z", "refused")):
        ticks.write_text(f"{stamp}\t{verdict}\t9\tbanked\n")
        assert yield_.unpriced(ticks, key) == f"last tick {stamp} {verdict}"
    ticks.write_text("20261107T0105Z\tidle\t9\tno output\n")
    assert yield_.unpriced(ticks, key) == ""
