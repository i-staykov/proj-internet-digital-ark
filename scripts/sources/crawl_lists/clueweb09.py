"""Read the ClueWeb09 url-docid map whole into 2009 hostname journals.

The map (`ir.nist.gov/clueweb.urls-docid.bz2`, 10.2 GB, read from its 2016 Wayback capture,
fleet #215) lists every page ClueWeb09 fetched in January and February 2009, `<url> <docid>`,
sorted by URL. A dated crawl list is a class on two conditions (#286): the dataset documents a
crawl inside one calendar year and its nodes are fetched pages; both hold here. A line dates
its exact host in 2009 (`crawl_list_node`), status-less, since a crawl list carries no response
code. One row per host as `{url, timestamp, node}`, the stamp the documented crawl's first
day, so it carries the year alone, into `data/raw/extended/crawl_lists/clueweb09_<n>.jsonl.gz`,
5,000,000 rows a part; the export folds what recurs to one host-year. The witness is the row's
node id, each part's sha256 in the export manifest and the map's own in `clueweb09.receipt`.

The map streams through `scripts/harness/fetch.py --to -`, the one download path, and never
touches the disk; the parts land together, only when the whole stream arrived and decoded, so a
cut stream books nothing and the read starts over, three times at most (`.clueweb09.failed`).
The tick starts it after the bank as its own user unit, `ark-clueweb`, so it outlives the tick
and never runs twice (`scripts/harness/scheduled_sync.sh`).

    uv run python scripts/sources/crawl_lists/clueweb09.py
"""

from __future__ import annotations

import bz2
import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path

from ark.hostnames import host_of

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data/raw/extended/crawl_lists"
MAP = "https://web.archive.org/web/20161228002334id_/https://ir.nist.gov/clueweb.urls-docid.bz2"
STAMP, PART, RECENT = "20090101000000", 5_000_000, 1_000_000


def fetch(url: str, max_bytes: str = "11G") -> subprocess.Popen:
    cmd = [sys.executable, str(REPO / "scripts/harness/fetch.py"), url, "--to", "-"]
    return subprocess.Popen([*cmd, "--max-bytes", max_bytes], stdout=subprocess.PIPE)


class Hashed:
    def __init__(self, raw):
        self.raw, self.sha1, self.bytes = raw, hashlib.sha256(), 0

    def read(self, n: int) -> bytes:
        got = self.raw.read(n)
        self.sha1.update(got)
        self.bytes += len(got)
        return got


def lines(stream):
    """The decoded lines of a bz2 stream, concatenated streams too; raises ValueError when
    the stream ends inside a block or a line."""
    dec, tail = bz2.BZ2Decompressor(), b""
    while chunk := stream.read(1 << 20):
        while chunk:
            if dec.eof:  # a parallel bzip2 writes streams back to back
                dec = bz2.BZ2Decompressor()
            tail += dec.decompress(chunk)
            chunk = dec.unused_data if dec.eof else b""
            *whole, tail = tail.split(b"\n")
            yield from whole
    if tail or not dec.eof:
        raise ValueError("the stream ends inside a block or a line")


def runs(raw_lines, recent: int = RECENT):
    """(url, node) once per host among the last `recent` seen, the host valid by his rules.
    The map is sorted by URL inside segments of some 20,000 pages, so a host's pages recur
    segments apart (36 runs of one host in 275,000 lines); the window folds those, the export's
    sort folds what recurs further."""
    seen: OrderedDict = OrderedDict()
    for line in raw_lines:
        url, _, node = line.rpartition(b" ")
        site = url.split(b"://", 1)[-1].split(b"/", 1)[0]
        if site in seen:
            seen.move_to_end(site)
            continue
        seen[site] = None
        if len(seen) > recent:
            seen.popitem(last=False)
        if host_of(url.decode("utf-8", "replace")):
            yield url.decode("utf-8", "replace"), node.decode("ascii", "replace")


def write_parts(pairs, folder: Path) -> list[Path]:
    """The parts, written under temporary names; how many rows each holds is PART."""
    parts, fh, n = [], None, 0
    for url, node in pairs:
        if n % PART == 0:
            if fh:
                fh.close()
            parts.append(folder / f".clueweb09_{len(parts)}.tmp")
            fh = io.TextIOWrapper(gzip.GzipFile(parts[-1], "wb", mtime=0))
        fh.write(json.dumps({"url": url, "timestamp": STAMP, "node": node}) + "\n")
        n += 1
    if fh:
        fh.close()
    return parts


def read() -> str:
    """One line for the log; the parts and the receipt land only on a whole, decoded stream."""
    t0, proc = time.time(), fetch(MAP)
    stream = Hashed(proc.stdout)
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        parts = write_parts(runs(lines(stream)), OUT)
        why = None
    except (ValueError, OSError) as exc:
        proc.kill()
        parts, why = sorted(OUT.glob(".clueweb09_*.tmp")), str(exc)
    proc.wait()
    if why or proc.returncode:
        for p in parts:
            p.unlink(missing_ok=True)
        why = f"clueweb09: not booked, fetch exit {proc.returncode}, {why or 'stream cut'}"
        with open(OUT / ".clueweb09.failed", "a") as fh:
            fh.write(why + "\n")
        return why
    for p in parts:
        os.replace(p, OUT / p.name.removeprefix(".").replace(".tmp", ".jsonl.gz"))
    receipt = {"url": MAP, "bytes": stream.bytes, "sha256": stream.sha1.hexdigest()}
    (OUT / "clueweb09.receipt").write_text(json.dumps(receipt) + "\n")
    return f"clueweb09\t{stream.bytes}\t{round(time.time() - t0)}\t{len(parts)} parts"


def main() -> None:
    marker = OUT / ".clueweb09.failed"
    if (OUT / "clueweb09.receipt").exists():
        return print("clueweb09: read", flush=True)
    if marker.exists() and len(marker.read_text().splitlines()) >= 3:
        return print("clueweb09: given up after three cut streams", flush=True)
    if subprocess.run(["bash", str(REPO / "scripts/harness/hold.sh"), "holds"]).returncode == 0:
        return print("clueweb09: held", flush=True)
    print(read(), flush=True)


if __name__ == "__main__":
    main()
