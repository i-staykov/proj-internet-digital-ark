"""Fill one missing year on names his files already hold: one CDX question per name.

The queue is names held at 2000 and missing 2001, the `edge` population of
`build_query_queue.py`. Each name is asked once, pinned to that year: `matchType=host`
(the exact host and the `www.` twin IA folds into it, every path), `limit=1`, 2xx and 3xx
only (ADR-011). A hit is filed under the host the archive NAMES, as the availability
engine does, because a capture of `www.example.com` does not establish `example.com`
(spec XIII): `years` carries the year only when the named host is the name itself, and
`hosts` carries whatever host answered, which `cdx_gap_hostgrain.py` turns into a
hostname row.

It writes the `ark cdx` journal shape, `{domain, status, years, hosts}`, to
`data/raw/cdx/cdx_yearfill_<lane>_<stamp>.jsonl.gz`, so the fold loop ingests it
unchanged and the queue builder never asks an answered name again. A journal is written
as `.part` and renamed every `--rotate` names; the resume marker moves only after the
rename, so a killed client re-asks at most one journal's names.

It is one archive client. It refuses to start when two CDX clients already run on this
machine (C-88: two CDX, the third is the availability engine), sleeps out `Retry-After` on
a 429 or 503 and stops after five in a row, and idles while `pause-yearfill` exists.

    uv run python scripts/engines/cdx_yearfill.py <queue> --lane a --deadline <epoch>
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ark.cdx import CDX_ENDPOINT, hosts_in

UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
OUT = Path("data/raw/cdx")
STATE_DIR = Path(os.environ.get("ARK_STATE_DIR", Path.home() / "ark/state"))
PAUSE_FLAG = STATE_DIR / "pause-yearfill"
YEAR = 2001
MAX_CDX_CLIENTS = 2
MAX_THROTTLED = 5
MAX_FAILS = 3


def fetch(params: dict, timeout: int) -> tuple[str, str, float | None]:
    """(status, body, Retry-After seconds when the server sent one)."""
    url = f"{CDX_ENDPOINT}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            return "200", fh.read().decode("utf-8", "replace"), None
    except urllib.error.HTTPError as exc:
        after = exc.headers.get("Retry-After") if exc.headers else None
        try:
            wait = float(after) if after else None
        except ValueError:
            wait = None
        return f"HTTP{exc.code}", "", wait
    except ConnectionRefusedError:
        # a refused connection is the host rate-limiting this IP, so it backs off too
        return "REFUSED", "", None
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{type(exc).__name__}", "", None


def record(name: str, body: str, year: int) -> dict:
    """The `ark cdx` row for one answer. The year counts for the name only when the host
    the archive named is the name; any other host rides in `hosts` alone."""
    hosts = hosts_in(body, year, year)
    return {
        "domain": name,
        "status": 200,
        "years": [year] if name in hosts else [],
        "hosts": hosts,
        "strategy": "cdx_yearfill",
    }


def ask(name: str, args: argparse.Namespace) -> dict | None:
    """One answered name, or None when it was not answered and should be asked again."""
    params = {
        "url": name,
        "matchType": "host",
        "from": str(args.year),
        "to": str(args.year),
        "filter": "statuscode:[23][0-9][0-9]",
        "fl": "timestamp,original",
        "collapse": "timestamp:4",
        "limit": "1",
    }
    throttled = fails = 0
    while True:
        status, body, retry_after = fetch(params, args.timeout)
        if status == "200":
            return record(name, body, args.year)
        if status in ("HTTP429", "HTTP503", "REFUSED"):
            throttled += 1
            if throttled >= MAX_THROTTLED:
                raise SystemExit(f"{name}: {status} {throttled} times running, stopping")
            wait = retry_after if retry_after is not None else 120.0
            print(f"{name}: {status}, Retry-After {retry_after}, resting {wait:.0f}s", flush=True)
            time.sleep(wait)
            continue
        fails += 1
        if fails >= MAX_FAILS:
            print(f"{name}: gave up on {status}, left unasked", flush=True)
            return None
        time.sleep(args.delay * 3)


def _comm(pid: str) -> str:
    return subprocess.run(["ps", "-o", "comm=", "-p", pid], capture_output=True, text=True).stdout


def _python_pids(pattern: str) -> set[str]:
    out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True).stdout
    pids = set(out.split()) - {str(os.getpid())}
    return {p for p in pids if "python" in _comm(p).lower()}


def cdx_clients() -> int:
    """CDX clients already on this machine. A `uv run` copy is a wrapper plus a python
    child, so only the python processes count."""
    loops = subprocess.run(
        ["pgrep", "-f", "platform_sweep_loop[.]sh"], capture_output=True, text=True
    ).stdout.split()
    return (
        len(loops)
        + len(_python_pids("cdx_thin_sweep[.]py"))
        + len(_python_pids("cdx_yearfill[.]py"))
        + len(_python_pids("cdx_platform_walk[.]py"))
        + len(_python_pids("cdx_suffix_sweep[.]py"))
    )


class Journal:
    """`.part` while open, renamed on close, and the resume marker moved after the rename."""

    def __init__(self, lane: str, state: Path):
        self.lane, self.state, self.fh, self.part, self.names = lane, state, None, None, 0
        self.seq = 0

    def write(self, row: dict) -> None:
        if self.fh is None:
            stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            self.seq += 1
            self.part = OUT / f"cdx_yearfill_{self.lane}_{stamp}_{self.seq:04d}.jsonl.gz.part"
            self.fh = gzip.open(self.part, "wt")
        self.fh.write(json.dumps(row) + "\n")
        self.fh.flush()
        self.names += 1

    def close(self, next_line: int) -> Path | None:
        done = None
        if self.fh is not None:
            self.fh.close()
            done = self.part.with_name(self.part.name.removesuffix(".part"))
            self.part.rename(done)
            self.fh, self.part, self.names = None, None, 0
        self.state.write_text(f"{next_line}\n")
        return done


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("queue", type=Path, help="one name per line, first field")
    ap.add_argument("--lane", required=True, help="journal and resume-marker name")
    ap.add_argument("--deadline", type=int, required=True, help="absolute epoch to stop at")
    ap.add_argument("--start-line", type=int, default=0, help="1-based; default the marker")
    ap.add_argument("--year", type=int, default=YEAR)
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--rotate", type=int, default=500, help="names per journal")
    args = ap.parse_args()

    running = cdx_clients()
    if running >= MAX_CDX_CLIENTS:
        raise SystemExit(f"{running} CDX clients already running; two is the cap (C-88)")
    OUT.mkdir(parents=True, exist_ok=True)
    state = OUT / f"yearfill_{args.lane}.done"
    start = args.start_line or (int(state.read_text()) if state.is_file() else 1)
    journal = Journal(args.lane, state)
    asked = hits = 0
    # the first line not yet handled; a throttle stop or a deadline leaves it unasked
    resume = start
    try:
        with args.queue.open() as fh:
            for n, line in enumerate(fh, 1):
                if n < start:
                    continue
                if time.time() >= args.deadline:
                    print("deadline reached", flush=True)
                    break
                if PAUSE_FLAG.exists():
                    journal.close(resume)
                    while PAUSE_FLAG.exists() and time.time() < args.deadline:
                        time.sleep(30)
                    if time.time() >= args.deadline:
                        break
                if line.strip() and not line.startswith("#"):
                    row = ask(line.split()[0].strip().lower(), args)
                    if row is not None:
                        journal.write(row)
                        asked += 1
                        hits += bool(row["hosts"])
                    time.sleep(args.delay)
                resume = n + 1
                if journal.names >= args.rotate:
                    done = journal.close(resume)
                    print(f"line {n}: asked {asked}, hits {hits}, wrote {done}", flush=True)
            else:
                print("queue walked", flush=True)
    finally:
        done = journal.close(resume)
        print(f"stopped before line {resume}: asked {asked}, hits {hits}, last {done}", flush=True)


if __name__ == "__main__":
    main()
