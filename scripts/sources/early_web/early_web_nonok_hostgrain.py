"""Re-emit the Early Web CDX rows other than 200 at hostname grain, each with its status.

`early_web_hostgrain.py` keeps `status == "200"`. This writes the other two lanes, one
journal per part, every row carrying its capture status:

- `--redirects-only`, the `early_web_3xx` lane: 3xx rows. A redirect is the exact host's
  server answering for that name, so it dates the host's year as a 200 does.
- the default `early_web_nonok` lane: 4xx and 5xx rows, for the candidate track only. The
  `nonok` in the name tells the ingest the whole journal is error captures.

A row with no three-digit status is dropped.

    uv run python scripts/sources/early_web/early_web_nonok_hostgrain.py
    uv run python scripts/sources/early_web/early_web_nonok_hostgrain.py --redirects-only
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "data/raw/early_web"
YEARS = range(1996, 2002)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--redirects-only", action="store_true", help="the 3xx lane")
    ap.add_argument("--out", type=Path, help="output directory; defaults by lane")
    args = ap.parse_args()

    lane = "early_web_3xx" if args.redirects_only else "early_web_nonok"
    keep = "3" if args.redirects_only else "45"
    out_dir = args.out or REPO / f"data/raw/{lane}_hostgrain"
    # still the ingest's `early_web_` family, under names its ledger has not read
    prefix = f"{lane}_status_"
    out_dir.mkdir(parents=True, exist_ok=True)
    totals = {"rows": 0, "kept": 0}
    for part in sorted(SRC.glob("*.cdx.gz")):
        dest = out_dir / (prefix + part.name.replace(".cdx.gz", "") + "_hostgrain.jsonl.gz")
        if dest.exists():
            continue
        rows = kept = 0
        with gzip.open(part, "rt", errors="replace") as fh, gzip.open(dest, "wt") as out:
            for line in fh:
                rows += 1
                fields = line.split(" ")
                if len(fields) < 5 or fields[0].startswith("CDX"):
                    continue
                ts, original, status = fields[1], fields[2], fields[4]
                if len(ts) != 14 or not ts.isdigit() or int(ts[:4]) not in YEARS:
                    continue
                if len(status) != 3 or not status.isdigit() or status[0] not in keep:
                    continue
                out.write(json.dumps({"url": original, "timestamp": ts, "status": status}) + "\n")
                kept += 1
        totals["rows"] += rows
        totals["kept"] += kept
    print(f"{totals['rows']:,} rows -> {totals['kept']:,} capture lines in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
