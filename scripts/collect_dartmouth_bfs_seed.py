"""Fetch the three CDX indexes of BFS level 0, which is the whole of the useful source.

IA ran a breadth-first crawl seeded with URLs pulled from SEC 10-K filings and deposited
the result as `Dartmouth_10KwebURLs_GWB-20180911224740_BFS_4-lvls`, 204 items and 2,064 GB
under `CorporationWebsitesCollection`. Almost none of that is worth downloading.

**Level 0 is the seed layer and it is three files and 13.6 MB.** Measured whole rather than
sampled: 311,543 rows, 58,035 in-window HTTP 200s, 57,878 distinct pairs, 55,418 already
held, **2,460 net-new pairs worth 1,419.9 equivalent-English**, at 104.7 EE per MB.

**Why not the rest.** Levels 2 and 3 are 92 of the 102 ARC items, and three indexes there
measured 0.00, 0.00 and 0.59 EE per MB; one level-1 index measured 1.93. So the family's
density is concentrated at the seed and a rate sampled from the shallow files overstates
the whole by roughly six-fold. Separately, the 102 `_warc` items hold 2012-2019 only, with
zero in-window rows, so half the collection is dead weight by construction.

**Two access facts, both of which cost a false negative before they were understood.**
The item-level merged `.cdx.gz` and `.cdx.idx` return **HTTP 401** while the per-file
`.arc.os.cdx.gz` returns **200**: the restriction is applied to the merged object, not to
the parts, and the item's `access-restricted-item: true` predicts nothing either way. And
`archive.org` item downloads are a different service from `web.archive.org` replay, so this
does not spend the project's two archive-client slots.

    uv run python scripts/collect_dartmouth_bfs_seed.py
    uv run ark ingest dartmouth_bfs_seed data/raw/dartmouth_bfs/*.cdx.gz
"""

import argparse
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://archive.org/download"
STEM = "Dartmouth_10KwebURLs_GWB-20180911224740"
# (item, file). Level 0 is two numbered ARCs plus a patch item that holds the
# captures the first pass missed.
FILES = [
    (f"{STEM}_BFS-lvl-0-00000-00001_arc", f"{STEM}_BFS-lvl-0-00000.arc.os.cdx.gz"),
    (f"{STEM}_BFS-lvl-0-00000-00001_arc", f"{STEM}_BFS-lvl-0-00001.arc.os.cdx.gz"),
    (f"{STEM}_BFS-lvl-0-patch-00000-00000_arc", f"{STEM}_BFS-lvl-0-patch-00000.arc.os.cdx.gz"),
]
OUT = Path("data/raw/dartmouth_bfs")
UA = "internet-digital-ark/1.0 (research; ivaylo.staykov@student.hpi.uni-potsdam.de)"


def fetch(url: str, tries: int, pause: float) -> bytes | None:
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=300) as response:
                body = response.read()
            if body:
                return body
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        if attempt < tries:
            time.sleep(pause)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tries", type=int, default=5, help="attempts per file")
    ap.add_argument("--pause", type=float, default=10.0, help="seconds between attempts")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    got = missing = skipped = 0
    for item, name in FILES:
        path = OUT / name
        if path.exists() and path.stat().st_size:
            skipped += 1
            continue
        body = fetch(f"{BASE}/{item}/{name}", args.tries, args.pause)
        if body is None:
            print(f"{name}: no bytes after {args.tries} attempts")
            missing += 1
            continue
        path.write_bytes(body)
        print(f"{name}: {len(body):,} bytes")
        got += 1

    print(f"fetched {got}, already held {skipped}, unreachable {missing}, into {OUT}")
    # A missing file is a smaller source, not a wrong one, so this is not an error exit.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
