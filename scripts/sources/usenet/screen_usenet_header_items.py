"""Screen usenet-* tops outside the group catalogue by a 30 MB price before any whole run.

For each named top: its two largest unread items, the three largest `.mbox.zip` under 20 MB they
hold, at most 30 MB, extracted by `build_usenet_header_pool.py` into WORKDIR (outside the bank)
and written as {host, year} items for `just price --items WORKDIR/<top>.items.jsonl --track
candidate`. `log.tsv` keeps bytes, seconds, posts, posts dated 1996 to 2001 and those with a
host, or the extractor's failing code. A 429 ends the run; any other failed listing skips its item.

    uv run python scripts/sources/usenet/screen_usenet_header_items.py WORKDIR SEEN.json \\
        creative,opera,ucb
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

from sample_usenet_header_items import BUILD, fetch, get, items, unread, write_items


def main(work: Path, seen: Path, tops: list[str]) -> None:
    size = {
        x["identifier"][7:]: int(x["item_size"])
        for x in items(work / "items.json")
        if x.get("item_size")
    }
    todo = unread(work, seen)
    with open(work / "log.tsv", "a") as log:
        for top in tops:
            files = []
            for item in sorted((i for i in todo if i.split(".")[0] == top), key=lambda i: -size[i])[
                :2
            ]:
                try:
                    meta = get(f"https://archive.org/metadata/usenet-{item}/files").get(
                        "result", []
                    )
                except OSError as exc:  # a 429 ends the run, else the item is skipped
                    if getattr(exc, "code", 0) == 429:
                        return
                    continue
                files += [
                    (item, f["name"], int(f["size"]))
                    for f in meta
                    if f["name"].endswith(".mbox.zip") and int(f.get("size", 0)) <= 2e7
                ]
                time.sleep(1)
            pick, total = [], 0
            for f in sorted(files, key=lambda f: -f[2]):
                if len(pick) < 3 and total + f[2] <= 3e7:
                    pick.append(f)
                    total += f[2]
            pool, t0, got = work / "pool" / top, time.time(), 0
            pool.mkdir(parents=True, exist_ok=True)
            for item, name, fsize in pick:
                url = f"https://archive.org/download/usenet-{item}/{urllib.parse.quote(name)}"
                code = fetch(url, pool / name, fsize)
                if code == "429":
                    return
                got += fsize if code == "200" else 0
                time.sleep(1)
            out = work / "out" / top
            r = subprocess.run(
                ["nice", sys.executable, BUILD, pool, out, "1"], capture_output=True, text=True
            )
            totals = [
                json.loads(line[6:]) for line in r.stdout.splitlines() if line.startswith("TOTAL ")
            ]
            st = totals[-1] if totals else {}
            for z in pool.glob("*.zip"):
                z.unlink()
            secs = round(time.time() - t0)
            if r.returncode:  # a failed extract is logged and its top left unpriced
                print(top, got, secs, f"build {r.returncode}", sep="\t", file=log, flush=True)
                continue
            write_items(sorted(out.glob("*.jsonl.gz")), work / f"{top}.items.jsonl")
            row = (top, got, secs, st.get("posts"), st.get("in_window"), st.get("with_hosts"))
            print(*row, sep="\t", file=log, flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3].split(","))
