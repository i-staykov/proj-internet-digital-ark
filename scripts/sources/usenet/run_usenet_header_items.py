"""The header lane, unattended: screen each unread usenet-* top, then run whole the ones that pay.

`data/queue/usenet_header/` holds the lane across boots: `seen.json` (the groups already read, a
JSON list placed once by hand; an item that is one of them or the parent of one is never read),
`tops.txt` (the tops in reading order, one a line, written when absent from archive.org's
listing, `items.json`: every top of an unread item, the largest first), `screen.tsv` (each top's
30 MB screen, `screen_usenet_header_items.py`) and `log.tsv` (every file run whole). In
`tops.txt`'s order a top not yet screened is screened, and one whose screen paid above FLOOR EE
per GB runs whole: every unread item under it, every `.mbox.zip` it holds, one download at a
time with `/` kept 70 GiB free and a file kept only when it came whole, about 1 GB a batch,
extracted by `build_usenet_header_pool.py`, priced on the candidate track through the ingest's
own reader and only then moved into `data/raw/usenet_header_items/hl_<UTC stamp>/`, which the
hourly bank folds, the zips deleted; a batch paying under FLOOR EE per GB drops its top. The
hold is read before every request. A 429 ends the run; any other failure is retried once after
120 s, and three in a row, a failed listing, a failed extract or a screen that read nothing or
could not be priced end it with a strike on the top, three strikes giving the top up. The next
start resumes from `log.tsv`, skipping every file read.

The tick starts it after the bank as its own user unit, `ark-header`, while `left()` counts a
top (`scripts/harness/scheduled_sync.sh`); it stops itself once no unscreened or above-floor top
is left.

    uv run python scripts/sources/usenet/run_usenet_header_items.py
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
import time
import urllib.parse
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sample_usenet_header_items import build, fetch, items, listing, price, unread  # noqa: E402
from screen_usenet_header_items import screen  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
WORK = REPO / "data/queue/usenet_header"
OUT = REPO / "data/raw/usenet_header_items"
FLOOR = 300


def rows(name: str) -> list[list[str]]:
    path = WORK / name
    return [ln.split("\t") for ln in path.read_text().splitlines()] if path.exists() else []


def pays(row: list[str]) -> bool:
    """A screen row priced above FLOOR EE per GB."""
    return len(row) == 7 and int(row[1]) > 0 and float(row[6]) > FLOOR * int(row[1]) / 1e9


def todo() -> list[str]:
    """The tops left in order, none struck three times: not screened, or screened above FLOOR
    and neither run out nor dropped."""
    screened = {r[0]: r for r in rows("screen.tsv")}
    log = rows("log.tsv")
    strikes = Counter(r[1] for r in log if r[0] == "stop" and r[-1] != "429")
    out = {r[1] for r in log if r[0] in ("ran", "drop")}
    tops = [t for t in (WORK / "tops.txt").read_text().split() if strikes[t] < 3]
    return [t for t in tops if t not in screened or (pays(screened[t]) and t not in out)]


def left() -> int:
    """Tops left, from the lane's own files alone; without `seen.json` or `tops.txt` it counts
    one, so the unattended check names a lane that cannot start."""
    if not (WORK / "seen.json").exists() or not (WORK / "tops.txt").exists():
        return 1
    return len(todo())


def summary() -> str:
    """The heartbeat's line: GB and candidate EE as priced per batch, since the lane began."""
    batches = {r[0]: (int(r[4]), float(r[7])) for r in rows("log.tsv") if len(r) == 8}
    gb = sum(s for s, _ in batches.values()) / 1e9
    ee = sum(e for _, e in batches.values() if not math.isnan(e))
    scr = rows("screen.tsv")
    scr_gb = sum(int(r[1]) for r in scr) / 1e9
    return (
        f"header lane: {len(scr)} tops screened ({scr_gb:.2f} GB), {len(batches)} batches run"
        f" whole, {gb:.2f} GB, {ee:,.0f} EE candidate; {left()} tops left"
    )


def held() -> bool:
    return subprocess.run(["bash", str(REPO / "scripts/harness/hold.sh"), "holds"]).returncode == 0


def note(*row) -> None:
    with open(WORK / "log.tsv", "a") as log:
        print(*row, sep="\t", file=log, flush=True)


def run(top: str, todo_items: list[str]) -> bool:
    """One top whole; False once a 429, the hold or a failure ends the run."""
    done = {r[3] for r in rows("log.tsv") if len(r) == 8}
    files = []
    for item in sorted(i for i in todo_items if i.split(".")[0] == top):
        if held():
            return False
        if isinstance(meta := listing(item), str):  # a 429 is no strike, anything else is
            note("stop", top, item, "meta", meta)
            return False
        files += [
            (item, f["name"], int(f.get("size", 0)))
            for f in meta
            if f["name"].endswith(".mbox.zip") and f["name"] not in done
        ]
        time.sleep(1)
    queued: set[str] = set()  # a group sits in its hierarchy's item and its own: read once
    files = [f for f in files if f[1] not in queued and not queued.add(f[1])]
    pool, fails, stop = WORK / "pool", 0, False
    while files:
        name = f"hl_{time.strftime('%Y%m%dT%H%M%S', time.gmtime())}"  # a run id, never a counter
        size, names, t0 = 0, [], time.time()
        while files and size < 1e9 and not (stop := held()):
            item, fname, fsize = files.pop(0)
            url = f"https://archive.org/download/usenet-{item}/{urllib.parse.quote(fname)}"
            code = fetch(url, pool / fname, fsize)
            if code not in ("200", "429"):
                time.sleep(120)
                code = fetch(url, pool / fname, fsize)
            if code != "200":
                fails += 1
                stop = code == "429" or fails >= 3
                note("stop" if stop else "fail", top, item, fname, code)
                if stop:
                    break
                continue
            fails = 0
            size += fsize
            names.append((item, fname))
            time.sleep(1)
        if names:
            tmp, t1 = OUT / f".{name}", time.time()  # the bank's glob skips a dot directory
            built = build(pool, tmp)
            for _item, fname in names:
                (pool / fname).unlink()
            if built:  # the batch is not charged as read
                shutil.rmtree(tmp, ignore_errors=True)
                note("stop", top, name, f"build {built}")
                return False
            ee, secs = price(WORK, tmp), (round(t1 - t0), round(time.time() - t1))
            tmp.rename(OUT / name)  # whole and priced, so the bank never folds half a batch
            for item, fname in names:
                note(name, top, item, fname, size, *secs, round(ee, 1))
            if ee < FLOOR * size / 1e9:
                note("drop", top, name, round(ee, 1), size)
                return True
        if stop:
            return False
    note("ran", top)
    return True


def main() -> None:
    if not (WORK / "seen.json").exists():
        return print(f"header: no {WORK.relative_to(REPO)}/seen.json, nothing read", flush=True)
    # a killed run's zips and extracts never outlive it
    for gone in (WORK / "pool", WORK / "out"):
        shutil.rmtree(gone, ignore_errors=True)
    (WORK / "pool").mkdir()
    OUT.mkdir(parents=True, exist_ok=True)
    for part in OUT.glob(".hl_*"):
        shutil.rmtree(part, ignore_errors=True)
    try:
        todo_items = unread(WORK, WORK / "seen.json")
    except OSError as exc:
        return print(f"header: the listing failed, {exc}", flush=True)
    size = {
        x["identifier"][7:]: int(x["item_size"])
        for x in items(WORK / "items.json")
        if x.get("item_size")
    }
    if not (WORK / "tops.txt").exists():
        by_top = Counter()
        for i in todo_items:
            by_top[i.split(".")[0]] += size[i]
        (WORK / "tops.txt").write_text("".join(f"{t}\n" for t, _ in by_top.most_common()))
    screened = {r[0] for r in rows("screen.tsv")}
    while queue := todo():
        if held():
            return print("header: held", flush=True)
        top = queue[0]
        if top in screened:
            if not run(top, todo_items):
                return print(f"header: stopped in {top}", flush=True)
            continue
        row = screen(WORK, top, todo_items, size, held)
        if row is None:
            return print(f"header: a 429 or the hold stopped the screen of {top}", flush=True)
        if isinstance(row, str) or (len(row) == 7 and math.isnan(row[6])):
            note("stop", top, "screen", row if isinstance(row, str) else "price")
            return print(f"header: the screen of {top} failed, a strike", flush=True)
        with open(WORK / "screen.tsv", "a") as fh:
            print(*row, sep="\t", file=fh, flush=True)
        screened.add(top)
    print("header: every top screened and every one that pays run whole", flush=True)


if __name__ == "__main__":
    main()
