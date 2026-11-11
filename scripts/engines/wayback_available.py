"""Screen (year, host) rows by the Wayback availability API: one light ask each, nearest mid-year.

`archive.org/wayback/available?url=<host>&timestamp=<year>0701` answers with the capture of the
host's root page closest to that date. When that capture falls in the row's year and its own URL
names the exact host, it is a same-year capture of that host, written as a walker journal row
(`walk_avail-<name>_<stamp>.jsonl.gz` under `<data>/raw/cdx_suffix/`, url, timestamp, status), so
the hostname ingest banks it and the bank decides whether it is new. The API folds `www.` and
`www1.` into one name, so an in-year capture under another spelling goes to `folded.txt` for an
exact index ask instead. 300 rows from one address: 2.6 s an ask, no 429; 14 hits and 12 folded.
A miss says nothing of deeper pages: the root alone is asked.

One ask at a time; a 429 or 503 rests `Retry-After` or a minute, a failed connection 30 s. Every
ask is a `log.tsv` row (year, host, verdict, stamp, seconds); a restart skips the rows logged.
Runs on Python 3.8.

    python3 scripts/engines/wayback_available.py ROWS --share 0/2 --data DIR [--seconds 3300]
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://archive.org/wayback/available"
UA = "InternetDigitalArk/1.0 (+historical domain research)"
FIRST, LAST = 1996, 2001


def closest(year: str, host: str, timeout: float) -> dict:
    q = urllib.parse.urlencode({"url": host, "timestamp": year + "0701"})
    req = urllib.request.Request(API + "?" + q, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        d = json.loads(fh.read().decode("utf-8", "replace"))
    return (d.get("archived_snapshots") or {}).get("closest") or {}


def original(replay: str) -> str:
    """The captured URL inside a replay URL `http://web.archive.org/web/<stamp>/<url>`."""
    parts = replay.split("/", 5)
    return parts[5] if len(parts) == 6 else ""


def host_of(url: str) -> str:
    rest = url.split("://", 1)[-1]
    return (urllib.parse.urlsplit("http://" + rest).hostname or "").lower().rstrip(".")


def verdict(year: str, host: str, c: dict) -> str:
    ts = c.get("timestamp", "")
    if ts[:4] != year or not str(c.get("status", "")).startswith(("2", "3")):
        return "miss"
    return "hit" if host_of(original(c.get("url", ""))) == host else "folded"


def flush(folder: Path, name: str, rows: list) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + f"{time.time() % 1:.6f}"[1:]
    tmp = folder / f".walk_avail-{name}_{stamp}.tmp"
    with gzip.GzipFile(tmp, "wb", mtime=0) as raw, io.TextIOWrapper(raw) as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    os.replace(tmp, folder / f"walk_avail-{name}_{stamp}.jsonl.gz")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("rows", type=Path, help="one 'year host' a line, tab or space apart")
    ap.add_argument("--share", default="0/1", help="i/n: this client asks every n-th row from i")
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--name", default="", help="state folder; the list's stem and share if empty")
    ap.add_argument("--timeout", type=float, default=60)
    ap.add_argument("--batch", type=int, default=50, help="hits a journal")
    ap.add_argument("--seconds", type=float, default=0, help="stop after this many; 0 runs out")
    a = ap.parse_args()
    i, n = map(int, a.share.split("/"))
    name = a.name or f"{a.rows.stem}_{i}of{n}"
    state = a.data / "raw/wayback_available" / name
    state.mkdir(parents=True, exist_ok=True)
    log_path = state / "log.tsv"
    seen = {tuple(ln.split("\t")[:2]) for ln in log_path.open()} if log_path.exists() else set()
    rows = []
    for k, ln in enumerate(x for x in a.rows.read_text().splitlines() if x.strip()):
        if k % n == i:
            year, host = ln.split()[:2]
            if FIRST <= int(year) <= LAST and (year, host.lower()) not in seen:
                rows.append((year, host.lower()))
    end = time.time() + a.seconds if a.seconds else float("inf")
    log, folded = log_path.open("a", buffering=1), (state / "folded.txt").open("a", buffering=1)
    hits: list = []
    for year, host in rows:
        if time.time() >= end:
            break
        while True:
            t0 = time.time()
            try:
                c = closest(year, host, a.timeout)
                break
            except urllib.error.HTTPError as exc:
                if exc.code not in (429, 503):
                    c = {"error": exc.code}
                    break
                try:
                    time.sleep(min(float(exc.headers.get("Retry-After") or 60), 900.0))
                except ValueError:
                    time.sleep(60)
            except Exception:  # noqa: BLE001  no connection or a cut answer: rest, ask again
                time.sleep(30)
        v = "error" if "error" in c else verdict(year, host, c)
        log.write(f"{year}\t{host}\t{v}\t{c.get('timestamp', '')}\t{time.time() - t0:.2f}\n")
        if v == "hit":
            hits.append(
                {"url": original(c["url"]), "timestamp": c["timestamp"], "status": c["status"]}
            )
            if len(hits) >= a.batch:
                flush(a.data / "raw/cdx_suffix", name, hits)
                hits = []
        elif v == "folded":
            folded.write(f"{year}\t{host}\t{host_of(original(c.get('url', '')))}\n")
    if hits:
        flush(a.data / "raw/cdx_suffix", name, hits)


if __name__ == "__main__":
    main()
