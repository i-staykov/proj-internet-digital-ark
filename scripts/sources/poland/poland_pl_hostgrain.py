"""Reduce the Poland .pl ccTLD extraction's item-level CDX indexes to one capture per
(host, year), the journal shape `ark ingest-hostnames` reads.

Same artifact shape and same evidence class as `usfedgov_extract_hostnames`: an
item-level CDX of an Internet Archive extraction collection, dated by field 2, the
crawler's own 14-digit capture timestamp. 36.1 million rows across the 19 indexes name
376,445 hosts, so writing every row would cost the ingest an hour to learn nothing.

**Only HTTP 200 rows inside 1996-2001 are kept, and that is deliberate**, because it is
the population the fleet priced at 158,490 net-new pairs and 16,958.4300 EE against
merged260908. Widening it here to non-200 answers would make the realised figure
incomparable with the approval, so a widening belongs in its own measured pass.

Asserts each file's byte size and sha256 against `receipts.tsv` first. A size floor is
not a content check, and a truncated index would date hosts off a half-read file.

    uv run python scripts/sources/poland/poland_pl_hostgrain.py data/raw/poland_cdx/
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data/raw/poland_hostgrain"
RECEIPTS = Path(__file__).resolve().parent / "receipts.tsv"
YEARS = range(1996, 2002)


def host_of(url: str) -> str:
    rest = url.split("://", 1)[-1]
    return rest.split("/", 1)[0].split(":", 1)[0].split("@")[-1].strip().lower().rstrip(".")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def receipts() -> dict[str, tuple[int, str]]:
    out = {}
    for line in RECEIPTS.read_text().splitlines():
        if not line.strip():
            continue
        item, size, sha = line.split("\t")
        out[f"{item}.cdx.gz"] = (int(size), sha)
    return out


def reduce_one(index: Path, expected: tuple[int, str]) -> int:
    size, sha = expected
    actual = index.stat().st_size
    if actual != size:
        print(f"{index.name}: {actual:,} B on disk, receipt says {size:,}", file=sys.stderr)
        return 2
    got = sha256_of(index)
    if got != sha:
        print(f"{index.name}: sha256 {got}, receipt says {sha}", file=sys.stderr)
        return 2
    # After the receipts, not before: a refused index must leave no directory behind to
    # suggest it was read.
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / ("poland_pl_" + index.name.replace(".cdx.gz", "") + "_hostgrain.jsonl.gz")
    # (host, year) -> (timestamp, url); the earliest 200 capture dates the pair
    best: dict[tuple[str, int], tuple[str, str]] = {}
    rows = headers = malformed = skipped = 0
    with gzip.open(index, "rt", errors="replace") as fh:
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
            year = int(ts[:4])
            if status != "200" or year not in YEARS:
                skipped += 1
                continue
            key = (host_of(original), year)
            cand = (ts, original)
            if key not in best or cand < best[key]:
                best[key] = cand
    with gzip.open(dest, "wt") as out:
        for _key, (ts, original) in sorted(best.items()):
            out.write(json.dumps({"url": original, "timestamp": ts}) + "\n")
    print(
        f"{index.name}: {rows:,} rows, {headers:,} member headers, {malformed:,} malformed, "
        f"{skipped:,} not 200-in-window -> {len(best):,} (host, year) lines in {dest.name}"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", type=Path, help="an index, or a directory of them")
    args = ap.parse_args()
    known = receipts()
    files = sorted(args.path.glob("*.cdx.gz")) if args.path.is_dir() else [args.path]
    if not files:
        print(f"{args.path}: no .cdx.gz found, nothing to reduce", file=sys.stderr)
        return 2
    bad = 0
    for index in files:
        expected = known.get(index.name)
        if expected is None:
            print(f"{index.name}: not in receipts.tsv, refusing", file=sys.stderr)
            bad += 1
            continue
        bad += 1 if reduce_one(index, expected) else 0
    return 2 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
