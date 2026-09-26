"""Re-emit the NYPW first-capture index at hostname grain, each row with its capture status.

Same bytes and same row shape as the TimeMap parts next door
(`<requested> <urlkey> <timestamp14> <original> <mime> <status> <digest> <len>`),
one row per URL instead of one row per capture. The registrable verdict on this
index was a rejection (99.998% overlap with the IA CDX the baseline drains), and
that verdict says nothing about the hosts beneath those registrables, so this
converts the file into the `{url, timestamp, status}` journal shape the hostname
unit reads, one output journal per input file. A 2xx or 3xx row dates the host's
year, a 4xx or 5xx reaches the candidate track only, and a row with no three-digit
status (a revisit record's `-`) is dropped.

    uv run python scripts/sources/nypw/nypw_firstcdx_hostgrain.py [--limit-files N]
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "data/raw/nypw"
OUT = REPO / "data/raw/nypw_firstcdx_hostgrain"
# still the ingest's `nypw_` family, under names its ledger has not read
PREFIX = "nypw_status_"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit-files", type=int, help="convert at most this many input files")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    parts = sorted(SRC.glob("*firstcdx.gz"))
    if args.limit_files:
        parts = parts[: args.limit_files]
    for part in parts:
        stem = part.name.removeprefix("nypw_").replace(".gz", "")
        dest = OUT / (PREFIX + stem + "_hostgrain.jsonl.gz")
        if dest.exists():
            print(f"{dest.name}: exists, skipping")
            continue
        seen: Counter[str] = Counter()
        with gzip.open(part, "rt", errors="replace") as fh, gzip.open(dest, "wt") as out:
            for line in fh:
                seen["rows"] += 1
                fields = line.split(" ")
                if len(fields) < 6:
                    continue
                ts, original, status = fields[2], fields[3], fields[5]
                if not (len(ts) == 14 and ts.isdigit()):
                    continue
                if not (len(status) == 3 and status.isdigit() and status[0] in "2345"):
                    seen["no_status"] += 1
                    continue
                out.write(json.dumps({"url": original, "timestamp": ts, "status": status}) + "\n")
                seen[f"{status[0]}xx"] += 1
        print(f"{part.name}: {dict(seen)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
