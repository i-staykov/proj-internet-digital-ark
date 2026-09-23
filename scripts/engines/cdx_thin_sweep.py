"""Walk a queue of thin parents with one CDX question each, in one process.

A thin parent is a registrable his files hold that no sweep has walked. It answers with about
one host, so the cost that decides its yield is the overhead around the question, not the
question: `platform_sweep_loop.sh` spends a page-count query, a `uv` start and up to a 10 s
poll on every parent, which caps a lane at about 290 parents an hour. Measured 2026-09-22 on
74 thin parents at 0.21 EE each, that is about 61 EE per client-hour. This asks the one
question the answer needs, at the sweeps' own 2 s delay.

It writes what the sweep writes, so the fold loop ingests it unchanged: `{url, timestamp}` lines
in `data/raw/cdx_suffix/suffix_<parent>_<stamp>.jsonl.gz`, renamed from `.part` once complete,
and `suffix_<parent>.done` so no shard walks the parent again. A parent whose answer reaches
`--limit` rows is not thin: its rows are kept, it is NOT marked done, and it goes to
`platform_rich.txt` for a paginated sweep.

It is one archive client. It refuses to start when the lanes already running make three, it
sleeps out `Retry-After` on a 429 or 503 and stops after five in a row, and it idles while the
pause flag is up.

    uv run python scripts/engines/cdx_thin_sweep.py <queue> --deadline <epoch>
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

UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
BASE = "https://web.archive.org/cdx/search/cdx"
OUT = Path("data/raw/cdx_suffix")
RICH = Path("data/raw/cdx/platform_rich.txt")
PAUSE_FLAG = Path(os.environ.get("ARK_STATE_DIR", Path.home() / "ark/state")) / "pause"
MAX_CLIENTS = 3
MAX_THROTTLED = 5
MAX_FAILS = 3


def fetch(params: dict, timeout: int) -> tuple[str, list[str], float | None]:
    """(status, lines, Retry-After seconds when the server sent one)."""
    url = f"{BASE}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            return "200", fh.read().decode("utf-8", "replace").splitlines(), None
    except urllib.error.HTTPError as exc:
        after = exc.headers.get("Retry-After") if exc.headers else None
        try:
            wait = float(after) if after else None
        except ValueError:
            wait = None
        return f"HTTP{exc.code}", [], wait
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{type(exc).__name__}", [], None


def capture_rows(lines: list[str]) -> list[dict]:
    """The `{url, timestamp}` rows of an `original timestamp` answer, malformed lines dropped."""
    rows = []
    for line in lines:
        parts = line.split(" ")
        if len(parts) >= 2 and len(parts[1]) == 14 and parts[1].isdigit():
            rows.append({"url": parts[0], "timestamp": parts[1]})
    return rows


def _pids(pattern: str) -> set[str]:
    out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True).stdout
    return set(out.split()) - {str(os.getpid())}


def other_clients() -> int:
    """Archive clients already running: one per sweep lane, one per other copy of this script.
    A `uv run` copy is a wrapper plus a python child, so only the python processes count."""

    def python(pattern: str) -> set[str]:
        return {
            p
            for p in _pids(pattern)
            if "python"
            in subprocess.run(
                ["ps", "-o", "comm=", "-p", p], capture_output=True, text=True
            ).stdout.lower()
        }

    thin = python("cdx_thin_sweep[.]py")
    walk = python("cdx_(platform_walk|yearfill)[.]py")
    return len(_pids("platform_sweep_loop[.]sh")) + len(thin) + len(walk)


def sweep_parent(parent: str, args: argparse.Namespace) -> str:
    """Ask once, write the journal, mark the parent. Returns what happened, for the log."""
    safe = parent.replace(".", "_")
    if (OUT / f"suffix_{safe}.done").exists():
        return "done already"
    params = {
        "url": parent,
        "matchType": "domain",
        "fl": "original,timestamp",
        "from": "1996",
        "to": "2001",
        # the sweep's own filter (ADR-011): 2xx and 3xx, never 4xx or 5xx
        "filter": "statuscode:[23][0-9][0-9]",
        "limit": str(args.limit),
    }
    throttled = fails = 0
    while True:
        while PAUSE_FLAG.exists() and time.time() < args.deadline:
            time.sleep(30)
        status, lines, retry_after = fetch(params, args.timeout)
        if status == "200":
            break
        if status in ("HTTP429", "HTTP503"):
            throttled += 1
            if throttled >= MAX_THROTTLED:
                raise SystemExit(f"{parent}: {status} {throttled} times running, stopping")
            wait = retry_after if retry_after is not None else 120.0
            print(f"{parent}: {status}, Retry-After {retry_after}, resting {wait:.0f}s", flush=True)
            time.sleep(wait)
            continue
        fails += 1
        if fails >= MAX_FAILS:
            return f"gave up on {status}, not marked done"
        time.sleep(args.delay * 3)

    rows = capture_rows(lines)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    if rows:
        journal = OUT / f"suffix_{safe}_{stamp}.jsonl.gz"
        part = journal.with_name(journal.name + ".part")
        with gzip.open(part, "wt") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        part.rename(journal)
    if len(lines) >= args.limit:
        with RICH.open("a") as fh:
            fh.write(parent + "\n")
        return f"{len(rows)} rows, at the limit, sent to the paginated sweep"
    (OUT / f"suffix_{safe}.done").touch()
    return f"{len(rows)} rows"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("queue", type=Path)
    ap.add_argument("--deadline", type=int, required=True, help="absolute epoch to stop at")
    ap.add_argument("--start-line", type=int, default=1, help="1-based line to begin at")
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--limit", type=int, default=20000)
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    running = other_clients()
    if running >= MAX_CLIENTS:
        raise SystemExit(f"{running} archive clients already running; three is the cap (C-88)")
    OUT.mkdir(parents=True, exist_ok=True)
    parents = [
        line.split()[0].lower()
        for line in args.queue.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    for n, parent in enumerate(parents, 1):
        if n < args.start_line:
            continue
        if time.time() >= args.deadline:
            print("deadline reached", flush=True)
            return
        print(f"{n} {parent}: {sweep_parent(parent, args)}", flush=True)
        time.sleep(args.delay)
    print("queue walked", flush=True)


if __name__ == "__main__":
    main()
