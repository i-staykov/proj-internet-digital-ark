"""IA CDX lookups, the platform walker and page expansion, offline: every `fetch` and `sleep` is
injected, so nothing here asks the archive anything."""

import email.utils
import gzip
import importlib.util
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

from ark import cdx, expand
from ark.cdx import REFUSED, TIMED_OUT, RateGovernor, answered, lookup_years

ROOT = Path(__file__).resolve().parents[1]
WALK = ROOT / "scripts" / "engines" / "cdx_platform_walk.py"
_SPEC = importlib.util.spec_from_file_location("walk", WALK)
walk = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(walk)

ONLY_2XX_3XX = "filter=statuscode%3A%5B23%5D%5B0-9%5D%5B0-9%5D"


def gov(delay: float = 0.0, min_delay: float = 0.0, sleep=None, **kw) -> RateGovernor:
    return RateGovernor(delay=delay, min_delay=min_delay, sleep=sleep or (lambda _s: None), **kw)


def test_every_query_asks_one_bounded_question_for_captures_the_host_answered() -> None:
    wide = cdx.cdx_url("example.com", 1996, 2001)
    assert "url=%2A.example.com" in wide and "collapse=timestamp%3A4" in wide
    probe = cdx.year_probe_url("foo.com", 1998)
    assert "from=1998&to=1998" in probe and probe.endswith("&limit=1") and "collapse" not in probe
    # every shape keeps the host the archive named, and never an error capture
    for url in (wide, cdx.host_url("foo.com", 1996, 2001), cdx.root_url("foo.com", 1996, 2001)):
        assert "from=1996&to=2001" in url and "limit=" in url, url
    for url in (wide, probe, cdx.host_url("a.com", 1996, 2001), cdx.root_url("a.com", 1996, 2001)):
        assert ONLY_2XX_3XX in url and "fl=timestamp%2Coriginal" in url, url
    # expansion asks one exact page's in-window captures, then their original bytes
    captures = expand.page_captures_url("http://x.com/", 1996, 2001, limit=3)
    assert "from=1996&to=2001" in captures and "statuscode%3A200" in captures
    snapshot = expand.snapshot_url("19980101000000", "http://x.com/")
    assert snapshot == "https://web.archive.org/web/19980101000000id_/http://x.com/"


def test_parsing_keeps_the_window_and_the_earliest_stamp_per_host() -> None:
    body = (
        "19980101000000 http://www.foo.com/\n19980102000000 http://www.foo.com/deeper/page.html\n"
        "19990202000000 http://shop.foo.com:80/x\n20040101000000 http://late.foo.com/\n"
        "19970101000000 not-a-url\nrubbish\n"
    )
    assert cdx.years_in(body, 1996, 2001) == {1997, 1998, 1999}
    hosts = {"www.foo.com": "19980101000000", "shop.foo.com": "19990202000000"}
    assert cdx.hosts_in(body, 1996, 2001) == hosts
    # a `timestamp`-only response yields no host rather than misparsing
    assert cdx.hosts_in("19980101000000\n19990101000000\n", 1996, 2001) == {}
    # exactly the years returned, nothing adjacent, nothing out of window
    assert list(cdx.evidence_years({"years": [1996, 1999, 2005]}, 1996, 2001)) == [1996, 1999]


def test_a_throttle_sleeps_out_its_retry_after_then_succeeds(monkeypatch) -> None:
    calls, slept = [], []

    def flaky(_url: str) -> tuple[int, str]:
        calls.append(1)
        return (429, "1") if len(calls) == 1 else (200, "19980101000000\n")

    governor = gov(sleep=slept.append)
    record = lookup_years("x.com", 1996, 2001, fetch=flaky, governor=governor)
    assert (record["years"], len(calls), governor.throttles) == ([1998], 2, 1)
    assert len(slept) == 1 and 0.5 < slept[0] <= 1.0, slept

    # the transport hands the server's Retry-After up as the body of a throttle
    def throttled(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 429, "slow", {"Retry-After": "7"}, None)

    monkeypatch.setattr(urllib.request, "urlopen", throttled)
    assert cdx._http_get("https://example.invalid/cdx") == (429, "7")


def test_a_truncated_response_probes_only_the_years_it_missed_unless_switched_off() -> None:
    def answer(url: str) -> tuple[int, str]:
        if "from=1996&to=2001" in url:
            return 200, "19980101000000\n19980202000000\n"
        return (200, "20000505000000\n") if "from=2000&to=2000" in url else (200, "")

    # limit=2, so the two rows of the first page count as truncated
    asked, common = [], {"governor": gov(), "limit": 2, "host_first": False}
    record = lookup_years("x.com", 1996, 2001, lambda u: asked.append(u) or answer(u), **common)
    assert (record["truncated"], record["years"]) == (True, [1998, 2000])
    assert not any("from=1998&to=1998" in u for u in asked), "a year already seen is re-probed"
    record = lookup_years("x.com", 1996, 2001, fetch=answer, probe_missing=False, **common)
    assert (record["truncated"], record["years"]) == (True, [1998])


def test_the_governor_backs_off_eases_up_and_never_paces_below_its_floor() -> None:
    governor, paces = gov(delay=1.0, min_delay=0.1, ramp_after=2, backoff_factor=2.0), []
    for step in (governor.on_throttle, governor.on_success, governor.on_success):
        step()
        paces.append(governor.delay)
    # a multiplicative decrease in pace, held until enough successes, then eased
    assert paces[:2] == [2.0, 2.0] and paces[2] < 2.0
    floor = gov(delay=0.12, min_delay=0.1, ramp_after=1)
    for _ in range(20):
        floor.on_success()
    assert floor.delay == 0.1


def test_the_breaker_trips_only_on_an_unbroken_run_of_refusals() -> None:
    governor, before = gov(breaker_after=3, breaker_pause=30.0), time.monotonic()
    for _ in range(3):
        governor.on_throttle(refused=True)
    assert governor.breaker_trips == 1
    # the pause is on the shared next-start time, so it holds the whole pool off
    assert governor._next_at >= before + 30.0
    forgiven = gov(breaker_after=3)
    for success in (False, False, True, False, False):
        forgiven.on_success() if success else forgiven.on_throttle(refused=True)
    assert forgiven.breaker_trips == 0, "a success broke the run"
    # 503 means the host answered; only a refused connection means it stopped talking
    served = gov(breaker_after=2)
    for _ in range(6):
        served.on_throttle()
    assert served.breaker_trips == 0


def test_a_timeout_and_a_refusal_are_told_apart() -> None:
    """A refusal is the host rate-limiting us and slows the pace. A timeout is the server
    failing a heavy question: asked once, and no evidence about the pace."""
    assert cdx._is_timeout(TimeoutError()) is True
    # urllib wraps the timeout in URLError.reason, which is the shape seen in the wild
    assert cdx._is_timeout(urllib.error.URLError(TimeoutError())) is True
    assert cdx._is_timeout(urllib.error.URLError(OSError(50, "Network is down"))) is False
    assert cdx._is_timeout(ConnectionResetError()) is False
    for status, asks, slower in ((REFUSED, 4, True), (TIMED_OUT, 1, False)):
        asked, governor = [], gov(delay=1.0, min_delay=0.1, backoff_factor=2.0)
        fetch = lambda u, s=status, a=asked: a.append(u) or (s, "")  # noqa: E731
        assert (cdx._fetch_retrying("q", fetch, governor, 4)[0], len(asked)) == (status, asks)
        assert (governor.throttles > 0, governor.delay > 1.0) == (slower, slower)


SHAPES = (("matchType=host", "host"), ("%2A.", "scan"), ("url=www.", "www"))


def shapes(**answers):
    """A fake CDX answering by the shape of the question, and naming each shape it was asked."""
    asked = []

    def fetch(url: str) -> tuple[int, str]:
        shape = next((name for key, name in SHAPES if key in url), "apex")
        if not asked or asked[-1] != shape:
            asked.append(shape)
        return answers.get(shape, (200, ""))

    return fetch, asked


B97 = (200, "19970101000000 http://www.foo.com/\n19990505000000 http://a.foo.com/x\n")
ROOTS = {"apex": (200, "19980101000000 http://foo.com/\n")}
ROOTS["www"] = (200, "20000202000000 http://www.foo.com/\n")
BIG_HOST, BIG_SCAN = ROOTS | {"host": (504, "")}, ROOTS | {"scan": (504, "")}
Y97, H97 = [1997, 1999], ["a.foo.com", "www.foo.com"]
Y98, H98 = [1998, 2000], ["foo.com", "www.foo.com"]
# case: host first, what each shape answers, (status, years, strategy, hosts), the shapes asked
TIERS = {
    "the-host-answers-and-no-scan-runs": (1, {"host": B97}, (200, Y97, "by_host", H97), "host"),
    "an-empty-host-buys-the-scan": (1, {"scan": B97}, (200, Y97, None, H97), "host scan"),
    "a-failed-scan-still-settles-it": (1, BIG_SCAN, (200, [], "by_host", []), "host scan"),
    "a-refused-host-buys-no-scan": (1, {"host": (REFUSED, "")}, (REFUSED, [], None, []), "host"),
    "a-big-host-asks-the-roots": (1, BIG_HOST, (200, Y98, "by_root", H98), "host apex www"),
    "a-big-scan-asks-the-roots": (0, BIG_SCAN, (200, Y98, "by_root", H98), "scan apex www"),
    "an-answered-scan-is-never-replaced": (0, {"scan": B97}, (200, Y97, None, H97), "scan"),
}


def test_each_tier_answers_what_the_cheaper_one_cannot() -> None:
    """Every tier that misanswers is listed at once, with what it asked."""
    wrong = {}
    for case, (host_first, answers, want, want_asked) in TIERS.items():
        fetch, asked = shapes(**answers)
        r = lookup_years("foo.com", 1996, 2001, fetch, gov(), host_first=bool(host_first))
        got = (r["status"], r["years"], r.get("strategy"), sorted(r.get("hosts", {})))
        if (got, " ".join(asked)) != (want, want_asked):
            wrong[case] = (got, asked)
    assert wrong == {}


def test_only_a_real_reply_settles_a_domain_or_a_page() -> None:
    """The evidence wall rests on this: an unanswered question is not a no."""
    for settled in (answered, expand.answered):
        assert settled({"status": 200}) is True
        assert [s for s in (0, 503, 504, TIMED_OUT, REFUSED) if settled({"status": s})] == []
    record = lookup_years("hopeless.com", 1996, 2001, fetch=lambda _u: (504, ""), governor=gov())
    assert (answered(record), record["years"]) == (False, [])


def test_per_year_collects_every_year_that_answers_and_a_failed_probe_is_unknown() -> None:
    def partial(url: str) -> tuple[int, str]:
        if "from=1998" in url:
            return 0, ""  # this year is unknown, not absent
        return (200, "19970601120000 http://a.x.com/\n") if "from=1997" in url else (200, "")

    r = cdx.lookup_years_per_year("x.com", 1996, 2001, fetch=partial, governor=gov())
    got = (r["years"], r["status"], r["probe_failures"], list(r["hosts"]))
    assert got == ([1997], 200, 1, ["a.x.com"]), "a partial answer is still an answer"
    # every probe failed, so the domain stays unanswered and is retried later
    r = cdx.lookup_years_per_year("x.com", 1996, 2001, fetch=lambda _u: (0, ""), governor=gov())
    assert (r["years"], answered(r)) == ([], False)


# ---------------------------------------------------------------- the platform walker


def _args(tmp_path: Path) -> SimpleNamespace:
    (out := tmp_path / "out").mkdir(exist_ok=True)
    (state := tmp_path / "state").mkdir(exist_ok=True)
    walker = {"limit": 3, "delay": 0, "rotate": 25, "timeout": 5}
    return SimpleNamespace(deadline=9e9, out=out, state_dir=state, **walker)


def _fake(monkeypatch, tmp_path, answers):
    monkeypatch.setattr(walk, "PAUSE_FLAG", tmp_path / "pause-platform")
    slept, asked, calls = [], [], iter(answers)
    monkeypatch.setattr(walk.time, "sleep", slept.append)
    monkeypatch.setattr(walk, "fetch", lambda params, _t: asked.append(dict(params)) or next(calls))
    return slept, asked


def test_the_walk_follows_the_key_dedupes_and_marks_done(tmp_path, monkeypatch):
    page1 = (
        "http://x.a.net:80/ 19990101000000 200\nhttp://x.a.net/p.html 19990601000000 301\n"
        "http://other.com/ 19990101000000 200\n\nKEY1\n"
    )
    page2 = "http://y.a.net/ 20010101000000 200\nhttp://x.a.net/ 20000101000000 200\n"
    _, asked = _fake(monkeypatch, tmp_path, [("200", page1, None)] + [("200", page2, None)] * 2)
    args = _args(tmp_path)
    assert walk.Walk("a.net", args).run().startswith("done: 2 pages, 3 host-years")
    assert "resumeKey" not in asked[0] and asked[1]["resumeKey"] == asked[2]["resumeKey"] == "KEY1"
    # no collapse: it folds a host into its neighbour whenever both sit in one year
    assert asked[0]["fl"] == "original,timestamp,statuscode" and "collapse" not in asked[0]
    stamps = ["http://x.a.net:80/ 1999", "http://y.a.net/ 2001", "http://x.a.net/ 2000"]
    journals = sorted(args.out.glob("suffix_a_net_rk_*.jsonl.gz"))
    rows = [json.loads(ln) for j in journals for ln in gzip.decompress(j.read_bytes()).splitlines()]
    assert [f"{r['url']} {r['timestamp'][:4]}" for r in rows] == stamps
    assert (args.state_dir / "a_net.done").exists() and not list(args.out.glob("*.part"))


def test_a_failed_walk_is_never_marked_done(tmp_path, monkeypatch):
    args, ok = _args(tmp_path), ("200", "http://x.a.net/ 19990101000000 200\n\nKEY1\n", None)
    _fake(monkeypatch, tmp_path, [ok] + [("ERR:TimeoutError", "", None)] * 3)
    assert "resumable" in walk.Walk("a.net", args).run()
    state = json.loads((args.state_dir / "a_net.state.json").read_text())
    assert (state["resume_key"], state["pages"]) == ("KEY1", 1)
    _fake(monkeypatch, tmp_path, [("HTTP403", "", None)])
    assert "parked" in walk.Walk("b.net", args).run()
    for run in range(3):  # a giant whose page the server cannot finish, three runs running
        _fake(monkeypatch, tmp_path, [("HTTP504", "", None)] * 3)
        assert ("parked" in walk.Walk("c.net", args).run()) == (run == 2)
    parked = sorted(p.name for p in args.state_dir.glob("*.refused"))
    assert (parked, list(args.state_dir.glob("*.done"))) == (["b_net.refused", "c_net.refused"], [])
    # a new process picks up the saved key
    _, asked = _fake(monkeypatch, tmp_path, [("200", "", None)] * 2)
    assert walk.Walk("a.net", args).run().startswith("done") and asked[0]["resumeKey"] == "KEY1"


def test_retry_after_is_slept_and_five_throttles_stop_the_client(tmp_path, monkeypatch):
    soon = email.utils.formatdate(time.time() + 60, usegmt=True)
    assert [walk.retry_after(v) for v in ("42", "-5", "soon", None)] == [42.0, 0.0, None, None]
    assert 50 < walk.retry_after(soon) <= 60
    slept, _ = _fake(monkeypatch, tmp_path, [("HTTP429", "", 42.0), ("200", "", None)])
    assert walk.Walk("a.net", _args(tmp_path)).run().startswith("done")
    assert 42.0 in slept
    _fake(monkeypatch, tmp_path, [("REFUSED", "", None)] * 5)
    with pytest.raises(SystemExit):
        walk.Walk("b.net", _args(tmp_path)).run()


def test_an_open_journal_is_a_part_and_one_a_killed_run_left_is_promoted(tmp_path):
    args = _args(tmp_path)
    left = args.out / "suffix_a_net_rk_20260923T080000Z_00000.jsonl.gz.part"
    with gzip.open(left, "wt") as fh:
        fh.write('{"url": "http://x.a.net/", "timestamp": "19990101000000", "status": "200"}\n')
    one = walk.Walk("a.net", args)
    promoted = left.with_name(left.name.removesuffix(".part"))
    assert not left.exists() and promoted.exists()
    # The sync pulls `suffix_*.jsonl.gz`, so an open journal stays behind only as a `.part`.
    one.write([["http://y.a.net/", "20000101000000", "200"]])
    assert sorted(args.out.iterdir()) == sorted([promoted, one.part])
    assert one.part.name.endswith(".jsonl.gz.part")
    one.close()


def test_lanes_split_the_seeds_disjointly():
    seeds = [f"p{i}.net" for i in range(60)]
    lanes = [[s for s in seeds if walk.mine(s, k, 3)] for k in range(3)]
    assert sorted(sum(lanes, [])) == sorted(seeds) and all(lanes)


# ---------------------------------------------------------------- page expansion

# Every link shape a page of the era carries; a click tracker's host is the portal's own.
PAGE = """<html><body>
  <a href="http://www.example.com/index.html">absolute</a> <a href="#top">fragment</a>
  <a href="http://shop.example.com/">same registered domain as the one above</a>
  <a href="/local/page.html">relative, resolves to the page's own domain</a> <a>no href</a>
  <a href="mailto:someone@nowhere.org">mail</a> <a href="javascript:void(0)">script</a>
  <a href="https://other.co.uk/deep/path?q=1">another domain, https</a>
  <a href="http://srd.yahoo.com/goo/Arts/*http://shop.tracked.org/x">click tracker</a>
  <a href="http://count.example/r?url=http%3A%2F%2Fwww.target.org%2Fa">encoded tracker</a>
  <a href="http://ok.com/">unclosed <b> <a href=http://bare.net/>bare attribute
"""


def test_outbound_domains_are_the_other_registered_domains() -> None:
    found = expand.outbound_domains(PAGE, "http://www.host.com/dir/index.html")
    assert found == "example.com other.co.uk tracked.org target.org ok.com bare.net".split()


def test_read_seeds_parses_the_directory_assertion() -> None:
    lines = ["http://p.example/", "http://c.example/\tdirectory", "# a comment", "   "]
    lines += ["http://s.example/\tDIRECTORY", "http://n.example/\tnot-a-directory"]
    want = [("http://p.example/", False), ("http://c.example/", True), ("http://s.example/", True)]
    assert expand.read_seeds(lines) == want + [("http://n.example/", False)]


LINK = '<a href="http://found.com/">x</a>'
EXPANDS = {  # what the CDX and the snapshot answer, and the (status, year, domains) recorded
    "one-record-per-capture-year": (
        (200, "19970101000000\n19990101000000\n"),
        (200, LINK),
        [(200, 1997, ["found.com"]), (200, 1999, ["found.com"])],
    ),
    "a-failed-page-fetch-is-asked-again": ((200, "19970101000000\n"), (503, ""), [(503, 1997, [])]),
    "no-in-window-capture-is-settled": ((200, "20080101000000\n"), (200, LINK), [(200, None, [])]),
}


@pytest.mark.parametrize(("captures", "snapshot", "want"), EXPANDS.values(), ids=EXPANDS)
def test_expand_page_records_each_capture_year_and_settles_only_a_reply(captures, snapshot, want):
    fetch = lambda url: captures if "cdx/search" in url else snapshot  # noqa: E731
    records = expand.expand_page("http://seed.org/", 1996, 2001, fetch, gov(), curated=True)
    assert [(r["status"], r["year"], r["domains"]) for r in records] == want
    assert all(r["curated"] for r in records)


def test_corroboration_keeps_known_names_curated_and_routes_the_rest() -> None:
    # archived HTML carries typos like arvard.edu for harvard.edu, so the split is per name
    page = dict(page_url="http://c/", year=1999, status=200, curated=True)
    listed = [{**page, "domains": ["known.com", "arvard.edu", "also-known.org"]}]
    curated, unverified = expand.split_by_corroboration(listed, {"known.com", "also-known.org"})
    assert curated[0]["domains"] == ["known.com", "also-known.org"] and curated[0]["curated"]
    assert unverified[0]["domains"] == ["arvard.edu"]
    assert unverified[0]["curated"] is False, "a candidate earns its own year"
    unseen = [{**page, "domains": ["never-seen.example"]}]
    assert expand.split_by_corroboration(unseen, set())[0] == []
