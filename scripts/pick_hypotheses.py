"""Print the slugs of the next open hypotheses, best first.

A hypothesis is a block in the hypothesis file headed `## <slug> | <title>`. It is OPEN
until its block carries a `result:` line with something after the colon, which is what the
harvester writes. Kept as its own script rather than inline in `agent_fanout.sh` because
macOS ships bash 3.2, which has no `mapfile`, and a heredoc inside a process substitution
inside a loop is how that script first failed to parse.
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
    args = ap.parse_args()
    slugs = open_slugs(args.path.read_text(encoding="utf-8"))
    for slug in slugs[: args.count]:
        print(slug)


if __name__ == "__main__":
    main()
