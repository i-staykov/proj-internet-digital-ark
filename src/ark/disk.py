"""Free space and log size, stdlib only: the CDX lanes load this file by path under bare python3.

The bank's floor is ARK_FREE_SPACE_GIB (50) and its write budget ARK_WRITE_BUDGET_GIB (20), the
budget never under the store's own size: an ingest or export refuses under their sum (`space`),
and the tick checks it every hour. A collector (the CDX lanes, the End of Term, HTTP Archive and
crawl-list readers, the header lane) stops under that sum plus EXPORT_DIP_GIB (`below_floor`),
so none eats the room the bank's own export dips into. A writer that appends for weeks keeps its
log under LOG_LIMIT with `trim`, in place, so a shell's `>>` or an open handle keeps writing.
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

STORE = Path("data/ark.duckdb")
GIB = 1024**3
# Headroom above the guard under which a write says so before it refuses.
WARN_GIB = 50
# The full export's free-space dip: unmeasured, so 0, until the ship's full export appends it to
# data/logs/export_dip.tsv (`watch`).
EXPORT_DIP_GIB = 0.0
LOG_LIMIT = 50 * 2**20
LOG_KEEP = 25 * 2**20


def settings() -> tuple[float, float]:
    """The floor and the write budget in GiB; a setting not finite and positive is a ValueError."""
    floor = float(os.environ.get("ARK_FREE_SPACE_GIB", "50"))
    budget = float(os.environ.get("ARK_WRITE_BUDGET_GIB", "20"))
    if not all(math.isfinite(n) and n > 0 for n in (floor, budget)):
        raise ValueError("space settings must be finite positive GiB values")
    return floor, budget


def free(path: Path) -> int:
    """Free bytes on the filesystem that holds `path`, or its nearest existing parent."""
    while not path.exists():
        path = path.parent
    return shutil.disk_usage(path).free


def required(root: Path) -> tuple[float, int]:
    """The floor in GiB and the write budget in bytes, never under the store's own size."""
    floor, budget = settings()
    store = root / STORE
    return floor, max(int(budget * GIB), store.stat().st_size if store.exists() else 0)


def space(*, root: Path = Path(".")) -> tuple[int, list[str]]:
    """Require the free-space floor plus a write budget on both destination filesystems."""
    try:
        floor, budget_bytes = required(root)
        required_bytes = int(floor * GIB) + budget_bytes
        lines = []
        for destination in (root / "data", root / "output"):
            have = free(destination)
            lines.append(
                f"space {destination.name}: {have / GIB:.1f} GiB free, "
                f"need {required_bytes / GIB:.1f} GiB "
                f"({floor:g} floor + {budget_bytes / GIB:.1f} write budget)"
            )
            if have < required_bytes:
                return 2, [
                    *lines,
                    "REFUSED: insufficient free space; no ingest or export started. "
                    "Use verified off-site cleanup or increase capacity.",
                ]
            if have < required_bytes + int(WARN_GIB * GIB):
                lines.append(
                    f"WARNING: within {WARN_GIB} GiB of the guard; "
                    "`just prune --disk` lists what can go"
                )
        return 0, lines
    except (OSError, ValueError, OverflowError) as exc:
        return 2, [f"REFUSED: cannot establish free space: {exc}"]


def collector_floor(root: Path = Path(".")) -> int:
    """The bytes a collector leaves free: what `space` requires of `root`, plus the dip."""
    floor, budget_bytes = required(root)
    return int((floor + EXPORT_DIP_GIB) * GIB) + budget_bytes


def below_floor(path: Path, more: int = 0, *, root: Path = Path(".")) -> str:
    """Why a collector writing `more` bytes at `path` must wait, or "" when it may write."""
    have, floor = free(path), collector_floor(root) + more
    if have >= floor:
        return ""
    return f"{have / GIB:.1f} GiB free, under the collectors' floor of {floor / GIB:.1f}"


def trim(path: Path, limit: int = LOG_LIMIT, keep: int = LOG_KEEP) -> bool:
    """Cut a log over `limit` bytes to its last whole lines within `keep`, in place."""
    try:
        if path.stat().st_size <= limit:
            return False
        with open(path, "r+b") as fh:
            fh.seek(-keep, os.SEEK_END)
            tail = fh.read()
            tail = tail[tail.index(b"\n") + 1 :] if b"\n" in tail else tail
            fh.seek(0)
            fh.write(tail)
            fh.truncate()
    except OSError:
        return False
    return True


def watch(cmd: list[str], path: Path, every: float = 1.0) -> tuple[int, int, int]:
    """Run `cmd`, reading free space at `path` every `every` s: its exit, the start, the least."""
    start = least = free(path)
    proc = subprocess.Popen(cmd)
    while proc.poll() is None:
        least = min(least, free(path))
        time.sleep(every)
    return proc.returncode, start, min(least, free(path))


if __name__ == "__main__":
    # python3 src/ark/disk.py LOG CMD...: run CMD, append its free-space dip to LOG, exit as CMD.
    log, cmd = Path(sys.argv[1]), sys.argv[2:]
    rc, start, least = watch(cmd, log.parent)
    when = time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime())
    try:  # the export's exit wins over a log that cannot be written
        with open(log, "a") as fh:
            fh.write(
                f"{when}\t{start / GIB:.2f}\t{least / GIB:.2f}\t{(start - least) / GIB:.2f}"
                f"\t{rc}\t{' '.join(cmd)}\n"
            )
    except OSError as exc:
        print(f"export dip not logged: {exc}", file=sys.stderr)
    sys.exit(rc)
