"""Re-emit IA's Early Web CDX files at hostname grain (fleet finding early_web_cdx_hostname_grain).

`ark ingest early_web` collapsed every capture to its registrable in 2026-07. The hostname
unit accepted on 2026-09-01 makes the captured host itself the record, so this converts each
classic CDX part (`surt timestamp original mime status ...`) into the `{url, timestamp}`
journal `ark ingest-hostnames` reads, keeping HTTP 200 rows exactly as the registrable
ingest did. One journal per part keeps the ingest ledger idempotent per part.

    uv run python scripts/sources/early_web/early_web_hostgrain.py
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "data/raw/early_web"
OUT = REPO / "data/raw/early_web_hostgrain"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for part in sorted(SRC.glob("*.cdx.gz")):
        dest = OUT / ("early_web_" + part.name.replace(".cdx.gz", "") + "_hostgrain.jsonl.gz")
        if dest.exists():
            print(f"{dest.name}: exists, skipping")
            continue
        rows = kept = 0
        with gzip.open(part, "rt", errors="replace") as fh, gzip.open(dest, "wt") as out:
            for line in fh:
                rows += 1
                fields = line.split(" ")
                if len(fields) < 5 or fields[0].startswith("CDX"):
                    continue
                ts, original, status = fields[1], fields[2], fields[4]
                if len(ts) == 14 and ts.isdigit() and status == "200":
                    out.write(json.dumps({"url": original, "timestamp": ts}) + "\n")
                    kept += 1
        print(f"{part.name}: {rows:,} rows -> {kept:,} capture lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
