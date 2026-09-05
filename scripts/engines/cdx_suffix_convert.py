"""Convert suffix-sweep journals into the `cdx_snapshot` journal format.

**Why convert rather than add a source.** `cdx_snapshot / cdx_timestamp` is
already approved master and its parser, invariants and provenance lineage are
tested. The suffix sweep produces the same *evidence*, an Internet Archive capture
timestamp for a domain, in a different *shape*: one row per capture rather than
one row per domain with a year list. So the right move is a converter, not a new
`SourceSpec`, which would duplicate a reviewed decision for no gain.

The conversion is a group-by: collapse many capture rows for one domain into the
set of in-window years, which is exactly what `ark cdx` writes.

A journal still being written has no gzip end-of-stream marker, so a truncated
tail is normal and everything before it is valid.

    uv run python scripts/engines/cdx_suffix_convert.py --tag 20260821
"""

import argparse
import glob
import gzip
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "src")
from ark.canonical import to_registrable  # noqa: E402

OUT = Path("data/raw/cdx")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", default=time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    ap.add_argument("--glob", default="data/raw/cdx_suffix/*.jsonl.gz")
    ap.add_argument(
        "--min-interval",
        type=float,
        default=float(os.environ.get("ARK_CONVERT_INTERVAL_S", 3600)),
        help="skip if a snapshot is newer than this many seconds. 0 to always run",
    )
    args = ap.parse_args()

    # **This re-reads every journal, so it gets slower as the sweep collects.** The fold loop
    # calls it once per pass and it runs in the loop's foreground, which on 2026-09-05 meant a
    # 25-minute conversion over 636 journals blocking the hostname ingest behind it. That trade
    # is badly wrong by measurement: the hostname half was 1,007,669 EE of the round against the
    # registrable half's 44,088, and the blocked pass added six registrable records.
    #
    # Skipping a pass costs nothing, because the read is cumulative rather than incremental: the
    # next run picks up everything this one would have. So it is rate-limited instead of made
    # incremental, which would be a real change to a script two live collectors feed.
    if args.min_interval > 0:
        newest = max(
            (p.stat().st_mtime for p in OUT.glob("cdx_suffix_*.jsonl.gz")),
            default=0.0,
        )
        age = time.time() - newest
        if newest and age < args.min_interval:
            print(f"snapshot {age / 60:.0f} min old, under {args.min_interval / 60:.0f}, skipping")
            return

    years: defaultdict[str, set[int]] = defaultdict(set)
    rows = truncated = 0
    paths = sorted(glob.glob(args.glob))
    for path in paths:
        try:
            with gzip.open(path, "rt", errors="replace") as fh:
                for line in fh:
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    rows += 1
                    stamp = d.get("timestamp") or ""
                    if len(stamp) != 14 or not stamp.isdigit():
                        continue
                    year = int(stamp[:4])
                    if not (1996 <= year <= 2001):
                        continue
                    dom = to_registrable(d.get("url") or "")
                    if dom:
                        years[dom].add(year)
        except EOFError:
            truncated += 1

    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"cdx_suffix_{args.tag}.jsonl.gz"
    with gzip.open(dest, "wt") as fh:
        for dom, ys in sorted(years.items()):
            fh.write(
                json.dumps(
                    {
                        "domain": dom,
                        "status": 200,
                        "years": sorted(ys),
                        "strategy": "suffix_sweep",
                    }
                )
                + "\n"
            )

    print(f"{len(paths)} journal(s), {rows:,} capture rows, {truncated} still being written")
    print(f"  {len(years):,} domains with in-window captures -> {dest}")
    print(f"  next: uv run ark ingest cdx_snapshot {dest}")


if __name__ == "__main__":
    main()
