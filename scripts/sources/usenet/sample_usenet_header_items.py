"""Seeded header-lane sample of the usenet-* items on archive.org the lane has not read, by bucket.

The group catalogue (`data/raw/usenet_catalog.json`) lists the big hierarchies only. This lists
every usenet-* item on archive.org through the scrape API, keeps an item when a
bucket names its top-level hierarchy and no group in `seen` (a JSON list of group names already
read) is it or under it, and per bucket reads about 0.4 GB of groups of 1 to 300 MB, at most
three per item, from items in seeded random order. One download at a time above the
collectors' floor (`ark.disk`), each zip extracted by `build_usenet_header_pool.py` and
deleted, a 429 ends the run. Each bucket's journals are then written as {host, year} items
through the ingest's own reader, a `text` holding several names included, for `just price
--items <workdir>/<bucket>.items.jsonl --track candidate`. `log.tsv` keeps bytes (or the build's
failing code) and download and extract seconds per group. Its helpers serve the header lane
(`run_usenet_header_items.py`).

    uv run python scripts/sources/usenet/sample_usenet_header_items.py WORKDIR SEEN.json \\
        us=ba,nyc,tx vendor=gnu,perl
"""

from __future__ import annotations

import http.client
import json
import os
import random
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from email.utils import parsedate_to_datetime
from pathlib import Path

from ark.disk import below_floor
from ark.hostnames import USENET_HEADER_FAMILY, usenet_item_rows

UA = "ark-research (header-lane measurement)"
BUILD = Path(__file__).with_name("build_usenet_header_pool.py")
SNAPSHOT = Path(__file__).resolve().parents[3] / "output/price_snapshot"
# every transfer bounded: no connection in 60 s, or under 1 KB/s for 300 s, is an outage
CURL = ["curl", "-sSL", "--connect-timeout", "60", "--speed-time", "300", "--speed-limit", "1024"]
FAILED = (OSError, ValueError, http.client.HTTPException)


class End(Exception):
    """A run's end that strikes nothing: a 429 (`retry`, its Retry-After seconds), an outage
    (no answer, a 5xx, a cut or stalled transfer) or the hold; `file`, the download it cut."""

    def __init__(self, code: str, retry: int = 0) -> None:
        super().__init__(code)
        self.code, self.retry, self.file = code, retry, ""


def never() -> bool:
    return False


def outage(code: str) -> bool:
    """No answer, a 5xx, a cut transfer or an exception's name; "size", a clean download of the
    wrong size, is no outage."""
    return code in ("000", "cut") or code.startswith("5") or not (code.isdigit() or code == "size")


def failure(exc: BaseException) -> End | str:
    """A failed request's End, or the 4xx (not 429) it answered."""
    code = str(getattr(exc, "code", "") or type(exc).__name__)
    if code == "429":
        headers = getattr(exc, "headers", None)
        return End(code, seconds(headers.get("Retry-After") if headers else None))
    return End(code) if outage(code) else code


def seconds(value: str | None) -> int:
    """A Retry-After in seconds, either form; 0 when absent or unreadable."""
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        try:
            return max(0, int(parsedate_to_datetime(value).timestamp() - time.time()))
        except (TypeError, ValueError, IndexError):
            return 0


def get(url: str) -> dict:
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120
    ) as r:
        return json.load(r)


def pause(held) -> None:
    """The 120 s before a second try, the hold read before it."""
    if held():
        raise End("held")
    time.sleep(120)


def listing(item: str, held=never) -> list[dict] | str:
    """An item's files, or the 4xx (not 429) it answered twice, 120 s apart; a 429, an outage
    or the hold raises End, the hold read before each request."""
    for again in (True, False):
        if held():
            raise End("held")
        try:
            return get(f"https://archive.org/metadata/usenet-{item}/files").get("result", [])
        except FAILED as exc:
            why = failure(exc)
        if isinstance(why, End) and why.code == "429":
            raise why
        if again:
            pause(held)
    if isinstance(why, End):
        raise why
    return why


def items(cache: Path, held=never) -> list[dict]:
    """Every usenet-* identifier with its size, paged by the scrape cursor, cached whole, the
    hold read before each page."""
    if not cache.exists():
        out, cursor = [], None
        while True:
            if held():
                raise End("held")
            q = {"q": "identifier:usenet-*", "fields": "identifier,item_size", "count": 10000}
            page = get(
                "https://archive.org/services/search/v1/scrape?"
                + urllib.parse.urlencode(q | ({"cursor": cursor} if cursor else {}))
            )
            out += page["items"]
            cursor = page.get("cursor")
            if not cursor:
                break
            time.sleep(2)
        part = cache.with_name(cache.name + ".part")
        part.write_text(json.dumps(out))
        os.replace(part, cache)
    return json.loads(cache.read_text())


def unread(work: Path, read: list[str], held=never) -> list[str]:
    """Items with a size that are neither a read group nor a parent of one."""
    seen = {".".join(g.split(".")[: i + 1]) for g in read for i in range(g.count(".") + 1)}
    return [
        x["identifier"][7:]
        for x in items(work / "items.json", held)
        if x.get("item_size") and x["identifier"][7:] not in seen
    ]


def fetch(url: str, dst: Path, size: int, held=never) -> str:
    """ "200" once the file came whole, else the code (not 429, no outage) it answered twice,
    120 s apart, "size" for a whole transfer of the wrong size;
    a 429, an outage or the hold raises End, the hold read before each request and while it
    waits above the collectors' floor (`ark.disk`). The file is kept only when it came whole."""
    for again in (True, False):
        while below_floor(dst.parent, 2 * size):
            if held():
                raise End("held")
            time.sleep(60)
        if held():
            raise End("held")
        w = "%{http_code} %header{retry-after}"
        r = subprocess.run(
            [*CURL, "-A", UA, "-o", dst, "-w", w, url], capture_output=True, text=True
        )
        code, _, retry = r.stdout.strip().partition(" ")
        if code == "200" and (r.returncode or not dst.exists()):
            code = "cut"
        elif code == "200" and dst.stat().st_size != size:
            code = "size"
        if code == "200":
            return code
        dst.unlink(missing_ok=True)
        if code == "429":
            raise End(code, seconds(retry))
        if again:
            pause(held)
    if outage(code):
        raise End(code)
    return code


def build(pool: Path, out: Path) -> int:
    """The extractor's exit code over every zip in `pool`."""
    cmd = ["nice", sys.executable, BUILD, pool, out, "1"]
    return subprocess.run(cmd, capture_output=True).returncode


def write_items(shards: list[Path], path: Path) -> None:
    """{host, year} items from header journals, through the ingest's own reader."""
    with open(path, "w") as fh:
        for shard in shards:
            for host, _parent, year, _value, _url in usenet_item_rows(
                shard, Counter(), USENET_HEADER_FAMILY
            ):
                fh.write(json.dumps({"host": host, "year": year}) + "\n")


def price(work: Path, out: Path) -> float:
    """Candidate EE of one extract's journals against the price snapshot, nan when unpriced;
    a snapshot that cannot be read (exit 2: no manifest, or one mid-restage) is an outage."""
    path = work / "batch.items.jsonl"
    write_items(sorted(out.glob("*.jsonl.gz")), path)
    ark = Path(sys.executable).with_name("ark")
    cmd = ["nice", ark, "price-snapshot", "--snapshot", SNAPSHOT, "--items", path]
    cmd += ["--track", "candidate", "--out", work / "batch.c.json"]
    if (rc := subprocess.run(cmd, capture_output=True).returncode) == 2:
        raise End("snapshot")
    if rc:
        return float("nan")
    return float(json.loads((work / "batch.c.json").read_text())["ee"])


def main(work: Path, seen_path: Path, buckets: dict[str, set[str]]) -> None:
    pool = work / "pool"
    pool.mkdir(parents=True, exist_ok=True)
    todo_all = unread(work, json.loads(seen_path.read_text()))
    rng = random.Random(20261104)
    with open(work / "log.tsv", "a") as log:
        for bucket, tops in buckets.items():
            todo = [i for i in todo_all if i.split(".")[0] in tops]
            rng.shuffle(todo)
            budget = 4e8
            for item in todo:
                files = get(f"https://archive.org/metadata/usenet-{item}/files").get("result", [])
                files = [
                    f
                    for f in files
                    if f["name"].endswith(".mbox.zip") and 1e6 <= int(f.get("size", 0)) <= 3e8
                ]
                rng.shuffle(files)
                for f in files[:3]:
                    if budget <= 0:
                        break
                    size, zip_path = int(f["size"]), pool / f["name"]
                    t0 = time.time()
                    url = f"https://archive.org/download/usenet-{item}/{urllib.parse.quote(f['name'])}"
                    try:
                        code = fetch(url, zip_path, size)
                    except End as e:
                        code = e.code
                    t1 = time.time()
                    if code != "200":
                        print(
                            bucket, item, f["name"], f"http {code}", sep="\t", file=log, flush=True
                        )
                        if code == "429":
                            return
                        continue
                    out = work / "out" / bucket / f["name"].removesuffix(".mbox.zip")
                    built = build(pool, out)
                    zip_path.unlink()
                    if not built:  # a failed extract is logged, not charged
                        budget -= size
                    print(
                        bucket,
                        item,
                        f["name"],
                        size if not built else f"build {built}",
                        round(t1 - t0, 1),
                        round(time.time() - t1, 1),
                        sep="\t",
                        file=log,
                        flush=True,
                    )
                    time.sleep(1)
                if budget <= 0:
                    break
            write_items(
                sorted((work / "out" / bucket).glob("*/*.jsonl.gz")), work / f"{bucket}.items.jsonl"
            )


if __name__ == "__main__":
    main(
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        {b: set(t.split(",")) for b, t in (a.split("=") for a in sys.argv[3:])},
    )
