"""Re-emit the NYPW TimeMap parts at hostname grain, each row with its capture status.

The parts are Wayback CDX rows: `<requested> <urlkey> <timestamp14> <original> <mime>
<status> ...`. The hostname unit makes the host itself the record, so this converts each
part into the `{url, timestamp, status}` journal shape `ark ingest-hostnames` reads, one
output journal per part so the ingest ledger stays idempotent per part. Every row with a
three-digit 2xx to 5xx status is kept with it: a 2xx or 3xx dates the host's year, and a
4xx or 5xx reaches the candidate track only.

    uv run python scripts/sources/nypw/nypw_hostgrain.py
"""

from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "data/raw/nypw_timemaps"
OUT = REPO / "data/raw/nypw_hostgrain"
# still the ingest's `nypw_` family, under names its ledger has not read
PREFIX = "nypw_status_"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for part in sorted(SRC.glob("*.cdx.gz")):
        stem = part.name.removeprefix("nypw_").replace(".cdx.gz", "")
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
