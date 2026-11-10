"""Screen one usenet-* top outside the group catalogue by a 30 MB price before any whole run.

Its top-level item (the one named as the top, which holds every group under it) and its largest
other unread item, the three largest `.mbox.zip` under 20 MB they hold, at most 30 MB (SAMPLE),
extracted by `build_usenet_header_pool.py`, priced on the candidate track through the ingest's
own reader, then deleted, or left in `keep` when the caller banks it, so the sample's side
journals are not lost with its zips. The row keeps bytes, seconds, posts, posts
dated 1996 to 2001, those with a host and the EE; a top with no such file is a row of zeros. A
429, a 503, an outage or the hold raises `End`; a 4xx that left nothing read, a failed extract
or a failed price is returned as the failure, never a row. The header lane
(`run_usenet_header_items.py`) calls it for each top it has not screened.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
import time
import urllib.parse
from collections.abc import Callable
from pathlib import Path

from sample_usenet_header_items import BUILD, End, fetch, listing, price

SAMPLE = 3e7  # bytes


def screen(
    work: Path,
    top: str,
    todo: list[str],
    size: dict[str, int],
    held: Callable[[], bool],
    keep: Path | None = None,
) -> list | str:
    """The top's row, or the failure that strikes it; a priced extract stays in `keep`."""
    files, failed = [], ""
    under = (i for i in todo if i.split(".")[0] == top)
    for item in sorted(under, key=lambda i: (i != top, -size[i]))[:2]:
        if isinstance(meta := listing(item, held), str):  # a 4xx: the item is skipped
            failed = meta
            continue
        files += [
            (item, f["name"], int(f.get("size", 0)))
            for f in meta
            if f["name"].endswith(".mbox.zip") and 0 < int(f.get("size", 0)) <= 2e7
        ]
        time.sleep(1)
    pick, total = [], 0
    for f in sorted(files, key=lambda f: -f[2]):  # a group sits in both items: read once
        if len(pick) < 3 and total + f[2] <= SAMPLE and f[1] not in {p[1] for p in pick}:
            pick.append(f)
            total += f[2]
    if not pick and not failed:
        return [top, 0, 0, 0, 0, 0, 0.0]
    pool, out, t0, got = work / "pool", keep or work / "out" / top, time.time(), 0
    pool.mkdir(parents=True, exist_ok=True)
    try:
        for item, name, fsize in pick:
            url = f"https://archive.org/download/usenet-{item}/{urllib.parse.quote(name)}"
            try:
                code = fetch(url, pool / name, fsize, held)
            except End as e:
                e.file = name
                raise
            got += fsize if code == "200" else 0
            failed = failed if code == "200" else code
        if failed and not got:
            return failed
        cmd = ["nice", sys.executable, BUILD, pool, out, "1"]
        r = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        for z in pool.glob("*.zip"):
            z.unlink()
    secs = round(time.time() - t0)
    if r.returncode:
        shutil.rmtree(out, ignore_errors=True)
        return f"build {r.returncode}"
    ee = price(work, out)
    if not keep or math.isnan(ee):
        shutil.rmtree(out, ignore_errors=True)
    if math.isnan(ee):
        return "price"
    totals = [json.loads(line[6:]) for line in r.stdout.splitlines() if line.startswith("TOTAL ")]
    st = totals[-1] if totals else {}
    return [
        top,
        got,
        secs,
        st.get("posts"),
        st.get("in_window"),
        st.get("with_hosts"),
        round(ee, 1),
    ]
