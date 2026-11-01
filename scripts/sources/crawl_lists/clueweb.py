"""Read the ClueWeb crawl lists whole into 2009 and 2012 hostname journals.

A dated crawl list is a class on two conditions (#286): the dataset documents a crawl inside one
calendar year and its nodes are fetched pages. Both hold for the two lists in `LISTS`
(`ark.hostnames.CRAWL_LISTS`): ClueWeb09's url-docid map (`ir.nist.gov`, 10.2 GB bz2, read from
its 2016 Wayback capture, fleet #215), every page fetched in January and February 2009 as
`<url> <docid>`, URL-sorted inside segments of some 20,000 pages; and LAW's ClueWeb12 URL list
(13.9 GB gzip), every page fetched from 2012-02-10 to 05-10 in crawl order, one URL a line, its
node id the URL's ordinal since LAW publishes no docid. A node dates its exact host in the list's
year (`crawl_list_node`), status-less, since a crawl list carries no response code. One row per
host among the last four million seen, `{url, timestamp, node}`, the stamp carrying the year
alone (`LISTS`), into `data/raw/extended/crawl_lists/<list>_<n>.jsonl.gz`,
5,000,000 rows a part; the export's sort folds a host that recurs further apart. The witness is
the row's node id, each part's sha256 in the export manifest and the list's own in
`<list>.receipt`.

A list streams through `scripts/harness/fetch.py --to -`, the one download path, and never
touches the disk; its parts land together, only when the whole stream arrived and decoded, so a
cut stream books nothing and the list is read again, three times at most (`.<list>.failed`). Each
list left, the hold read between: the tick starts it after the bank as its own user unit,
`ark-clueweb`, so it outlives the tick and never runs twice (`scripts/harness/scheduled_sync.sh`).

    uv run python scripts/sources/crawl_lists/clueweb.py
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
import zlib
from collections import OrderedDict
from pathlib import Path

from ark.hostnames import CRAWL_LISTS, host_of

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data/raw/extended/crawl_lists"
PART, RECENT = 5_000_000, 4_000_000  # the window holds about 700 MB
# name: (the row stamp, the stream's codec). The stamp carries the list's year, not a capture
# time: the documented crawl's first day, 2012-02-10 for ClueWeb12 (LAW); ClueWeb09's
# documentation gives January and February 2009, no day, so its stamp is the year's first day.
LISTS = {"clueweb09": ("20090101000000", "bz2"), "clueweb12": ("20120210000000", "gzip")}


def fetch(url: str, max_bytes: str = "14G") -> subprocess.Popen:
    cmd = [sys.executable, str(REPO / "scripts/harness/fetch.py"), url, "--to", "-"]
    return subprocess.Popen([*cmd, "--max-bytes", max_bytes], stdout=subprocess.PIPE)


class Hashed:
    def __init__(self, raw):
        self.raw, self.sha, self.bytes = raw, hashlib.sha256(), 0

    def read(self, n: int) -> bytes:
        got = self.raw.read(n)
        self.sha.update(got)
        self.bytes += len(got)
        return got


def lines(stream, codec: str = "bz2"):
    """The decoded lines of a bz2 or gzip stream, concatenated members too; raises ValueError
    when the stream ends inside a member or a line."""
    fresh = bz2.BZ2Decompressor if codec == "bz2" else lambda: zlib.decompressobj(31)
    dec, tail = fresh(), b""
    while chunk := stream.read(1 << 20):
        while chunk:
            if dec.eof:  # a parallel compressor writes members back to back
                dec = fresh()
            tail += dec.decompress(chunk)
            chunk = dec.unused_data if dec.eof else b""
            *whole, tail = tail.split(b"\n")
            yield from whole
    if tail or not dec.eof:
        raise ValueError("the stream ends inside a member or a line")


def runs(raw_lines, recent: int = RECENT):
    """(url, node) once per host among the last `recent` seen, the host valid by his rules; a
    line is `<url> <node>`, or a URL alone whose node is its ordinal."""
    seen: OrderedDict = OrderedDict()
    for n, line in enumerate(raw_lines):
        url, _, node = line.rpartition(b" ")
        if not url:
            url, node = node, str(n).encode()
        site = url.split(b"://", 1)[-1].split(b"/", 1)[0]
        if site in seen:
            seen.move_to_end(site)
            continue
        seen[site] = None
        if len(seen) > recent:
            seen.popitem(last=False)
        if host_of(url.decode("utf-8", "replace")):
            yield url.decode("utf-8", "replace"), node.decode("ascii", "replace")


def write_parts(pairs, folder: Path, name: str, stamp: str) -> list[Path]:
    """The parts, written under temporary names, PART rows each."""
    parts, fh, n = [], None, 0
    for url, node in pairs:
        if n % PART == 0:
            if fh:
                fh.close()
            parts.append(folder / f".{name}_{len(parts)}.tmp")
            fh = io.TextIOWrapper(gzip.GzipFile(parts[-1], "wb", mtime=0))
        fh.write(json.dumps({"url": url, "timestamp": stamp, "node": node}) + "\n")
        n += 1
    if fh:
        fh.close()
    return parts


def read(name: str) -> str:
    """One line for the log; the parts and the receipt land only on a whole, decoded stream."""
    stamp, codec = LISTS[name]
    t0, proc = time.time(), fetch(CRAWL_LISTS[name])
    stream = Hashed(proc.stdout)
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        parts = write_parts(runs(lines(stream, codec)), OUT, name, stamp)
        why = None
    except (ValueError, OSError) as exc:
        proc.kill()
        parts, why = sorted(OUT.glob(f".{name}_*.tmp")), str(exc)
    proc.wait()
    if why or proc.returncode:
        for p in parts:
            p.unlink(missing_ok=True)
        why = f"{name}: not booked, fetch exit {proc.returncode}, {why or 'stream cut'}"
        with open(OUT / f".{name}.failed", "a") as fh:
            fh.write(why + "\n")
        return why
    for p in parts:
        os.replace(p, OUT / p.name.removeprefix(".").replace(".tmp", ".jsonl.gz"))
    receipt = {"url": CRAWL_LISTS[name], "bytes": stream.bytes, "sha256": stream.sha.hexdigest()}
    (OUT / f"{name}.receipt").write_text(json.dumps(receipt) + "\n")
    return f"{name}\t{stream.bytes}\t{round(time.time() - t0)}\t{len(parts)} parts"


def failures(name: str) -> int:
    marker = OUT / f".{name}.failed"
    return len(marker.read_text().splitlines()) if marker.exists() else 0


def todo() -> list[str]:
    return [n for n in LISTS if not (OUT / f"{n}.receipt").exists() and failures(n) < 3]


def main() -> None:
    while left := todo():
        if subprocess.run(["bash", str(REPO / "scripts/harness/hold.sh"), "holds"]).returncode == 0:
            return print("clueweb: held", flush=True)
        print(read(min(left, key=failures)), flush=True)
    print("clueweb: every list read or given up", flush=True)


if __name__ == "__main__":
    main()
