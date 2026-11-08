"""Read the crawl lists whole into 2009 and 2012 hostname journals: ClueWeb09, ClueWeb12, WDC 2012.

A dated crawl list is a class on two conditions (#286): the dataset documents a crawl inside one
calendar year and its nodes are fetched pages, or the hosts of fetched pages as the dataset
documents (#467). Both hold for the three lists in `LISTS`
(`ark.hostnames.CRAWL_LISTS`): the first 357,226,562 bytes of ClueWeb09's url-docid map
(`ir.nist.gov`, bz2) as its 2016 Wayback capture serves them (the capture is itself a prefix, so
the receipted range is the artifact, fleet #215),
every page fetched in January and February 2009 as
`<url> <docid>`, sorted by URL inside segments of some 20,000 pages, the segments in crawl
order; and LAW's ClueWeb12 URL list (13.9 GB gzip), every page fetched from 2012-02-10 to 05-10
in crawl order, one URL a line, its node id the URL's ordinal since LAW publishes no docid; and
the Web Data Commons 2012 Hyperlink Graph's host index (`sd-index.gz`, 872 MB gzip), "extracted
from a Web corpus gathered in the first half of 2012" keeping "every hyperlink pointing to another
crawled HTML page" (WDC's own words), so every host there had a page fetched, one host and its
index a line (`0---0.com	0`), sorted by name. A node dates its exact host in the list's
year (`crawl_list_node`), status-less, since a crawl list carries no response code. One row per
host among the last four million seen, `{url, timestamp, node}`, the stamp carrying the year
alone (`LISTS`), into `data/raw/extended/crawl_lists/<list>_<n>.jsonl.gz`,
5,000,000 rows a part; the export's sort folds a host that recurs further apart. The witness is
the row's node id, each part's sha256 in the export manifest and the artifact's own in
`<artifact>.receipt` (the list, or list.prefixbytes).

A list streams through `scripts/harness/fetch.py --to -`, the one download path, and never
touches the disk; its journals land together, only when the whole stream, or exactly the prefix
with its sha256, arrived and decoded, so a cut stream books nothing and the list is read again,
three times at most (`.<tag>.failed`, the tag naming the artifact). Each list left, the hold read
between: the tick starts it after the bank as its own user unit, `ark-clueweb`, so it outlives
the tick and never runs twice (`scripts/harness/scheduled_sync.sh`).

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

from ark.disk import below_floor, trim
from ark.hostnames import CRAWL_LISTS, host_of

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data/raw/extended/crawl_lists"
LOG = REPO / "data/logs/clueweb.log"  # the tick's `>>` for the unit
PART, RECENT = 5_000_000, 4_000_000  # the window holds about 700 MB
# name: (the row stamp, the stream's codec, the prefix in bytes and its sha256, or None for the
# whole file). The stamp is the crawl window's first documented day at year precision, not a
# capture time: 2012-02-10 for ClueWeb12 (LAW); ClueWeb09's documentation gives January and
# February 2009, no day, so the year's first day. The export ranks a capture with a status above
# it for the same host-year. ClueWeb09's prefix is the 2026-10-18 receipt's range, priced then.
LISTS = {
    "clueweb09": (
        "20090101000000",
        "bz2",
        357_226_562,
        "05e3c7b154539a9376b6aa91c5630f54d7a6a3f4b30c9c2655a0456350a9e744",
    ),
    "clueweb12": ("20120210000000", "gzip", None, None),
    "wdc2012": ("20120127000000", "gzip", None, None),  # CC-MAIN-2012: 2012-01-27 to 06-05
}


def fetch(url: str, max_bytes: str = "14G") -> subprocess.Popen:
    cmd = [sys.executable, str(REPO / "scripts/harness/fetch.py"), url, "--to", "-"]
    return subprocess.Popen([*cmd, "--max-bytes", max_bytes], stdout=subprocess.PIPE)


class Hashed:
    """The stream, hashed as it is read, and cut at `limit` bytes when the artifact is a prefix."""

    def __init__(self, raw, limit: int | None = None):
        self.raw, self.sha, self.bytes, self.limit = raw, hashlib.sha256(), 0, limit

    def read(self, n: int) -> bytes:
        if self.limit is not None:
            n = min(n, self.limit - self.bytes)
        got = self.raw.read(n) if n > 0 else b""
        self.sha.update(got)
        self.bytes += len(got)
        return got


def lines(stream, codec: str = "bz2", whole: bool = True):
    """The decoded lines of a bz2 or gzip stream, concatenated members too; raises ValueError
    when a whole stream ends inside a member or a line, and drops that tail for a prefix."""
    fresh = bz2.BZ2Decompressor if codec == "bz2" else lambda: zlib.decompressobj(31)
    dec, tail = fresh(), b""
    while chunk := stream.read(1 << 20):
        while chunk:
            if dec.eof:  # a parallel compressor writes members back to back
                dec = fresh()
            tail += dec.decompress(chunk)
            chunk = dec.unused_data if dec.eof else b""
            *done, tail = tail.split(b"\n")
            yield from done
    if whole and not dec.eof:
        raise ValueError("the stream ends inside a member")
    if whole and tail:  # a last line without its newline
        yield tail


def runs(raw_lines, recent: int = RECENT):
    """(url, node) once per host among the last `recent` seen, the host valid by his rules; a
    line is `<url> <node>`, `<host>\t<node>`, or a URL alone whose node is its ordinal."""
    seen: OrderedDict = OrderedDict()
    for n, line in enumerate(raw_lines):
        fields = line.split()
        if not fields:
            continue
        url, node = fields[0], fields[-1] if len(fields) > 1 else str(n).encode()
        if b"://" not in url:  # a host list: the host's root is its URL
            url = b"http://" + url + b"/"
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


def tag(name: str) -> str:
    """The artifact's name for its receipt and marker: the list, and the prefix when it is one."""
    prefix = LISTS[name][2]
    return f"{name}.{prefix}" if prefix else name


def read(name: str) -> str:
    """One line for the log; the journals and the receipt land only on a whole, decoded stream,
    or on exactly the prefix with its sha256, whatever the fetch's own exit says of the rest."""
    stamp, codec, prefix, sha = LISTS[name]
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob(f".{name}_*.tmp"):  # a killed run's journals
        stale.unlink()
    for old in OUT.glob(f".{name}*.failed"):  # a redefined prefix's strikes
        if old.name != f".{tag(name)}.failed":
            old.unlink()
    t0, proc = time.time(), fetch(CRAWL_LISTS[name])
    stream = Hashed(proc.stdout, prefix)
    try:
        parts = write_parts(runs(lines(stream, codec, whole=prefix is None)), OUT, name, stamp)
        why = None
    except (ValueError, OSError, zlib.error) as exc:  # a cut, a refused fetch, a corrupt byte
        parts, why = sorted(OUT.glob(f".{name}_*.tmp")), str(exc)
    if why or prefix:
        proc.kill()
    proc.wait()
    if prefix and not why and (stream.bytes != prefix or stream.sha.hexdigest() != sha):
        why = f"{stream.bytes} bytes, sha256 {stream.sha.hexdigest()}, not the prefix's"
    if why or (proc.returncode and not prefix):
        for p in parts:
            p.unlink(missing_ok=True)
        why = f"{name}: not booked, fetch exit {proc.returncode}" + (f", {why}" if why else "")
        with open(OUT / f".{tag(name)}.failed", "a") as fh:
            fh.write(why + "\n")
        return why
    for p in parts:
        os.replace(p, OUT / p.name.removeprefix(".").replace(".tmp", ".jsonl.gz"))
    receipt = {"url": CRAWL_LISTS[name], "bytes": stream.bytes, "sha256": stream.sha.hexdigest()}
    (OUT / f"{tag(name)}.receipt").write_text(json.dumps(receipt) + "\n")
    return f"{name}\t{stream.bytes}\t{round(time.time() - t0)}\t{len(parts)} parts"


def failures(name: str) -> int:
    marker = OUT / f".{tag(name)}.failed"
    return len(marker.read_text().splitlines()) if marker.exists() else 0


def todo() -> list[str]:
    return [n for n in LISTS if not (OUT / f"{tag(n)}.receipt").exists() and failures(n) < 3]


def left() -> int:
    return len(todo())


def main() -> None:
    trim(LOG)
    while queue := todo():
        if subprocess.run(["bash", str(REPO / "scripts/harness/hold.sh"), "holds"]).returncode == 0:
            return print("clueweb: held", flush=True)
        if why := below_floor(OUT, root=REPO):
            return print(f"clueweb: {why}", flush=True)
        print(read(min(queue, key=failures)), flush=True)
    print("clueweb: every list read or given up", flush=True)


if __name__ == "__main__":
    main()
