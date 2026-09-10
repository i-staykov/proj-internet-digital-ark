"""Measure what a parent costs per host, from the journals the collectors already wrote.

`rank_platform_parents.py` divides a parent's headroom by `data/raw/cdx/rows_per_host.tsv`,
capture rows per distinct host, because a CDX page costs the same whatever it returns and
only distinct (host, year) pairs are records. That divisor is the difference between a
queue ordered by value per request and one ordered by value alone.

**The table it reads was built once, by hand, and covered 339 parents.** By 2026-09-10 the
collectors had written 5,200 journals over 3,571 parents, so the divisor was live for 9% of
the measured queue and every other parent fell through to the unmeasured fallback. That is
not a neutral gap: the fallback is the CHEAPEST value the ratio can take, so an unasked
parent outranks a measured one on identical headroom, and the head of the queue filled with
parents whose cost nobody had checked. Measured across the 3,001 parents with more than
50 KB fetched, banked records per megabyte span 253x between the tenth and ninetieth
percentile, so this is most of what separates a good hour from a bad one.

The parent is read from the journal's own name, which the sweep loop writes as the parent
with every `.` replaced by `_`. A hostname label cannot contain `_`, so the reverse is
unambiguous.

Hosts are counted with `awk` over one decompressed stream per parent rather than in Python.
Both are one pass, but the whole corpus is about 300M capture rows and the difference is
minutes against an hour. Memory is bounded by the widest single parent rather than by the
corpus, which matters on a laptop that also holds two collectors and a fold loop.

    uv run python scripts/engines/build_rows_per_host.py
    uv run python scripts/engines/build_rows_per_host.py --max-age-hours 6   # skip if fresh
"""

from __future__ import annotations

import argparse
import re
import statistics
import subprocess
import time
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JOURNALS = REPO / "data/raw/cdx_suffix"
OUT = REPO / "data/raw/cdx/rows_per_host.tsv"

# `suffix_<parent with dots as underscores>_<UTC stamp>.jsonl.gz`
JOURNAL = re.compile(r"^suffix_(?P<safe>.+)_\d{8}T\d{6}Z\.jsonl\.gz$")

# One pass: count every line, and keep the set of hosts seen. The url field is the first
# quoted value on the line, so the host is the run after `://` up to the next `/` or `"`.
# A malformed line contributes to rows and not to hosts, which is the honest reading: it
# was fetched and it named nothing.
AWK = r"""
    match($0, /"url": "[a-zA-Z]+:\/\/[^\/"]+/) {
        h = substr($0, RSTART + 9, RLENGTH - 9)
        sub(/^[a-zA-Z]+:\/\//, "", h)
        sub(/:.*$/, "", h)
        seen[tolower(h)] = 1
    }
    END { print NR, length(seen) }
"""


def parents_and_journals() -> dict[str, list[Path]]:
    by_parent: dict[str, list[Path]] = defaultdict(list)
    for path in JOURNALS.glob("suffix_*.jsonl.gz"):
        m = JOURNAL.match(path.name)
        if m:
            by_parent[m.group("safe").replace("_", ".")].append(path)
    return by_parent


def measure(files: list[Path]) -> tuple[int, int]:
    """Capture rows and distinct hosts across one parent's journals. A torn tail is what
    `gzip -cd` already gives up to, so a non-zero exit still carries a usable count."""
    gz = subprocess.Popen(
        ["gzip", "-cd", *[str(f) for f in files]], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    out = subprocess.run(["awk", AWK], stdin=gz.stdout, capture_output=True, text=True)
    if gz.stdout is not None:
        gz.stdout.close()
    gz.wait()
    parts = out.stdout.split()
    if len(parts) != 2:
        return 0, 0
    return int(parts[0]), int(parts[1])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--max-age-hours",
        type=float,
        default=None,
        help="do nothing when the table is younger than this, so a refill can call it blind",
    )
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    if args.max_age_hours is not None and args.out.is_file():
        age = (time.time() - args.out.stat().st_mtime) / 3600
        if age < args.max_age_hours:
            print(f"{args.out} is {age:.1f}h old, under {args.max_age_hours}h, leaving it")
            return 0

    by_parent = parents_and_journals()
    if not by_parent:
        print(f"no journals under {JOURNALS}, nothing to measure")
        return 1

    rows_out: list[tuple[str, int, int, float]] = []
    for i, (parent, files) in enumerate(sorted(by_parent.items()), 1):
        rows, hosts = measure(files)
        # A parent that returned nothing has no measured cost. Writing 0 hosts as a ratio
        # would be a division by zero here and a claim of infinite cost downstream, and the
        # sweep loop already routes a silent parent to its own retry list.
        if rows and hosts:
            rows_out.append((parent, rows, hosts, rows / hosts))
        if i % 500 == 0:
            print(f"  {i:,}/{len(by_parent):,} parents", flush=True)

    ratios = [r for _, _, _, r in rows_out]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as fh:
        fh.write("# parent\trows\tdistinct_hosts\trows_per_host\n")
        for parent, rows, hosts, ratio in sorted(rows_out):
            fh.write(f"{parent}\t{rows}\t{hosts}\t{ratio:.2f}\n")

    print(
        f"{len(rows_out):,} parents measured over {sum(r for _, r, _, _ in rows_out):,} capture "
        f"rows -> {args.out}"
    )
    if ratios:
        ordered = sorted(ratios)
        print(
            f"rows per host: median {statistics.median(ratios):.2f}, "
            f"p10 {ordered[len(ordered) // 10]:.2f}, p90 {ordered[len(ordered) * 9 // 10]:.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
