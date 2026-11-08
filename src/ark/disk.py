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
from pathlib import Path

STORE = Path("data/ark.duckdb")
GIB = 1024**3
# Headroom above the guard under which a write says so before it refuses.
WARN_GIB = 50
# The full export's free-space dip under the bank's floor plus its budget: laws.md "full export
# dip", measured on the VM; 0 until it is.
EXPORT_DIP_GIB = 0.0
LOG_LIMIT = 50 * 2**20
LOG_KEEP = 25 * 2**20


def settings() -> tuple[float, float]:
    """The floor and the write budget in GiB; a setting not finite and positive is a ValueError."""
    floor = float(os.environ.get("ARK_FREE_SPACE_GIB") or 50)
    budget = float(os.environ.get("ARK_WRITE_BUDGET_GIB") or 20)
    if not all(math.isfinite(n) and n > 0 for n in (floor, budget)):
        raise ValueError("space settings must be finite positive GiB values")
    return floor, budget


def free(path: Path) -> int:
    """Free bytes on the filesystem that holds `path`, or its nearest existing parent."""
    while not path.exists():
        path = path.parent
    return shutil.disk_usage(path).free


def space(*, root: Path = Path(".")) -> tuple[int, list[str]]:
    """Require the free-space floor plus a write budget on both destination filesystems."""
    try:
        floor, budget = settings()
        store = root / STORE
        budget_bytes = max(int(budget * GIB), store.stat().st_size if store.exists() else 0)
        required = int(floor * GIB) + budget_bytes
        lines = []
        for destination in (root / "data", root / "output"):
            have = free(destination)
            lines.append(
                f"space {destination.name}: {have / GIB:.1f} GiB free, "
                f"need {required / GIB:.1f} GiB "
                f"({floor:g} floor + {budget_bytes / GIB:.1f} write budget)"
            )
            if have < required:
                return 2, [
                    *lines,
                    "REFUSED: insufficient free space; no ingest or export started. "
                    "Use verified off-site cleanup or increase capacity.",
                ]
            if have < required + int(WARN_GIB * GIB):
                lines.append(
                    f"WARNING: within {WARN_GIB} GiB of the guard; "
                    "`just prune --disk` lists what can go"
                )
        return 0, lines
    except (OSError, ValueError, OverflowError) as exc:
        return 2, [f"REFUSED: cannot establish free space: {exc}"]


def collector_floor() -> int:
    """The bytes a collector leaves free: the bank's floor, its budget and the export's dip."""
    floor, budget = settings()
    return int((floor + budget + EXPORT_DIP_GIB) * GIB)


def below_floor(path: Path, more: int = 0) -> str:
    """Why a collector writing `more` bytes at `path` must wait, or "" when it may write."""
    have, floor = free(path), collector_floor() + more
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
