"""Read one HTTP Archive year whole into 2002 to 2013 hostname journals.

Each zip of the archive.org item `httparchive_<year>` (2012: 112 zips, 651 GB) is a stored zip of
WebPageTest test zips; a test holds `<run>_IEWTR.txt.gz`, the agent's own tab-separated log of
every request it made, stamped at fetch time: Date, Time, Action, Host, URL, Response Code,
Secure. A request answered 2xx or 3xx dates its exact host (`httparchive_har_entry`, #449), one
row per (host, year), the earliest, as `{url, timestamp, status}` in
`data/raw/extended/httparchive_har/har_<zip>.jsonl.gz`; 4xx and 5xx date nothing.

A zip streams through `scripts/harness/fetch.py --to -`, the one download path, and never
touches the disk; its journal lands only when the stream's sha1 is the item's own for that file,
so a cut stream books nothing. A zip with a journal is done, a failed one is retried after the
others, three times at most (`.har_<zip>.failed`); a test zip that does not open is skipped and
counted. Every zip left, back to back in crawl order, the hold read between: the tick starts it
after the bank as its own user unit, `ark-har`, so it outlives the tick and never runs twice
(`scripts/harness/scheduled_sync.sh`). Each zip logs its host-years and how many are new to the
year, the measure of EE a GB and of saturation.

    uv run python scripts/sources/httparchive/har_year.py [--year 2012]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import struct
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from ark.hostnames import host_of

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data/raw/extended/httparchive_har"
ITEM = "https://archive.org/{what}/httparchive_{year}"
LOCAL = struct.Struct("<4sHHHHHIIIHH")  # a zip member's local header
WHEN = re.compile(r"(\d\d)/(\d\d)/(20(?:0[2-9]|1[0-3]))\t(\d\d):(\d\d):(\d\d)")
YES = re.compile(r"[23]\d\d")


def fetch(url: str, max_bytes: str = "1G") -> subprocess.Popen:
    cmd = [sys.executable, str(REPO / "scripts/harness/fetch.py"), url, "--to", "-"]
    return subprocess.Popen([*cmd, "--max-bytes", max_bytes], stdout=subprocess.PIPE)


def members(stream):
    """(name, bytes) of each member of a stored zip read front to back, to its central
    directory; a member compressed or of unknown size fails the zip."""
    while (head := stream.read(LOCAL.size))[:4] == b"PK\x03\x04":
        _, _, flag, method, _, _, _, size, _, nlen, elen = LOCAL.unpack(head)
        name = stream.read(nlen + elen)[:nlen].decode("utf-8", "replace")
        if flag & 8 or method or size == 0xFFFFFFFF:
            raise ValueError(f"{name}: not stored with its size")
        yield name, stream.read(size)


def requests(test: bytes):
    """Every row of every IEWTR log in one test zip."""
    with zipfile.ZipFile(io.BytesIO(test)) as z:
        for name in z.namelist():
            if name.endswith("_IEWTR.txt.gz"):
                yield from gzip.decompress(z.read(name)).decode("utf-8", "replace").splitlines()


def earliest(rows, keep: dict) -> None:
    """(host, year) -> (timestamp, url, status), the earliest 2xx or 3xx request a year."""
    for row in rows:
        f = row.split("\t")
        if len(f) < 47 or not f[4] or not YES.fullmatch(f[7]) or not (m := WHEN.match(row)):
            continue
        mm, dd, yyyy, h, mi, s = m.groups()
        ts, url = yyyy + mm + dd + h + mi + s, f"http{'s' * (f[46] == '1')}://{f[5]}{f[6]}"
        host = host_of(url)
        if host and ((host, yyyy) not in keep or ts < keep[(host, yyyy)][0]):
            keep[(host, yyyy)] = (ts, url, f[7])


class Hashed:
    def __init__(self, raw):
        self.raw, self.sha1 = raw, hashlib.sha1()

    def read(self, n: int) -> bytes:
        got = self.raw.read(n)
        self.sha1.update(got)
        return got


def read(year: int, name: str, size: int, sha1: str) -> tuple[str, dict]:
    """One zip's line for the log, and its (host, year) rows once booked."""
    part, t0 = name.removesuffix(".zip"), time.time()
    proc = fetch(ITEM.format(what="download", year=year) + "/" + name, str(size))
    stream, keep, broken = Hashed(proc.stdout), {}, 0
    try:
        for _, test in members(stream):
            try:
                earliest(requests(test), keep)
            except (zipfile.BadZipFile, OSError, EOFError, ValueError):
                broken += 1
        while stream.read(1 << 20):  # the central directory, hashed with the rest
            pass
    except ValueError as exc:
        proc.kill()
        print(f"{part}: {exc}", flush=True)
    proc.wait()
    OUT.mkdir(parents=True, exist_ok=True)
    if proc.returncode or stream.sha1.hexdigest() != sha1:
        why = f"{part}: not booked, fetch exit {proc.returncode}, sha1 {stream.sha1.hexdigest()}"
        with open(OUT / f".har_{part}.failed", "a") as fh:
            fh.write(why + "\n")
        return why, {}
    tmp = OUT / f".har_{part}.tmp"
    with gzip.GzipFile(tmp, "wb", mtime=0) as raw, io.TextIOWrapper(raw) as fh:
        for ts, url, status in sorted(keep.values()):
            fh.write(json.dumps({"url": url, "timestamp": ts, "status": status}) + "\n")
    os.replace(tmp, OUT / f"har_{part}.jsonl.gz")
    return f"{part}\t{size}\t{round(time.time() - t0)}\t{len(keep)}\t{broken}", keep


def failures(part: str) -> int:
    marker = OUT / f".har_{part}.failed"
    return len(marker.read_text().splitlines()) if marker.exists() else 0


def seen_so_far() -> set:
    """Every (host, year) the year's booked journals hold."""
    seen = set()
    for journal in OUT.glob("har_*.jsonl.gz"):
        with gzip.open(journal, "rt") as fh:
            for line in fh:
                row = json.loads(line)
                seen.add((host_of(row["url"]), row["timestamp"][:4]))
    return seen


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, default=2012)
    year = ap.parse_args().year
    proc = fetch(ITEM.format(what="metadata", year=year))
    files = json.loads(proc.stdout.read() or b"{}").get("files", [])
    if proc.wait():
        return print(f"har {year}: the item's file list did not arrive", flush=True)
    zips = {
        f["name"]: (int(f["size"]), f["sha1"])
        for f in files
        if f["name"].endswith(".zip") and int(f["size"])
    }
    seen = seen_so_far()
    print("zip\tbytes\tseconds\thost-years\ttests broken\tnew to the year", flush=True)
    while subprocess.run(["bash", str(REPO / "scripts/harness/hold.sh"), "holds"]).returncode:
        done = {p.name for p in OUT.glob("har_*.jsonl.gz")}
        todo = [n for n in zips if f"har_{n[:-4]}.jsonl.gz" not in done and failures(n[:-4]) < 3]
        if not todo:
            return print(f"har {year}: every zip read or given up", flush=True)
        name = min(todo, key=lambda n: (failures(n[:-4]), n))  # crawl order, failures last
        line, keep = read(year, name, *zips[name])
        print(line + (f"\t{len(keep.keys() - seen)}" if keep else ""), flush=True)
        seen |= keep.keys()
    print(f"har {year}: held", flush=True)


if __name__ == "__main__":
    main()
