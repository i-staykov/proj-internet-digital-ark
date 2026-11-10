"""The header lane's share on a runner's own address: the `.mbox.zip` files of the usenet-*
items a name list picks, extracted to the header journals the bank folds.

A name picks the item it is and every item under it (`fido7` picks `usenet-fido7.ru.anime`).
Archive.org's scrape API lists the items; dealt largest first, every `--of`-th from `--shard`
is this job's, and `--split files` deals files by their name's CRC instead, every job listing
every item, for an item too large for one job. PARALLEL downloads at once, their starts 1 s
apart as on the bank host (`run_usenet_header_items.py`), about 1 GB or 300 files a batch, each
extracted by `build_usenet_header_pool.py` into `OUT/hr_<UTC stamp>_<shard>/` on every core
while the next one downloads, and no zip outlives its extract. `OUT/read_<shard>.tsv` keeps
each file's batch, item, name, bytes and answer, and each batch's download and extract seconds.
A 429 or a 503 is never asked twice and ends the job, as `--seconds` does; any other failure
is asked once more after 120 s, then logged and its file left. Stdlib, curl and unzip alone,
and no price: a runner installs nothing and holds no snapshot.

    python3 scripts/sources/usenet/runner_header_items.py OUT --names "fido7 relcom" --of 4
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

UA = "internet-digital-ark/1.0 (usenet header lane)"  # the tool and its version, as the host asks
BUILD = Path(__file__).with_name("build_usenet_header_pool.py")
# every transfer bounded: no connection in 60 s, or under 1 KB/s for 300 s, ends it
CURL = ["curl", "-sSL", "--connect-timeout", "60", "--speed-time", "300", "--speed-limit", "1024"]
PARALLEL, BATCH, FILES = 3, 1e9, 300  # a batch: a GB, or 300 small files
BUSY = ("429", "503")  # the host asks for a pause
LOCK, NEXT, STOP = threading.Lock(), [0.0], threading.Event()


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def listed() -> list[dict]:
    """Every usenet-* identifier with its size, paged by the scrape cursor."""
    out, cursor = [], None
    while True:
        q = {"q": "identifier:usenet-*", "fields": "identifier,item_size", "count": 10000}
        if cursor:
            q["cursor"] = cursor
        page = get("https://archive.org/services/search/v1/scrape?" + urllib.parse.urlencode(q))
        out += page["items"]
        cursor = page.get("cursor")
        if not cursor:
            return out
        time.sleep(2)


def picked(names: set[str], items: list[dict]) -> list[str]:
    """The items a name is or is above, largest first."""
    keep = []
    for x in items:
        item = x["identifier"][7:]
        parts = item.split(".")
        if x.get("item_size") and any(".".join(parts[: i + 1]) in names for i in range(len(parts))):
            keep.append((-int(x["item_size"]), item))
    return [item for _, item in sorted(keep)]


def mine(index: int, name: str, shard: int, of: int, split: str) -> bool:
    """Whether the `index`-th item's file `name` is this shard's."""
    return (zlib.crc32(name.encode()) if split == "files" else index) % of == shard


def fetch(item: str, name: str, size: int, pool: Path) -> str:
    """ "200" once the file came whole, else its last answer: an HTTP code, "cut" for a broken
    transfer, "size" for a whole one of the wrong size, "stop" once the job is ending."""
    url = f"https://archive.org/download/usenet-{item}/{urllib.parse.quote(name)}"
    code, dst = "stop", pool / name
    for again in (True, False):
        if STOP.is_set():
            return "stop"
        with LOCK:
            wait = NEXT[0] - time.monotonic()
            NEXT[0] = max(NEXT[0], time.monotonic()) + 1
        time.sleep(max(0.0, wait))
        cmd = [*CURL, "-A", UA, "-o", str(dst), "-w", "%{http_code}", url]
        r = subprocess.run(cmd, capture_output=True, text=True)
        code = r.stdout.strip() or "cut"
        if code == "200" and (r.returncode or not dst.exists()):
            code = "cut"
        elif code == "200" and dst.stat().st_size != size:
            code = "size"
        if code == "200":
            return code
        if dst.exists():
            dst.unlink()
        if code in BUSY:
            STOP.set()
            return code
        if again:
            STOP.wait(120)
    return code


class Reader:
    """Batches downloaded one after the other, each extracted while the next downloads."""

    def __init__(self, out: Path, shard: int) -> None:
        self.out, self.shard, self.building, self.files, self.size = out, shard, None, 0, 0
        self.log = open(out / f"read_{shard}.tsv", "a")

    def note(self, *row) -> None:
        print(*row, sep="\t", file=self.log, flush=True)

    def settle(self) -> None:
        """The extract in flight, awaited: its journals take their name, a failed one is gone."""
        if not self.building:
            return
        proc, name, t0 = self.building
        rc, self.building = proc.wait(), None
        shutil.rmtree(self.out / f".pool_{name}", ignore_errors=True)
        if rc == 0:
            (self.out / f".{name}").rename(self.out / name)
        else:
            shutil.rmtree(self.out / f".{name}", ignore_errors=True)
        self.note("built", name, rc, round(time.time() - t0))

    def batch(self, rows: list[tuple[str, str, int]]) -> None:
        name = f"hr_{time.strftime('%Y%m%dT%H%M%S', time.gmtime())}_{self.shard}"
        pool, t0 = self.out / f".pool_{name}", time.time()
        pool.mkdir(parents=True)
        with ThreadPoolExecutor(PARALLEL) as ex:
            codes = list(ex.map(lambda f: fetch(*f, pool), rows))
        got = 0
        for i, code in enumerate(codes):  # no zip(strict=): a self-hosted runner's Python is 3.8
            self.note(name, *rows[i], code)
            if code == "200":
                got, self.size = got + 1, self.size + rows[i][2]
        self.files += got
        self.note("got", name, got, round(time.time() - t0))
        self.settle()  # one extract at a time: two batches of zips on disk at most
        if not got:
            shutil.rmtree(pool, ignore_errors=True)
            return
        cmd = [sys.executable, str(BUILD), str(pool), str(self.out / f".{name}")]
        workers = min(got, os.cpu_count() or 1)  # a shard a worker: none left empty
        proc = subprocess.Popen([*cmd, str(workers)], stdout=subprocess.DEVNULL)
        self.building = (proc, name, time.time())


def files(a: argparse.Namespace, note) -> Iterator[tuple[str, str, int]]:
    """This shard's (item, file, bytes), an item's listing asked as its turn comes; a group
    sits in its hierarchy's item and its own, and is read once."""
    queued: set[str] = set()
    for index, item in enumerate(picked(set(a.names.split()), listed())):
        if a.split == "items" and not mine(index, "", a.shard, a.of, a.split):
            continue
        try:
            meta = get(f"https://archive.org/metadata/usenet-{item}/files").get("result", [])
        except urllib.error.HTTPError as exc:
            if str(exc.code) in BUSY:
                STOP.set()
                return
            note("unlisted", item, exc.code)
            continue
        for f in meta:
            name, size = f["name"], int(f.get("size", 0))
            if not name.endswith(".mbox.zip") or "/" in name or not size or name in queued:
                continue
            if mine(index, name, a.shard, a.of, a.split):
                queued.add(name)
                yield item, name, size


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", type=Path)
    ap.add_argument("--names", required=True, help="tops or items, space separated")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    ap.add_argument("--split", choices=("items", "files"), default="items")
    ap.add_argument("--seconds", type=int, default=19800)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    end, reader, rows, why = time.time() + a.seconds, Reader(a.out, a.shard), [], ""
    try:
        for row in files(a, reader.note):
            if STOP.is_set() or time.time() > end:
                break
            if row[2] > shutil.disk_usage(a.out).free / 3:  # the zip, its batch and its extract
                reader.note("-", *row, "disk")
                continue
            rows.append(row)
            if sum(r[2] for r in rows) >= BATCH or len(rows) >= FILES:
                reader.batch(rows)
                rows = []
        else:
            why = "read out"
        if rows and not STOP.is_set():  # what was listed is read, the deadline's margin its room
            reader.batch(rows)
    except (OSError, ValueError) as exc:  # a listing that failed: what is built still uploads
        why = f"listing failed: {type(exc).__name__}"
    why = "asked to pause" if STOP.is_set() else why or "out of time"
    reader.settle()
    reader.note("end", why, reader.files, reader.size)
    print(f"header runner: {why}, {reader.files} files, {reader.size / 1e9:.2f} GB")


if __name__ == "__main__":
    main()
