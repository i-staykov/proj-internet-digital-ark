"""Report retention eligibility, or prune verified round duplicates with --round --write.

Reads the tracked `docs/registers/retention.md` and nothing else, so the page a human can read
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

The retention report grants no deletion permission. Round cleanup is limited to
superseded store backups and CRC-matched reviewer zips. Every removed file needs
an unchanged local verification receipt and a current matching remote hash.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RETENTION = REPO / "docs/registers/retention.md"

# Classes whose bytes can come back. The other three are held whatever else holds:
# `live_input` is read by `just reproduce sources`, `keep_journal` is ours alone, `reference`
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


def sibling(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def remove_verified(root: Path, path: Path, *, write: bool = False) -> str:
    """Delete one regular file only after checking its recorded and live remote copy."""
    offsite = sibling("offsite")
    stamp = offsite.deletion_proof(root, path)
    if write:
        if offsite.signature(root, path) != stamp:
            raise ValueError(f"changed before deletion: {path.relative_to(root)}")
        path.unlink()
    return f"{'removed' if write else 'would remove'}: {path.relative_to(root)}"


def round_cleanup(root: Path, *, write: bool = False) -> tuple[int, list[str]]:
    """Keep extracted releases and the current store; never select submissions or output."""
    root = root.resolve()
    offsite, releases = sibling("offsite"), sibling("releases")
    lines, held = [], False
    store = root / "data/ark.duckdb"
    for backup in sorted((root / "data").glob("ark.duckdb.pre-*.bak")):
        try:
            before = offsite.signature(root, store)
            backup_stamp = offsite.signature(root, backup)
            if (
                before[2] == 0
                or before[3] <= backup_stamp[3]
                or before[:2] == backup_stamp[:2]
                or store.with_suffix(".duckdb.wal").exists()
            ):
                raise ValueError("store is not a quiescent successor")
            offsite.deletion_proof(root, backup)
            if not write:
                lines.append(f"would check store and remove: {backup.relative_to(root)}")
                continue
            done = subprocess.run(["uv", "run", "ark", "check"], cwd=root, check=False)
            if (
                done.returncode
                or offsite.signature(root, store) != before
                or store.with_suffix(".duckdb.wal").exists()
            ):
                raise ValueError("ark check failed or store changed; backup retained")
            lines.append(remove_verified(root, backup, write=True))
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            held = True
            lines.append(f"HELD {backup.relative_to(root)}: {exc}")

    trees = releases.find_trees(root / "feedback", {})
    zips = releases.find_zips(root / "feedback")
    for archive in sorted({p for paths in zips.values() for p in paths}):
        try:
            archive_stamp = offsite.signature(root, archive)
            offsite.deletion_proof(root, archive)
            inventories = {}
            for marker in sorted(releases.zip_markers(archive)):
                if not trees.get(marker):
                    raise ValueError(f"no extracted tree for {marker}")
                tree = trees[marker][0]
                inventories[tree] = offsite.local_files(root, tree)
                counts, problems = releases.verify_tree(tree, archive, marker)
                if not counts["members"] or problems:
                    raise ValueError(f"CRC verification failed for {marker}: {problems[:3]}")
            if offsite.signature(root, archive) != archive_stamp or any(
                offsite.local_files(root, tree) != before for tree, before in inventories.items()
            ):
                raise ValueError("release changed during CRC verification")
            lines.append(remove_verified(root, archive, write=write))
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            RuntimeError,
            zipfile.BadZipFile,
            zlib.error,
            subprocess.SubprocessError,
        ) as exc:
            held = True
            lines.append(f"HELD {archive.relative_to(root)}: {exc}")
    if not lines:
        lines.append("round duplicates: nothing to prune")
    return (1 if held else 0), lines


def report(groups: list[Group], path: Path) -> list[str]:
    total = sum(g.size for g in groups)
    count = sum(len(g.entries) for g in groups)
    free = sum(g.size for g in groups if g.deletable)
    out = [
        f"{path}: {count} entries, {total:,} B ({human(total)}).",
        "Nothing was deleted: retention eligibility is not remote-copy verification.",
    ]
    for heading, deletable in (
        ("ELIGIBLE FOR REVIEW: class, refetch route and checksum record all hold", True),
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
            f"prune.py has no {', '.join(refused)}: the retention report never deletes. "
            "Only --round --write permits verified round cleanup.",
            file=sys.stderr,
        )
        return 2

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--table", type=Path, default=RETENTION, help="retention table to read")
    ap.add_argument("--json", action="store_true", help="machine-readable form")
    ap.add_argument(
        "--round", action="store_true", help="check superseded backups and release zips"
    )
    ap.add_argument("--write", action="store_true", help="with --round, remove verified copies")
    ap.add_argument("--root", type=Path, default=REPO)
    args = ap.parse_args(argv)

    if args.write and not args.round:
        ap.error("--write requires --round")
    if args.round:
        if args.json:
            ap.error("--round does not accept --json")
        code, lines = round_cleanup(args.root, write=args.write)
        print("\n".join(lines))
        return code

    groups = group(read_table(args.table))
    if args.json:
        print(json.dumps(as_json(groups, args.table), indent=2))
    else:
        print("\n".join(report(groups, args.table)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
