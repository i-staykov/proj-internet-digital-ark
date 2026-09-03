"""Re-emit the Early Web CDX rows the 200-only ingests threw away, at hostname grain.

`early_web_hostgrain.py` keeps `status == "200"`, exactly as the registrable ingest did,
and 172,975 in-window rows of the 224 parts are something else. The ruling that makes them
evidence is already banked: `nypw_timemaps_nonok / cdx_timestamp` is `Decision: master`
since 2026-09-01, on the ground that **a three-digit status means the name resolved, a TCP
connection was accepted and a server answered at the stamped instant**, so a 302 dates the
year exactly as a 200 does. Nobody had applied that ruling to this corpus.

`--redirects-only` keeps 3xx alone. That is the conservative reading of the hostname
purpose rule of 2026-09-02, which asks the observation to show the host serving web
content: a redirect is unambiguously a live server answering for that name, while a 401 or
a 403 is a server refusing. Both lanes are priced before either is banked.

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
    ap.add_argument("--redirects-only", action="store_true", help="3xx alone, no 4xx or 5xx")
    ap.add_argument("--out", type=Path, help="output directory; defaults by lane")
    args = ap.parse_args()

    lane = "early_web_3xx" if args.redirects_only else "early_web_nonok"
    out_dir = args.out or REPO / f"data/raw/{lane}_hostgrain"
    prefix = f"{lane}_"
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
                if status == "200" or not status.isdigit():
                    continue
                if args.redirects_only and not status.startswith("3"):
                    continue
                out.write(json.dumps({"url": original, "timestamp": ts}) + "\n")
                kept += 1
        totals["rows"] += rows
        totals["kept"] += kept
    print(f"{totals['rows']:,} rows -> {totals['kept']:,} capture lines in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
