"""fetch.py on loopback hosts that log each request: a robots refusal costs the artifact zero
requests, the cap holds when `Content-Length` lies, and a destination outside the roots opens no
socket."""

import gzip
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
BY_NAME_REFUSAL = PERMISSIVE + ("\n# padding\n" * 40) + "User-agent: ClaudeBot\nDisallow: /\n"
NAMED = "User-agent: *\nAllow: /\n\nUser-agent: {}\nDisallow: /data\n"
OURS = ("Claude-User", "anthropic-ai", "InternetDigitalArk")
NARROW = "User-agent: *\nDisallow: /data\nAllow: /data/public\n"
PAYLOAD = b"".join(b"com,example%d)/ 1999%08d 200\n" % (i, i) for i in range(60000))
SECOND, WHOLE, BIG = b"second-half", b"first-halfsecond-half", 1 << 40
RANGE0 = {"content-range": "bytes 0-20/21"}
CASES = pytest.mark.parametrize("case", [str.title, str.lower], ids=["title-case", "lower-case"])


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

            def log_message(self, *_):
                pass

            def do_GET(self):
                outer.asked.append(self.path)
                outer.ranges.append(self.headers.get("Range"))
                route = outer.routes.get(self.path, (404, {}, b""))
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
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        host, port = self.httpd.server_address[:2]
        self.base = f"http://{host}:{port}"


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
            if reset:
                # Time for the reader to take what arrived, then a linger of zero.
                time.sleep(0.2)
                linger = struct.pack("ii", 1, 0)
                handler.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
            handler.close_connection = True
            handler.connection.close()

    return answer


@pytest.fixture
def leg(tmp_path, monkeypatch):
    """The probe root fetch.py writes under, and `serve` for hosts shut down at teardown."""
    probe = tmp_path / "probe"
    probe.mkdir()
    monkeypatch.setenv("ARK_PROBE_DIR", str(probe))
    monkeypatch.delenv("ARK_FETCH_DEST_ROOT", raising=False)
    made = []

    def serve(routes: dict, robots: str | None = PERMISSIVE) -> Server:
        if robots is not None:
            routes = {"/robots.txt": page(robots.encode()), **routes}
        made.append(Server(routes))
        return made[-1]

    yield types.SimpleNamespace(probe=probe, serve=serve)
    for server in made:
        server.httpd.shutdown()
        server.httpd.server_close()


def run(url: str, *args, env: dict | None = None) -> tuple[int, dict, str, bytes]:
    """fetch.py as a leg runs it: (exit code, receipt, stderr, stdout bytes)."""
    cmd, environ = [sys.executable, str(FETCH), url, *args], {**os.environ, **(env or {})}
    result = subprocess.run(cmd, capture_output=True, env=environ, cwd=ROOT, timeout=60)
    err = result.stderr.decode()
    where = err if "-" in args else result.stdout.decode()
    lines = [line for line in where.splitlines() if line.startswith("{")]
    return result.returncode, json.loads(lines[-1]) if lines else {}, err, result.stdout


def test_a_by_name_refusal_exits_three_with_zero_requests_for_the_artifact(leg):
    server = leg.serve({"/zones/1999.txt": page(b"never read\n")}, robots=BY_NAME_REFUSAL)
    code, receipt, *_ = run(f"{server.base}/zones/1999.txt")
    assert code == fetch.ROBOTS_REFUSED
    assert receipt["robots"] == "refused"
    assert "claudebot" in receipt["reason"].lower()
    assert server.asked == ["/robots.txt"], "the artifact was asked for anyway"
    assert list(leg.probe.iterdir()) == []


ROBOTS = {
    "by-name-below-star": (BY_NAME_REFUSAL, "/zones/1999.txt", ("refused", 0.0)),
    **{n: (NAMED.format(n), "/data/x.gz", ("refused", 0.0)) for n in OURS},
    "star": ("User-agent: *\nDisallow: /private\n", "/private/x", ("refused", 0.0)),
    "outside-the-narrow-allow": (NARROW, "/data/private/x", ("refused", 0.0)),
    "narrower-allow-wins": (NARROW, "/data/public/x", ("allowed", 0.0)),
    "crawl-delay-is-read": ("User-agent: *\nCrawl-delay: 5\nDisallow:\n", "/x", ("allowed", 5.0)),
}


@pytest.mark.parametrize(("text", "path", "expected"), list(ROBOTS.values()), ids=list(ROBOTS))
def test_a_refusal_in_any_of_our_groups_refuses_the_path(text, path, expected):
    assert fetch.robots_verdict(text, path)[:2] == expected


def test_no_robots_is_allowed_and_an_unreadable_or_dead_one_fails_closed(leg):
    open_host = leg.serve({"/x.txt": page()}, robots=None)
    code, receipt, *_ = run(f"{open_host.base}/x.txt")
    assert (code, receipt["robots"]) == (fetch.OK, "allowed")
    broken = leg.serve({"/robots.txt": (500, {}, b"oops\n"), "/x.txt": page()})
    code, receipt, *_ = run(f"{broken.base}/x.txt")
    assert (code, receipt["robots"]) == (fetch.ROBOTS_UNREADABLE, "unknown")
    assert broken.asked == ["/robots.txt"]
    with socket.socket() as closed:
        closed.bind(("127.0.0.1", 0))
        port = closed.getsockname()[1]
    verdict, _, why = fetch.read_robots(f"http://127.0.0.1:{port}/x.txt", timeout=2.0)
    assert verdict == "unknown", why


@CASES
def test_a_two_gigabyte_content_length_stops_at_the_cap_and_reads_no_body(leg, case):
    two_gb = 2 * 1024**3
    headers = {case("content-type"): "application/gzip", case("content-length"): str(two_gb)}
    server = leg.serve({"/IA.cdxj.gz": (200, headers, b"")})
    code, receipt, *_ = run(f"{server.base}/IA.cdxj.gz")  # the default cap is 1G
    assert code == fetch.OVER_CAP, receipt
    assert receipt["capped"] is True
    assert receipt["bytes"] == two_gb
    assert "downloads.md" in receipt["reason"]
    assert list(leg.probe.iterdir()) == [], "a capped fetch must leave nothing behind"


def test_the_stream_is_counted_when_the_server_understates_its_length(leg):
    liar = {"Content-Type": "text/plain", "Transfer-Encoding": "identity"}
    server = leg.serve({"/liar.txt": (200, liar, b"x" * 40_000)})
    code, receipt, *_ = run(f"{server.base}/liar.txt", "--max-bytes", "1024")
    assert code == fetch.OVER_CAP
    assert receipt["capped"] is True
    assert receipt["path"] is None
    assert list(leg.probe.iterdir()) == []


def test_sizes_parse_in_binary_units():
    assert fetch.parse_size("1G") == fetch.parse_size("1GiB") == 1024**3
    assert fetch.parse_size("512m") == 512 * 1024**2
    assert fetch.parse_size("1073741824") == 1024**3
    for bad in ("", "1X", "-1", "0", "lots"):
        with pytest.raises(ValueError):
            fetch.parse_size(bad)


@CASES
def test_a_clean_fetch_writes_one_file_and_prints_the_receipt(leg, case):
    body = gzip.compress(b"org,example)/ 19991128153001\n")
    gz = {case("content-type"): "application/gzip"}
    server = leg.serve({"/zones/1999.cdx.gz": (200, gz, body)})
    code, receipt, *_ = run(f"{server.base}/zones/1999.cdx.gz")
    assert code == fetch.OK, receipt
    written = leg.probe / "1999.cdx.gz"
    assert written.read_bytes() == body
    assert receipt["bytes"] == len(body)
    assert receipt["path"] == str(written)
    assert receipt["content_type"] == "application/gzip"
    assert receipt["sha256"] == hashlib.sha256(body).hexdigest()


def test_a_destination_outside_the_roots_is_refused_before_a_request(leg, tmp_path):
    server = leg.serve({"/x.txt": page()})
    outside = tmp_path / "workspace" / "x.txt"
    outside.parent.mkdir()
    code, receipt, *_ = run(f"{server.base}/x.txt", "--to", str(outside))
    assert code == fetch.USAGE
    assert "outside" in receipt["reason"]
    # A symlinked parent is the same escape by another route, and so is a symlinked target.
    (leg.probe / "elsewhere").symlink_to(outside.parent, target_is_directory=True)
    code, *_ = run(f"{server.base}/x.txt", "--to", str(leg.probe / "elsewhere" / "x.txt"))
    assert code == fetch.USAGE
    outside.write_text("mine\n")
    (leg.probe / "x.txt").symlink_to(outside)
    code, receipt, *_ = run(f"{server.base}/x.txt", "--to", str(leg.probe / "x.txt"))
    assert code == fetch.USAGE
    assert "symlink" in receipt["reason"]
    assert outside.read_text() == "mine\n", "it wrote through the link"
    code, receipt, *_ = run(f"{server.base}/x.txt", env={"ARK_PROBE_DIR": ""})
    assert code == fetch.USAGE
    assert "nowhere" in receipt["reason"]
    assert server.asked == [], "robots was read for a fetch that could never write"


def test_the_content_type_decides_where_the_bytes_may_go(leg, tmp_path):
    corpus = tmp_path / "corpora" / "arquivo-ia-cdxj"
    corpus.mkdir(parents=True)
    risky, exe = (
        page(b"a line\n", "application/octet-stream"),
        page(b"MZ\n", "application/x-msdownload"),
    )
    server = leg.serve({"/IA.cdxj": risky, "/setup.exe": exe})
    approved = {"ARK_FETCH_DEST_ROOT": str(corpus)}
    # A risky type stays off the probe root, even with the approved root set elsewhere.
    for env in (None, approved):
        code, receipt, *_ = run(f"{server.base}/IA.cdxj", env=env)
        assert code == fetch.BAD_TYPE, env
        assert "downloads.md" in receipt["reason"]
        assert receipt["path"].startswith(str(leg.probe))
    # In-stream it may be read: the payload owns stdout and the receipt goes to stderr.
    code, receipt, err, out = run(f"{server.base}/IA.cdxj", "--to", "-")
    assert (code, out) == (fetch.OK, b"a line\n"), err
    assert json.loads(err.splitlines()[-1])["bytes"] == receipt["bytes"] == len(out)
    assert list(leg.probe.iterdir()) == [], "a streamed fetch writes no file"
    code, receipt, *_ = run(f"{server.base}/IA.cdxj", "--to", str(corpus), env=approved)
    assert code == fetch.OK, receipt
    assert (corpus / "IA.cdxj").read_bytes() == b"a line\n"
    # An executable is refused whatever the destination.
    for args, env in (([], None), (["--to", "-"], None), (["--to", str(corpus)], approved)):
        code, receipt, *_ = run(f"{server.base}/setup.exe", *args, env=env)
        assert code == fetch.BAD_TYPE, receipt
        assert "allowlist" in receipt["reason"]


def test_a_redirect_onto_a_refusing_host_is_refused_and_never_fetched(leg):
    refuser = leg.serve({"/data.txt": page(b"never read\n")}, robots=BY_NAME_REFUSAL)
    landing = leg.serve({"/get": hop(f"{refuser.base}/data.txt")})
    code, receipt, *_ = run(f"{landing.base}/get")
    assert code == fetch.ROBOTS_REFUSED, receipt
    assert receipt["url"].endswith("/data.txt"), "the receipt must name the host that refused"
    assert refuser.asked == ["/robots.txt"], "the second host was fetched without a check"
    assert list(leg.probe.iterdir()) == []


def test_a_redirect_within_one_host_rechecks_the_new_path(leg):
    routes = {"/public": hop("/private/x.txt"), "/private/x.txt": page(b"never read\n")}
    server = leg.serve(routes, robots="User-agent: *\nDisallow: /private\n")
    code, receipt, *_ = run(f"{server.base}/public")
    assert code == fetch.ROBOTS_REFUSED, receipt
    assert "/private/x.txt" not in server.asked
    assert server.asked.count("/robots.txt") == 1, "robots is reused for the second hop"


@pytest.mark.parametrize(
    ("routes", "reason"),
    [
        ({"/a": hop("/b"), "/b": hop("/a")}, "redirects"),
        ({"/a": hop("file:///x")}, "not http or https"),
    ],
    ids=["loop", "off-http"],
)
def test_a_redirect_that_leads_nowhere_fails(leg, routes, reason):
    server = leg.serve(routes)
    code, receipt, *_ = run(f"{server.base}/a")
    assert code == fetch.HTTP_FAILED
    assert reason in receipt["reason"]
    assert len([p for p in server.asked if p in ("/a", "/b")]) <= fetch.MAX_HOPS + 1


def test_retry_after_is_honoured_in_seconds_and_as_a_date():
    assert fetch.retry_after_seconds({"Retry-After": "30"}) == 30.0
    header = {"retry-after": "Wed, 09 Sep 2026 12:00:30 GMT"}
    assert 0 <= fetch.retry_after_seconds(header, now=1789300800.0) <= 120
    assert fetch.retry_after_seconds({}) is None
    assert fetch.retry_after_seconds({"Retry-After": "soon"}) is None


@CASES
def test_a_503_is_retried_and_an_allowed_redirect_followed_to_the_asked_name(leg, case):
    body, asks = b"a,b\n1,2\n", []
    final = leg.serve({"/real.csv": (200, {case("content-type"): "text/csv"}, body)})

    def flaky(_handler):
        asks.append(1)
        if len(asks) == 1:
            return 503, {case("retry-after"): "0"}, b""
        return 301, {case("location"): f"{final.base}/real.csv"}, b""

    server = leg.serve({"/x.txt": flaky})
    code, receipt, *_ = run(f"{server.base}/x.txt")
    assert code == fetch.OK, receipt
    assert (receipt["url"].endswith("/real.csv"), receipt["bytes"], len(asks)) == (True, 8, 2)
    # Named from the URL the caller asked for: a redirect must not move where it writes.
    assert (leg.probe / "x.txt").read_bytes() == body
    assert not (leg.probe / "real.csv").exists()
    # A wait longer than the leg has is a refusal for now, not a nap.
    slept = []
    server.routes["/x.txt"] = (503, {"Retry-After": "9000"}, b"")
    code, receipt = fetch.fetch(f"{server.base}/x.txt", 1024, None, 30.0, sleep=slept.append)
    assert (code, slept) == (fetch.HTTP_FAILED, [])
    assert "longer than we wait" in receipt["reason"]


def test_a_404_or_a_non_http_url_is_a_failure_not_an_empty_success(leg):
    code, receipt, *_ = run(f"{leg.serve({}).base}/gone.txt")
    assert (code, receipt["bytes"], receipt["sha256"]) == (fetch.HTTP_FAILED, 0, None)
    code, _, err, _ = run("file:///etc/passwd")
    assert code == fetch.USAGE
    assert "http" in err


RESUME = {
    "2gib-wall": ([(206, {}, SECOND)], BIG, False, 21, None, 1),
    "range-ignored": ([(200, {}, WHOLE)], BIG, False, 10, "ignored the Range header", 1),
    "no-progress": ([(206, {}, b"")], BIG, False, 10, "stopped making progress", 2),
    "cap-binds": ([(206, {}, SECOND)], 15, False, 21, "passed the 15 byte cap", 1),
    "throttled": ([(503, {"retry-after": "3"}, b""), (206, {}, SECOND)], BIG, False, 21, None, 2),
    "wrong-byte": ([(206, RANGE0, WHOLE)], BIG, True, 10, "from byte 0, not 10", 1),
}


@pytest.mark.parametrize(
    ("rounds", "cap", "pipe", "total", "why", "asks"), list(RESUME.values()), ids=list(RESUME)
)
def test_resume_appends_only_the_next_bytes(tmp_path, rounds, cap, pipe, total, why, asks):
    path, calls, slept = tmp_path / "artifact.gz", [], []
    path.write_bytes(b"first-half")
    digest, sink = hashlib.sha256(b"first-half"), io.BytesIO() if pipe else None

    def opener(url, timeout, start=None, end=None):
        calls.append((start, end))
        status, headers, body = rounds[min(len(calls), len(rounds)) - 1]
        return status, headers, io.BytesIO(body)

    dest = None if pipe else str(path)
    got, reason = fetch.resume("h", dest, 10, 21, digest, cap, 5.0, slept.append, opener, sink)
    assert got == total
    assert reason is None if why is None else why in reason, reason
    # A bounded span from where it stopped: `bytes=N-` past 2 GiB is answered 206 and empty.
    assert calls == [(10, 20)] * asks
    assert slept == [3.0] * (rounds[0][0] == 503)
    kept = b"" if pipe else b"first-half"
    want = kept + SECOND if why is None else kept
    assert (sink.getvalue() if pipe else path.read_bytes()) == want
    if why is None:
        assert digest.hexdigest() == hashlib.sha256(WHOLE).hexdigest()


def test_a_part_file_from_an_earlier_run_is_continued(leg):
    whole = b"the first part only\n" + b"x" * 80
    server = leg.serve({"/half.txt": dropping(whole, len(whole))})
    (leg.probe / "half.txt").write_bytes(whole[:20])
    code, receipt = fetch.fetch(f"{server.base}/half.txt", 1 << 30, str(leg.probe), 10.0)
    assert code == fetch.OK, receipt
    assert receipt["bytes"] == len(whole)
    assert receipt["sha256"] == hashlib.sha256(whole).hexdigest()
    assert (leg.probe / "half.txt").read_bytes() == whole
    assert [r for r in server.ranges if r] == [f"bytes=20-{len(whole) - 1}"]


@pytest.mark.parametrize(
    ("drop", "reset", "every_round"),
    [(600_000, False, False), (600_000, True, False), (300_000, True, True)],
    ids=["early-eof", "reset", "drops-every-round"],
)
def test_a_dropped_stream_resumes_and_hashes_the_whole_artifact(leg, drop, reset, every_round):
    server = leg.serve({"/read.cdx": dropping(PAYLOAD, drop, reset, every_round)}, robots=None)
    code, receipt, _, out = run(f"{server.base}/read.cdx", "--to", "-", "--max-bytes", "1G")
    assert code == fetch.OK, receipt
    assert out == PAYLOAD, "the pipe saw every byte once and in order"
    assert receipt["sha256"] == hashlib.sha256(PAYLOAD).hexdigest()
    assert receipt["bytes"] == len(PAYLOAD)
    if every_round:
        assert receipt["resumes"] >= len(PAYLOAD) // drop
    else:
        assert receipt["resumes"] == 1
    if not reset:
        assert server.ranges[-1] == f"bytes=600000-{len(PAYLOAD) - 1}"
    assert list(leg.probe.iterdir()) == [], "a streamed read writes no file"


@pytest.mark.parametrize("pipe", [False, True], ids=["file", "pipe"])
def test_a_transfer_that_dies_where_the_range_is_ignored_fails_and_writes_nothing_twice(leg, pipe):
    server = leg.serve({"/half.txt": dropping(PAYLOAD, 600_000, honour=False)})
    code, receipt, err, out = run(f"{server.base}/half.txt", *(("--to", "-") if pipe else ()))
    assert code == fetch.HTTP_FAILED, (receipt, err)
    assert "Traceback" not in err
    assert "ignored the Range header" in receipt["reason"], receipt["reason"]
    assert list(leg.probe.iterdir()) == [], "a part-file was left behind"
    if pipe:
        assert out == PAYLOAD[:600_000], "nothing was written twice"
    else:
        assert receipt["path"] is None
