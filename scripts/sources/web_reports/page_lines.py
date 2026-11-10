"""A runner-pages job's share of the lines its dispatch names, as its reader takes them.

The lines are the hits of a runner-grep run (`IN/*/hits.txt`) and the dispatch's own list
(`LIST`, plain or gzip then base64, which carries 4,000 URLs in one input); `WANT` is an ERE a
line must match. `arc` writes the lines as they are, since `arc_pages.py` deals CDX lines
itself, a URL's captures to one job. `replay` writes the trees `wayback_trees.py` reads: a CDX
line asks its own capture and counts only as a 200, a bare URL asks the capture nearest 2001
or nearest the stamp written after it; a URL is asked once, at its first stamp, without its
`:80`; every `of`-th URL from `shard` is this job's, in trees of 25 so each thread has one.

    LIST= WANT=. python3 scripts/sources/web_reports/page_lines.py replay IN trees.json 0/4
"""

import base64
import gzip
import json
import os
import re
import sys
from collections.abc import Iterator
from pathlib import Path

PORT = re.compile(r"^(https?://[^/]+):80(?=/|$)")


def lines(folder: Path, packed: str) -> Iterator[str]:
    for hits in sorted(folder.glob("*/hits.txt")):
        yield from hits.read_text(encoding="latin-1").splitlines()
    try:
        packed = gzip.decompress(base64.b64decode(packed, validate=True)).decode("latin-1")
    except (ValueError, OSError, EOFError):
        pass  # a plain list
    yield from packed.splitlines()


def asks(kept: list[str]) -> dict[str, str]:
    """Each URL's first stamp, "" for the capture nearest 2001."""
    first: dict[str, str] = {}
    for line in kept:
        f = line.split()
        cdx = len(f) > 4 and f[1].isdigit()
        if cdx and f[4] != "200":
            continue
        url = PORT.sub(r"\1", f[2] if cdx else f[0])
        stamp = f[1] if len(f) > 1 and f[1].isdigit() else ""
        if url not in first or stamp < first[url]:
            first[url] = stamp
    return first


def main() -> None:
    reader, folder, out, share = sys.argv[1:5]
    shard, of = (int(x) for x in share.split("/"))
    want = re.compile(os.environ.get("WANT") or ".", re.IGNORECASE)
    kept = [
        x for x in lines(Path(folder), os.environ.get("LIST", "")) if x.split() and want.search(x)
    ]
    if reader == "arc":
        Path(out).write_text("".join(x + "\n" for x in kept), encoding="latin-1")
        print(json.dumps({"lines": len(kept)}))
        return
    first = asks(kept)
    mine = sorted(first)[shard::of]
    trees: dict[str, dict] = {}
    for i, url in enumerate(mine):
        stamp = "\t" + first[url] if first[url] else ""
        trees.setdefault(f"{i // 25:06d}", {"urls": []})["urls"].append(url + stamp)
    Path(out).write_text(json.dumps(trees))
    print(json.dumps({"lines": len(kept), "urls": len(first), "mine": len(mine)}))


if __name__ == "__main__":
    main()
