"""Walk multi-tenant platforms to the end of the CDX index with resumeKey, one lane of N.

A free host (`alice.cjb.net`) or dynamic-DNS name is a distinct site, which spec IV.8 counts
host by host. `cdx_suffix_sweep.py` walked 31 such platforms in September by page number, and
a page that failed was skipped and still ended in `.done`, so five walks stopped short
(freeservers.com at c, netfirms.com at d, dyndns.org in the digits, 50megs.com in www, cjb.net
near the end). This asks `matchType=domain` with `showResumeKey` until the index says twice
that there is no more, and writes `.done` only then.

**No `collapse`.** The server collapses adjacent index lines, and a domain walk is sorted by
SURT across every host, so `collapse=timestamp:4` folds a host into its neighbour whenever
both sit in the same year: on tonight's cjb.net probe that is at least 56.7% of host-years,
dropped without an error. One row per `(host, year)` is kept here instead, and written as the
captured `{url, timestamp, status}` to `suffix_<platform>_rk_<stamp>_<page>.jsonl.gz` in
`--out` (`.part` until the walk ends or `--rotate` pages pass), the family the fold ingests as
`ia_cdx_domain_sweep`. Its own markers live in `--state-dir`, so September's are left alone.
A restart resumes from the saved key and first promotes any `.part` the last run left, which
holds every row up to that key because the journal is flushed before the key is saved.

One archive client per process: it refuses to start beside `--max-local` other CDX clients on
this machine, sleeps out `Retry-After` (seconds or a date) on 429, 5xx or a refused
connection and stops after five in a row, parks a platform that answers 400, 403 or 404,
idles while `pause-platform` exists, and re-reads the seed file every hour.

    python3 scripts/engines/cdx_platform_walk.py <seeds> --lane 0 --lanes 3 --deadline <epoch>
"""

from __future__ import annotations

import argparse
import email.utils
import gzip
import hashlib
import json
import os
import signal
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
BASE = "https://web.archive.org/cdx/search/cdx"
REPO = Path(__file__).resolve().parents[2]
STATE_HOME = Path(os.environ.get("ARK_STATE_DIR", Path.home() / "ark/state"))
PAUSE_FLAG = STATE_HOME / "pause-platform"
MAX_THROTTLED = 5
MAX_FAILS = 3
RESEED_S = 3600
END_CONFIRM_S = 30
THROTTLES = {"HTTP429", "HTTP503", "REFUSED"}
# A 5xx on a giant (yahoo.com) is the server failing to finish the page, not a pace signal: it
# rests and counts against this platform, and three failed runs park it as too heavy.
SERVER_FAILS = {"HTTP500", "HTTP502", "HTTP504"}
REFUSALS = {"HTTP400", "HTTP403", "HTTP404"}
MAX_FAILED_RUNS = 3


class Throttled(SystemExit):
    pass


def _sigterm(signum, frame):  # noqa: ARG001
    raise SystemExit(f"signal {signum}")


def retry_after(value: str | None) -> float | None:
    """Seconds from a Retry-After header, in either of its two forms, never negative."""
    if not value:
        return None
    try:
        wait = float(value)
    except ValueError:
        try:
            wait = email.utils.parsedate_to_datetime(value).timestamp() - time.time()
        except (TypeError, ValueError):
            return None
    return max(0.0, wait) if wait == wait and wait != float("inf") else None


def fetch(params: dict, timeout: int) -> tuple[str, str, float | None]:
    """(status, body, Retry-After seconds when the server sent one)."""
    url = f"{BASE}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            return "200", fh.read().decode("utf-8", "replace"), None
    except urllib.error.HTTPError as exc:
        after = exc.headers.get("Retry-After") if exc.headers else None
        return f"HTTP{exc.code}", "", retry_after(after)
    except urllib.error.URLError as exc:
        refused = isinstance(exc.reason, ConnectionRefusedError)
        return ("REFUSED" if refused else f"ERR:{type(exc.reason).__name__}"), "", None
    except ConnectionRefusedError:
        return "REFUSED", "", None
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{type(exc).__name__}", "", None


def split_page(body: str) -> tuple[list[list[str]], str | None]:
    """Rows and the resume key. IA ends a page that has more with a blank line and the key."""
    lines = body.replace("\r\n", "\n").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    key = None
    if len(lines) >= 2 and not lines[-2].strip():
        key = lines[-1].strip()
        lines = lines[:-2]
    return [line.split() for line in lines if line.strip()], key


def host_of(original: str) -> str | None:
    try:
        parsed = urllib.parse.urlsplit(original if "//" in original else f"http://{original}")
        host = (parsed.hostname or "").strip().lower().rstrip(".")
    except ValueError:
        return None
    return host or None


def mine(seed: str, lane: int, lanes: int) -> bool:
    return hashlib.blake2b(seed.encode(), digest_size=8).digest()[0] % lanes == lane


def read_seeds(path: Path) -> list[str]:
    out = []
    for line in path.read_text().splitlines():
        seed = line.split("#", 1)[0].strip().lower()
        if seed and seed not in out:
            out.append(seed)
    return out


def _comm(pid: str) -> str:
    return subprocess.run(["ps", "-o", "comm=", "-p", pid], capture_output=True, text=True).stdout


def _python_pids(pattern: str) -> set[str]:
    out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True).stdout
    return {p for p in set(out.split()) - {str(os.getpid())} if "python" in _comm(p).lower()}


def cdx_clients() -> int:
    """CDX clients already on this machine: sweep loops and the python clients. A `uv run`
    copy is a wrapper plus a python child, so only the python processes count."""
    loops = subprocess.run(
        ["pgrep", "-f", "platform_sweep(_loop)?[.]sh"], capture_output=True, text=True
    ).stdout.split()
    clients = ("cdx_suffix_sweep", "cdx_thin_sweep", "cdx_yearfill", "cdx_platform_walk")
    return len(loops) + sum(len(_python_pids(f"{c}[.]py")) for c in clients)


class Walk:
    """One platform: state file, journal, and the (host, year) pairs already written."""

    def __init__(self, seed: str, args: argparse.Namespace):
        self.seed, self.args = seed, args
        safe = seed.replace(".", "_")
        self.state_path = args.state_dir / f"{safe}.state.json"
        self.done_path = args.state_dir / f"{safe}.done"
        self.refused_path = args.state_dir / f"{safe}.refused"
        self.prefix = f"suffix_{safe}_rk_"
        try:
            state = json.loads(self.state_path.read_text()) if self.state_path.is_file() else {}
        except ValueError:
            print(f"{seed}: unreadable state, starting over (the ingest dedupes)", flush=True)
            state = {}
        self.key = state.get("resume_key")
        self.pages = state.get("pages", 0)
        self.written = state.get("written", 0)
        self.failed_runs = state.get("failed_runs", 0)
        self.seen: set[tuple[str, str]] = set()
        self.fh = self.part = None
        self.since_rotate = 0
        # A killed run leaves its journal as `.part`; every row in it precedes the saved key.
        for left in args.out.glob(f"{self.prefix}*.jsonl.gz.part"):
            left.rename(left.with_name(left.name.removesuffix(".part")))

    def save(self) -> None:
        state = {
            "resume_key": self.key,
            "pages": self.pages,
            "written": self.written,
            "failed_runs": self.failed_runs,
        }
        tmp = self.state_path.with_name(self.state_path.name + ".tmp")
        tmp.write_text(json.dumps(state) + "\n")
        os.replace(tmp, self.state_path)

    def write(self, rows: list[list[str]]) -> int:
        new = 0
        for row in rows:
            if len(row) < 3 or len(row[1]) != 14 or not row[1].isdigit():
                continue
            host = host_of(row[0])
            if not host or not (host == self.seed or host.endswith("." + self.seed)):
                continue
            pair = (host, row[1][:4])
            if pair in self.seen:
                continue
            self.seen.add(pair)
            if self.fh is None:
                stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
                self.part = self.args.out / f"{self.prefix}{stamp}_{self.pages:05d}.jsonl.gz.part"
                self.fh = gzip.open(self.part, "wt")
            self.fh.write(json.dumps({"url": row[0], "timestamp": row[1], "status": row[2]}) + "\n")
            new += 1
        if self.fh is not None:
            self.fh.flush()
        self.written += new
        return new

    def close(self) -> None:
        if self.fh is not None:
            self.fh.close()
            self.part.rename(self.part.with_name(self.part.name.removesuffix(".part")))
            self.fh = self.part = None
        self.since_rotate = 0

    def rest(self, seconds: float) -> None:
        time.sleep(max(0.0, min(seconds, self.args.deadline - time.time())))

    def run(self) -> str:
        """Walk until the index ends, the deadline passes, or a page keeps failing."""
        a = self.args
        throttled = fails = 0
        ended_once = False
        try:
            while time.time() < a.deadline:
                if PAUSE_FLAG.exists():
                    self.close()
                    while PAUSE_FLAG.exists() and time.time() < a.deadline:
                        time.sleep(30)
                    continue
                params = {
                    "url": self.seed,
                    "matchType": "domain",
                    "from": "1996",
                    "to": "2001",
                    "filter": "statuscode:[23][0-9][0-9]",
                    "fl": "original,timestamp,statuscode",
                    "limit": str(a.limit),
                    "showResumeKey": "true",
                }
                if self.key:
                    params["resumeKey"] = self.key
                status, body, wait = fetch(params, a.timeout)
                if status in THROTTLES:
                    throttled += 1
                    if throttled >= MAX_THROTTLED:
                        raise Throttled(f"{self.seed}: {status} {throttled} times running")
                    wait = 120.0 if wait is None else wait
                    print(f"{self.seed}: {status}, resting {wait:.0f}s", flush=True)
                    self.rest(wait)
                    continue
                if status in REFUSALS:
                    self.refused_path.write_text(f"{status} at key {self.key}\n")
                    return f"refused with {status}; parked"
                if status != "200":
                    fails += 1
                    if fails >= MAX_FAILS:
                        self.failed_runs += 1
                        self.save()
                        if self.failed_runs >= MAX_FAILED_RUNS:
                            self.refused_path.write_text(f"too heavy: {status} at key {self.key}\n")
                            return f"page {self.pages} failed {self.failed_runs} runs; parked"
                        return f"page {self.pages} failed {fails} times on {status}; resumable"
                    rest = wait if status in SERVER_FAILS and wait is not None else 60.0
                    self.rest(rest if status in SERVER_FAILS else a.delay * 3)
                    continue
                throttled = fails = 0
                self.failed_runs = 0
                rows, key = split_page(body)
                new = self.write(rows)
                print(
                    f"{self.seed} page {self.pages + 1}: {len(rows)} rows, {new} new host-years",
                    flush=True,
                )
                if key is None and self.key and not ended_once:
                    # a resumed page with no key may be a short answer; ask it once more
                    ended_once = True
                    self.rest(END_CONFIRM_S)
                    continue
                self.pages += 1
                self.since_rotate += 1
                self.key = key
                self.save()
                if key is None:
                    self.close()
                    self.done_path.write_text(f"{self.pages} pages, {self.written} host-years\n")
                    return f"done: {self.pages} pages, {self.written} host-years"
                ended_once = False
                if self.since_rotate >= a.rotate:
                    self.close()
                self.rest(a.delay)
            return f"deadline at page {self.pages}; resumable"
        finally:
            self.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("seeds", type=Path, help="one platform per line; re-read every hour")
    ap.add_argument("--lane", type=int, required=True)
    ap.add_argument("--lanes", type=int, default=1)
    ap.add_argument("--deadline", type=int, required=True, help="absolute epoch to stop at")
    ap.add_argument("--out", type=Path, default=REPO / "data/raw/cdx_suffix")
    ap.add_argument("--state-dir", type=Path, default=REPO / "data/raw/cdx_platform")
    ap.add_argument("--skip", type=Path, help="platforms already walked to the end, one a line")
    ap.add_argument("--max-local", type=int, default=2, help="CDX clients allowed here")
    ap.add_argument("--limit", type=int, default=10000, help="rows per page")
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--rotate", type=int, default=25, help="pages per journal")
    args = ap.parse_args()

    signal.signal(signal.SIGTERM, _sigterm)
    if signal.getsignal(signal.SIGHUP) is not signal.SIG_IGN:  # leave nohup's ignore alone
        signal.signal(signal.SIGHUP, _sigterm)
    running = cdx_clients()
    if running >= args.max_local:
        raise SystemExit(f"{running} CDX clients already here; {args.max_local} is the cap")
    args.out.mkdir(parents=True, exist_ok=True)
    args.state_dir.mkdir(parents=True, exist_ok=True)
    seeds: list[str] = []
    while time.time() < args.deadline:
        try:
            skip = set(read_seeds(args.skip)) if args.skip and args.skip.is_file() else set()
            seeds = [s for s in read_seeds(args.seeds) if s not in skip]
        except OSError as exc:
            print(f"seed file unreadable ({exc}), keeping the last list", flush=True)
        todo = [
            s
            for s in seeds
            if mine(s, args.lane, args.lanes)
            and not (args.state_dir / f"{s.replace('.', '_')}.done").exists()
            and not (args.state_dir / f"{s.replace('.', '_')}.refused").exists()
        ]
        reseed_at = time.time() + RESEED_S
        finished = 0
        for seed in todo:
            if time.time() >= min(args.deadline, reseed_at):
                break
            outcome = Walk(seed, args).run()
            finished += outcome.startswith(("done", "refused"))
            print(f"{seed}: {outcome}", flush=True)
        if todo and not finished:
            # every walk this pass failed or hit the deadline: rest before asking again
            time.sleep(max(0, min(600, args.deadline - time.time())))
        if not todo:
            print("every seed of this lane is done; waiting for the list to grow", flush=True)
            while time.time() < min(args.deadline, reseed_at):
                time.sleep(max(0, min(60, args.deadline - time.time())))
    print("deadline reached", flush=True)


if __name__ == "__main__":
    main()
