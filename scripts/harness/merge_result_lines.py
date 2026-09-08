"""Replay our result lines onto the fleet's current `hypotheses.md` after a rejected push.

**Why this is a script and not a shell one-liner.** Three times on 2026-09-08 a stale branch
silently dropped work: the generator's `git pull --rebase` stopped on a content conflict and still
reported success, a PR of mine was branched off a main that had moved, and the 21:37Z bank's result
lines were rejected as non-fast-forward with the failure swallowed by `|| true`. That last one made
`origin/main` report 24 open hypotheses when 6 were left, so the generator's gate correctly refused
to refill and the lane that finds sources sat idle on a queue that only looked full.

**Why a merge rather than a rebase.** Both sides only ever add: the generator appends whole
`## slug` blocks, and a bank adds `result:` lines inside blocks that exist. So the merge is
mechanical. A block the remote does not have is appended. A block both sides have is taken from
whichever copy is LONGER, which is the one carrying the newer result line. Nothing is ever deleted,
so a lost race costs a retry rather than a verdict.

    uv run python scripts/harness/merge_result_lines.py <our copy> <the file to rewrite>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BLOCK = re.compile(r"^## (\S+)")


def blocks(text: str) -> dict[str, str]:
    """Slug to block body, for a file that is a run of `## slug` sections."""
    found: dict[str, str] = {}
    for chunk in re.split(r"\n(?=## )", text):
        match = BLOCK.match(chunk)
        if match:
            found[match.group(1)] = chunk.rstrip()
    return found


def merge(ours: str, theirs: str) -> tuple[str, int, int]:
    mine, remote = blocks(ours), blocks(theirs)
    merged: list[str] = []
    kept = 0
    for slug, body in remote.items():
        ourblock = mine.get(slug)
        if ourblock and len(ourblock) > len(body):
            merged.append(ourblock)
            kept += 1
        else:
            merged.append(body)
    added = [body for slug, body in mine.items() if slug not in remote]
    merged.extend(added)
    return "\n".join(block + "\n" for block in merged), kept, len(added)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__.strip().splitlines()[-1])
        return 2
    ours = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    target = Path(sys.argv[2])
    theirs = target.read_text(encoding="utf-8", errors="replace")
    text, kept, added = merge(ours, theirs)
    target.write_text(text, encoding="utf-8")
    print(f"replayed {kept} extended block(s), appended {added} the remote did not have")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
