"""The one download path, tested against a local server that counts what it is asked.

The properties worth a test are the expensive ones. A by-name robots refusal must cost the
artifact host zero requests, because the breach that put this program here was a read that
happened anyway. A cap must hold when the server lies about `Content-Length` as well as
when it tells the truth, because a chunked response has no length to check. And a
destination outside the two allowed roots must be refused before a socket opens, because
probe bytes on the wrong filesystem is how a shared box fills up.

Nothing here reaches the network: `http.server` on a loopback port, and the request log is
the assertion.
"""

import gzip
import hashlib
import importlib.util
import io
import json
import os
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FETCH = ROOT / "scripts" / "harness" / "fetch.py"

_SPEC = importlib.util.spec_from_file_location("ark_fetch", FETCH)
fetch = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fetch)

PERMISSIVE = "User-agent: *\nDisallow:\n"
# The `tomocha.net` shape: a permissive group first, the refusal far below it.
BY_NAME_REFUSAL = PERMISSIVE + ("\n# padding\n" * 40) + "User-agent: ClaudeBot\nDisallow: /\n"


class Server:
    """A loopback host with a routing table and a log of every path it was asked for."""

    def __init__(self, routes: dict):
        self.routes = routes
        self.asked: list[str] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_):
                pass

            def do_GET(self):
                outer.asked.append(self.path)
                route = outer.routes.get(self.path)
                if route is None:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                status, headers, body = route() if callable(route) else route
                headers = dict(headers)
                # A server that promises more than it sends, then hangs up: the mid-stream
                # failure that used to traceback out with no receipt at all.
                truncate = headers.pop("X-Ark-Truncate", None)
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                named = {k.lower() for k in headers}
                if truncate:
                    self.send_header("Content-Length", str(len(body) + int(truncate)))
                elif "content-length" not in named and "transfer-encoding" not in named:
                    self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)
                if truncate:
                    self.close_connection = True

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def serve():
    made = []

    def factory(routes: dict) -> Server:
        server = Server(routes)
        made.append(server)
        return server

    yield factory
    for server in made:
        server.close()


@pytest.fixture
def probe(tmp_path, monkeypatch):
    directory = tmp_path / "probe"
    directory.mkdir()
    monkeypatch.setenv("ARK_PROBE_DIR", str(directory))
    monkeypatch.delenv("ARK_FETCH_DEST_ROOT", raising=False)
    return directory


def run(url: str, *args, env: dict | None = None) -> tuple[int, dict, str]:
    """fetch.py as a leg runs it, returning (exit code, receipt, stderr)."""
    result = subprocess.run(
        [sys.executable, str(FETCH), url, *args],
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
        cwd=ROOT,
    )
    where = result.stderr if "-" in args else result.stdout
    receipt = {}
    for line in where.splitlines():
        if line.startswith("{"):
            receipt = json.loads(line)
    return result.returncode, receipt, result.stderr


# ---------------------------------------------------------------- robots


def test_a_by_name_refusal_exits_three_with_zero_requests_for_the_artifact(serve, probe):
    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, BY_NAME_REFUSAL.encode()),
            "/zones/1999.txt": (200, {"Content-Type": "text/plain"}, b"never read\n"),
        }
    )
    code, receipt, _ = run(f"{server.base}/zones/1999.txt")
    assert code == fetch.ROBOTS_REFUSED
    assert receipt["robots"] == "refused"
    assert "claudebot" in receipt["reason"].lower()
    assert server.asked == ["/robots.txt"], "the artifact was asked for anyway"
    assert list(probe.iterdir()) == []


def test_a_permissive_star_group_does_not_override_a_group_further_down():
    verdict, _, why = fetch.robots_verdict(BY_NAME_REFUSAL, "/zones/1999.txt")
    assert verdict == "refused", why
    # And the refusal is honoured whichever of our names carries it.
    for name in ("Claude-User", "anthropic-ai", "InternetDigitalArk"):
        text = f"User-agent: *\nAllow: /\n\nUser-agent: {name}\nDisallow: /data\n"
        assert fetch.robots_verdict(text, "/data/x.gz")[0] == "refused", name


def test_a_star_refusal_is_honoured_and_a_narrower_allow_wins_inside_its_group():
    assert fetch.robots_verdict("User-agent: *\nDisallow: /private\n", "/private/x")[0] == "refused"
    text = "User-agent: *\nDisallow: /data\nAllow: /data/public\n"
    assert fetch.robots_verdict(text, "/data/private/x")[0] == "refused"
    assert fetch.robots_verdict(text, "/data/public/x")[0] == "allowed"
    # An empty Disallow permits everything, and a crawl delay is read, not a refusal.
    verdict, delay, _ = fetch.robots_verdict("User-agent: *\nCrawl-delay: 5\nDisallow:\n", "/x")
    assert (verdict, delay) == ("allowed", 5.0)


def test_a_host_with_no_robots_is_allowed_and_an_unreadable_one_fails_closed(serve, probe):
    open_host = serve({"/x.txt": (200, {"Content-Type": "text/plain"}, b"ok\n")})
    code, receipt, _ = run(f"{open_host.base}/x.txt")
    assert (code, receipt["robots"]) == (fetch.OK, "allowed")

    broken = serve(
        {
            "/robots.txt": (500, {"Content-Type": "text/plain"}, b"oops\n"),
            "/x.txt": (200, {"Content-Type": "text/plain"}, b"ok\n"),
        }
    )
    code, receipt, _ = run(f"{broken.base}/x.txt")
    assert code == fetch.ROBOTS_UNREADABLE
    assert receipt["robots"] == "unknown"
    assert broken.asked == ["/robots.txt"]


def test_a_dead_host_is_unknown_rather_than_allowed():
    # A closed port, so no server is involved at all: a refused connection must never
    # read as permission.
    with socket.socket() as probe_socket:
        probe_socket.bind(("127.0.0.1", 0))
        port = probe_socket.getsockname()[1]
    verdict, _, why = fetch.read_robots(f"http://127.0.0.1:{port}/x.txt", timeout=2.0)
    assert verdict == "unknown", why


# ---------------------------------------------------------------- the cap


def test_a_two_gigabyte_content_length_stops_at_the_cap_and_reads_no_body(serve, probe):
    two_gb = 2 * 1024**3
    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/IA.cdxj.gz": (
                200,
                {"Content-Type": "application/gzip", "Content-Length": str(two_gb)},
                b"",
            ),
        }
    )
    code, receipt, _ = run(f"{server.base}/IA.cdxj.gz", "--max-bytes", "1G")
    assert code == fetch.OVER_CAP
    assert receipt["capped"] is True
    assert receipt["bytes"] == two_gb
    assert "downloads.md" in receipt["reason"]
    assert list(probe.iterdir()) == [], "a capped fetch must leave nothing behind"


def test_the_stream_is_counted_when_the_server_understates_its_length(serve, probe):
    # The second count, and the reason there are two: this server claims 10 bytes and
    # sends 40,000, which the Content-Length check believes.
    payload = b"x" * 40_000

    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/liar.txt": (
                200,
                {"Content-Type": "text/plain", "Transfer-Encoding": "identity"},
                payload,
            ),
        }
    )
    code, receipt, _ = run(f"{server.base}/liar.txt", "--max-bytes", "1024")
    assert code == fetch.OVER_CAP
    assert receipt["capped"] is True
    assert receipt["path"] is None
    assert list(probe.iterdir()) == []


def test_sizes_parse_in_binary_units():
    assert fetch.parse_size("1G") == 1024**3
    assert fetch.parse_size("1GiB") == 1024**3
    assert fetch.parse_size("512m") == 512 * 1024**2
    assert fetch.parse_size("1073741824") == 1024**3
    for bad in ("", "1X", "-1", "0", "lots"):
        with pytest.raises(ValueError):
            fetch.parse_size(bad)


# ---------------------------------------------------------------- what it writes


def test_a_clean_fetch_writes_one_file_and_prints_the_receipt(serve, probe):
    body = gzip.compress(b"org,example)/ 19991128153001\n")
    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/zones/1999.cdx.gz": (200, {"Content-Type": "application/gzip"}, body),
        }
    )
    code, receipt, _ = run(f"{server.base}/zones/1999.cdx.gz")
    assert code == fetch.OK, receipt
    written = probe / "1999.cdx.gz"
    assert written.read_bytes() == body
    assert receipt["bytes"] == len(body)
    assert receipt["path"] == str(written)
    assert receipt["content_type"] == "application/gzip"
    import hashlib

    assert receipt["sha256"] == hashlib.sha256(body).hexdigest()


def test_the_payload_owns_stdout_and_the_receipt_stderr_when_streamed(serve, probe):
    body = b"a,b\n1,2\n"
    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/x.csv": (200, {"Content-Type": "text/csv"}, body),
        }
    )
    result = subprocess.run(
        [sys.executable, str(FETCH), f"{server.base}/x.csv", "--to", "-"],
        capture_output=True,
        env={**os.environ},
        cwd=ROOT,
    )
    assert result.returncode == fetch.OK, result.stderr
    assert result.stdout == body
    assert json.loads(result.stderr.decode().splitlines()[-1])["bytes"] == len(body)
    assert list(probe.iterdir()) == [], "a streamed fetch writes no file"


def test_a_destination_outside_the_roots_is_refused_before_a_request(serve, probe, tmp_path):
    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/x.txt": (200, {"Content-Type": "text/plain"}, b"ok\n"),
        }
    )
    outside = tmp_path / "workspace" / "x.txt"
    outside.parent.mkdir()
    code, receipt, _ = run(f"{server.base}/x.txt", "--to", str(outside))
    assert code == fetch.USAGE
    assert "outside" in receipt["reason"]
    assert server.asked == [], "robots was read for a fetch that could never write"

    # A symlinked parent is the same escape by another route.
    link = probe / "elsewhere"
    link.symlink_to(outside.parent, target_is_directory=True)
    code, _, _ = run(f"{server.base}/x.txt", "--to", str(link / "x.txt"))
    assert code == fetch.USAGE

    # And with neither root set there is nowhere to write at all.
    code, receipt, _ = run(f"{server.base}/x.txt", env={"ARK_PROBE_DIR": ""})
    assert code == fetch.USAGE
    assert "nowhere" in receipt["reason"]


def test_the_second_root_is_the_one_an_approved_download_uses(serve, probe, tmp_path):
    corpus = tmp_path / "corpora" / "arquivo-ia-cdxj"
    corpus.mkdir(parents=True)
    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/IA.cdxj": (200, {"Content-Type": "application/octet-stream"}, b"a line\n"),
        }
    )
    # Unnamed and zip types are the download backlog's whole population, so a leg may not
    # put one on disk...
    code, receipt, _ = run(f"{server.base}/IA.cdxj")
    assert code == fetch.BAD_TYPE
    assert "downloads.md" in receipt["reason"]
    # ...but reading it in-stream is always allowed, and so is the approved destination.
    code, _, _ = run(f"{server.base}/IA.cdxj", "--to", "-")
    assert code == fetch.OK
    code, receipt, _ = run(
        f"{server.base}/IA.cdxj",
        "--to",
        str(corpus),
        env={"ARK_FETCH_DEST_ROOT": str(corpus)},
    )
    assert code == fetch.OK, receipt
    assert (corpus / "IA.cdxj").read_bytes() == b"a line\n"


def test_an_executable_is_refused_whatever_the_destination(serve, probe, tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/setup.exe": (200, {"Content-Type": "application/x-msdownload"}, b"MZ\n"),
        }
    )
    approved = {"ARK_FETCH_DEST_ROOT": str(corpus)}
    for args, env in (([], None), (["--to", "-"], None), (["--to", str(corpus)], approved)):
        code, receipt, _ = run(f"{server.base}/setup.exe", *args, env=env)
        assert code == fetch.BAD_TYPE, receipt
        assert "allowlist" in receipt["reason"]


# ---------------------------------------------------------------- redirects


def test_a_redirect_onto_a_refusing_host_is_refused_and_never_fetched(serve, probe):
    """The `www.fac.gov` shape with the check skipped: urllib would follow this."""
    refuser = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, BY_NAME_REFUSAL.encode()),
            "/data.txt": (200, {"Content-Type": "text/plain"}, b"never read\n"),
        }
    )
    landing = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/get": (302, {"Location": f"{refuser.base}/data.txt"}, b""),
        }
    )
    code, receipt, _ = run(f"{landing.base}/get")
    assert code == fetch.ROBOTS_REFUSED, receipt
    assert receipt["url"].endswith("/data.txt"), "the receipt must name the host that refused"
    assert refuser.asked == ["/robots.txt"], "the second host was fetched without a check"
    assert list(probe.iterdir()) == []


def test_a_redirect_within_one_host_rechecks_the_new_path(serve, probe):
    robots = "User-agent: *\nDisallow: /private\n"
    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, robots.encode()),
            "/public": (302, {"Location": "/private/x.txt"}, b""),
            "/private/x.txt": (200, {"Content-Type": "text/plain"}, b"never read\n"),
        }
    )
    code, receipt, _ = run(f"{server.base}/public")
    assert code == fetch.ROBOTS_REFUSED, receipt
    assert "/private/x.txt" not in server.asked
    # Robots was read once and reused for the second hop rather than fetched twice.
    assert server.asked.count("/robots.txt") == 1


def test_an_allowed_redirect_is_followed_and_fetched(serve, probe):
    body = b"a,b\n1,2\n"
    final = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/real.csv": (200, {"Content-Type": "text/csv"}, body),
        }
    )
    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/get": (301, {"Location": f"{final.base}/real.csv"}, b""),
        }
    )
    code, receipt, _ = run(f"{server.base}/get")
    assert code == fetch.OK, receipt
    assert receipt["bytes"] == len(body)
    assert receipt["url"].endswith("/real.csv")
    # Named from the URL the caller asked for, not from the hop: where this writes is
    # settled before the first request and a redirect must not move it.
    assert (probe / "get").read_bytes() == body
    assert not (probe / "real.csv").exists()


def test_a_redirect_loop_stops_rather_than_spinning(serve, probe):
    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/a": (302, {"Location": "/b"}, b""),
            "/b": (302, {"Location": "/a"}, b""),
        }
    )
    code, receipt, _ = run(f"{server.base}/a")
    assert code == fetch.HTTP_FAILED
    assert "redirects" in receipt["reason"]
    assert len([p for p in server.asked if p in ("/a", "/b")]) <= fetch.MAX_HOPS + 1


def test_a_redirect_off_http_is_refused(serve, probe):
    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/x": (302, {"Location": "file:///etc/passwd"}, b""),
        }
    )
    code, receipt, _ = run(f"{server.base}/x")
    assert code == fetch.HTTP_FAILED
    assert "not http or https" in receipt["reason"]


# ---------------------------------------------------------------- header casing


def test_lower_case_headers_are_read_like_any_other(serve, probe):
    # HTTP field names are case-insensitive. A `dict()` of them is not, which read a
    # lower-case content-type as unnamed and skipped the first cap check entirely.
    two_gb = 2 * 1024**3
    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/x.gz": (200, {"content-type": "application/gzip"}, b"body\n"),
            "/big.gz": (
                200,
                {"content-type": "application/gzip", "content-length": str(two_gb)},
                b"",
            ),
        }
    )
    code, receipt, _ = run(f"{server.base}/x.gz")
    assert code == fetch.OK, receipt
    assert receipt["content_type"] == "application/gzip"

    code, receipt, _ = run(f"{server.base}/big.gz", "--max-bytes", "1G")
    assert code == fetch.OVER_CAP, receipt
    assert receipt["bytes"] == two_gb


def test_a_lower_case_retry_after_and_location_are_read(serve, probe):
    state = {"asks": 0}

    def flaky():
        state["asks"] += 1
        if state["asks"] == 1:
            return 503, {"retry-after": "0", "content-type": "text/plain"}, b""
        return 302, {"location": "/final.txt"}, b""

    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/x.txt": flaky,
            "/final.txt": (200, {"content-type": "text/plain"}, b"ok\n"),
        }
    )
    code, receipt, _ = run(f"{server.base}/x.txt")
    assert code == fetch.OK, receipt
    assert receipt["url"].endswith("/final.txt")


# ---------------------------------------------------------------- a broken transfer


def test_a_connection_that_dies_mid_body_exits_seven_and_leaves_nothing(serve, probe):
    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/half.txt": (
                200,
                {"Content-Type": "text/plain", "X-Ark-Truncate": "5000"},
                b"the first part only\n",
            ),
        }
    )
    code, receipt, err = run(f"{server.base}/half.txt")
    assert code == fetch.HTTP_FAILED, (receipt, err)
    assert "Traceback" not in err
    # It now tries to continue with Range first; this server answers 200 to one, which
    # means "starting over", and appending that would duplicate what is already here.
    assert "ignored the Range header" in receipt["reason"], receipt["reason"]
    assert receipt["path"] is None
    assert list(probe.iterdir()) == [], "a part-file was left behind"


# ------------------------------------------------------- continuing a short transfer


class _Body(io.BytesIO):
    """A response body: bytes that can be read and closed like a stream."""


def _opener(rounds):
    """A fake server: each call returns the next (status, headers, body) in the list."""
    calls = []

    def opener(url, timeout, start=None, end=None):
        calls.append((start, end))
        status, headers, body = rounds[min(len(calls) - 1, len(rounds) - 1)]
        return status, headers, _Body(body)

    opener.calls = calls
    return opener


def test_a_wall_at_two_gibibytes_is_continued_with_range(tmp_path):
    """The UKWA dataset ends every continuous stream at exactly 2 GiB and answers 206."""
    path = tmp_path / "artifact.gz"
    path.write_bytes(b"first-half")
    digest = hashlib.sha256(b"first-half")
    opener = _opener([(206, {}, b"second-half")])
    total, why = fetch.resume(
        "https://host/x.gz", str(path), 10, 21, digest, 1 << 40, 5.0, opener=opener
    )
    assert (total, why) == (21, None)
    assert path.read_bytes() == b"first-halfsecond-half"
    assert digest.hexdigest() == hashlib.sha256(b"first-halfsecond-half").hexdigest()
    # Bounded, not open-ended: `bytes=N-` past 2 GiB is answered 206 and then delivers
    # nothing, while `bytes=N-M` comes back with a correct Content-Range.
    assert opener.calls == [(10, 20)], "it asks for a bounded span from where it stopped"


def test_a_server_that_ignores_the_range_is_refused(tmp_path):
    """200 to a Range means starting over, and appending that duplicates the artifact."""
    path = tmp_path / "artifact.gz"
    path.write_bytes(b"first-half")
    total, why = fetch.resume(
        "https://host/x.gz",
        str(path),
        10,
        21,
        hashlib.sha256(b"first-half"),
        1 << 40,
        5.0,
        opener=_opener([(200, {}, b"first-halfsecond-half")]),
    )
    assert total == 10
    assert "ignored the Range header" in why
    assert path.read_bytes() == b"first-half", "nothing was appended"


def test_a_resume_that_stops_making_progress_gives_up(tmp_path):
    path = tmp_path / "artifact.gz"
    path.write_bytes(b"first-half")
    total, why = fetch.resume(
        "https://host/x.gz",
        str(path),
        10,
        21,
        hashlib.sha256(b"first-half"),
        1 << 40,
        5.0,
        opener=_opener([(206, {}, b"")]),
    )
    assert total == 10
    assert "stopped making progress" in why


def test_the_cap_still_binds_while_resuming(tmp_path):
    """What is already on disk counts, so a resume cannot walk past the caller's ceiling."""
    path = tmp_path / "artifact.gz"
    path.write_bytes(b"first-half")
    total, why = fetch.resume(
        "https://host/x.gz",
        str(path),
        10,
        21,
        hashlib.sha256(b"first-half"),
        15,
        5.0,
        opener=_opener([(206, {}, b"second-half")]),
    )
    assert "passed the 15 byte cap" in why
    assert total >= 10


def test_a_throttled_round_waits_and_carries_on(tmp_path):
    path = tmp_path / "artifact.gz"
    path.write_bytes(b"first-half")
    slept = []
    opener = _opener([(503, {"retry-after": "3"}, b""), (206, {}, b"second-half")])
    total, why = fetch.resume(
        "https://host/x.gz",
        str(path),
        10,
        21,
        hashlib.sha256(b"first-half"),
        1 << 40,
        5.0,
        sleep=slept.append,
        opener=opener,
    )
    assert (total, why) == (21, None)
    assert slept == [3.0]


def test_a_part_file_from_an_earlier_run_is_continued(serve, probe, monkeypatch):
    """The runner kills the job at 90 minutes and a 20 GB artifact may need longer.

    Without this each dispatch starts at zero and the fetch can never finish, however
    many times it is asked.
    """
    whole = b"the first part only\n" + b"x" * 80
    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/half.txt": (
                200,
                {"Content-Type": "text/plain", "Content-Length": str(len(whole))},
                whole[:20],
            ),
        }
    )
    part = probe / "half.txt"
    part.write_bytes(whole[:20])

    rounds = [(206, {}, whole[20:])]
    calls = []
    plain = fetch.get

    def opener(url, timeout, start=None, end=None):
        if start is None:
            return plain(url, timeout)
        calls.append((start, end))
        status, headers, body = rounds[0]
        return status, headers, io.BytesIO(body)

    monkeypatch.setattr(fetch, "get", opener)
    code, receipt = fetch.fetch(f"{server.base}/half.txt", 1 << 30, str(probe), 10.0)
    assert code == fetch.OK, receipt
    assert receipt["bytes"] == len(whole)
    assert receipt["sha256"] == hashlib.sha256(whole).hexdigest()
    assert part.read_bytes() == whole
    assert calls == [(20, len(whole) - 1)]


# ---------------------------------------------------------------- the two roots


def test_a_symlink_as_the_target_itself_is_refused(serve, probe, tmp_path):
    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/x.txt": (200, {"Content-Type": "text/plain"}, b"ok\n"),
        }
    )
    elsewhere = tmp_path / "elsewhere.txt"
    elsewhere.write_text("mine\n")
    link = probe / "x.txt"
    link.symlink_to(elsewhere)
    code, receipt, _ = run(f"{server.base}/x.txt", "--to", str(link))
    assert code == fetch.USAGE
    assert "symlink" in receipt["reason"]
    assert elsewhere.read_text() == "mine\n", "it wrote through the link"
    assert server.asked == []


def test_the_approved_root_admits_a_risky_type_only_for_a_file_going_into_it(
    serve, probe, tmp_path
):
    # The nit: `approved` used to be true whenever the variable was set, so a probe write
    # inherited a decision made about a different directory.
    corpus = tmp_path / "corpora" / "one"
    corpus.mkdir(parents=True)
    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/x.bin": (200, {"Content-Type": "application/octet-stream"}, b"bytes\n"),
        }
    )
    approved = {"ARK_FETCH_DEST_ROOT": str(corpus)}
    code, receipt, _ = run(f"{server.base}/x.bin", env=approved)
    assert code == fetch.BAD_TYPE, "the probe root took a risky type on someone else's decision"
    assert receipt["path"].startswith(str(probe))
    code, receipt, _ = run(f"{server.base}/x.bin", "--to", str(corpus), env=approved)
    assert code == fetch.OK, receipt


# ---------------------------------------------------------------- throttling


def test_retry_after_is_honoured_in_seconds_and_as_a_date():
    assert fetch.retry_after_seconds({"Retry-After": "30"}) == 30.0
    header = {"retry-after": "Wed, 09 Sep 2026 12:00:30 GMT"}
    later = fetch.retry_after_seconds(header, now=1789300800.0)
    assert 0 <= later <= 120
    assert fetch.retry_after_seconds({}) is None
    assert fetch.retry_after_seconds({"Retry-After": "soon"}) is None


def test_a_503_is_retried_once_the_server_says_it_may_be(serve, probe):
    state = {"asks": 0}

    def flaky():
        state["asks"] += 1
        if state["asks"] == 1:
            return 503, {"Retry-After": "0", "Content-Type": "text/plain"}, b""
        return 200, {"Content-Type": "text/plain"}, b"ok\n"

    server = serve(
        {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode()),
            "/x.txt": flaky,
        }
    )
    code, receipt, _ = run(f"{server.base}/x.txt")
    assert code == fetch.OK, receipt
    assert state["asks"] == 2

    # A wait longer than the leg has is a refusal for now, not a nap.
    slept = []
    server.routes["/x.txt"] = (503, {"Retry-After": "9000", "Content-Type": "text/plain"}, b"")
    code, receipt = fetch.fetch(f"{server.base}/x.txt", 1024, None, 30.0, sleep=slept.append)
    assert code == fetch.HTTP_FAILED
    assert slept == []
    assert "longer than we wait" in receipt["reason"]


def test_a_404_on_the_artifact_is_an_http_failure_not_an_empty_success(serve, probe):
    server = serve({"/robots.txt": (200, {"Content-Type": "text/plain"}, PERMISSIVE.encode())})
    code, receipt, _ = run(f"{server.base}/gone.txt")
    assert code == fetch.HTTP_FAILED
    assert receipt["bytes"] == 0
    assert receipt["sha256"] is None


def test_only_http_and_https(probe):
    code, _, err = run("file:///etc/passwd")
    assert code == fetch.USAGE
    assert "http" in err
