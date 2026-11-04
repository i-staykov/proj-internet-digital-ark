"""Seeded header-lane sample of the usenet-* items on archive.org the lane has not read, by bucket.

The group catalogue (`data/raw/usenet_catalog.json`) lists the big hierarchies only; archive.org
holds 26,352 usenet-* items. This lists them all through the scrape API, keeps an item when a
bucket names its top-level hierarchy and no group in `seen` (a JSON list of group names already
read) is it or under it, and per bucket reads about 0.4 GB of groups of 1 to 300 MB, at most
three per item, from items in seeded random order. One download at a time, `/` kept 70 GiB free,
each zip extracted by `build_usenet_header_pool.py` and deleted, a 429 ends the run. Each
bucket's journals are then written as {host, year} items through the ingest's own reader, a
`text` holding several names included, for `just price --items <workdir>/<bucket>.items.jsonl
--track candidate`. `log.tsv` keeps bytes and download and extract seconds per group.

    uv run python scripts/sources/usenet/sample_usenet_header_items.py WORKDIR SEEN.json \\
        us=ba,nyc,tx vendor=gnu,perl
"""

from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

from ark.hostnames import USENET_HEADER_FAMILY, usenet_item_rows

UA = "ark-research (header-lane measurement)"
BUILD = Path(__file__).with_name("build_usenet_header_pool.py")


def get(url: str) -> dict:
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120
    ) as r:
        return json.load(r)


def items(cache: Path) -> list[dict]:
    """Every usenet-* identifier with its size, paged by the scrape cursor, cached."""
    if not cache.exists():
        out, cursor = [], None
        while True:
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
        cache.write_text(json.dumps(out))
    return json.loads(cache.read_text())


def main(work: Path, seen_path: Path, buckets: dict[str, set[str]]) -> None:
    pool = work / "pool"
    pool.mkdir(parents=True, exist_ok=True)
    seen = {
        ".".join(g.split(".")[: i + 1])
        for g in json.loads(seen_path.read_text())
        for i in range(g.count(".") + 1)
    }
    unread = [
        x["identifier"][7:]
        for x in items(work / "items.json")
        if x.get("item_size") and x["identifier"][7:] not in seen
    ]
    rng = random.Random(20261104)
    with open(work / "log.tsv", "a") as log:
        for bucket, tops in buckets.items():
            todo = [i for i in unread if i.split(".")[0] in tops]
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
                    while shutil.disk_usage("/").free < 70 * 2**30 + 2 * size:
                        time.sleep(60)
                    t0 = time.time()
                    url = f"https://archive.org/download/usenet-{item}/{urllib.parse.quote(f['name'])}"
                    code = subprocess.run(
                        ["curl", "-sSL", "-A", UA, "-o", zip_path, "-w", "%{http_code}", url],
                        capture_output=True,
                        text=True,
                    ).stdout
                    t1 = time.time()
                    if code != "200":
                        zip_path.unlink(missing_ok=True)
                        print(
                            bucket, item, f["name"], f"http {code}", sep="\t", file=log, flush=True
                        )
                        if code == "429":
                            return
                        continue
                    out = work / "out" / bucket / f["name"].removesuffix(".mbox.zip")
                    subprocess.run(
                        ["nice", sys.executable, BUILD, pool, out, "1"], capture_output=True
                    )
                    zip_path.unlink()
                    budget -= size
                    print(
                        bucket,
                        item,
                        f["name"],
                        size,
                        round(t1 - t0, 1),
                        round(time.time() - t1, 1),
                        sep="\t",
                        file=log,
                        flush=True,
                    )
                    time.sleep(1)
                if budget <= 0:
                    break
            with open(work / f"{bucket}.items.jsonl", "w") as fh:
                for shard in sorted((work / "out" / bucket).glob("*/*.jsonl.gz")):
                    for host, _parent, year, _value, _url in usenet_item_rows(
                        shard, Counter(), USENET_HEADER_FAMILY
                    ):
                        fh.write(json.dumps({"host": host, "year": year}) + "\n")


if __name__ == "__main__":
    main(
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        {b: set(t.split(",")) for b, t in (a.split("=") for a in sys.argv[3:])},
    )
