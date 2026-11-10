"""Read captures straight out of public ARC files, by the byte range their CDX line names.

Input: CDX lines of an extraction collection whose ARC files are public on archive.org
(`urlkey stamp url mime status digest - - size offset item/file.arc.gz`). Each wanted line is
one range request for that gzip member; the member holds the ARC record (one header line, the
HTTP response headers, the body). No replay and no CDX endpoint is asked: this is the item's
own file at `https://archive.org/download/<item>/<file>`, which redirects to a data node.
The robots.txt of archive.org and of each data node is read with the project fetcher's reader.

    uv run python scripts/sources/web_reports/arc_pages.py DEST HITS.cdx [threads] [interval_s]
        [shard i/n]

Only status 200 text pages are read. A page lands at <dest_root>/<host>/<path>; a later capture
of the same URL with other bytes lands at <dest_root>/<host>~<stamp>/<path>. Each read leaves a
JSON line in <dest_root>/receipts.receipts: url, stamp, replay (the capture's public replay
address, for a reader who wants to see the same bytes), arc, offset, size, status, bytes,
sha256, sha1_ok (payload SHA-1 equals the CDX digest), path. A (url, stamp) read once, or whose
file is refused, is not read again. 429 and 503 rest every thread (60, 180, 600 s), the fourth
in a row ends the run; a failed connect rests them and is tried again, ten in a row end the run.
"""

import base64
import concurrent.futures as cf
import hashlib
import http.client
import importlib.util
import json
import os
import posixpath
import re
import sys
import threading
import time
import urllib.parse
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEST, HITS = Path(sys.argv[1]), Path(sys.argv[2])
THREADS = int(sys.argv[3]) if len(sys.argv) > 3 else 3
INTERVAL = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
SHARD = tuple(int(x) for x in sys.argv[5].split("/")) if len(sys.argv) > 5 else (0, 1)
WANT = re.compile(os.environ.get("ARK_WANT", "."), re.I)
MAX_SIZE = int(os.environ.get("ARK_MAX_SIZE", str(8 << 20)))  # compressed bytes of one record

_spec = importlib.util.spec_from_file_location("hf", REPO / "scripts/harness/fetch.py")
hf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hf)

SAFE = re.compile(r"[^A-Za-z0-9._/~-]")
lock = threading.Lock()
gate = threading.Lock()
state = {"next": 0.0, "strikes": 0, "errors": 0, "stop": False, "got": 0, "miss": 0}
robots_cache: dict = {}
where: dict[str, str] = {}  # ARC file -> the data node URL its redirect named
local = threading.local()


def local_name(url: str, stamp: str | None) -> str:
    parts = urllib.parse.urlsplit(url)
    path = posixpath.normpath(parts.path or "/").lstrip("/")
    if "." not in path.rsplit("/", 1)[-1]:
        path = (path + "/_index.html").lstrip("/")
    if parts.query:
        path += "_" + parts.query
    host = parts.netloc.lower().split(":")[0] + (f"~{stamp}" if stamp else "")
    return f"{host}/{SAFE.sub('_', path)}"[:240]


def wait_turn() -> None:
    with gate:
        now = time.time()
        if state["next"] > now:
            time.sleep(state["next"] - now)
        state["next"] = time.time() + INTERVAL


def allowed(url: str) -> bool:
    with lock:
        verdict, _, why = hf.read_robots(url, 60, robots_cache)
    if verdict == "allowed":
        return True
    if "could not be read" in why:
        with lock:
            robots_cache.clear()
        raise ConnectionError(why)
    with lock:
        state["stop"] = True
    print(json.dumps({"stopped": "robots", "url": url, "why": why}), flush=True)
    return False


def get(url: str, headers: dict) -> tuple[int, dict, bytes]:
    parts = urllib.parse.urlsplit(url)
    conns = local.__dict__.setdefault("conns", {})
    conn = conns.get(parts.netloc)
    if conn is None:
        conn = conns[parts.netloc] = http.client.HTTPSConnection(parts.netloc, timeout=120)
    try:
        conn.request(
            "GET",
            parts.path + ("?" + parts.query if parts.query else ""),
            headers={"User-Agent": hf.USER_AGENT, "Accept-Encoding": "identity", **headers},
        )
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, body
    except Exception:
        conn.close()
        conns.pop(parts.netloc, None)
        raise


def node_url(arc: str) -> str | None:
    """The data node address of an ARC file, from archive.org's own redirect, asked once."""
    if arc in where:
        return where[arc]
    url = "https://archive.org/download/" + arc
    for _ in range(4):
        if not allowed(url):
            return None
        status, headers, _ = get(url, {"Range": "bytes=0-0"})
        if status in (301, 302, 303, 307) and headers.get("location"):
            url = urllib.parse.urljoin(url, headers["location"])
            continue
        if status in (200, 206):
            where[arc] = url
            return url
        raise LookupError(status)
    raise LookupError("redirects")


def payload(member: bytes) -> tuple[bytes, bytes, str]:
    """(raw HTTP entity, decoded body, HTTP status line) of one gzip ARC record."""
    record = zlib.decompress(member, 31)
    _, _, rest = record.partition(b"\n")  # the ARC header line
    head, sep, raw = rest.partition(b"\r\n\r\n")
    if not sep:
        head, sep, raw = rest.partition(b"\n\n")
    raw = raw[:-1] if raw.endswith(b"\n") else raw  # the record's closing newline
    body = raw
    if re.search(rb"(?im)^transfer-encoding:\s*chunked", head):
        out, pos = [], 0
        try:
            while pos < len(raw):
                eol = raw.index(b"\n", pos)
                size = int(raw[pos:eol].split(b";")[0].strip() or b"0", 16)
                if size == 0:
                    break
                out.append(raw[eol + 1 : eol + 1 + size])
                pos = raw.index(b"\n", eol + 1 + size) + 1
            body = b"".join(out)
        except ValueError:
            body = raw
    return raw, body, head.split(b"\n", 1)[0].decode("latin-1").strip()


def read(job, rec) -> None:
    url, stamp, digest, size, offset, arc, name = job
    while not state["stop"]:
        wait_turn()
        receipt = {
            "url": url, "stamp": stamp, "replay": f"https://web.archive.org/web/{stamp}id_/{url}",
            "arc": arc, "offset": offset, "size": size, "status": None, "bytes": 0, "sha256": None,
            "sha1_ok": None, "path": None,
        }  # fmt: skip
        try:
            node = node_url(arc)
            if node is None or not allowed(node):
                return
            status, _, member = get(node, {"Range": f"bytes={offset}-{offset + size - 1}"})
        except LookupError as exc:
            status, member = f"no file: {exc}", b""
        except (http.client.HTTPException, TimeoutError, ConnectionError, OSError):
            with lock:
                where.pop(arc, None)
                state["errors"] += 1
                state["next"] = max(state["next"], time.time() + min(300, 20 * state["errors"]))
                if state["errors"] >= 10:
                    state["stop"] = True
                    print(json.dumps({"stopped": "connect errors"}), flush=True)
            continue
        if status in (429, 503):
            with lock:
                state["strikes"] += 1
                if state["strikes"] >= 4:
                    state["stop"] = True
                    print(json.dumps({"stopped": "throttled", "status": status}), flush=True)
                    return
                state["next"] = time.time() + (60, 180, 600)[state["strikes"] - 1]
            continue
        receipt["status"] = status
        hit = False
        if status == 206:
            try:
                raw, body, line = payload(member)
                sha1 = base64.b32encode(hashlib.sha1(raw).digest()).decode()
                out = DEST / name
                try:
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(body)
                except OSError:  # a page already sits where this one needs a directory
                    host, _, rest = name.partition("/")
                    name = f"{host}/{rest.replace('/', '__')}"
                    out = DEST / name
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(body)
                receipt.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
                               sha1_ok=sha1 == digest, http=line, path=name)  # fmt: skip
                hit = True
            except (zlib.error, OSError) as exc:
                receipt["status"] = f"bad record: {type(exc).__name__}"
        with lock:
            state["strikes"] = state["errors"] = 0
            state["got" if hit else "miss"] += 1
            rec.write(json.dumps(receipt) + "\n")
            rec.flush()
            if (state["got"] + state["miss"]) % 200 == 0:
                print(json.dumps({"got": state["got"], "miss": state["miss"]}), flush=True)
        return


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    rec_path = DEST / "receipts.receipts"
    done: set = set()
    taken: dict[str, str] = {}  # url -> digest of the capture that holds the plain path
    seen_digest: set = set()
    if rec_path.exists():
        for line in rec_path.read_text().splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("path") or str(r.get("status")).startswith("no file: 4"):
                done.add((r["url"], r["stamp"]))  # anything else is read again
    jobs = []
    for line in HITS.read_text(errors="replace").splitlines():
        p = line.split(" ")
        if len(p) != 11 or p[4] != "200" or not p[3].startswith("text/") or not WANT.search(p[2]):
            continue
        url, stamp, digest = p[2], p[1], p[5]
        if not (p[8].isdigit() and p[9].isdigit()) or int(p[8]) > MAX_SIZE:
            continue
        if (url, digest) in seen_digest:
            continue  # the same bytes captured again
        seen_digest.add((url, digest))
        first = taken.setdefault(url, digest) == digest
        if (url, stamp) in done or zlib.crc32(url.encode()) % SHARD[1] != SHARD[0]:
            continue
        jobs.append(
            (
                url,
                stamp,
                digest,
                int(p[8]),
                int(p[9]),
                p[10],
                local_name(url, None if first else stamp),
            )
        )
    print(json.dumps({"jobs": len(jobs), "already": len(done)}), flush=True)
    with rec_path.open("a") as rec, cf.ThreadPoolExecutor(THREADS) as ex:
        list(ex.map(lambda j: read(j, rec), jobs))
    print(
        json.dumps({"done": not state["stop"], "got": state["got"], "miss": state["miss"]}),
        flush=True,
    )
    return 0 if not state["stop"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
