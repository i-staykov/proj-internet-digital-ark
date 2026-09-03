"""Print the slugs of the next open hypotheses, best first.

A hypothesis is a block in the hypothesis file headed `## <slug> | <title>`. It is OPEN
until its block carries a `result:` line with something after the colon, which is what the
harvester writes, AND has no unharvested findings file (see `--pending-dir`).

Kept as its own script rather than inline in the shell that calls it, because macOS ships
bash 3.2, which has no `mapfile`, and a heredoc inside a process substitution inside a loop
is how the caller first failed to parse.
"""

import argparse
import re
from pathlib import Path


def open_slugs(doc: str) -> list[str]:
    out = []
    for block in re.split(r"\n(?=## )", doc):
        head = re.match(r"##\s+([a-z0-9_-]+)\s*\|", block)
        if not head:
            continue
        if re.search(r"^result:\s*\S", block, re.M):
            continue
        out.append(head.group(1))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", type=Path)
    ap.add_argument("count", type=int, nargs="?", default=4)
    ap.add_argument(
        "--pending-dir",
        type=Path,
        default=None,
        help="also skip slugs with a findings file here: written but not yet harvested",
    )
    args = ap.parse_args()
    slugs = open_slugs(args.path.read_text(encoding="utf-8"))
    # **A findings file that exists but carries no `result:` line yet is IN FLIGHT.**
    # The harvester runs in the background so the next round can start immediately, which
    # means it has usually not written its `result:` lines by the time the next round
    # picks. Without this the loop relaunches the slugs it just finished, which it did on
    # 2026-08-27 at 23:09.
    if args.pending_dir and args.pending_dir.is_dir():
        pending = {f.stem for f in args.pending_dir.glob("*.md")}
        slugs = [s for s in slugs if s not in pending]
    for slug in slugs[: args.count]:
        print(slug)


if __name__ == "__main__":
    main()
