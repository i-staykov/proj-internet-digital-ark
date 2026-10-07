"""Walk public suffixes through the CDX index for 2002 to 2015 host-years, one lane of N.

His 2014 file holds 101 names and his 2002 to 2011 files are thin, so one paged
`matchType=domain` request over a public suffix (`co.uk`, `co.nz`, `com.au`) returns thousands
of exact (host, year) captures that are net-new to his same-year file: every host under a
1,000-block slice of the index, with the years it was captured in. A bare TLD answers 403, so
`.com` cannot be walked this way (`docs/lore/laws.md`).

**Root URLs only.** `filter=urlkey:^[^/]*\\)/$` keeps the root captures of each host: 92.5% of
the hosts of a page at a third of the bytes, and a page answers 2 to 3 times faster. The regex
must be anchored; IA's filter is a search, so an unanchored `\\)/` matches every row.

**One row per (host, year)**, the earliest 2xx or 3xx capture, as `{url, timestamp, status}` in
`<out>/<suffix>_ps<P>_p<N>.jsonl.gz`, the journal `scripts/round/extended_export.py` prices: the
folder name is the source it approves, and it drops whatever his same-year file holds. The host
is read from `original`, never from the urlkey, which folds `www.` into the apex.

**Failures cost time, never rows.** A page streams for up to minutes, and the server can cut a
long sparse scan. A cut page keeps what arrived (`_cut_<stamp>` journal) and is asked again as
its ten exact 1/10 subpages, last first, stopping at the subpage that holds the cut row. A page
silent for 60 s answers 504; that is almost always a region captured only after 2015, so its
100-block subpages 0 and 5 are probed and the other eight asked only if a probe has rows. A
dropped connect is retried after 5 s (web.archive.org drops some SYNs from the VPS); 429 and
503 back off, and six in a row stop the lane.

`--workers` requests run at once in this one client; the channel rule counts clients, so this
refuses to start beside `--max-local` other CDX clients here, and idles while
`<state home>/pause-extended` exists. Every request is a `log.tsv` row in `--state-dir`, so a
rate is always charged with its waits and failures.

    uv run python scripts/engines/cdx_extended_walk.py SUFFIXES --lane 0 --lanes 3 \\
        --deadline <epoch> [--workers 2]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import http.client
import importlib.util
import json
import os
import random
import signal
import threading
import time
import urllib.parse
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
HOST = "web.archive.org"
ROOT = r"^[^/]*\)/$"
PAGE = 1000
STATE_HOME = Path(os.environ.get("ARK_STATE_DIR", Path.home() / "ark/state"))
PAUSE_FLAG = STATE_HOME / "pause-extended"
THROTTLES = {"HTTP429", "HTTP503"}
TRANSIENT = {
    "ConnectTimeout",
    "TimeoutError",
    "ConnectionResetError",
    "ConnectionRefusedError",
    "RemoteDisconnected",
    "OSError",
    "gaierror",
    "SSLError",
}
STOP = threading.Event()

_spec = importlib.util.spec_from_file_location(
    "cdx_platform_walk", Path(__file__).with_name("cdx_platform_walk.py")
)
_platform = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_platform)
host_of = _platform.host_of
cdx_clients = _platform.cdx_clients


def _sigterm(signum, frame):  # noqa: ARG001
    STOP.set()


def mine(key: str, lane: int, lanes: int) -> bool:
    return hashlib.blake2b(key.encode(), digest_size=8).digest()[0] % lanes == lane


def subpages(task: tuple[str, int, int], cut: bool) -> list[tuple[str, int, int]]:
    """The 1/10 subpages to ask after a failed page: all ten last first after a cut, or the
    0 and 5 probes after a silent 504. A 100-block page is not split again on a 504."""
    sfx, size, page = task
    if size < 10 or (not cut and size < PAGE):
        return []
    ks = range(9, -1, -1) if cut else (0, 5)
    return [(sfx, size // 10, page * 10 + k) for k in ks]


def fetch(task, a, sink):
    """Stream one page into `sink`; (status, complete, seconds, bytes, Retry-After)."""
    sfx, size, page = task
    query = urllib.parse.urlencode(
        [
            ("url", sfx),
            ("matchType", "domain"),
            ("from", str(a.first)),
            ("to", str(a.last)),
            ("filter", "statuscode:[23][0-9][0-9]"),
            ("filter", "urlkey:" + ROOT),
            ("fl", "urlkey,timestamp,original,statuscode"),
            ("pageSize", str(size)),
            ("page", str(page)),
        ]
    )
    t0 = time.time()
    nbytes = 0
    conn = http.client.HTTPSConnection(HOST, timeout=a.connect_timeout)
    try:
        try:
            conn.connect()
        except Exception as exc:  # noqa: BLE001
            name = "ConnectTimeout" if isinstance(exc, TimeoutError) else type(exc).__name__
            return name, False, time.time() - t0, 0, None
        conn.sock.settimeout(a.timeout)
        conn.request("GET", "/cdx/search/cdx?" + query, headers={"User-Agent": UA})
        resp = conn.getresponse()
        if resp.status != 200:
            after = _platform.retry_after(resp.getheader("Retry-After"))
            resp.read(4096)
            return f"HTTP{resp.status}", False, time.time() - t0, 0, after
        buf, complete = b"", True
        try:
            while chunk := resp.read1(1 << 16):
                nbytes += len(chunk)
                *lines, buf = (buf + chunk).split(b"\n")
                for line in lines:
                    sink(line)
        except Exception:  # noqa: BLE001  a cut stream keeps what arrived
            complete = False
        return "200", complete, time.time() - t0, nbytes, None
    except Exception as exc:  # noqa: BLE001
        return type(exc).__name__, False, time.time() - t0, nbytes, None
    finally:
        conn.close()


class Lane:
    """The queue, the done set and the log of one lane, shared by its workers under a lock."""

    def __init__(self, a: argparse.Namespace, queue: list[tuple[str, int, int]]):
        self.a, self.lock = a, threading.Lock()
        a.state_dir.mkdir(parents=True, exist_ok=True)
        a.out.mkdir(parents=True, exist_ok=True)
        done = a.state_dir / "done.txt"
        self.done = set(done.read_text().splitlines()) if done.exists() else set()
        self.pending = a.state_dir / "pending.txt"
        sub = (
            [tuple(ln.split()) for ln in self.pending.read_text().splitlines()]
            if self.pending.exists()
            else []
        )
        self.queue = [(s, int(z), int(p)) for s, z, p in sub] + queue
        self.subs = set(self.queue[: len(sub)])
        self.stops: dict = {}
        self.probes: dict = {}
        self.opened: set = set()
        self.log = open(a.state_dir / "log.tsv", "a", buffering=1)
        self.delay, self.throttled, self.transient, self.pause_until = a.delay, 0, 0, 0.0

    def take(self):
        with self.lock:
            while self.queue and not STOP.is_set() and time.time() < self.a.deadline:
                task = self.queue.pop(0)
                key = " ".join(map(str, task))
                if key not in self.done:
                    self.done.add(key)
                    return task, key
            return None, None

    def work(self) -> None:
        a = self.a
        while True:
            while PAUSE_FLAG.exists() and not STOP.is_set() and time.time() < a.deadline:
                time.sleep(30)
            task, key = self.take()
            if task is None:
                return
            while time.time() < self.pause_until:
                time.sleep(1)
            keep: dict = {}
            edge: list = []

            rows = [0]

            def sink(line: bytes, keep=keep, edge=edge, rows=rows) -> None:
                parts = line.decode("utf-8", "replace").split(" ")
                if len(parts) < 4:
                    return
                rows[0] += 1
                urlkey, ts, original, status = parts[:4]
                edge[1:] = [urlkey] if edge else [urlkey, urlkey]
                host = host_of(original)
                if (
                    host
                    and ts[:4].isdigit()
                    and ((host, ts[:4]) not in keep or ts < keep[(host, ts[:4])][0])
                ):
                    keep[(host, ts[:4])] = (ts, original, status)

            started = time.time()
            status, complete, secs, nbytes, after = fetch(task, a, sink)
            stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(started))
            if keep:
                cut = "" if complete else f"_cut_{stamp}"
                name = f"{task[0]}_ps{task[1]}_p{task[2]}{cut}.jsonl.gz"
                with gzip.open(a.out / f"{name}.part", "wt") as fh:
                    for (_host, _year), (ts, original, st) in sorted(keep.items()):
                        fh.write(
                            json.dumps({"url": original, "timestamp": ts, "status": st}) + "\n"
                        )
                os.replace(a.out / f"{name}.part", a.out / name)
            self.settle(
                task,
                key,
                status,
                complete,
                edge,
                after,
                [
                    stamp,
                    *task,
                    status,
                    int(complete),
                    round(secs, 1),
                    nbytes,
                    rows[0],
                    len(keep),
                    round(self.delay, 1),
                ],
            )
            time.sleep(self.delay + random.random())

    def settle(self, task, key, status, complete, edge, after, row) -> None:
        with self.lock:
            self.log.write("\t".join(map(str, row)) + "\n")
            if status in TRANSIENT and not row[7] and self.transient < 8:
                self.transient += 1
                self.pause_until = time.time() + 5
                self.done.discard(key)
                self.queue.insert(0, task)
                return
            if status in THROTTLES or status in TRANSIENT:
                self.throttled += 1
                self.delay = min(self.delay * 2, 60)
                self.pause_until = time.time() + (after or 60.0 * self.throttled)
                self.done.discard(key)
                self.queue.insert(0, task)
                if self.throttled >= 6:
                    self.log.write(f"# stop: {self.throttled} throttles running\n")
                    STOP.set()
                return
            self.throttled = self.transient = 0
            self.delay = max(self.a.delay, self.delay * 0.9)
            stop = self.stops.get(task)
            if stop and edge and edge[0] <= stop[0]:  # holds the cut row: the rest lie before it
                self.queue = [
                    t for t in self.queue if self.stops.get(t, (None, None))[1] != stop[1]
                ]
            parent = self.probes.pop(task, None)
            if parent and edge and parent not in self.opened:
                self.opened.add(parent)
                base = (task[2] // 10) * 10
                rest = [(task[0], task[1], base + k) for k in range(10) if k not in (0, 5)]
                self.queue[0:0] = rest
                self.subs.update(rest)
            if not (status == "200" and complete):
                subs = subpages(task, cut=bool(edge))
                for t in subs:
                    if edge:
                        self.stops[t] = (edge[-1], key)
                    else:
                        self.probes[t] = key
                self.queue[0:0] = subs
                self.subs.update(subs)
                if not subs:
                    self.log.write(f"# skipped {status} {key}\n")
            with open(self.a.state_dir / "done.txt", "a") as fh:
                fh.write(key + "\n")
            self.pending.write_text(
                "".join(f"{s} {z} {p}\n" for s, z, p in self.queue if (s, z, p) in self.subs)
            )


def page_counts(suffixes: list[str], a: argparse.Namespace) -> dict[str, int]:
    """Pages of PAGE blocks per suffix, asked once and kept in `<state-dir>/pages.json`."""
    path = a.state_dir / "pages.json"
    counts = json.loads(path.read_text()) if path.exists() else {}
    for sfx in suffixes:
        if sfx in counts:
            continue
        params = {"url": sfx, "matchType": "domain", "showNumPages": "true", "pageSize": str(PAGE)}
        status, body, _ = _platform.fetch(params, 90)
        if status == "200" and body.strip().isdigit():
            counts[sfx] = int(body.strip())
            path.write_text(json.dumps(counts, indent=1, sort_keys=True))
        time.sleep(1)
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("suffixes", type=Path, help="one public suffix per line, in priority order")
    ap.add_argument("--lane", type=int, required=True)
    ap.add_argument("--lanes", type=int, default=1)
    ap.add_argument("--deadline", type=int, required=True, help="absolute epoch to stop at")
    ap.add_argument("--out", type=Path, default=REPO / "data/raw/extended/ia_cdx_hostnames")
    ap.add_argument("--state-dir", type=Path, default=REPO / "data/raw/cdx_extended")
    ap.add_argument("--workers", type=int, default=1, help="requests at once in this client")
    ap.add_argument("--max-local", type=int, default=2, help="CDX clients allowed here")
    ap.add_argument("--first", type=int, default=2002)
    ap.add_argument("--last", type=int, default=2015)
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--connect-timeout", type=float, default=20)
    ap.add_argument("--timeout", type=float, default=70, help="per read; the gateway 504s at 60 s")
    a = ap.parse_args()
    signal.signal(signal.SIGTERM, _sigterm)
    running = cdx_clients()
    if running >= a.max_local:
        raise SystemExit(f"{running} CDX clients already here; {a.max_local} is the cap")
    a.state_dir.mkdir(parents=True, exist_ok=True)
    suffixes = [s.split("#", 1)[0].strip().lower() for s in a.suffixes.read_text().splitlines()]
    suffixes = [s for s in suffixes if s]
    counts = page_counts(suffixes, a)
    queue = []
    for sfx in suffixes:  # priority order between suffixes, shuffled pages within one
        pages = [
            (sfx, PAGE, p) for p in range(counts.get(sfx, 0)) if mine(f"{sfx} {p}", a.lane, a.lanes)
        ]
        random.Random(sfx).shuffle(pages)
        queue += pages
    lane = Lane(a, queue)
    threads = [threading.Thread(target=lane.work) for _ in range(a.workers)]
    for i, t in enumerate(threads):
        t.start()
        time.sleep(5 if i < a.workers - 1 else 0)
    for t in threads:
        t.join()
    lane.log.write(
        f"# exit {time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())} queue={len(lane.queue)}\n"
    )


if __name__ == "__main__":
    main()
