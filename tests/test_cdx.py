"""The CDX lanes the VM's cron runs (`scripts/engines/cdx_extended_walk.py`, with the helpers it
loads from `cdx_platform_walk.py`), the walk order (`cdx_walk_order.py`) and the pool's questions
(`pool_questions.py`), offline: every `fetch` and `sleep` is injected, so nothing here asks the
archive anything."""

import email.utils
import json
import time
import urllib.error
import urllib.request
from types import SimpleNamespace

from conftest import script

walk = script("engines/cdx_platform_walk.py")


def test_retry_after_is_seconds_or_a_date_and_a_throttle_hands_it_up(monkeypatch):
    def throttled(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 429, "slow", {"Retry-After": "7"}, None)

    monkeypatch.setattr(urllib.request, "urlopen", throttled)
    assert walk.fetch({"url": "a.net"}, 5) == ("HTTP429", "", 7.0)
    soon = email.utils.formatdate(time.time() + 60, usegmt=True)
    assert [walk.retry_after(v) for v in ("42", "-5", "soon", None)] == [42.0, 0.0, None, None]
    assert 50 < walk.retry_after(soon) <= 60


def test_lanes_split_the_seeds_disjointly_and_a_row_is_read_by_its_host():
    seeds = [f"p{i}.net" for i in range(60)]
    lanes = [[s for s in seeds if walk.mine(s, k, 3)] for k in range(3)]
    assert sorted(sum(lanes, [])) == sorted(seeds) and all(lanes)
    rows = ("http://X.a.net:80/p", "x.a.net.", "http://[bad/")
    assert [walk.host_of(u) for u in rows] == ["x.a.net", "x.a.net", None]


extended = script("engines/cdx_extended_walk.py")
order = script("engines/cdx_walk_order.py")


def test_extended_walk_reasks_a_cut_page_last_subpage_first_and_probes_a_silent_one():
    task = ("co.uk", 1000, 7, 1996, 2013, "all")
    cut = extended.subpages(task, cut=True)
    assert cut == [("co.uk", 100, 70 + k, 1996, 2013, "all") for k in range(9, -1, -1)]
    assert [t[2] for t in extended.subpages(task, cut=False)] == [70, 75]
    assert extended.subpages(("co.uk", 100, 70, 1996, 2013, "all"), cut=False) == []


def test_extended_walk_asks_the_best_ee_a_second_first_whichever_window_pays():
    prices = {
        "com.pk all": {"p1": 0.14, "p2": 40.7, "s": 40},
        "co.nz all": {"p1": 0.0, "p2": 100.0, "s": 600},  # more a request, less a second
        "me.uk all": {"p1": 0.0, "p2": 11156.4, "s": 300},
        "co.uk p1": {"p1": 40.84, "p2": 0.0, "s": 10},
        "gov.au all": {"p1": 0.0, "p2": 0.0, "n": 6},
        "on.ca all": {"p1": 0.0, "p2": 0.0, "n": 1},
    }
    units = [tuple(u.split()) for u in prices]
    priced, exploring, waiting, early = extended.rank(units, prices, {("on.ca", "all"): 0}, 2, 10)
    assert priced == [("me.uk", "all"), ("co.uk", "p1"), ("com.pk", "all"), ("co.nz", "all")]
    assert early == [("co.uk", "p1"), ("com.pk", "all")], "1996 to 2001 alone, a second"
    assert exploring == [("on.ca", "all")] and waiting == []


def test_extended_walk_asks_questions_once_pages_pay_less_a_second_at_their_laws_price():
    prices = {"me.uk all": {"p2": 11156.0, "s": 300}, "co.nz all": {"p2": 0.5, "s": 50}}
    prices |= {"ask-edge ask": {"n": 1999}, "ask-pool ask": {"n": 5000}, "ask-x ask": {"n": 3000}}
    units = [tuple(u.split()) for u in [*prices, "ask-gap ask"]]
    priced, exploring, waiting, early = extended.rank(units, prices, {}, 2, 10.0)
    want = [("me.uk", "all"), ("ask-gap", "ask"), ("co.nz", "all")]
    assert early == [("ask-gap", "ask")], "pages paying 2002 on never lead"
    assert priced == want and exploring == [], "laws price at the 10 s floor: 0.23 a s"
    assert waiting == [("ask-edge", "ask"), ("ask-x", "ask")], "an unpriced tier waits; pool drops"


def test_extended_walk_gives_early_starts_of_four_to_1996_to_2001_ahead_of_owed_subpages(
    tmp_path,
):
    (tmp_path / "o.json").write_text('{"units": {"me.uk all": {"p2": 900.0, "s": 60, "n": 9}}}')
    a = SimpleNamespace(state_dir=tmp_path, order=tmp_path / "o.json", data=tmp_path)
    a.questions, a.min_interval = True, 10
    lane = extended.Lane(a)
    asks = [("ask-gap", 1, f"d{n}.com", 1996, 2013, "ask") for n in range(9)]
    pages = [("me.uk", 1000, n, 1996, 2013, "all") for n in range(9)]
    lane.pages = {("ask-gap", "ask"): asks, ("me.uk", "all"): pages}
    lane.asked = dict.fromkeys(lane.pages, 0)
    lane.rerank(force=True)
    lane.subq = [("co.uk", 100, n, 1996, 2013, "all") for n in range(9)]
    kinds = [lane.take()[5] for _ in range(8)]
    assert kinds.count("ask") == 2 * extended.EARLY and "all" in kinds, kinds


def test_walk_order_charges_a_unit_every_second_over_its_answers():
    units, names = {}, {}
    rows = [("co.uk", "200", 30), ("co.uk", "HTTP503", 5), ("co.uk", "HTTP504", 60)]
    rows += [("on.ca", "ConnectionRefusedError", 4)]
    lines = [
        "\t".join(["s", sfx, "1000", "1", "1996", "2013", "all", st, "0", str(t), *"0000"])
        for sfx, st, t in rows
    ]
    order.charge(lines, units, names)
    assert order.prices(units) == {"co.uk all": {"p1": 0.0, "p2": 0.0, "n": 2, "s": 47.5}}


def test_extended_walk_books_only_answers_and_keeps_owed_subpages_across_a_restart(tmp_path):
    a = SimpleNamespace(
        state_dir=tmp_path, order=tmp_path / "o.json", max_transient=0, data=tmp_path
    )
    a.questions, a.min_interval = False, 10
    page = ("co.uk", 1000, 7, 1996, 2013, "all")

    def lane_with(page):
        lane = extended.Lane(a)
        lane.pages, lane.asked = {("co.uk", "all"): [page]}, {("co.uk", "all"): 0}
        lane.rerank(force=True)
        return lane

    lane = lane_with(page)
    lane.settle(("on.ca", 100, 279, 1996, 2013, "all"), "HTTP400", False, 0, [], None, ["row"])
    silent = ("on.ca", 100, 280, 1996, 2013, "all")
    lane.subq, lane.meta[silent] = [silent], ("probe", "on.ca 1000 28 1996 2013", "")
    for _ in range(4):  # a silent subpage is asked again at once, never pausing the lane
        assert lane.take() == silent and "on.ca 100 280 1996 2013" not in lane.done
        lane.settle(silent, "HTTP504", False, 0, [], None, ["row"])
        assert not lane.pause_until
    assert {f"on.ca 100 {n} 1996 2013" for n in (279, 280)} <= lane.done and lane.subq == []
    assert lane.take() == page
    lane.settle(page, "SSLZeroReturnError", False, 0, [], None, ["row"])
    assert "co.uk 1000 7 1996 2013" not in lane.done, "an unknown failure is no answer"
    assert lane.take() == page
    lane.settle(page, "200", False, 5, ["k1", "k5"], None, ["row"])  # cut at k5
    p9 = lane.take()
    assert p9[1:3] == (100, 79)
    for n in range(10):  # flat a minute, then an address block's 15 after ten in a row
        lane.pause_until = 0
        lane.settle(p9, "HTTP503", False, 0, [], None, ["row"])  # backed off, still owed
        assert round(lane.pause_until - time.time(), -1) == (900 if n == 9 else 60)
        assert lane.take() == p9
    restarted = lane_with(page)
    assert restarted.subq[0] == p9 and restarted.meta[p9] == ("cut", "co.uk 1000 7 1996 2013", "k5")
    p9 = restarted.take()
    restarted.settle(p9, "200", True, 3, ["k8", "k9"], None, ["row"])
    p8 = restarted.take()
    restarted.settle(p8, "200", True, 3, ["k4", "k6"], None, ["row"])  # holds the cut row
    assert restarted.subq == [], "the subpages below the cut row were received before it"


def test_a_200_cut_before_its_first_row_is_a_dropped_connection_until_the_cap(tmp_path):
    a = SimpleNamespace(state_dir=tmp_path, order=tmp_path / "o.json", max_transient=1)
    a.data, a.questions, a.min_interval = tmp_path, False, 10
    lane = extended.Lane(a)
    pages = [("co.uk", 1000, n, 1996, 2013, "all") for n in (7, 8)]
    lane.pages, lane.asked = {("co.uk", "all"): pages}, {("co.uk", "all"): 0}
    lane.rerank(force=True)
    page = lane.take()
    lane.settle(page, "200", False, 0, [], None, ["row"])
    assert lane.take() == page and round(lane.pause_until - time.time()) == 5
    assert lane.refused == lane.refusal_end == 0, "no refusal and no refusal pause"
    lane.settle(page, "200", False, 0, [], None, ["row"])  # past the cap: the refusal's ladder
    assert lane.refused == 1 and round(lane.refusal_end - time.time()) == 30


def test_a_parked_subpage_is_asked_on_the_next_start_until_its_third_park(tmp_path):
    a = SimpleNamespace(state_dir=tmp_path, order=tmp_path / "o.json", data=tmp_path)
    a.questions, a.min_interval = False, 10
    sub, meta = ("ac.mz", 100, 1, 1996, 2013, "all"), ("rest", "ac.mz 1000 0 1996 2013", "")
    (tmp_path / "pending.txt").write_text(extended.encode(sub, meta) + "\n")
    for parks in range(1, extended.PARKS + 1):  # each start asks it nine times, then parks it
        lane = extended.Lane(a)
        for _ in range(9):
            assert lane.take() == sub
            lane.settle(sub, "HTTP502", False, 0, [], None, ["row"])
        assert lane.take() is None, "parked: not asked again this start"
        kept = "" if parks == extended.PARKS else extended.encode(sub, (*meta, str(parks))) + "\n"
        assert (tmp_path / "pending.txt").read_text() == kept, "kept with its count, then dropped"
    (tmp_path / "pending.txt").write_text(extended.encode(sub, (*meta, "1")) + "\n")
    lane = extended.Lane(a)
    assert lane.take() == sub
    lane.settle(sub, "200", True, 3, ["k1", "k2"], None, ["row"])
    assert "ac.mz 100 1 1996 2013" in lane.done and lane.take() is None


def test_walk_order_finds_a_host_in_a_c_sorted_year_file(tmp_path):
    f = tmp_path / "2001.txt"
    f.write_bytes(b"a.co.uk\nb-c.co.uk\nb.co.uk\nzz.com.au\n")
    release = order.Release(tmp_path)
    assert all(release.holds(2001, h) for h in ("a.co.uk", "b-c.co.uk", "b.co.uk", "zz.com.au"))
    assert not any(release.holds(2001, h) for h in ("a.co", "b.co.ukx", "c.co.uk", "zzz"))


def test_a_low_disk_holds_the_lane_and_an_unreadable_floor_does_not(tmp_path, monkeypatch):
    a = SimpleNamespace(state_dir=tmp_path / "lane0", order=tmp_path / "o.json")
    a.data, a.questions, a.min_interval, a.max_transient = tmp_path, False, 10, 0
    a.state_dir.mkdir()
    lane = extended.Lane(a)
    monkeypatch.setattr(extended._disk, "free", lambda p: 0)
    assert lane.low() is True
    monkeypatch.setenv("ARK_FREE_SPACE_GIB", "fifty")
    assert lane.low() is False and lane.low() is False
    assert (a.state_dir / "log.tsv").read_text().count("# floor unreadable") == 1


def test_a_sibling_lane_answer_ends_only_the_refusal_pause(tmp_path, monkeypatch):
    monkeypatch.setattr(extended._platform, "PAUSE_FLAG", tmp_path / "pause-platform")
    monkeypatch.setattr(extended.time, "sleep", lambda _: extended.STOP.set())  # one gate pass
    lanes = []
    for i in range(2):
        a = SimpleNamespace(state_dir=tmp_path / f"lane{i}", order=tmp_path / "o.json")
        a.data, a.questions, a.min_interval, a.max_transient = tmp_path, False, 10, 0
        a.state_dir.mkdir()
        lanes.append(extended.Lane(a))
    now = time.time()
    lanes[0].refused, lanes[0].refusal_at, lanes[0].refusal_end = 3, now - 1, now + 900
    lanes[0].pause_until = now + 60  # a 503's pause running beside the refusal's
    (tmp_path / "lane0/answered").touch()  # its own answer is not a sibling's
    assert lanes[0].eased() is False
    (tmp_path / "lane1/answered").touch()
    assert lanes[0].gate() is False  # eased, yet the throttle's pause still holds the lane
    extended.STOP.clear()
    assert lanes[0].refusal_end == lanes[0].refused == 0
    assert lanes[0].pause_until == now + 60, "easing never touches the throttle's pause"
    lanes[0].refusal_at = now + 1  # a refusal after that answer: the ladder holds
    assert lanes[0].eased() is False


def test_a_refused_connection_ladder_caps_at_two_minutes_and_a_wall_at_fifteen():
    coin = [extended.refusal_pause(n, "ConnectionRefusedError") for n in range(1, 7)]
    assert coin == [30, 60, 120, 120, 120, 120]
    assert [extended.refusal_pause(n, "HTTP403") for n in (1, 3, 5, 6, 9)] == [
        30,
        120,
        480,
        900,
        900,
    ]
    assert extended.refusal_pause(6, "OSError") == 900, "ENETDOWN is an OSError, a wall"


def test_pool_questions_bracket_the_2001_edge_by_his_2002_file(tmp_path, monkeypatch, capsys):
    import duckdb

    from ark import held

    pq = script("engines/pool_questions.py")
    release, data = tmp_path / "release", tmp_path / "data"
    (data / "queue").mkdir(parents=True)
    his_years = {1998: ["gap.com"], 2000: ["gap.com", "edge.com", "both.com", "x.com", "plain.com"]}
    his_years[2001] = ["both.com"]
    years = {}
    for y in range(1996, 2002):
        years[y] = release / f"{y}.txt"
        years[y].parent.mkdir(exist_ok=True)
        years[y].write_text("".join(n + "\n" for n in sorted(his_years.get(y, []))))
    (release / "all.txt").write_text(
        "".join(n + "\n" for n in sorted({*his_years[2000], "gap.com"}))
    )
    (release / "2002.txt").write_text("Edge.com\r\nours.com\nboth.com\ngap.com\npool.com\nx.com\n")
    his = held.Held("m", release, release, years, release / "all.txt", release / "c", (), {})
    monkeypatch.setattr(held, "load", lambda baseline=None: his)
    monkeypatch.setattr(pq, "queried_domains", lambda *_: {"x.com"})
    monkeypatch.setattr(pq, "english_weights", lambda: {"com": 1.0})
    monkeypatch.setattr(pq, "DATA", data)
    monkeypatch.setattr(pq, "OUT", data / "queue/pool_questions.tsv")
    conn = duckdb.connect(str(data / "ark.duckdb"))
    conn.execute("CREATE TABLE domain (domain TEXT, tld TEXT)")
    conn.execute("CREATE TABLE domain_year (domain TEXT, assigned_year INTEGER)")
    names = ["gap.com", "edge.com", "ours.com", "both.com", "x.com", "pool.com", "plain.com"]
    conn.executemany("INSERT INTO domain VALUES (?, 'com')", [(n,) for n in names])
    conn.execute("INSERT INTO domain_year VALUES ('ours.com', 2000)")  # dated by us: held
    conn.close()
    pq.main()
    tiers = dict(ln.split("\t")[::-1] for ln in pq.OUT.read_text().splitlines())
    assert tiers == {
        "gap.com": "gap",
        "edge.com": "edge-2002",
        "ours.com": "edge-2002",
        "plain.com": "edge",
        "pool.com": "pool",
    }, "2000 held, 2001 not, in his 2002 file; both.com holds 2001; x.com was asked"
    assert "'edge-2002': 2" in capsys.readouterr().out, "the tier's size is the laws row"


def test_a_unit_measured_under_both_floors_drops_and_the_2002_edge_runs_to_its_measurement(
    tmp_path, monkeypatch
):
    floors = {"1996-2001": 1.0, "2002-2013": 100.0}
    prices = {
        "co.nz all": {"p1": 0.5, "p2": 90.0, "n": 5, "s": 50},
        "co.nz p1": {"p1": 0.5, "p2": 90.0, "n": 1, "s": 50},
        "me.uk all": {"p1": 0.0, "p2": 1354.0, "n": 9, "s": 300},
    }
    edge = ("ask-edge-2002", "ask")
    units = [*(tuple(u.split()) for u in prices), edge]
    priced, _, waiting, early = extended.rank(units, prices, {}, 2, 10.0, floors)
    assert priced == [("me.uk", "all"), ("co.nz", "p1"), edge], "unmeasured, the edge at 0.26"
    prices["ask-edge-2002 ask"] = {"p1": 0.2645, "p2": 0.0, "n": 2000, "s": 4.0}
    assert edge not in sum(extended.rank(units, prices, {}, 2, 10.0, floors), [])
    assert edge in extended.rank(units, prices, {}, 2, 10.0)[0], "no floor, no stop"
    (tmp_path / "queue").mkdir()
    (tmp_path / "baseline.json").write_text('{"current": {"directory": "his", "marker": "m"}}')
    (tmp_path / "queue/cdx_order.json").write_text(json.dumps({"units": prices, "floor": floors}))
    monkeypatch.setattr(order, "DATA", tmp_path)
    order.main()  # re-priced, the floor kept
    a = SimpleNamespace(state_dir=tmp_path, order=tmp_path / "queue/cdx_order.json", data=tmp_path)
    a.questions, a.min_interval = True, 10

    def lane_asks() -> tuple | None:
        lane = extended.Lane(a)
        lane.pages = {edge: [("ask-edge-2002", 1, "e.com", 1996, 2013, "ask")]}
        lane.asked = {edge: 0}
        lane.rerank(force=True)
        return lane.take()

    assert lane_asks() is None, "the floor is read from cdx_order.json"
    for bad in (1, {"1996-2001": "inf"}, {"2002-2013": 10**309}):
        a.order.write_text(json.dumps({"units": prices, "floor": bad}))
        assert lane_asks(), "a bare-number, infinite or overflowing floor is unread, units read"
