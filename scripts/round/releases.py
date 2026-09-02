"""Fill the release table in docs/releases.md from what is on disk.

One row per reviewer release. The per-year cells are `wc -l` over `1996.txt` to
`2001.txt` of the extracted tree under `feedback/`; the checksum is of his zip where
one still exists, since his bytes are the artifact of record, and of our
`data/archive/<marker>.tar.zst` where the zip was discarded after extraction.

The script fills cells, it does not reset them: a cell is written when the file
behind it is on disk, and kept when it is not, so the table keeps a hash after the
zip has moved off-site. `--refresh` recomputes every cell that can be computed and
reports the ones that changed. With `feedback/` absent it prints what it would do
and leaves the page alone, which is what a checkout without data gets.

    uv run python scripts/round/releases.py
    uv run python scripts/round/releases.py --zstd      # also pack the zip-less trees
    uv run python scripts/round/releases.py --refresh   # recount and rehash everything

Zips are matched to markers by content, not by name: his zips are called
`Domain_Data_Collection_Task_0831_UpdateV2.zip` and the marker inside is
`merged260830`, so only the member list says which release a zip holds.
"""

import argparse
import hashlib
import re
import shlex
import subprocess
import sys
import zipfile
from pathlib import Path

PAGE = Path("docs/releases.md")
FEEDBACK = Path("feedback")
ARCHIVE = Path("data/archive")
YEARS = tuple(range(1996, 2002))

# Every release the reviewer has named, oldest first. Three of them he scored against
# but never sent: the mail names the marker, the zip that followed holds the next one.
# `merged260715-2` is the task's original corpus and lives in `legacy-data/`, not under
# `feedback/`.
RELEASES = (
    "merged260715-2",
    "merged260727",
    "merged260730",
    "merged260802-2",
    "merged260810",
    "merged260815",
    "merged260817",
    "merged260817-2",
    "merged260820",
    "merged260821",
    "merged260826",
    "merged260827",
    "merged260827-2",
    "merged260830",
    "merged260901",
    "merged260902",
    "merged260902-2",
    "merged260902-3",
)

# marker -> (date of the mail that quoted its totals, the received release that holds them)
NOT_RECEIVED = {
    "merged260817": ("2026-08-18", "merged260817-2"),
    "merged260826": ("2026-08-27", "merged260827"),
    "merged260902-2": ("2026-09-02", "merged260902-3"),
}

TREE_ALIASES = {"merged260715-2": Path("legacy-data")}

MARKER = re.compile(r"merged(\d{6})(-\d+)?")
COLUMNS = ("marker", "released", "received", *map(str, YEARS), "artifact", "sha256")
BEGIN = "<!-- releases:table -->"
END = "<!-- /releases:table -->"
PENDING = "pending"
NONE = "none"


def release_date(marker: str) -> str:
    """`merged260830` -> `2026-08-30`. The marker is the only date every release carries."""
    m = MARKER.fullmatch(marker)
    if not m:
        raise ValueError(f"not a release marker: {marker}")
    d = m.group(1)
    return f"20{d[:2]}-{d[2:4]}-{d[4:]}"


def received_text(marker: str) -> str:
    if marker not in NOT_RECEIVED:
        return "yes"
    mailed, successor = NOT_RECEIVED[marker]
    return f"not received: totals from the reviewer's mail of {mailed}, superseded by `{successor}`"


def find_trees(feedback: Path, aliases: dict[str, Path]) -> dict[str, list[Path]]:
    """Extracted release trees by marker: a `merged*` directory holding a year file.

    Shallowest first, so a duplicate extraction deeper down is reported, not used.
    """
    trees: dict[str, list[Path]] = {}
    if feedback.is_dir():
        found = (p for p in feedback.rglob("merged*") if p.is_dir() and MARKER.fullmatch(p.name))
        for p in sorted(found, key=lambda p: (len(p.parts), str(p))):
            if (p / "1996.txt").is_file():
                trees.setdefault(p.name, []).append(p)
    for marker, alias in aliases.items():
        if (alias / "1996.txt").is_file():
            trees.setdefault(marker, []).append(alias)
    return trees


def zip_markers(zip_path: Path) -> set[str]:
    """The release markers a zip holds, read from its member list."""
    found: set[str] = set()
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            for part in name.split("/"):
                if MARKER.fullmatch(part):
                    found.add(part)
    return found


def find_zips(feedback: Path) -> dict[str, list[Path]]:
    zips: dict[str, list[Path]] = {}
    if not feedback.is_dir():
        return zips
    for z in sorted(feedback.rglob("*.zip")):
        try:
            markers = zip_markers(z)
        except zipfile.BadZipFile:
            print(f"  skip {z}: not a zip", file=sys.stderr)
            continue
        for marker in markers:
            zips.setdefault(marker, []).append(z)
    return zips


def count_lines(path: Path) -> int:
    """Newlines, which is what `wc -l` reports and what the reviewer quotes."""
    n = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            n += chunk.count(b"\n")
    return n


def year_counts(tree: Path) -> dict[int, int]:
    return {y: count_lines(tree / f"{y}.txt") for y in YEARS if (tree / f"{y}.txt").is_file()}


def sha256(path: Path) -> str:
    with path.open("rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def zstd_command(tree: Path, target: Path) -> str:
    """Pack the tree as `<name>/...` inside the tarball, from its parent, at level 19."""
    return (
        f"tar -C {shlex.quote(str(tree.parent))} -cf - {shlex.quote(tree.name)}"
        f" | zstd -19 -T0 -q -o {shlex.quote(str(target))}"
    )


def run_zstd(tree: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tar = subprocess.Popen(
        ["tar", "-C", str(tree.parent), "-cf", "-", tree.name], stdout=subprocess.PIPE
    )
    zstd = subprocess.run(
        ["zstd", "-19", "-T0", "-q", "-o", str(target)], stdin=tar.stdout, check=False
    )
    tar.stdout.close()
    if tar.wait() != 0 or zstd.returncode != 0:
        target.unlink(missing_ok=True)
        raise RuntimeError(f"zstd of {tree} failed")


def split_page(text: str) -> tuple[str, list[dict[str, str]], str]:
    """The prose before the table, the rows keyed by column, the prose after."""
    try:
        head, rest = text.split(BEGIN, 1)
        table, tail = rest.split(END, 1)
    except ValueError as exc:
        raise SystemExit(f"{PAGE}: needs {BEGIN} and {END} around the table") from exc
    rows = []
    for line in table.strip().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(COLUMNS) or not cells[0].startswith("`merged"):
            continue
        cells[0] = cells[0].strip("`")
        rows.append(dict(zip(COLUMNS, cells, strict=True)))
    return head, rows, tail


def render_table(rows: list[dict[str, str]]) -> str:
    lines = [
        "| " + " | ".join(COLUMNS) + " |",
        "|" + "|".join("---" for _ in COLUMNS) + "|",
    ]
    for row in rows:
        cells = [f"`{row['marker']}`", *(row[c] for c in COLUMNS[1:])]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def blank_row(marker: str) -> dict[str, str]:
    row = {"marker": marker, "released": release_date(marker), "received": received_text(marker)}
    fill = NONE if marker in NOT_RECEIVED else PENDING
    for c in COLUMNS[3:]:
        row[c] = fill
    return row


def fill_row(
    row: dict[str, str],
    trees: list[Path],
    zips: list[Path],
    archive: Path,
    refresh: bool,
    pack: bool,
) -> list[str]:
    """Update one row in place; return the log lines."""
    marker = row["marker"]
    log: list[str] = []
    if marker in NOT_RECEIVED:
        return [f"{marker}: not received, nothing to measure"]

    def put(column: str, value: str) -> None:
        old = row[column]
        if old == value:
            return
        if old not in (PENDING, NONE):
            log.append(f"  {column}: {old} -> {value}")
        row[column] = value

    tree = trees[0] if trees else None
    if tree is None:
        log.append(f"{marker}: no extracted tree on disk")
    else:
        log.append(f"{marker}: tree {tree}")
        for extra in trees[1:]:
            log.append(f"  duplicate tree {extra}")
        if refresh or any(row[str(y)] == PENDING for y in YEARS):
            for y, n in year_counts(tree).items():
                put(str(y), f"{n:,}")

    target = archive / f"{marker}.tar.zst"
    if zips:
        for extra in zips[1:]:
            log.append(f"  also in {extra}")
        if refresh or row["sha256"] == PENDING:
            put("artifact", zips[0].name)
            put("sha256", sha256(zips[0]))
        log.append(f"  zip {zips[0]}")
    elif target.is_file() or (pack and tree is not None):
        if not target.is_file():
            log.append(f"  packing {tree} -> {target}")
            run_zstd(tree, target)
        if refresh or row["sha256"] == PENDING:
            put("artifact", target.name)
            put("sha256", sha256(target))
        log.append(f"  zstd {target}")
    elif tree is not None:
        log.append(f"  no zip and no {target}; to pack it:")
        log.append(f"  {zstd_command(tree, target)}")
    else:
        log.append(f"  no zip, no {target}")
    return log


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--page", type=Path, default=PAGE)
    ap.add_argument("--feedback", type=Path, default=FEEDBACK)
    ap.add_argument("--archive", type=Path, default=ARCHIVE)
    ap.add_argument("--legacy", type=Path, default=TREE_ALIASES["merged260715-2"])
    ap.add_argument("--zstd", action="store_true", help="pack every zip-less tree into --archive")
    ap.add_argument("--refresh", action="store_true", help="recount and rehash filled cells too")
    args = ap.parse_args()

    if not args.feedback.is_dir():
        print(f"{args.feedback}/ not found: would scan it for merged*/ trees and *.zip files")
    if not args.archive.is_dir():
        print(f"{args.archive}/ not found: would look there for <marker>.tar.zst copies")

    head, rows, tail = split_page(args.page.read_text())
    by_marker = {r["marker"]: r for r in rows}
    rows = [by_marker.get(m) or blank_row(m) for m in RELEASES]

    trees = find_trees(args.feedback, {"merged260715-2": args.legacy})
    zips = find_zips(args.feedback)
    for stray in sorted(set(trees) | set(zips)):
        if stray not in RELEASES:
            print(f"on disk but not in RELEASES: {stray}")

    for row in rows:
        m = row["marker"]
        for line in fill_row(
            row, trees.get(m, []), zips.get(m, []), args.archive, args.refresh, args.zstd
        ):
            print(line)

    new_text = f"{head}{BEGIN}\n{render_table(rows)}\n{END}{tail}"
    if new_text != args.page.read_text():
        args.page.write_text(new_text)
        print(f"wrote {args.page}")
    else:
        print(f"{args.page} unchanged")


if __name__ == "__main__":
    main()
