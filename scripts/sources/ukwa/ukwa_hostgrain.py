"""Re-emit the UKWA Geoindex in-window extracts at hostname grain.

The rows are `<14-digit timestamp>/<URL>` and a tab and a postcode, so each row
carries its own IA capture stamp next to the URL it captured. The registrable
ingest sent that URL through `to_registrable` and threw the host away
(`scripts/sources/ukwa/ukwa_geoindex_price.py:41-44`); the hostname unit accepted
on 2026-09-01 makes the host itself the record. This writes the `{url, timestamp}`
journal shape the hostname pricer and ingest read, one output journal per input
member so the ingest ledger stays idempotent per member.

    uv run python scripts/sources/ukwa/ukwa_hostgrain.py
    uv run python scripts/sources/ukwa/ukwa_hostgrain.py --limit-files 2
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "data/raw/ukwa"
OUT = REPO / "data/raw/ukwa_hostgrain"


def convert(member: Path, dest: Path) -> tuple[int, int]:
    """One member into one journal; returns (rows read, capture lines written)."""
    rows = kept = 0
    with gzip.open(member, "rt", errors="replace") as fh, gzip.open(dest, "wt") as out:
        for line in fh:
            rows += 1
            head = line.split("\t", 1)[0]
            ts, _, url = head.partition("/")
            if len(ts) != 14 or not ts.isdigit() or not url:
                continue
            out.write(json.dumps({"url": url, "timestamp": ts}) + "\n")
            kept += 1
    return rows, kept


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit-files", type=int, help="convert only the first N members")
    args = ap.parse_args()

    members = sorted(SRC.glob("geoindex_postcode-*_inwindow.tsv.gz"))
    if args.limit_files:
        members = members[: args.limit_files]
    OUT.mkdir(parents=True, exist_ok=True)
    for member in members:
        stem = member.name.replace(".tsv.gz", "")
        dest = OUT / f"ukwa_{stem}_hostgrain.jsonl.gz"
        if dest.exists():
            print(f"{dest.name}: exists, skipping")
            continue
        rows, kept = convert(member, dest)
        print(f"{member.name}: {rows:,} rows -> {kept:,} capture lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
