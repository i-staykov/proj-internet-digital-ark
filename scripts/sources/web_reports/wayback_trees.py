"""Read report trees out of the Wayback Machine, a tree at a time, giving up on a tree it lacks.

Input: a JSON object {tree: {"urls": [original URL, ...]}}, each list in probe order; a URL may
carry "\t<14-digit stamp>" to ask for the capture nearest that instant. For a
tree the first PROBES URLs are asked; if none has a capture the tree is left, else every URL is
asked. Each ask is `https://web.archive.org/web/<stamp>id_/<url>`, the unmodified capture
nearest <stamp>; the CDX, timemap and availability endpoints are never asked. The archive's
robots.txt is read once with the project fetcher's reader and matched against every path.

    uv run python scripts/sources/web_reports/wayback_trees.py DEST TREES.json [threads] \\
        [interval_s] [shard i/n]

A page lands at <dest_root>/<host>/<path>; each ask leaves one JSON line in
<dest_root>/receipts.receipts (url, replay with its 14-digit stamp, memento, status, bytes,
sha256, path), and a URL with a receipt is not asked again. Each thread keeps one connection
open, since the archive refuses an address that connects too often. A 429 or 503 rests every
thread (60 s, 180 s, 600 s) and the fourth in a row ends the run; a failed connect rests them
too and is asked again, ten in a row ending the run.
"""

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
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEST, TREES = Path(sys.argv[1]), Path(sys.argv[2])
THREADS = int(sys.argv[3]) if len(sys.argv) > 3 else 3
INTERVAL = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
SHARD = tuple(int(x) for x in sys.argv[5].split("/")) if len(sys.argv) > 5 else (0, 1)
STAMP = "2001"
PROBES = int(os.environ.get("ARK_PROBES", "3"))  # asks before a tree with no capture is left

_spec = importlib.util.spec_from_file_location("hf", ROOT / "scripts/harness/fetch.py")
hf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hf)

SAFE = re.compile(r"[^A-Za-z0-9._/~-]")
CAPTURE = re.compile(r"/web/(\d{14})")
lock = threading.Lock()
gate = threading.Lock()
state = {"next": 0.0, "strikes": 0, "errors": 0, "stop": False, "got": 0, "miss": 0}
robots_cache: dict = {}


def local_name(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    path = posixpath.normpath(parts.path or "/").lstrip("/")
    if "." not in path.rsplit("/", 1)[-1]:
        path = (path + "/_index.html").lstrip("/")  # a directory URL, with or without its slash
    if parts.query:
        path += "_" + parts.query
    return f"{parts.netloc.lower()}/{SAFE.sub('_', path)}"[:240]


def wait_turn() -> None:
    with gate:
        now = time.time()
        if state["next"] > now:
            time.sleep(state["next"] - now)
        state["next"] = time.time() + INTERVAL


local = threading.local()


def get(path: str) -> tuple[int, dict, bytes]:
    """One GET on this thread's kept-alive connection to the archive."""
    conn = getattr(local, "conn", None)
    if conn is None:
        conn = local.conn = http.client.HTTPSConnection("web.archive.org", timeout=120)
    try:
        conn.request(
            "GET", path, headers={"User-Agent": hf.USER_AGENT, "Accept-Encoding": "identity"}
        )
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, body
    except Exception:
        conn.close()
        local.conn = None
        raise


def ask(url: str, rec) -> bool | None:
    """True for a capture, False for none, None when the run must stop. A failed connect is
    neither: it rests every thread and is asked again, and ten in a row end the run."""
    while not state["stop"]:
        wait_turn()
        url, _, near = url.partition("\t")  # "<url>\t<14-digit stamp>" asks the capture nearest it
        path = f"/web/{near or STAMP}id_/" + re.sub(  # a byte outside ASCII goes percent-encoded
            r"[^\x21-\x7e]",
            lambda m: urllib.parse.quote(m.group(0).encode("latin-1", "replace")),
            url,
        )
        with lock:
            verdict, _, why = hf.read_robots("https://web.archive.org" + path, 60, robots_cache)
        if verdict != "allowed":
            if "could not be read" in why:
                with lock:
                    robots_cache.clear()
                    state["errors"] += 1
                    state["next"] = time.time() + 60
                    if state["errors"] >= 10:
                        state["stop"] = True
                        print(json.dumps({"stopped": "robots unreadable", "why": why}), flush=True)
                continue
            state["stop"] = True
            print(json.dumps({"stopped": "robots", "verdict": verdict, "why": why}), flush=True)
            return None
        receipt = {
            "url": url,
            "replay": None,
            "memento": None,
            "status": None,
            "bytes": 0,
            "sha256": None,
            "path": None,
        }
        try:
            status, headers, body = get(path)
            hops = 0
            while status in (301, 302, 303, 307) and hops < 4:
                loc = urllib.parse.urlsplit(
                    urllib.parse.urljoin(
                        "https://web.archive.org" + path, headers.get("location", "")
                    )
                )
                if loc.netloc not in ("web.archive.org", ""):
                    break
                path = loc.path + ("?" + loc.query if loc.query else "")
                status, headers, body = get(path)
                hops += 1
        except (http.client.HTTPException, TimeoutError, ConnectionError, OSError):
            with lock:
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
                    return None
                state["next"] = time.time() + (60, 180, 600)[state["strikes"] - 1]
            continue
        hit = status == 200 and bool(CAPTURE.search(path))
        receipt.update(
            status=status,
            replay="https://web.archive.org" + path if hit else None,
            memento=headers.get("memento-datetime"),
        )
        if hit:
            name = local_name(url)
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
            receipt.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), path=name)
        with lock:
            state["strikes"] = state["errors"] = 0
            state["got" if hit else "miss"] += 1
            rec.write(json.dumps(receipt) + "\n")
            rec.flush()
            if (state["got"] + state["miss"]) % 100 == 0:
                print(json.dumps({"got": state["got"], "miss": state["miss"]}), flush=True)
        return hit
    return None


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    rec_path = DEST / "receipts.receipts"
    known: dict[str, bool] = {}
    if rec_path.exists():
        for line in rec_path.read_text().splitlines():
            try:
                r = json.loads(line)
                known[r["url"]] = r.get("status") == 200 and bool(r.get("path"))
            except (json.JSONDecodeError, KeyError):
                pass
    trees = json.loads(TREES.read_text())
    mine = [
        (t, v["urls"])
        for t, v in sorted(trees.items())
        if zlib.crc32(t.encode()) % SHARD[1] == SHARD[0]
    ]
    rec = rec_path.open("a")
    tstate = (DEST / "trees.state").open("a")

    def tree(job) -> None:
        name, urls = job
        hits = sum(1 for u in urls if known.get(u))
        asked = 0
        for i, url in enumerate(urls):
            if state["stop"]:
                return
            if i >= PROBES and hits == 0:
                break
            if url.partition("\t")[0] in known:
                continue
            got = ask(url, rec)
            if got is None:
                return
            asked += 1
            hits += bool(got)
        with lock:
            tstate.write(
                json.dumps({"tree": name, "urls": len(urls), "asked": asked, "hits": hits}) + "\n"
            )
            tstate.flush()

    with cf.ThreadPoolExecutor(THREADS) as ex:
        list(ex.map(tree, mine))
    print(
        json.dumps({"done": not state["stop"], "got": state["got"], "miss": state["miss"]}),
        flush=True,
    )
    return 0 if not state["stop"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
