"""Re-emit IA's Early Web CDX files at hostname grain (fleet finding early_web_cdx_hostname_grain).

`ark ingest early_web` banks every capture at its registrable; the hostname unit makes the
captured host itself the record. This converts each classic CDX part (`surt timestamp
original mime status ...`) into the `{url, timestamp, status}` journal `ark ingest-hostnames`
reads, keeping HTTP 200 rows exactly as the registrable ingest does. The 3xx and the error
rows are `early_web_nonok_hostgrain.py`'s lanes. One journal per part keeps the ingest ledger
idempotent per part.

    uv run python scripts/sources/early_web/early_web_hostgrain.py
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "data/raw/early_web"
OUT = REPO / "data/raw/early_web_hostgrain"
# still the ingest's `early_web_` family, under names its ledger has not read
PREFIX = "early_web_status_"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for part in sorted(SRC.glob("*.cdx.gz")):
        dest = OUT / (PREFIX + part.name.replace(".cdx.gz", "") + "_hostgrain.jsonl.gz")
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
                    row = {"url": original, "timestamp": ts, "status": status}
                    out.write(json.dumps(row) + "\n")
                    kept += 1
        print(f"{part.name}: {rows:,} rows -> {kept:,} capture lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
