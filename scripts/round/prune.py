"""Say which local data entries could be deleted, and delete nothing.

Reads the tracked `docs/retention.md` and nothing else, so the page a human can read
is the single source of truth: the classification tables inside `verify_raw.py` are
not consulted here. An entry with no row is not in the table and so cannot appear.

An entry is deletable only when all three of these hold at once:

  1. its class is `regenerable` (a recipe rebuilds it) or `keep_until_priced` (nobody
     reads it yet, so only the bytes are at stake);
  2. `refetch` names somebody who could serve the bytes again: a URL, a recipe or the
     reviewer release. `own_journal` is our own collector's output and `unknown` is
     nobody, so neither is a route;
  3. `digest` and `record` say a checksum exists, so a refetch can be checked.

Everything else is listed under what it is missing, which makes the second half of the
output the to-do list for the off-site copy: an entry missing only a checksum needs one
before it can be copied and verified.

    uv run python scripts/round/prune.py
    uv run python scripts/round/prune.py --json

Deleting is a separate approved ticket. This script has no flag that deletes.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RETENTION = REPO / "docs/retention.md"

# Classes whose bytes can come back. The other three are held whatever else holds:
# `live_input` is read by `just sources`, `keep_journal` is ours alone, `reference`
# is kept for the record.
RECLAIMABLE = ("regenerable", "keep_until_priced")

# `refetch` values naming nobody who could serve the bytes again.
NO_ROUTE = frozenset({"unknown", "own_journal", "none", "?", ""})

# Flags a caller might reach for. None of them exist, and saying why beats a usage error.
DELETE_FLAGS = frozenset({"--delete", "--apply", "--force", "--rm", "--execute", "--yes", "-f"})


@dataclass(frozen=True)
class Entry:
    key: str
    cls: str
    files: int | None
    size: int | None
    digest: str
    refetch: str
    record: str

    @property
    def route(self) -> str:
        """Kind of refetch route, or `none`."""
        if self.refetch in NO_ROUTE:
            return "none"
        if self.refetch.startswith(("http://", "https://", "ftp://")):
            return "url"
        if self.refetch == "reviewer_release":
            return "reviewer_release"
        return "recipe"

    @property
    def checksummed(self) -> bool:
        return self.digest not in ("none", "?", "") and self.record not in ("none", "?", "")

    @property
    def missing(self) -> list[str]:
        """Why this entry is not deletable, in the order the three conditions are stated."""
        out = []
        if self.cls not in RECLAIMABLE:
            out.append(f"class {self.cls} is held")
        if self.route == "none":
            out.append("no refetch route")
        if not self.checksummed:
            out.append("no checksum record")
        return out

    @property
    def deletable(self) -> bool:
        return not self.missing

    @property
    def group(self) -> str:
        if self.deletable:
            return f"{self.cls}, {self.route} route, checksum recorded"
        return " + ".join(self.missing)


@dataclass
class Group:
    label: str
    deletable: bool
    entries: list[Entry]

    @property
    def size(self) -> int:
        return sum(e.size or 0 for e in self.entries)


def _cells(line: str) -> list[str]:
    return [c.strip().strip("`") for c in line.strip().strip("|").split("|")]


def _number(cell: str) -> int | None:
    return None if not cell.isdigit() else int(cell)


def read_table(path: Path) -> list[Entry]:
    """The retention rows, in page order. A row is a line whose first cell is a path."""
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        cells = _cells(line)
        if len(cells) != 7:
            raise ValueError(f"{path}: expected 7 cells, got {len(cells)}: {line}")
        key, cls, files, size, digest, refetch, record = cells
        entries.append(Entry(key, cls, _number(files), _number(size), digest, refetch, record))
    if not entries:
        raise ValueError(f"{path}: no rows")
    return entries


def group(entries: list[Entry]) -> list[Group]:
    """One group per distinct reason, deletable first, then largest first."""
    groups: dict[str, Group] = {}
    for e in entries:
        g = groups.setdefault(e.group, Group(e.group, e.deletable, []))
        g.entries.append(e)
    return sorted(groups.values(), key=lambda g: (not g.deletable, -g.size, g.label))


def human(size: int) -> str:
    for unit, step in (("GB", 10**9), ("MB", 10**6), ("kB", 10**3)):
        if size >= step:
            return f"{size / step:.1f} {unit}"
    return f"{size} B"


def report(groups: list[Group], path: Path) -> list[str]:
    total = sum(g.size for g in groups)
    count = sum(len(g.entries) for g in groups)
    free = sum(g.size for g in groups if g.deletable)
    out = [
        f"{path}: {count} entries, {total:,} B ({human(total)}).",
        "Nothing was deleted: this script has no flag that deletes.",
    ]
    for heading, deletable in (
        ("DELETABLE: class, refetch route and checksum record all hold", True),
        ("HELD: what each entry is missing, which is the off-site copy to-do list", False),
    ):
        out += ["", heading]
        for g in (g for g in groups if g.deletable == deletable):
            out.append(f"\n  {g.label}  [{len(g.entries)} entries, {g.size:,} B, {human(g.size)}]")
            for e in g.entries:
                size = "?" if e.size is None else human(e.size)
                out.append(f"    {e.key:<52} {size:>9}  {e.refetch[:60]}")
    out += [
        "",
        f"deletable {free:,} B ({human(free)}), "
        f"held {total - free:,} B ({human(total - free)}), "
        f"groups sum to {total:,} B.",
    ]
    return out


def as_json(groups: list[Group], path: Path) -> dict:
    return {
        "table": str(path),
        "deletes": False,
        "entries": sum(len(g.entries) for g in groups),
        "total_bytes": sum(g.size for g in groups),
        "deletable_bytes": sum(g.size for g in groups if g.deletable),
        "groups": [
            {
                "label": g.label,
                "deletable": g.deletable,
                "bytes": g.size,
                "entries": [
                    {
                        "entry": e.key,
                        "class": e.cls,
                        "files": e.files,
                        "bytes": e.size,
                        "refetch": e.refetch,
                        "route": e.route,
                        "record": e.record,
                        "missing": e.missing,
                    }
                    for e in g.entries
                ],
            }
            for g in groups
        ],
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    refused = [a for a in argv if a.split("=", 1)[0] in DELETE_FLAGS]
    if refused:
        print(
            f"prune.py has no {', '.join(refused)}: it never deletes, it only says what could be. "
            "Deletion is a separate approved ticket.",
            file=sys.stderr,
        )
        return 2

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], epilog="Deletes nothing.")
    ap.add_argument("--table", type=Path, default=RETENTION, help="retention table to read")
    ap.add_argument("--json", action="store_true", help="machine-readable form")
    args = ap.parse_args(argv)

    groups = group(read_table(args.table))
    if args.json:
        print(json.dumps(as_json(groups, args.table), indent=2))
    else:
        print("\n".join(report(groups, args.table)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
