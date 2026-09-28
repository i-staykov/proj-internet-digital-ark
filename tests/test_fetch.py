"""fetch.py on loopback hosts that log each request: a robots refusal costs the artifact zero
requests, the cap holds when `Content-Length` lies, and no Wayback CDX url is ever asked.
The subprocess runs are the exit-code guards; the rest call `fetch.fetch` in process."""

import hashlib
import importlib.util
import io
import json
import os
import socket
import struct
import subprocess
import sys
import threading
import time
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FETCH = ROOT / "scripts" / "harness" / "fetch.py"
_SPEC = importlib.util.spec_from_file_location("ark_fetch", FETCH)
fetch = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fetch)

PERMISSIVE = "User-agent: *\nDisallow:\n"
# A permissive group first and the refusal by name far below it.
BY_NAME = PERMISSIVE + ("\n# padding\n" * 40) + "User-agent: ClaudeBot\nDisallow: /\n"
STAR = "User-agent: *\nDisallow: /private\n"
NAMED = "User-agent: *\nAllow: /\n\nUser-agent: {}\nDisallow: /data\n"
NARROW = "User-agent: *\nDisallow: /data\nAllow: /data/public\n"
OURS = ("Claude-User", "anthropic-ai", "InternetDigitalArk")
# Longer than two of the 256 KiB chunks `stream` reads, which a reset only ever delivers whole.
PAYLOAD = b"".join(b"com,example%d)/ 1999%08d 200\n" % (i, i) for i in range(18000))
SECOND, WHOLE, BIG = b"second-half", b"first-halfsecond-half", 1 << 40


def page(body: bytes = b"ok\n", kind: str = "text/plain") -> tuple:
    return 200, {"Content-Type": kind}, body


def hop(to: str, status: int = 302) -> tuple:
    return status, {"Location": to}, b""


class Server:
    """A loopback host logging every path and `Range` asked; a callable route gets the handler."""

    def __init__(self, routes: dict):
        self.routes, self.asked, self.ranges = routes, [], []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            log_message = lambda *_: None  # noqa: E731

            def do_GET(self):
                outer.asked.append(self.path)
                outer.ranges.append(self.headers.get("Range"))
                route = outer.routes.get(self.path, (404, {}, b""))
                if isinstance(route, list):  # successive answers, the last one repeated
                    route = route.pop(0) if len(route) > 1 else route[0]
                if callable(route) and (route := route(self)) is None:
                    return
                status, headers, body = route
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                if not {k.lower() for k in headers} & {"content-length", "transfer-encoding"}:
                    self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        # A short poll, or every shutdown at teardown waits half a second for it.
        loop = {"target": self.httpd.serve_forever, "kwargs": {"poll_interval": 0.01}}
        threading.Thread(**loop, daemon=True).start()
        self.base = "http://{}:{}".format(*self.httpd.server_address[:2])


def dropping(payload: bytes, drop: int, reset=False, drop_ranges=False, honour=True):
    """A route serving `bytes=S-E` of `payload` that hangs up or resets `drop` bytes into a 200."""

    def answer(handler):
        span = (handler.headers.get("Range") or "").removeprefix("bytes=")
        body, cut = payload, drop
        if span and honour:
            first, _, last = span.partition("-")
            start, stop = int(first), int(last or len(payload) - 1)
            body = payload[start : stop + 1]
            cut = drop if drop_ranges else len(body)
            handler.send_response(206)
            handler.send_header("Content-Range", f"bytes {start}-{stop}/{len(payload)}")
        else:
            handler.send_response(200)
        handler.send_header("Content-Type", "text/plain")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body[:cut])
        if cut < len(body):
            handler.wfile.flush()
            if reset:  # time for the reader to take what arrived, then a linger of zero
                time.sleep(0.2)
                linger = struct.pack("ii", 1, 0)
                handler.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
            handler.close_connection = True
            handler.connection.close()

    return answer


@pytest.fixture
def leg(tmp_path, monkeypatch):
    """The probe root fetch.py writes under, and `serve` for hosts shut down at teardown."""
    (probe := tmp_path / "probe").mkdir()
    monkeypatch.setenv("ARK_PROBE_DIR", str(probe))
    monkeypatch.delenv("ARK_FETCH_DEST_ROOT", raising=False)
    made = []

    def serve(routes: dict, robots: str | None = PERMISSIVE) -> Server:
        extra = {} if robots is None else {"/robots.txt": page(robots.encode())}
        made.append(Server(extra | routes))
        return made[-1]

    yield types.SimpleNamespace(probe=probe, serve=serve)
    for server in made:
        server.httpd.shutdown()
        server.httpd.server_close()


def run(url: str, *args) -> tuple[int, dict, str, bytes]:
    """fetch.py as a leg runs it: (exit code, receipt, stderr, stdout bytes)."""
    cmd = [sys.executable, str(FETCH), url, *args]
    result = subprocess.run(cmd, capture_output=True, env=os.environ, cwd=ROOT, timeout=60)
    err = result.stderr.decode()
    where = err if "-" in args else result.stdout.decode()
    lines = [line for line in where.splitlines() if line.startswith("{")]
    return result.returncode, json.loads(lines[-1]) if lines else {}, err, result.stdout


def get(url: str, to: str | None = None, **kw) -> tuple[int, dict]:
    return fetch.fetch(url, 1 << 30, to, 5.0, **kw)


@pytest.mark.parametrize(
    ("robots", "path"), [(BY_NAME, "/zones/1999.txt"), (STAR, "/private/x")], ids=["name", "star"]
)
def test_a_robots_refusal_exits_three_with_zero_requests_for_the_artifact(leg, robots, path):
    server = leg.serve({path: page(b"never read\n")}, robots=robots)
    code, receipt, *_ = run(f"{server.base}{path}")
    assert (code, receipt["robots"]) == (fetch.ROBOTS_REFUSED, "refused")
    assert (server.asked, list(leg.probe.iterdir())) == (["/robots.txt"], [])


ROBOTS = [
    (BY_NAME, "/zones/1999.txt", ("refused", 0.0)),
    *((NAMED.format(name), "/data/x.gz", ("refused", 0.0)) for name in OURS),
    (STAR, "/private/x", ("refused", 0.0)),
    (NARROW, "/data/private/x", ("refused", 0.0)),
    (NARROW, "/data/public/x", ("allowed", 0.0)),
    ("User-agent: *\nCrawl-delay: 5\nDisallow:\n", "/x", ("allowed", 5.0)),
]


def test_a_refusal_in_any_of_our_groups_refuses_the_path():
    """Every misread case is listed at once."""
    assert [case for case in ROBOTS if fetch.robots_verdict(*case[:2])[:2] != case[2]] == []


def test_no_robots_is_allowed_and_an_unreadable_or_dead_one_fails_closed(leg):
    assert get(f"{leg.serve({'/x.txt': page()}, robots=None).base}/x.txt")[0] == fetch.OK
    broken = leg.serve({"/robots.txt": (500, {}, b"oops\n"), "/x.txt": page()})
    code, receipt, *_ = run(f"{broken.base}/x.txt")
    assert (code, receipt["robots"]) == (fetch.ROBOTS_UNREADABLE, "unknown")
    assert broken.asked == ["/robots.txt"]
    with socket.socket() as closed:
        closed.bind(("127.0.0.1", 0))
        port = closed.getsockname()[1]
    assert fetch.read_robots(f"http://127.0.0.1:{port}/x.txt", timeout=2.0)[0] == "unknown"


LIAR = {"Content-Type": "text/plain", "Transfer-Encoding": "identity"}
CAPPED = {
    "a-content-length-over-the-default-1G": ({"Content-Length": str(2 << 30)}, b"", None),
    "the-stream-when-the-server-understates-its-length": (LIAR, b"x" * 40_000, 1024),
}


@pytest.mark.parametrize(("headers", "body", "cap"), CAPPED.values(), ids=CAPPED)
def test_over_the_cap_it_stops_and_leaves_nothing_behind(leg, headers, body, cap):
    args = ("--max-bytes", str(cap)) if cap else ()
    code, receipt, *_ = run(f"{leg.serve({'/IA.gz': (200, headers, body)}).base}/IA.gz", *args)
    assert (code, receipt["capped"]) == (fetch.OVER_CAP, True)
    assert f"the {cap or 1 << 30} byte cap" in receipt["reason"]
    assert cap or receipt["bytes"] == 2 << 30, "the leg backlogs the declared size"
    assert list(leg.probe.iterdir()) == [], "a capped fetch must leave nothing behind"
    assert fetch.parse_size("1G") == fetch.parse_size("1GiB") == fetch.parse_size(str(1 << 30))
    assert fetch.parse_size("512m") == 512 << 20
    for bad in ("", "1X", "0"):
        with pytest.raises(ValueError):
            fetch.parse_size(bad)


def test_a_destination_outside_the_roots_is_refused_before_a_request(leg, tmp_path, monkeypatch):
    server = leg.serve({"/x.txt": page()})
    outside = tmp_path / "workspace" / "x.txt"
    outside.parent.mkdir()
    outside.write_text("mine\n")
    # A symlinked parent is the same escape by another route, and so is a symlinked target.
    (leg.probe / "elsewhere").symlink_to(outside.parent, target_is_directory=True)
    (leg.probe / "x.txt").symlink_to(outside)
    escapes = {outside: "outside", leg.probe / "elsewhere/x.txt": "outside"}
    for to, why in (escapes | {leg.probe / "x.txt": "symlink"}).items():
        code, receipt = get(f"{server.base}/x.txt", str(to))
        assert (code, why in receipt["reason"]) == (fetch.USAGE, True), to
    monkeypatch.setenv("ARK_PROBE_DIR", "")
    code, receipt = get(f"{server.base}/x.txt")
    assert (code, "nowhere" in receipt["reason"]) == (fetch.USAGE, True)
    assert (outside.read_text(), server.asked) == ("mine\n", []), "it wrote, or asked robots"


def test_the_content_type_decides_where_the_bytes_may_go(leg, tmp_path, monkeypatch):
    (corpus := tmp_path / "corpus").mkdir()
    risky, exe = page(b"a line\n", "application/octet-stream"), page(b"MZ\n", "application/x-exe")
    url = leg.serve({"/IA.cdxj": risky, "/setup.exe": exe}).base
    assert get(f"{url}/IA.cdxj")[0] == fetch.BAD_TYPE
    # The approved root set elsewhere does not admit a risky type to the probe root.
    monkeypatch.setenv("ARK_FETCH_DEST_ROOT", str(corpus))
    assert get(f"{url}/IA.cdxj")[0] == fetch.BAD_TYPE
    assert (get(f"{url}/IA.cdxj", str(corpus))[0], list(leg.probe.iterdir())) == (fetch.OK, [])
    assert (corpus / "IA.cdxj").read_bytes() == b"a line\n"
    assert get(f"{url}/setup.exe", str(corpus))[0] == fetch.BAD_TYPE
    # In-stream a risky type may be read, and an executable never.
    code, _, err, out = run(f"{url}/IA.cdxj", "--to", "-")
    assert (code, out, list(leg.probe.iterdir())) == (fetch.OK, b"a line\n", []), err
    assert run(f"{url}/setup.exe", "--to", "-")[::3] == (fetch.BAD_TYPE, b"")


def test_every_hop_is_checked_again_and_a_refusing_host_is_never_fetched(leg):
    refuser = leg.serve({"/data.txt": page(b"never read\n")}, robots=BY_NAME)
    code, receipt, *_ = run(f"{leg.serve({'/get': hop(f'{refuser.base}/data.txt')}).base}/get")
    assert (code, receipt["url"]) == (fetch.ROBOTS_REFUSED, f"{refuser.base}/data.txt")
    assert (refuser.asked, list(leg.probe.iterdir())) == (["/robots.txt"], [])
    # within one host the rules in hand are matched against the new path
    server = leg.serve({"/public": hop("/private/x.txt"), "/private/x.txt": page()}, robots=STAR)
    assert get(f"{server.base}/public")[0] == fetch.ROBOTS_REFUSED
    assert server.asked == ["/robots.txt", "/public"], "robots is reused for the second hop"


CDX, WB = "/cdx/search/cdx?url=example.com&matchType=domain", "/__wb/sparkline?url=example.com"


@pytest.mark.parametrize(
    ("start", "refused", "asked"),
    [
        ("{cdx}" + CDX, "{cdx}" + CDX, []),
        ("{cdx}/list.txt", "{cdx}" + CDX, ["/robots.txt", "/list.txt"]),
        ("{landing}/get", "{cdx}" + WB, []),
        ("http://%5B::1/x.txt", "http://%5B::1/x.txt", []),
    ],
    ids=["the-url", "a-hop-within-one-host", "a-hop-onto-another-host", "an-unparsable-host"],
)
def test_the_wayback_cdx_is_asked_nothing_by_the_url_or_any_hop(leg, start, refused, asked):
    """A loopback host is an address, so it could be the Wayback's: not even its robots.txt is
    asked for. Within one host the robots.txt is read, so the hop would be the next request."""
    for to in (None, "-"):  # into the probe root, and into a pipe
        cdx = leg.serve({"/list.txt": hop(CDX), CDX: page(b"com,example)/ 19990101000000\n")})
        at = {"cdx": cdx.base, "landing": leg.serve({"/get": hop(f"{cdx.base}{WB}", 301)}).base}
        code, receipt = get(start.format(**at), to)
        want = (fetch.CDX_REFUSED, refused.format(**at), 0)
        assert (code, receipt["url"], receipt["bytes"]) == want, to
        assert (cdx.asked, list(leg.probe.iterdir())) == (asked, []), to


ADDRESSES = "127.0.0.1 2130706433 0x7f000001 0177.0.0.01 127.1 [::1] [::ffff:127.0.0.1]".split()
ADDRESSES.append("１２７.０.０.１")  # full-width digits
# Any spelling of the host and path; `?Q` is the query `?url=example.com`.
SPELLED = """
https://web.archive.org/cdx/search/cdx?url=example.com&matchType=domain
http://WEB.archive.org.:80//cdx/search/cdx         https://wayback.archive.org/%63dx/search/cdx
https://web.archive.org/web/timemap/cdx?Q          http://www.archive.org/wayback/available?Q
https://web.archive.org/__wb/sparkline?output=json&url=example.com&collection=web
https://web.archive.org/__WB/calendarcaptures/2?url=example.com&date=1999
https://archive.org/wayback/available?url=example.com&timestamp=19990101
https://wayback.archive.org/wayback/available?Q    http://127.0.0.1/cdx/search/cdx?Q
http://[::1]:8080/__wb/sparkline?Q                 https://web.archive.org/web/../cdx/search/cdx?Q
https://web.archive.org/x%3F/%2e%2e/cdx/search/cdx?Q  https://web.archive.org/;/cdx/search/cdx?Q
https://ｗｅｂ.archive.org/cdx/search/cdx?Q  https://web%2Earchive.org/cdx/search/cdx?Q
https://%77eb.archive.org/cdx/search/cdx?Q         https://archive%2Eorg/wayback/available?Q
https://web.archive.org%3A443/cdx/search/cdx?Q     http://127%2E0%2E0%2E1/cdx/search/cdx?Q
""".replace("?Q", "?url=example.com").split()
# An address in any form could be the Wayback's, but its download is not a query.
PATHS = ("/cdx/search/cdx", "/web/timemap/json")
ADDRESSED = [f"http://{host}{path}?url=example.com" for host in ADDRESSES for path in PATHS]
DOWNLOADS = [f"http://{host}/download/x/x.cdx.gz" for host in ADDRESSES]
# A replay, a download, or another host.
NOT_CDX = """
https://archive.org/download/some-item/big.cdx.gz  https://archive.org/cdx/search/cdx
https://archive.org/download/some-item/wayback/available.txt
https://archive%2Eorg/download/some-item/big.cdx.gz  https://ia800100.us.archive.org/cdx/x.cdx.gz
https://web.archive.org/web/2001id_/http://example.com/cdx/list.txt
https://web.archive.org/web/19991128153001/http://example.com/
https://example.org/cdx/search/cdx  https://example.org/__wb/sparkline?url=example.com
http://127.0.0.1/small.cdx
""".split()


def test_cdx_query_reads_every_spelling():
    """Every url that is misread is listed at once."""
    assert [url for url in SPELLED + ADDRESSED if not fetch.cdx_query(url)] == []
    assert [url for url in DOWNLOADS + NOT_CDX if fetch.cdx_query(url)] == []
    with pytest.raises(ValueError):
        fetch.cdx_query("http://%5B::1/x.txt")


def test_retry_after_is_honoured_in_seconds_and_as_a_date():
    assert fetch.retry_after_seconds({"Retry-After": "30"}) == 30.0
    date = {"retry-after": "Sun, 13 Sep 2026 12:00:30 GMT"}
    assert fetch.retry_after_seconds(date, now=1789300800.0) == 30.0
    assert fetch.retry_after_seconds({}) is fetch.retry_after_seconds({"Retry-After": "x"}) is None


def test_a_503_is_retried_and_an_allowed_redirect_followed_to_the_asked_name(leg):
    body, slept = b"org,example)/ 19991128153001\n", []
    final = leg.serve({"/real.gz": (200, {"Content-Type": "application/gzip"}, body)})
    moved = hop(f"{final.base}/real.gz", 301)
    server = leg.serve({"/x.gz": [(503, {"Retry-After": "7"}, b""), moved]})
    code, receipt = get(f"{server.base}/x.gz", sleep=slept.append)
    assert (code, receipt["url"], slept) == (fetch.OK, f"{final.base}/real.gz", [7.0]), receipt
    assert server.asked == ["/robots.txt", "/x.gz", "/x.gz"], "the 503 is asked again once"
    # Named from the URL the caller asked for: a redirect must not move where it writes.
    assert [(p.name, p.read_bytes()) for p in leg.probe.iterdir()] == [("x.gz", body)]
    # the receipt a leg quotes in its finding
    fields = [receipt[k] for k in ("bytes", "sha256", "path", "content_type")]
    sha = hashlib.sha256(body).hexdigest()
    assert fields == [len(body), sha, str(leg.probe / "x.gz"), "application/gzip"]
    # A wait longer than the leg has is a refusal for now, not a nap.
    slept, server.routes["/x.gz"] = [], (503, {"Retry-After": "9000"}, b"")
    code, receipt = get(f"{server.base}/x.gz", sleep=slept.append)
    assert (code, slept) == (fetch.HTTP_FAILED, []) and "longer than we wait" in receipt["reason"]


RESUME = {
    "2gib-wall": ([(206, {}, SECOND)], BIG, False, 21, None, 1),
    "range-ignored": ([(200, {}, WHOLE)], BIG, False, 10, "ignored the Range header", 1),
    "no-progress": ([(206, {}, b"")], BIG, False, 10, "stopped making progress", 2),
    "cap-binds": ([(206, {}, SECOND)], 15, False, 21, "passed the 15 byte cap", 1),
    "throttled": ([(503, {"retry-after": "3"}, b""), (206, {}, SECOND)], BIG, False, 21, None, 2),
    "wrong-byte": ([(206, {"content-range": "bytes 0-20/21"}, WHOLE)], BIG, True, 10, "byte 0,", 1),
}


@pytest.mark.parametrize(
    ("rounds", "cap", "pipe", "got", "why", "asks"), RESUME.values(), ids=RESUME
)
def test_resume_appends_only_the_next_bytes(tmp_path, rounds, cap, pipe, got, why, asks):
    path, calls, slept = tmp_path / "artifact.gz", [], []
    path.write_bytes(b"first-half")
    digest, sink = hashlib.sha256(b"first-half"), io.BytesIO() if pipe else None

    def opener(url, timeout, start=None, end=None):
        calls.append((start, end))
        status, headers, body = rounds[min(len(calls), len(rounds)) - 1]
        return status, headers, io.BytesIO(body)

    dest = None if pipe else str(path)
    total, reason = fetch.resume("h", dest, 10, 21, digest, cap, 5.0, slept.append, opener, sink)
    assert (total, reason is None if why is None else why in reason) == (got, True), reason
    # A bounded span from where it stopped: `bytes=N-` past 2 GiB is answered 206 and empty.
    assert (calls, slept) == ([(10, 20)] * asks, [3.0] * (rounds[0][0] == 503))
    want = (b"" if pipe else b"first-half") + (SECOND if why is None else b"")
    assert (sink.getvalue() if pipe else path.read_bytes()) == want
    assert why or digest.hexdigest() == hashlib.sha256(WHOLE).hexdigest()


def test_a_part_file_from_an_earlier_run_is_continued(leg):
    whole = b"the first part only\n" + b"x" * 80
    server = leg.serve({"/half.txt": dropping(whole, len(whole))})
    (leg.probe / "half.txt").write_bytes(whole[:20])
    code, receipt = get(f"{server.base}/half.txt", str(leg.probe))
    assert (code, receipt["sha256"]) == (fetch.OK, hashlib.sha256(whole).hexdigest()), receipt
    assert (leg.probe / "half.txt").read_bytes() == whole
    assert [r for r in server.ranges if r] == [f"bytes=20-{len(whole) - 1}"]


DROPS = {
    "a-reset-every-round-into-a-pipe": (270_000, True, True, (), True),
    "a-fault-into-a-pipe": (len(PAYLOAD), False, False, ("--fault-after-bytes", "60000"), True),
    "a-fault-into-the-file": (len(PAYLOAD), False, False, ("--fault-after-bytes", "60000"), False),
}


@pytest.mark.parametrize(("drop", "reset", "every", "fault", "pipe"), DROPS.values(), ids=DROPS)
def test_a_dropped_transfer_resumes_every_byte_once(leg, drop, reset, every, fault, pipe):
    """A `--fault-after-bytes` server never hangs up, so its one drop is the one asked for."""
    server = leg.serve({"/read.cdx": dropping(PAYLOAD, drop, reset, every)}, robots=None)
    to = ("--to", "-" if pipe else str(leg.probe / "read.cdx"))
    code, receipt, _, out = run(f"{server.base}/read.cdx", *to, *fault)
    got = out if pipe else (leg.probe / "read.cdx").read_bytes()
    assert (code, got) == (fetch.OK, PAYLOAD), "every byte once, in order and into the same file"
    assert (receipt["bytes"], receipt["sha256"]) == (len(got), hashlib.sha256(got).hexdigest())
    assert receipt["resumes"] >= len(PAYLOAD) // drop if every else receipt["resumes"] == 1
    assert receipt.get("fault_after_bytes") == (int(fault[1]) if fault else None)
    tail = f"bytes=60000-{len(PAYLOAD) - 1}"
    assert reset or server.ranges == [None, None, tail], "robots, then the read and its range"
    assert [p.name for p in leg.probe.iterdir()] == ([] if pipe else ["read.cdx"])


FAULT, IGNORED = "--fault-after-bytes", "ignored the Range header"
CANNOT = {
    "a-fault-at-the-declared-length": (True, ("-", FAULT, str(len(PAYLOAD))), fetch.USAGE, 2, b""),
    "a-fault-under-one-byte": (True, ("-", FAULT, "0"), fetch.USAGE, 0, b""),
    "the-range-ignored-into-a-file": (False, (), fetch.HTTP_FAILED, 3, None),
    "the-range-ignored-into-a-pipe": (False, ("-",), fetch.HTTP_FAILED, 3, PAYLOAD[:60_000]),
}


@pytest.mark.parametrize(("honour", "to", "code", "asks", "out"), CANNOT.values(), ids=CANNOT)
def test_a_transfer_it_cannot_resume_writes_nothing_twice(leg, honour, to, code, asks, out):
    """A fault the declared length cannot honour exits 2; a server ignoring the Range fails."""
    route = dropping(PAYLOAD, len(PAYLOAD) if honour else 60_000, honour=honour)
    server = leg.serve({"/read.cdx": route}, robots=None)
    got, receipt, err, stdout = run(f"{server.base}/read.cdx", *(("--to", *to) if to else ()))
    why = "at least 1" if "0" in to else "declared length above" if honour else IGNORED
    assert (got, why in receipt.get("reason", err), "Traceback" in err) == (code, True, False)
    assert (len(server.asked), list(leg.probe.iterdir())) == (asks, []), "a part-file was left"
    assert out is None or stdout == out, "nothing was written twice"


def test_a_404_a_redirect_loop_or_a_hop_off_http_is_a_failure_not_an_empty_success(leg):
    server = leg.serve({"/a": hop("/b"), "/b": hop("/a"), "/c": hop("file:///x")})
    for path, why in (("/gone.txt", "answered 404"), ("/a", "redirects"), ("/c", "not http")):
        code, receipt = get(f"{server.base}{path}")
        assert (code, receipt["sha256"]) == (fetch.HTTP_FAILED, None) and why in receipt["reason"]
    assert len([p for p in server.asked if p in ("/a", "/b")]) <= fetch.MAX_HOPS + 1
    assert fetch.main(["file:///etc/passwd"]) == fetch.USAGE
