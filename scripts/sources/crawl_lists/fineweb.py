"""Read FineWeb's two 2013 crawls into 2013 hostname journals, by HTTP range, never the text.

FineWeb (`huggingface.co/datasets/HuggingFaceFW/fineweb`, ODC-By, no login, robots `Allow: /`)
keeps the Common Crawl pages it extracted text from, one row a page: its `url`, its fetch `date`
and the `file_path` of the CC WARC holding the record. CC-MAIN-2013-20 (205 parts) and
CC-MAIN-2013-48 (212) are each a crawl inside 2013 whose rows are fetched pages, a dated crawl
list (#286) read as `crawl_lists` (`clueweb.py`, `ark.hostnames.CRAWL_LISTS`).

A part is some 2.1 GB of parquet in some 1,100 row groups whose `url`, `date` and `file_path`
chunks lie side by side: its footer is read, then one range GET a row group spans those three
(about 62 KB), so a part costs some 68 MB and six minutes, and the text is never asked for.
One row per host new to 2013 among the parts read, `{url, timestamp, node}`, the stamp the
page's fetch time and the node its WARC, into
`data/raw/extended/crawl_lists/fineweb-2013-NN_<part>.jsonl.gz`, one journal a part; a host the
earlier crawl gave adds nothing to the year, so the later one skips it. The year's hosts so far
are Arrow arrays rebuilt from the journals at a start, a fifth of a Python set's memory. A part
is done once its journal landed and `fineweb.done` holds its line (its LFS sha256, which the
hub's redirect confirmed, row groups, rows, hosts, bytes and GETs); a start deletes a journal
without one.

One client, through `scripts/harness/fetch.py`'s robots and User-Agent: the parts in order,
PAUSE_S between them, each part's hub redirect resolved once and again when its signed URL
expires. A 429, a 5xx or a failed connection is asked again after each of RETRY_S, Retry-After
honoured up to the last; a part that still fails takes a strike (`.fineweb.failed`, three give
it up) and the run stops, `waits until` WAIT_S later (`.fineweb.wait`), which the unattended
check reads. The hold and the collectors' floor are read before each part: the tick starts it
after the bank as its own user unit, `ark-fineweb`, so it outlives the tick and never runs twice
(`scripts/harness/scheduled_sync.sh`).

    uv run python scripts/sources/crawl_lists/fineweb.py
"""

from __future__ import annotations

import gzip
import http.client
import importlib.util
import io
import json
import os
import re
import subprocess
import time
import urllib.parse
from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.json as pj
import pyarrow.parquet as pq

from ark.disk import below_floor, trim
from ark.hostnames import host_of

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data/raw/extended/crawl_lists"
LOG = REPO / "data/logs/fineweb.log"  # the tick's `>>` for the unit
DONE, FAILED, WAIT = OUT / "fineweb.done", OUT / ".fineweb.failed", OUT / ".fineweb.wait"
HUB = "https://huggingface.co"
TREE = HUB + "/api/datasets/HuggingFaceFW/fineweb/tree/main/data/{crawl}"
PART = HUB + "/datasets/HuggingFaceFW/fineweb/resolve/main/{path}"
CRAWLS = {"CC-MAIN-2013-20": 205, "CC-MAIN-2013-48": 212}  # in reading order, parts each
COLUMNS = ("url", "date", "file_path")
PAUSE_S, RETRY_S, WAIT_S, TIMEOUT_S = 30, (30, 120, 600), 3600, 60
READ_MAX = 16 << 20  # one answer's bytes: a footer is some 4.2 MB, a row group's span 63 KB
DIGITS = re.compile(r"\D")


def _fetch():
    spec = importlib.util.spec_from_file_location("fetch", REPO / "scripts/harness/fetch.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FETCH = _fetch()
ROBOTS: dict = {}  # fetch.py's per-host cache, read once a run


class Failed(Exception):
    """A request that failed past its retries, or an answer that is not the part's."""


def ask(url: str, start: int | None = None, end: int | None = None) -> tuple[int, dict, bytes]:
    """One GET once its host's robots.txt allows it, bytes start to end inclusive when given."""
    verdict, _, why = FETCH.read_robots(url, TIMEOUT_S, ROBOTS)
    if verdict != "allowed":
        raise Failed(f"robots {verdict}: {why}")
    for tries in range(len(RETRY_S) + 1):
        try:
            status, headers, body = FETCH.get(url, TIMEOUT_S, start, end)
            data = body.read(READ_MAX + 1)
        except (OSError, http.client.HTTPException) as exc:  # a dead host, a cut answer
            status, headers, data = 0, {}, str(exc).encode()
        if status and status != 429 and status < 500:
            if len(data) > READ_MAX:
                raise Failed(f"{url}: over {READ_MAX} bytes")
            return status, headers, data
        if tries < len(RETRY_S):
            after = FETCH.retry_after_seconds(headers) or 0
            time.sleep(max(RETRY_S[tries], min(after, RETRY_S[-1])))
    raise Failed(f"{status or data.decode(errors='replace')} after {len(RETRY_S)} retries")


class Part(io.RawIOBase):
    """A parquet part as pyarrow reads it: each read served from the span `fetch` holds, else
    asked for itself; the hub's signed redirect resolved once, again when it expires (403)."""

    def __init__(self, path: str, size: int, sha: str):
        self.url, self.size, self.sha = PART.format(path=path), size, sha
        self.cdn, self.pos, self.held, self.gets, self.bytes = None, 0, (0, b""), 0, 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = (0, self.pos, self.size)[whence] + offset
        return self.pos

    def tell(self) -> int:
        return self.pos

    def resolve(self) -> None:
        status, headers, _ = ask(self.url, 0, 0)
        etag = headers.get("x-linked-etag", "").strip('"')
        if status != 302 or etag != self.sha:
            raise Failed(f"the hub answered {status}, etag {etag or 'none'}, not {self.sha}")
        self.cdn = urllib.parse.urljoin(self.url, headers["location"])

    def fetch(self, start: int, end: int) -> None:
        """Hold bytes start to end, exclusive, for the reads that follow."""
        for _ in range(2):
            if self.cdn is None:
                self.resolve()
            status, headers, data = ask(self.cdn, start, end - 1)
            if status != 403:
                break
            self.cdn = None  # the signed URL expired: resolve once more
        if status != 206 or len(data) != end - start or FETCH._range_start(headers) != start:
            raise Failed(f"bytes {start}-{end - 1}: {status}, {len(data)} bytes")
        self.held, self.gets, self.bytes = (start, data), self.gets + 1, self.bytes + len(data)

    def readinto(self, buf) -> int:
        n = min(len(buf), self.size - self.pos)
        start, data = self.held
        if not start <= self.pos <= self.pos + n <= start + len(data):
            self.fetch(self.pos, self.pos + n)
            start, data = self.held
        buf[:n] = data[self.pos - start : self.pos - start + n]
        self.pos += n
        return n


def firsts(part: Part) -> tuple[dict, int, int]:
    """Each valid host's first row in the part, (url, stamp, WARC); row groups; rows."""
    pf = pq.ParquetFile(part)
    meta, index = pf.metadata, [pf.schema_arrow.get_field_index(c) for c in COLUMNS]
    found: dict = {}
    for g in range(meta.num_row_groups):
        chunks = [meta.row_group(g).column(i) for i in index]
        starts = [c.dictionary_page_offset or c.data_page_offset for c in chunks]
        end = max(s + c.total_compressed_size for s, c in zip(starts, chunks, strict=True))
        if end - min(starts) > READ_MAX:
            raise Failed(f"row group {g}: the columns are not side by side")
        part.fetch(min(starts), end)
        table = pf.read_row_group(g, columns=list(COLUMNS), use_threads=False)
        for url, date, node in zip(*(table.column(c).to_pylist() for c in COLUMNS), strict=True):
            if url and (host := host_of(url)) and host not in found:
                if len(stamp := DIGITS.sub("", date or "")[:14]) == 14:
                    found[host] = (url, stamp, node)
    return found, meta.num_row_groups, meta.num_rows


def unseen(found: dict, seen: list) -> pa.Array:
    """The part's hosts no earlier journal holds: the year's arrays probed against a hash table
    of the part's hosts, never one of the year's."""
    fresh = pa.array(list(found), pa.string())
    year = pa.chunked_array(seen, pa.string())
    hits = year.filter(pc.is_in(year, value_set=fresh)).combine_chunks()
    return fresh.filter(pc.invert(pc.is_in(fresh, value_set=hits)))


def journal(path: str) -> Path:
    """`data/CC-MAIN-2013-20/000_00000.parquet`'s journal, named for its list and part."""
    crawl = path.split("/")[1].removeprefix("CC-MAIN-")
    return OUT / f"fineweb-{crawl}_{Path(path).stem}.jsonl.gz"


def read(path: str, size: int, sha: str, seen: list) -> str:
    """One part: its journal, unless no host is new, and its done line; a line for the log."""
    t0, part = time.time(), Part(path, size, sha)
    found, groups, rows = firsts(part)
    new = unseen(found, seen)
    if len(new):
        out = journal(path)
        tmp = out.with_name(f".{out.name}.tmp")
        with io.TextIOWrapper(gzip.GzipFile(tmp, "wb", mtime=0)) as fh:
            for host in new.to_pylist():
                url, stamp, node = found[host]
                fh.write(json.dumps({"url": url, "timestamp": stamp, "node": node}) + "\n")
        os.replace(tmp, out)
    line = {"part": path, "sha256": sha, "row_groups": groups, "rows": rows, "hosts": len(found)}
    line |= {"new": len(new), "bytes": part.bytes, "gets": part.gets}
    with open(DONE, "a") as fh:
        fh.write(json.dumps(line) + "\n")
    seen.append(new)
    took = round(time.time() - t0)
    return f"{path}\t{groups}\t{rows}\t{len(found)}\t{len(new)}\t{part.bytes}\t{part.gets}\t{took}"


def done() -> set[str]:
    lines = DONE.read_text().splitlines() if DONE.exists() else []
    return {json.loads(ln)["part"] for ln in lines}


def strikes() -> Counter:
    lines = FAILED.read_text().splitlines() if FAILED.exists() else []
    return Counter(ln.split("\t")[0] for ln in lines)


def left() -> int:
    """Parts under three strikes without a done line, from the files here alone."""
    booked = done()
    given_up = {p for p, n in strikes().items() if n >= 3} - booked
    return sum(CRAWLS.values()) - len(booked) - len(given_up)


def year_so_far() -> list:
    """The hosts each done part's journal holds; a journal or temporary no done line names is a
    killed run's, deleted."""
    names = {journal(p).name for p in done()}
    for stray in [*OUT.glob(".fineweb-*.tmp"), *OUT.glob("fineweb-*.jsonl.gz")]:
        if stray.name not in names:
            stray.unlink()
    urls = [pj.read_json(p).column("url").to_pylist() for p in OUT.glob("fineweb-*.jsonl.gz")]
    return [pa.array([host_of(u) for u in some], pa.string()) for some in urls]


def listing(crawl: str) -> list[tuple[str, int, str]]:
    """(path, size, LFS sha256) of the crawl's parts, from the hub's file listing."""
    status, _, data = ask(TREE.format(crawl=crawl))
    if status != 200:
        raise Failed(f"{crawl}'s listing answered {status}")
    files = [f for f in json.loads(data) if f["path"].endswith(".parquet")]
    if len(files) != CRAWLS[crawl]:
        print(f"fineweb: {crawl} lists {len(files)} parts, not {CRAWLS[crawl]}", flush=True)
    return sorted((f["path"], f["size"], f["lfs"]["oid"]) for f in files)


def stamp(at: float) -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(at))


def main() -> None:
    trim(LOG)
    OUT.mkdir(parents=True, exist_ok=True)
    if WAIT.exists() and (until := float(WAIT.read_text())) > time.time():
        return print(f"fineweb: waits until {stamp(until)}", flush=True)
    hold = ["bash", str(REPO / "scripts/harness/hold.sh"), "holds"]
    try:
        parts = [p for crawl in CRAWLS for p in listing(crawl)]
        booked, struck, seen = done(), strikes(), year_so_far()
        print("part\trow groups\trows\thosts\tnew to 2013\tbytes\tGETs\tseconds", flush=True)
        for path, size, sha in parts:
            if path in booked or struck[path] >= 3:
                continue
            if subprocess.run(hold).returncode == 0:
                return print("fineweb: held", flush=True)
            if why := below_floor(OUT, root=REPO):
                return print(f"fineweb: {why}", flush=True)
            try:
                print(read(path, size, sha, seen), flush=True)
            except (Failed, OSError, pa.ArrowException) as exc:  # a cut, a refusal, a bad byte
                with open(FAILED, "a") as fh:
                    fh.write(f"{path}\t{' '.join(str(exc).split())}\n")
                raise Failed(f"{path} struck, {exc}") from exc
            time.sleep(PAUSE_S)
    except Failed as exc:
        WAIT.write_text(f"{time.time() + WAIT_S:.0f}\n")
        return print(f"fineweb: {exc}, waits until {stamp(time.time() + WAIT_S)}", flush=True)
    print("fineweb: every part read or given up", flush=True)


if __name__ == "__main__":
    main()
