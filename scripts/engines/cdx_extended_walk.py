"""Walk public suffixes through the CDX index for 1996 to 2013 host-years, one lane of N.

One paged
`matchType=domain` request over a public suffix (`co.uk`, `co.nz`, `com.au`) returns thousands
of exact (host, year) captures: every host under a
1,000-block slice of the index, with the years it was captured in. A bare TLD answers 403, so
`.com` cannot be walked this way (`docs/lore/laws.md`). The suffixes are the ICANN two-label ones
of TLDs he weighs at 0.5 or more English, ranked by `cdx_walk_order.py`.

**Root URLs only.** `filter=urlkey:^[^/]*\\)/$` keeps the root captures of each host: 92.5% of
the hosts of a page at a third of the bytes, and a page answers 2 to 3 times faster. The regex
must be anchored; IA's filter is a search, so an unanchored `\\)/` matches every row.

**One row per (host, year)**, the earliest 2xx or 3xx capture, as `{url, timestamp, status}` in
`walk_<suffix>_ps<P>_p<N>_<years>.jsonl.gz`, 1996 to 2001 under `<data>/raw/cdx_suffix/` (the
hostname ingest prices it) and 2002 to 2013 under `<data>/raw/extended/ia_cdx_hostnames/` (the
extended exporter), written under a dot name and renamed whole. The host
is read from `original`, never from the urlkey, which folds `www.` into the apex.

**Failures cost time, never rows.** A page streams for up to minutes, and the server can cut a
long sparse scan. A cut page keeps what arrived (`_cut_<stamp>` journal) and is asked again as
its ten exact 1/10 subpages, last first, stopping at the subpage that starts before the cut
row. A page silent for 60 s answers 504, so its
100-block subpages 0 and 5 are probed and the other eight asked only if a probe has rows. Any
other answer marks nothing done: a 429 or 503 pauses the lane for `Retry-After` or a minute a
throttle, a refusal, `ENETDOWN` or 403 from 30 s doubling to 15 min, and requests start
`--min-interval` apart, since a burst earns a block of the address.

`--workers` requests run at once in this one client; the channel rule counts clients, so this
refuses to start beside `--max-local` other CDX clients here, and idles while
`<state home>/pause-platform` exists. Every request is a `log.tsv` row in its state folder, so a
rate is always charged with its waits and failures.

    python3 scripts/engines/cdx_extended_walk.py --lane 0 --lanes 3 [--workers 2] [--data DIR]
"""

from __future__ import annotations

import argparse
import gzip
import http.client
import importlib.util
import io
import json
import os
import random
import signal
import threading
import time
import urllib.parse
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOST = "web.archive.org"
ROOT = r"^[^/]*\)/$"
PAGE = 1000
FIRST, SPLIT, LAST = 1996, 2002, 2013
DROP_AFTER = 5  # answered requests priced at nothing before a unit is dropped
THROTTLES = {"HTTP429", "HTTP503"}
FAST = {
    "ConnectTimeout",
    "TimeoutError",
    "ConnectionResetError",
    "RemoteDisconnected",
}
STOP = threading.Event()

_spec = importlib.util.spec_from_file_location(
    "cdx_platform_walk", Path(__file__).with_name("cdx_platform_walk.py")
)
_platform = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_platform)
host_of = _platform.host_of
cdx_clients = _platform.cdx_clients
mine, UA = _platform.mine, _platform.UA


def _sigterm(signum, frame):  # noqa: ARG001
    STOP.set()


def heavy_suffixes() -> list[str]:
    """The ICANN two-label public suffixes of the TLDs he weighs at 0.5 or more English."""
    spec = importlib.util.spec_from_file_location("share", REPO / "src/ark/english_share.py")
    share = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(share)  # one module, not the package: the VPS runs bare python3
    heavy = {t for t, w in share.english_weights().items() if w >= 0.5} - {"arpa"}
    psl = (REPO / "src/ark/data/public_suffix_list.dat").read_text(encoding="utf-8")
    icann = psl.split("===BEGIN ICANN DOMAINS===")[1].split("===END ICANN DOMAINS===")[0]
    names = (line.strip() for line in icann.splitlines())
    return [s for s in names if s.isascii() and s.count(".") == 1 and s.split(".")[1] in heavy]


def subpages(task: tuple, cut: bool) -> list[tuple]:
    """The 1/10 subpages to ask after a failed page: all ten last first after a cut, or the
    0 and 5 probes after a silent 504. A 100-block page is not split again on a 504."""
    sfx, size, page, *rest = task
    if size < 10 or (not cut and size < PAGE):
        return []
    ks = range(9, -1, -1) if cut else (0, 5)
    return [(sfx, size // 10, page * 10 + k, *rest) for k in ks]


def rank(units, order: dict, asked: dict, explore: int) -> tuple[list, list, list]:
    """(priced, exploring, waiting): every unit that prices at all on 1996 to 2001, then the
    rest, each by its EE per request over both parts; the unpriced ones still owed `explore`
    pages; the explored ones waiting for a price. A unit priced at nothing over `DROP_AFTER`
    answered requests is dropped."""
    priced, exploring, waiting = [], [], []
    for u in units:
        price = order.get(f"{u[0]} {u[1]}") or {}
        p1, total = price.get("p1", 0), price.get("p1", 0) + price.get("p2", 0)
        if total > 0:
            priced.append(((p1 <= 0, -total), u))
        elif price.get("n", 0) < DROP_AFTER:
            (exploring if asked.get(u, 0) < explore else waiting).append(u)
    priced.sort(key=lambda k: k[0])
    return [u for _, u in priced], exploring, waiting


def fetch(task, a, sink):
    """Stream one page into `sink`; (status, complete, seconds, bytes, Retry-After)."""
    sfx, size, page, first, last, _kind = task
    query = urllib.parse.urlencode(
        [
            ("url", sfx),
            ("matchType", "domain"),
            ("from", str(first)),
            ("to", str(last)),
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


def write_journal(out: Path, name: str, rows: list) -> None:
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / f".{name}.tmp"
    with gzip.GzipFile(tmp, "wb", mtime=0) as raw, io.TextIOWrapper(raw) as fh:
        for ts, original, st in rows:
            fh.write(json.dumps({"url": original, "timestamp": ts, "status": st}) + "\n")
    os.replace(tmp, out / f"{name}.jsonl.gz")


def key_of(task: tuple) -> str:
    """A task's done key: suffix, page size, page and years; the kind is how it was queued."""
    return " ".join(map(str, task[:5]))


def encode(task: tuple, meta: tuple) -> str:
    """A pending subpage and why it is asked: `cut` (stop at the cut row), `probe` (open the
    other eight if it has rows) or `rest`, with the parent's key."""
    return "\t".join([key_of(task) + " " + task[5], *meta])


def decode(line: str) -> tuple[tuple, tuple]:
    head, *meta = line.split("\t")
    s, z, p, f, la, k = head.split()
    return (s, int(z), int(p), int(f), int(la), k), tuple(meta)


class Lane:
    """The queue, the done set and the log of one lane, shared by its workers under a lock."""

    def __init__(self, a: argparse.Namespace):
        self.a, self.lock, self.pages, self.asked = a, threading.Lock(), {}, {}
        done = a.state_dir / "done.txt"
        lines = done.read_text().splitlines() if done.exists() else []
        self.done = {" ".join(ln.split()[:5]) for ln in lines}
        self.pending, self.subq, self.meta = a.state_dir / "pending.txt", [], {}
        for ln in self.pending.read_text().splitlines() if self.pending.exists() else []:
            task, meta = decode(ln)
            if key_of(task) not in self.done and task not in self.meta:
                self.subq.append(task)
                self.meta[task] = meta
        self.opened = {m[1] for m in self.meta.values() if m[0] == "rest"}
        self.inflight, self.fails, self.order, self.order_mtime, self.taken = set(), {}, {}, -1.0, 0
        self.log = open(a.state_dir / "log.tsv", "a", buffering=1)
        self.pause_until = self.next_start = 0.0
        self.throttled = self.refused = self.transient = 0

    def add_pages(self, sfx: str, n: int) -> None:
        """Queue this lane's share of a suffix's pages, those not answered yet, shuffled."""
        for kind in ("p1", "all"):
            ps = [p for p in range(n) if mine(f"{sfx} {p}", self.a.lane, self.a.lanes)]
            ps = [p for p in ps if ((sfx, str(p)) in self.a.walked) == (kind == "p1")]
            tasks = [(sfx, PAGE, p, FIRST, LAST, kind) for p in ps]
            random.Random(f"{sfx} {kind}").shuffle(tasks)
            if tasks:
                self.pages[(sfx, kind)] = [t for t in tasks if key_of(t) not in self.done]
                self.asked[(sfx, kind)] = len(tasks) - len(self.pages[(sfx, kind)])

    def rerank(self, force: bool = False) -> None:
        mtime = self.a.order.stat().st_mtime if self.a.order.exists() else 0.0
        if mtime != self.order_mtime:
            try:
                self.order = json.loads(self.a.order.read_text()).get("units", {}) if mtime else {}
                self.order_mtime, force = mtime, True
            except (OSError, ValueError):
                pass
        if force:
            self.ranked, self.exploring, self.waiting = rank(self.pages, self.order, self.asked, 2)
            self.log.write(f"# order {len(self.ranked)} priced, {len(self.exploring)} exploring\n")

    def save_pending(self) -> None:
        owed = self.subq + sorted(self.inflight & self.meta.keys())
        tmp = self.pending.with_suffix(".tmp")
        tmp.write_text("".join(encode(t, self.meta[t]) + "\n" for t in owed))
        os.replace(tmp, self.pending)

    def requeue(self, task: tuple, front: bool) -> None:
        """Put an unanswered task back: a subpage at the head (the pause does the waiting), a
        page at the front or the back of its unit."""
        self.inflight.discard(task)
        if task in self.meta:
            self.subq.insert(0, task)
        else:
            q = self.pages[(task[0], task[5])]
            q.insert(0, task) if front else q.append(task)
            self.asked[(task[0], task[5])] -= 1
        self.save_pending()

    def take(self):
        with self.lock:
            self.rerank()
            while self.subq:
                task = self.subq.pop(0)
                if key_of(task) not in self.done:
                    self.inflight.add(task)
                    return task
                self.meta.pop(task, None)
            self.taken += 1
            first = self.exploring if self.taken % 4 == 0 else self.ranked
            for u in first + self.ranked + self.exploring + self.waiting:
                if self.pages[u]:
                    task = self.pages[u].pop(0)
                    self.asked[u] += 1
                    if u in self.exploring and self.asked[u] == 2:
                        self.rerank(force=True)
                    self.inflight.add(task)
                    return task
            return None

    def gate(self) -> bool:
        """Wait for the pause and the start interval; False once the lane is stopping."""
        while not STOP.is_set():
            with self.lock:
                now = time.time()
                held = _platform.PAUSE_FLAG.exists() or now < self.pause_until
                if not held and now >= self.next_start:
                    self.next_start = now + self.a.min_interval
                    return True
            time.sleep(1)
        return False

    def count_missing(self, missing: list[str]) -> None:
        """Count the suffixes pages.json lacks, one a minute, while the lane walks."""
        path, ask = self.a.state_dir / "pages.json", {"matchType": "domain", "showNumPages": "true"}
        for sfx in missing:
            if STOP.wait(60) or not self.gate():
                return
            status, body, _ = _platform.fetch({**ask, "url": sfx, "pageSize": str(PAGE)}, 90)
            n = int(body.strip()) if status == "200" and body.strip().isdigit() else None
            with self.lock:
                self.log.write(f"# count {sfx} {n}\n")
                if n is not None:
                    counts = json.loads(path.read_text()) if path.exists() else {}
                    counts[sfx] = n
                    path.with_suffix(".tmp").write_text(json.dumps(counts, sort_keys=True))
                    os.replace(path.with_suffix(".tmp"), path)
                    self.add_pages(sfx, n)
                    self.rerank(force=True)

    def work(self) -> None:
        while self.gate():
            task = None
            try:
                task = self.take()
                if task is None:
                    with self.lock:
                        if not self.subq and not self.inflight:
                            return
                    time.sleep(30)
                    continue
                answer = self.ask(task)
                with self.lock:
                    self.settle(task, *answer)
            except Exception as exc:  # noqa: BLE001  a worker never dies holding a task
                with self.lock:
                    if task is not None and task in self.inflight:
                        self.requeue(task, front=True)
                    self.pause_until = max(self.pause_until, time.time() + 30)
                    self.log.write(f"# error {type(exc).__name__}: {exc}\n")

    def ask(self, task: tuple) -> tuple:
        """Fetch one page and write its journals; what settle needs."""
        keep: dict = {}
        edge: list = []
        rows = [0]

        def sink(line: bytes) -> None:
            parts = line.decode("utf-8", "replace").split(" ")
            if len(parts) < 4:
                return
            rows[0] += 1
            urlkey, ts, original, status = parts[:4]
            edge[1:] = [urlkey] if edge else [urlkey, urlkey]
            host, year = host_of(original), ts[:4]
            if host and year.isdigit() and ((host, year) not in keep or ts < keep[(host, year)][0]):
                keep[(host, year)] = (ts, original, status)

        started = time.time()
        status, complete, secs, nbytes, after = fetch(task, self.a, sink)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(started))
        sfx, size, page, first, last, _kind = task
        core = sorted(v for (_h, y), v in keep.items() if int(y) < SPLIT)
        ext = sorted(v for (_h, y), v in keep.items() if SPLIT <= int(y) <= last)
        name = f"walk_{sfx}_ps{size}_p{page}_{first}-{last}" + ("" if complete else f"_cut_{stamp}")
        if core:
            write_journal(self.a.data / "raw/cdx_suffix", name, core)
        if ext:
            write_journal(self.a.data / "raw/extended/ia_cdx_hostnames", name, ext)
        row = [stamp, *task, status, int(complete), round(secs, 1), nbytes, rows[0], len(core)]
        row.append(len(ext))
        return status, complete, rows[0], edge, after, row

    def back_off(self, task: tuple, seconds: float, why: str) -> None:
        self.requeue(task, front=False)
        self.pause_until = max(self.pause_until, time.time() + seconds)
        self.log.write(f"# pause {round(seconds)} s: {why}\n")

    def settle(self, task, status, complete, rows, edge, after, row) -> None:
        """Book one answer under the lane lock."""
        key = key_of(task)
        self.log.write("\t".join(map(str, row)) + "\n")
        tries = self.fails.get(key, 0)
        silent = status == "HTTP504" and (task[1] >= PAGE or tries >= 3)
        if not (silent or (status == "200" and (complete or rows > 0))):
            self.fails[key] = tries + 1
            address = status in THROTTLES | FAST | {"ConnectionRefusedError", "OSError"}
            if tries >= 8 and not address:
                self.inflight.discard(task)
                self.save_pending()
                self.log.write(f"# parked {status} {key}: asked again next start\n")
            elif status in THROTTLES:
                self.throttled += 1
                wait = after or 60.0 * self.throttled
                self.back_off(task, max(wait, 1800) if self.throttled >= 6 else wait, status)
            elif status in FAST and self.transient < self.a.max_transient:
                self.transient += 1
                self.requeue(task, front=True)
                self.pause_until = max(self.pause_until, time.time() + 5)
            else:
                self.refused, self.transient = self.refused + 1, 0
                self.back_off(task, min(900, 30 * 2 ** min(self.refused - 1, 5)), status)
            return
        self.throttled = self.refused = self.transient = 0
        self.inflight.discard(task)
        role, parent, stop = self.meta.pop(task, ("", "", ""))
        if role == "cut" and edge and edge[0] < stop:  # the lower siblings came before the cut
            sib = {t for t in self.subq if self.meta[t][1] == parent and t[2] < task[2]}
            self.subq = [t for t in self.subq if t not in sib]
        if role == "probe" and edge and parent not in self.opened:
            self.opened.add(parent)
            base = (task[2] // 10) * 10
            rest = [(task[0], task[1], base + k, *task[3:]) for k in range(10) if k not in (0, 5)]
            self.meta.update({t: ("rest", parent, "") for t in rest})
            self.subq[0:0] = rest
        if not (status == "200" and complete):
            subs = subpages(task, cut=bool(edge))
            self.meta.update(
                {t: ("cut", key, edge[-1]) if edge else ("probe", key, "") for t in subs}
            )
            self.subq[0:0] = subs
            if not subs:
                self.log.write(f"# skipped {status} {key}\n")
        self.save_pending()
        self.done.add(key)
        with open(self.a.state_dir / "done.txt", "a") as fh:
            fh.write(key + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lane", type=int, required=True)
    ap.add_argument("--lanes", type=int, default=1)
    ap.add_argument("--data", type=Path, default=os.environ.get("ARK_WALK_DATA", REPO / "data"))
    ap.add_argument("--workers", type=int, default=1, help="requests at once in this client")
    ap.add_argument("--max-local", type=int, default=2, help="CDX clients allowed here")
    ap.add_argument("--min-interval", type=float, default=10.0, help="seconds between starts")
    ap.add_argument("--connect-timeout", type=float, default=20)
    ap.add_argument(
        "--max-transient",
        type=int,
        default=8,
        help="dropped connects in a row before pausing longer",
    )
    ap.add_argument("--timeout", type=float, default=70, help="per read; the gateway 504s at 60 s")
    a = ap.parse_args()
    signal.signal(signal.SIGTERM, _sigterm)
    signal.signal(signal.SIGHUP, _sigterm)
    running = cdx_clients()
    if running >= a.max_local:
        raise SystemExit(f"{running} CDX clients already here; {a.max_local} is the cap")
    a.data = Path(a.data)
    a.state_dir = a.data / f"raw/cdx_walk/lane{a.lane}"
    a.state_dir.mkdir(parents=True, exist_ok=True)
    a.order, walked = a.data / "queue/cdx_order.json", a.data / "queue/cdx_walked.txt"
    a.walked = (
        {tuple(ln.split()[:2]) for ln in walked.read_text().splitlines()}
        if walked.exists()
        else set()
    )
    pages = a.state_dir / "pages.json"
    counts = json.loads(pages.read_text()) if pages.exists() else {}
    wanted = sorted(heavy_suffixes(), key=lambda s: -counts.get(s, 0))
    lane = Lane(a)
    for sfx in wanted:
        lane.add_pages(sfx, counts.get(sfx, 0))
    lane.rerank(force=True)
    missing = [s for s in wanted if s not in counts]
    threading.Thread(target=lane.count_missing, args=(missing,), daemon=True).start()
    threads = [threading.Thread(target=lane.work) for _ in range(a.workers)]
    for i, t in enumerate(threads):
        t.start()
        time.sleep(5 if i < a.workers - 1 else 0)
    for t in threads:
        t.join()
    lane.log.write(
        f"# exit {time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())} pending={len(lane.subq)}\n"
    )


if __name__ == "__main__":
    main()
