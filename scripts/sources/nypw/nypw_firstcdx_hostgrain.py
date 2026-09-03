"""Re-emit the NYPW first-capture index at hostname grain.

Same bytes and same row shape as the TimeMap parts next door
(`<requested> <urlkey> <timestamp14> <original> <mime> <status> <digest> <len>`),
one row per URL instead of one row per capture. The registrable verdict on this
index was a rejection (99.998% overlap with the IA CDX the baseline drains), and
that verdict says nothing about the hosts beneath those registrables, so this
converts the file into the `{url, timestamp}` journal shape the hostname unit
reads, one output journal per input file.

    uv run python scripts/sources/nypw/nypw_firstcdx_hostgrain.py [--limit-files N]
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "data/raw/nypw"
OUT = REPO / "data/raw/nypw_firstcdx_hostgrain"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit-files", type=int, help="convert at most this many input files")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    parts = sorted(SRC.glob("*firstcdx.gz"))
    if args.limit_files:
        parts = parts[: args.limit_files]
    for part in parts:
        dest = OUT / ("nypw_" + part.name.replace(".gz", "") + "_hostgrain.jsonl.gz")
        if dest.exists():
            print(f"{dest.name}: exists, skipping")
            continue
        rows = kept = 0
        with gzip.open(part, "rt", errors="replace") as fh, gzip.open(dest, "wt") as out:
            for line in fh:
                rows += 1
                fields = line.split(" ")
                if len(fields) < 4:
                    continue
                ts, original = fields[2], fields[3]
                if len(ts) == 14 and ts.isdigit():
                    out.write(json.dumps({"url": original, "timestamp": ts}) + "\n")
                    kept += 1
        print(f"{part.name}: {rows:,} rows -> {kept:,} capture lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
