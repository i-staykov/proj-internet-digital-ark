"""Re-emit the gap engine's own CDX answers at hostname grain.

**Why this exists, and it is a lesson rather than a converter.** The gap engine asked the
archive `fl=timestamp` and kept `{domain, status, years}`, so the hostname the archive had
just named was discarded: 1,164 journals and 1,108,452 dated pairs of querying, none of it
re-readable one level down. Since ADR-009 a `www.` host is a record, so every one of those
rows was a record we had paid a request for and thrown away. `ark.cdx` now asks for
`timestamp,original` and records a `hosts` map, and this turns that map into the
`{url, timestamp}` journal `ark ingest-hostnames` already reads.

Journals written before 2026-09-04 carry no `hosts` key and yield nothing here. That is not a
bug to work around: the information is not in them, and no amount of parsing will recover it.

    uv run python scripts/engines/cdx_gap_hostgrain.py [--src DIR] [--out DIR]
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def convert(src: Path, out: Path) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    totals = {"journals": 0, "records": 0, "hosts": 0, "without_hosts": 0}
    for path in sorted(src.glob("cdx_*.jsonl.gz")):
        dest = out / ("cdx_gap_" + path.name[len("cdx_") :])
        if dest.exists():
            continue
        rows = 0
        # A journal a collector is still writing, or one a deadline killed mid-flush, raises
        # EOFError partway. What was read is real, so keep it and let the next pass see the
        # rest; the `.part` convention covers live files but not abandoned ones.
        with gzip.open(path, "rt", errors="replace") as fh, gzip.open(dest, "wt") as sink:
            try:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    totals["records"] += 1
                    hosts = record.get("hosts")
                    if not isinstance(hosts, dict) or not hosts:
                        totals["without_hosts"] += 1
                        continue
                    for host, stamp in sorted(hosts.items()):
                        sink.write(
                            json.dumps({"url": f"http://{host}/", "timestamp": stamp}) + "\n"
                        )
                        rows += 1
            except (EOFError, OSError):
                totals["truncated"] = totals.get("truncated", 0) + 1
        totals["journals"] += 1
        totals["hosts"] += rows
        if rows == 0:
            dest.unlink(missing_ok=True)
    return totals


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, default=REPO / "data/raw/cdx")
    ap.add_argument("--out", type=Path, default=REPO / "data/raw/cdx_gap_hostgrain")
    args = ap.parse_args()
    totals = convert(args.src, args.out)
    print(
        f"{totals['journals']:,} journals, {totals['records']:,} records, "
        f"{totals['hosts']:,} host rows written, "
        f"{totals['without_hosts']:,} records carried no hosts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
