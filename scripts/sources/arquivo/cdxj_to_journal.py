"""Turn Arquivo.pt's `IA.cdxj` into `{url, timestamp}` journals for the hostname ingest.

**What dates a record here.** The 14-digit capture timestamp that CDXJ carries between the SURT
key and the JSON body, written by the crawler at capture time. `cdx_timestamp`, the same unit the
domain-wide sweeps use, and the same field `arquivo_ia` was already ingested on at registrable
grain (14,819,170 record rows in the ledger).

**Two traps this file sets, both measured on 2026-09-08.**

Its FIRST block is written differently from the rest: the `PT-HISTORICAL-EMBEDS-*` group emits a
bare `{...}` object with no SURT and no timestamp, and its only 14-digit token is the ARC's own
write date, `20100830000000`, which is out of window and would date nothing. Sampling the head of
the file therefore says the corpus cannot date a host, and sampling the middle says it can. Read
the middle. A line without a parseable timestamp is skipped and counted, never guessed at.

The file also carries about 4.27M NUL bytes, concentrated near the start. They are in the published
artifact, not an artefact of the transfer, which two independent downloads confirmed. So NULs are
stripped per line and cannot be used to detect a bad transfer; the fetch script verifies byte
ranges instead.

    uv run python scripts/sources/arquivo/cdxj_to_journal.py data/raw/arquivo/IA.cdxj \\
        --out data/raw/arquivo_hostgrain --shard-lines 4000000
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
from pathlib import Path

WINDOW = range(1996, 2002)
# `<surt> <14 digits> {json}`; the JSON is taken whole so a URL containing a space cannot split it.
LINE = re.compile(rb"^\S+\s+(\d{14})\s+(\{.*\})\s*$")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cdxj", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--shard-lines", type=int, default=4_000_000)
    ap.add_argument(
        "--status",
        default="200",
        help="keep only this HTTP status; a capture that did not serve is not evidence",
    )
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    kept = skipped_no_stamp = skipped_window = skipped_status = broken = 0
    shard = 0
    handle = None
    with args.cdxj.open("rb") as source:
        for raw in source:
            raw = raw.replace(b"\x00", b"").strip()
            if not raw:
                continue
            match = LINE.match(raw)
            if match is None:
                # The head block's bare objects land here, and so does any line a 2 GB part
                # boundary cut in half. Both are counted rather than repaired.
                skipped_no_stamp += 1
                continue
            stamp = match.group(1).decode()
            if int(stamp[:4]) not in WINDOW:
                skipped_window += 1
                continue
            try:
                row = json.loads(match.group(2))
            except ValueError:
                broken += 1
                continue
            if args.status and str(row.get("status")) != args.status:
                skipped_status += 1
                continue
            url = row.get("url")
            if not url:
                broken += 1
                continue
            if handle is None or kept % args.shard_lines == 0:
                if handle is not None:
                    handle.close()
                handle = gzip.open(args.out / f"arquivo_ia_{shard:04d}.jsonl.gz", "wt")
                shard += 1
            handle.write(json.dumps({"url": url, "timestamp": stamp}) + "\n")
            kept += 1
    if handle is not None:
        handle.close()

    print(
        f"kept {kept:,} in-window captures into {shard} shard(s); "
        f"skipped {skipped_window:,} out of window, {skipped_status:,} on status, "
        f"{skipped_no_stamp:,} with no parseable timestamp, {broken:,} unparseable"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
