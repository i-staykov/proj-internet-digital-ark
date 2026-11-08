"""Screen one usenet-* top outside the group catalogue by a 30 MB price before any whole run.

Its two largest unread items, the three largest `.mbox.zip` under 20 MB they hold, at most
30 MB, extracted by `build_usenet_header_pool.py` into WORKDIR/out (outside the bank), priced on
the candidate track through the ingest's own reader, then deleted. The row keeps bytes, seconds,
posts, posts dated 1996 to 2001, those with a host and the EE, or the extractor's failing code.
A 429 or the hold ends the screen; any other failed listing skips its item, and a screen
that read nothing for a failure returns it, unwritten. The header lane
(`run_usenet_header_items.py`) calls it for each top it has not screened.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.parse
from collections.abc import Callable
from pathlib import Path

from sample_usenet_header_items import BUILD, fetch, listing, price


def screen(
    work: Path, top: str, todo: list[str], size: dict[str, int], held: Callable[[], bool]
) -> list | str | None:
    """The top's row; None when a 429 or the hold ended it, the failure when nothing came."""
    files, failed = [], ""
    for item in sorted((i for i in todo if i.split(".")[0] == top), key=lambda i: -size[i])[:2]:
        if held():
            return None
        if (meta := listing(item)) == "429":
            return None
        if isinstance(meta, str):  # the item is skipped
            failed = f"meta {meta}"
            continue
        files += [
            (item, f["name"], int(f.get("size", 0)))
            for f in meta
            if f["name"].endswith(".mbox.zip") and 0 < int(f.get("size", 0)) <= 2e7
        ]
        time.sleep(1)
    pick, total = [], 0
    for f in sorted(files, key=lambda f: -f[2]):
        if len(pick) < 3 and total + f[2] <= 3e7:
            pick.append(f)
            total += f[2]
    pool, out, t0, got = work / "pool", work / "out" / top, time.time(), 0
    pool.mkdir(parents=True, exist_ok=True)
    for item, name, fsize in pick:
        url = f"https://archive.org/download/usenet-{item}/{urllib.parse.quote(name)}"
        code = "held" if held() else fetch(url, pool / name, fsize)
        if code in ("429", "held"):
            return None
        got += fsize if code == "200" else 0
        failed = failed if code == "200" else code
        time.sleep(1)
    if failed and not got:  # an outage is no screen
        return failed
    r = subprocess.run(
        ["nice", sys.executable, BUILD, pool, out, "1"], capture_output=True, text=True
    )
    totals = [json.loads(line[6:]) for line in r.stdout.splitlines() if line.startswith("TOTAL ")]
    st = totals[-1] if totals else {}
    for z in pool.glob("*.zip"):
        z.unlink()
    secs = round(time.time() - t0)
    if r.returncode:  # a failed extract is logged and its top left unpriced
        shutil.rmtree(out, ignore_errors=True)
        return [top, got, secs, f"build {r.returncode}"]
    ee = price(work, out) if got else 0.0
    shutil.rmtree(out, ignore_errors=True)
    return [
        top,
        got,
        secs,
        st.get("posts"),
        st.get("in_window"),
        st.get("with_hosts"),
        round(ee, 1),
    ]
