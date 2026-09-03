"""Re-emit the NYPW TimeMap parts at hostname grain (fleet hypothesis nypw_hostgrain).

The parts are Wayback CDX rows: `<requested> <urlkey> <timestamp14> <original> ...`.
The registrable ingest collapsed the original URL's host; the hostname unit accepted
on 2026-09-01 makes the host itself the record. This converts each part into the
`{url, timestamp}` journal shape `ark ingest-hostnames` reads, one output journal per
part so the ingest ledger stays idempotent per part.

    uv run python scripts/sources/nypw/nypw_hostgrain.py
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "data/raw/nypw_timemaps"
OUT = REPO / "data/raw/nypw_hostgrain"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for part in sorted(SRC.glob("*.cdx.gz")):
        dest = OUT / (part.name.replace(".cdx.gz", "") + "_hostgrain.jsonl.gz")
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
