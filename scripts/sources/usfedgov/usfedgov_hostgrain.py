"""Reduce a USFEDGOV-EXTRACT merged CDX index to one capture per host (fleet finding
usfedgov_extract_hostname_grain, admitted 2026-09-02).

The item's `<item>.cdx.gz` is a ZipNum index: concatenated gzip members whose first line
is `CDX N b a m s k r M S V g`, then one classic CDX row per capture. 48 million rows name
33,631 hosts, so writing every row into a journal would cost `ark ingest-hostnames` an hour
to learn nothing: the record is (host, year) and one capture dates it. This keeps, per
host and year, the earliest HTTP 200 capture, or the earliest capture of any status where
the host never answered 200 (a 4xx is still a dated server answer from that host), and
writes the `{url, timestamp}` journal the ingest reads. Asserts the file's byte size
against the item metadata first, because a size floor is not a content check and a
truncated fetch must not date anything.

    uv run python scripts/sources/usfedgov/usfedgov_hostgrain.py \\
        data/raw/usfedgov/USFEDGOV-EXTRACT-2001.cdx.gz
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data/raw/usfedgov_hostgrain"
# archive.org/metadata/<item> `size` for each merged index; a byte-exact match is the
# fetch check, and an unknown file is refused rather than trusted.
EXPECTED_BYTES = {
    "USFEDGOV-EXTRACT-2001.cdx.gz": 1_364_737_799,
}


def host_of(url: str) -> str:
    rest = url.split("://", 1)[-1]
    return rest.split("/", 1)[0].split(":", 1)[0].split("@")[-1].strip().lower().rstrip(".")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("index", type=Path)
    args = ap.parse_args()
    expected = EXPECTED_BYTES.get(args.index.name)
    if expected is None:
        print(f"{args.index.name}: not a known merged index, refusing", file=sys.stderr)
        return 2
    actual = args.index.stat().st_size
    if actual != expected:
        print(f"{args.index.name}: {actual:,} B on disk, item says {expected:,}", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / ("usfedgov_" + args.index.name.replace(".cdx.gz", "") + "_hostgrain.jsonl.gz")
    # (host, year) -> (rank, timestamp, url); rank 0 is a 200 answer, 1 anything else
    best: dict[tuple[str, int], tuple[int, str, str]] = {}
    rows = headers = malformed = 0
    with gzip.open(args.index, "rt", errors="replace") as fh:
        for line in fh:
            rows += 1
            if line.startswith((" CDX", "CDX")):
                headers += 1
                continue
            fields = line.split(" ")
            if len(fields) < 5 or len(fields[1]) != 14 or not fields[1].isdigit():
                malformed += 1
                continue
            ts, original, status = fields[1], fields[2], fields[4]
            key = (host_of(original), int(ts[:4]))
            cand = (0 if status == "200" else 1, ts, original)
            if key not in best or cand < best[key]:
                best[key] = cand
    with gzip.open(dest, "wt") as out:
        for _key, (_, ts, original) in sorted(best.items()):
            out.write(json.dumps({"url": original, "timestamp": ts}) + "\n")
    print(
        f"{args.index.name}: {rows:,} rows, {headers:,} member headers, {malformed:,} malformed "
        f"-> {len(best):,} (host, year) capture lines in {dest.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
