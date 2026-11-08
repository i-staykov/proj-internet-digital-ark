"""The header lane, unattended: screen each unread usenet-* top, then run whole the ones that pay.

`data/queue/usenet_header/` holds the lane across boots: `seen.json` (the groups already read, a
JSON list seeded once by hand; an item that is one of them or the parent of one is never read),
`tops.txt` (the tops in reading order, one a line, written when absent from archive.org's
listing, `items.json`: every top of an unread item, the largest first), `screen.tsv` (each top's
30 MB screen, `screen_usenet_header_items.py`) and `log.tsv` (every file run whole, every
strike, drop and back-off). In `tops.txt`'s order a top not yet screened is screened, and one
whose screen paid above FLOOR EE per GB runs whole: every unread item under it, every
`.mbox.zip` it holds, one download at a time above the collectors' floor (`ark.disk`) and a file
kept only when it came whole, about 1 GB a batch, extracted by `build_usenet_header_pool.py`,
priced on the candidate track through the ingest's own reader, logged, and only then moved into
`data/raw/usenet_header_items/hl_<UTC stamp>/`, which the hourly bank folds; a whole batch
paying under FLOOR EE per GB drops its top, one an End cut short judges nothing. A start moves a
logged batch a kill left behind into place and deletes an unlogged one, and no zip outlives its
extract.

The hold is read before every request. A failed request is asked once more after 120 s. A 429
backs the lane off for an hour or its Retry-After up to a day, whichever is longer, and an
outage (no answer, a 5xx, a cut or stalled transfer, a price snapshot it cannot read) for half
an hour, striking nothing; a start inside a back-off exits at once. Three failed files in a row
(any other code, or a whole file of the wrong size), a failed extract or a failed price is a
strike on its top (a failed listing only skips its item) and backs off as an outage does, and so
is one file cut as an outage on three starts running, three strikes giving the top up; one event
strikes once. The next start resumes from `log.tsv`, skipping every file read.

The tick starts it after the bank as its own user unit, `ark-header`, while `left()` counts a
top (`scripts/harness/scheduled_sync.sh`); it stops itself once no unscreened or above-floor top
is left. Its last line, `waits until <UTC stamp>` or `held`, is what the unattended check reads,
and `stalled()` fails that check once a day passes with tops left and no batch, screen or `ran`
row (`progress`, touched by each).

    uv run python scripts/sources/usenet/run_usenet_header_items.py
"""

from __future__ import annotations

import calendar
import json
import math
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sample_usenet_header_items import (  # noqa: E402
    FAILED,
    End,
    build,
    failure,
    fetch,
    items,
    listing,
    price,
    unread,
)
from screen_usenet_header_items import screen  # noqa: E402

from ark.disk import trim  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
WORK = REPO / "data/queue/usenet_header"
POOL = WORK / "pool"
OUT = REPO / "data/raw/usenet_header_items"
LOG = REPO / "data/logs/usenet_header.log"  # the tick's `>>` for the unit
FLOOR = 300
OUTAGE_S, RATE_S, DAY_S = 1800, 3600, 86400
SCRIPT = Path(__file__)
STAMP = "%Y%m%dT%H%M%SZ"


def rows(name: str) -> list[list[str]]:
    path = WORK / name
    return [ln.split("\t") for ln in path.read_text().splitlines()] if path.exists() else []


def pays(row: list[str]) -> bool:
    """A screen row priced above FLOOR EE per GB."""
    return len(row) == 7 and int(row[1]) > 0 and float(row[6]) > FLOOR * int(row[1]) / 1e9


def struck(row: list[str]) -> bool:
    """A `stop` row that strikes its top: any HTTP code but a 429 (fetch returns no outage's),
    a download of the wrong size, a failed extract or price, or a file's outage three starts on."""
    code = row[-1]
    return row[0] == "stop" and (
        code.startswith(("build", "price", "size", "outage")) or (code.isdigit() and code != "429")
    )


def todo() -> list[str]:
    """The tops left in order, none struck three times, run out or dropped: not screened, or
    screened above FLOOR."""
    screened = {r[0]: r for r in rows("screen.tsv")}
    log = rows("log.tsv")
    strikes = Counter(r[1] for r in log if struck(r))
    out = {r[1] for r in log if r[0] in ("ran", "drop")}
    tops = [t for t in (WORK / "tops.txt").read_text().split() if strikes[t] < 3]
    return [t for t in tops if t not in out and (t not in screened or pays(screened[t]))]


def left() -> int:
    """Tops left, from the lane's own files alone: none before `seen.json` is seeded, one while
    the first start has yet to write `tops.txt`."""
    if not (WORK / "seen.json").exists():
        return 0
    return len(todo()) if (WORK / "tops.txt").exists() else 1


def summary() -> str:
    """The heartbeat's line: GB and candidate EE as priced per batch, since the lane began."""
    if not (WORK / "seen.json").exists():
        return "header lane: not seeded, no data/queue/usenet_header/seen.json"
    batches = {r[0]: (int(r[4]), float(r[7])) for r in rows("log.tsv") if len(r) == 8}
    gb = sum(s for s, _ in batches.values()) / 1e9
    ee = sum(e for _, e in batches.values() if not math.isnan(e))
    scr = rows("screen.tsv")
    scr_gb = sum(int(r[1]) for r in scr) / 1e9
    gone = sum(n >= 3 for n in Counter(r[1] for r in rows("log.tsv") if struck(r)).values())
    return (
        f"header lane: {len(scr)} tops screened ({scr_gb:.2f} GB), {len(batches)} batches run"
        f" whole, {gb:.2f} GB, {ee:,.0f} EE candidate; {gone} tops given up, {left()} left"
    )


def stalled() -> str:
    """`stalled at <top>` once a day passes with tops left and no batch, screen or `ran` row
    (`progress`), counted from the seeding or this code's arrival when later."""
    if not left():
        return ""
    marks = (WORK / "progress", WORK / "seen.json", SCRIPT)
    if time.time() - max(p.stat().st_mtime for p in marks if p.exists()) < DAY_S:
        return ""
    return f"stalled at {todo()[0] if (WORK / 'tops.txt').exists() else 'its listing'}"


def progress() -> None:
    (WORK / "progress").touch()


def held() -> bool:
    return subprocess.run(["bash", str(REPO / "scripts/harness/hold.sh"), "holds"]).returncode == 0


def note(*row) -> None:
    with open(WORK / "log.tsv", "a") as log:
        print(*row, sep="\t", file=log, flush=True)


def say(line: str) -> None:
    print(f"header: {line}", flush=True)


def waits() -> float:
    """When the last back-off ends, as epoch seconds; 0 without one."""
    last = [r for r in rows("log.tsv") if r[0] == "backoff"][-1:]
    return calendar.timegm(time.strptime(last[0][3], STAMP)) if last else 0.0


def run(top: str, todo_items: list[str]) -> None:
    """One top whole, ending in its `ran` or `drop` row; a strike raises End after its row."""
    done = {r[3] for r in rows("log.tsv") if len(r) == 8}
    files = []
    for item in sorted(i for i in todo_items if i.split(".")[0] == top):
        if isinstance(meta := listing(item, held), str):  # a 4xx: the item is skipped
            note("fail", top, item, "meta", meta)
            continue
        files += [
            (item, f["name"], int(f.get("size", 0)))
            for f in meta
            if f["name"].endswith(".mbox.zip")
            and 0 < int(f.get("size", 0))
            and f["name"] not in done
        ]
        time.sleep(1)
    queued: set[str] = set()  # a group sits in its hierarchy's item and its own: read once
    files = [f for f in files if f[1] not in queued and not queued.add(f[1])]
    fails = 0
    while files:
        name = f"hl_{time.strftime('%Y%m%dT%H%M%S', time.gmtime())}"  # a run id, never a counter
        size, names, t0, end, low = 0, [], time.time(), None, False
        try:
            while files and size < 1e9:
                item, fname, fsize = files.pop(0)
                url = f"https://archive.org/download/usenet-{item}/{urllib.parse.quote(fname)}"
                if (code := fetch(url, POOL / fname, fsize, held)) != "200":
                    fails += 1
                    note("stop" if fails >= 3 else "fail", top, item, fname, code)
                    if fails >= 3:
                        end = End("strike")
                        break
                    continue
                fails = 0
                size += fsize
                names.append((item, fname))
                time.sleep(1)
        except End as e:  # what came is still built
            e.file, end = fname, e
        if names:
            tmp, t1 = OUT / f".{name}", time.time()  # the bank's glob skips a dot directory
            try:
                built = build(POOL, tmp)
            finally:
                for _item, fname in names:
                    (POOL / fname).unlink(missing_ok=True)
            struck_now = end is not None and end.code == "strike"  # one event, one strike
            if built:  # the batch is not charged as read
                shutil.rmtree(tmp, ignore_errors=True)
                if not struck_now:
                    note("stop", top, name, f"build {built}")
                raise end or End("strike")
            try:
                ee, secs = price(WORK, tmp), (round(t1 - t0), round(time.time() - t1))
            except End as e:  # unlogged, so the next start deletes it and reads it again
                raise (end or e) from e
            for item, fname in names:
                note(name, top, item, fname, size, *secs, round(ee, 1))
            progress()
            low = end is None and ee < FLOOR * size / 1e9  # a batch an End cut judges nothing
            if low:
                note("drop", top, name, round(ee, 1), size)
            tmp.rename(OUT / name)  # logged first, so a kill before this lands it at the next start
            if math.isnan(ee):
                if not struck_now:
                    note("stop", top, name, "price")
                raise end or End("strike")
        if end:
            raise end
        if low:
            return
    note("ran", top)
    progress()


def write(path: Path, text: str) -> None:
    part = path.with_name(path.name + ".part")
    part.write_text(text)
    os.replace(part, path)


def main() -> None:
    trim(LOG)
    if not (WORK / "seen.json").exists():
        return say("not seeded, no data/queue/usenet_header/seen.json")
    read = json.loads((WORK / "seen.json").read_text())  # malformed: a crash, not an outage
    if (until := waits()) > time.time():
        return say(f"backing off, waits until {time.strftime(STAMP, time.gmtime(until))}")
    shutil.rmtree(WORK / "out", ignore_errors=True)  # a killed run's zips and extracts
    shutil.rmtree(POOL, ignore_errors=True)
    POOL.mkdir(parents=True)
    OUT.mkdir(parents=True, exist_ok=True)
    logged = {r[0] for r in rows("log.tsv") if len(r) == 8}
    for part in OUT.glob(".hl_*"):
        if part.name[1:] in logged:
            part.rename(OUT / part.name[1:])
        else:
            shutil.rmtree(part, ignore_errors=True)
    top = "-"
    try:
        if held():
            raise End("held")
        try:
            todo_items = unread(WORK, read, held)
        except FAILED as exc:
            why = failure(exc)
            raise why if isinstance(why, End) else End(why) from exc
        listed = items(WORK / "items.json", held)
        size = {x["identifier"][7:]: int(x["item_size"]) for x in listed if x.get("item_size")}
        if not (WORK / "tops.txt").exists():
            by_top = Counter()
            for i in todo_items:
                by_top[i.split(".")[0]] += size[i]
            write(WORK / "tops.txt", "".join(f"{t}\n" for t, _ in by_top.most_common()))
        screened = {r[0] for r in rows("screen.tsv")}
        while queue := todo():
            if held():
                raise End("held")
            top = queue[0]
            if top in screened:
                run(top, todo_items)
                continue
            if isinstance(row := screen(WORK, top, todo_items, size, held), str):
                note("stop", top, "screen", row)
                raise End("strike")
            with open(WORK / "screen.tsv", "a") as fh:
                print(*row, sep="\t", file=fh, flush=True)
            progress()
            screened.add(top)
    except End as e:
        if e.code == "held":
            return say("held")
        wait = max(RATE_S, min(e.retry, DAY_S)) if e.code == "429" else OUTAGE_S
        until = time.strftime(STAMP, time.gmtime(time.time() + wait))
        note("backoff", top, e.code, until, e.file)
        # one file cut as an outage three starts running, its listing answering each time: the
        # site is up and the file is not, so the top takes a strike and the lane moves on
        last = [r for r in rows("log.tsv") if r[0] == "backoff"][-3:]
        same = [r[1] == top and r[2] != "429" and r[4:] == [e.file] for r in last]
        if e.file and len(same) == 3 and all(same):
            note("stop", top, e.file, "outage")
        return say(f"{e.code} in {top}, waits until {until}")
    say("every top screened and every one that pays run whole")


if __name__ == "__main__":
    main()
