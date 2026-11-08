"""Header lane over whole usenet-* items outside the group catalogue, by top in a given order.

The run behind a `sample_usenet_header_items.py` price: for each named top, every unread item
under it, every `.mbox.zip` it holds, one download at a time with `/` kept 70 GiB free and a file
kept only when it came whole, about 1 GB per batch and one top per batch, extracted by
`build_usenet_header_pool.py` into `data/raw/usenet_header_items/<prefix>_NNN/`, which the bank
folds, the zips deleted. After each batch its journals are priced on the candidate track through
the ingest's own reader; a top whose batch pays under 300 EE per GB is dropped. A 429 ends the
run, any other failure is retried once after 120 s and three failed files in a row end it; no top
or batch starts at or after `--until` (UTC HH:MM, the next one). `log.tsv` in WORKDIR keeps every
file read, so a restart skips them.

    uv run python scripts/sources/usenet/run_usenet_header_items.py WORKDIR SEEN.json a_v \\
        netscape,sybase,gnu --until 06:45
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

from sample_usenet_header_items import build, fetch, get, unread, write_items

FLOOR = 300


def price(work: Path, out: Path) -> float:
    """Candidate EE of one batch's journals against the price snapshot."""
    path = work / "batch.items.jsonl"
    write_items(sorted(out.glob("*.jsonl.gz")), path)
    ark = Path(sys.executable).with_name("ark")
    cmd = [
        ark,
        "price-snapshot",
        "--snapshot",
        "output/price_snapshot",
        "--items",
        path,
        "--track",
        "candidate",
        "--out",
        work / "batch.c.json",
    ]
    if subprocess.run(["nice", *cmd], capture_output=True).returncode:
        return float("nan")  # unpriced: the top is kept
    return float(json.loads((work / "batch.c.json").read_text())["ee"])


def over(deadline: float) -> bool:
    """Past `--until`, or held (scripts/harness/hold.sh): read before every request."""
    hold = ["bash", "scripts/harness/hold.sh", "holds"]
    return time.time() >= deadline or subprocess.run(hold).returncode == 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("work", type=Path)
    ap.add_argument("seen", type=Path)
    ap.add_argument("prefix")
    ap.add_argument("tops")
    ap.add_argument("--until", default="06:45")
    a = ap.parse_args()
    pool = a.work / "pool"
    pool.mkdir(parents=True, exist_ok=True)
    todo = unread(a.work, a.seen)
    logp = a.work / "log.tsv"
    rows = [line.rstrip("\n").split("\t") for line in open(logp)] if logp.exists() else []
    ours = [r for r in rows if r[0].startswith(a.prefix + "_")]
    done, batch = {r[3] for r in ours}, len({r[0] for r in ours})
    now, (hh, mm) = time.time(), (int(x) for x in a.until.split(":"))
    deadline = now - now % 86400 + hh * 3600 + mm * 60
    deadline += 86400 if deadline <= now else 0  # an hour already past today means tomorrow's
    fails, stop = 0, False
    with open(logp, "a") as log:
        for top in a.tops.split(","):
            if over(deadline):
                break
            files = []
            for item in sorted(i for i in todo if i.split(".")[0] == top):
                if over(deadline):
                    break
                try:
                    meta = get(f"https://archive.org/metadata/usenet-{item}/files").get(
                        "result", []
                    )
                except (
                    OSError
                ) as exc:  # HTTPError included: a 429 ends the run, else the item waits
                    print("meta", top, item, exc, sep="\t", file=log, flush=True)
                    stop = getattr(exc, "code", 0) == 429
                    if stop:
                        break
                    continue
                files += [
                    (item, f["name"], int(f["size"]))
                    for f in meta
                    if f["name"].endswith(".mbox.zip") and f["name"] not in done
                ]
                time.sleep(1)
            queued: set[str] = set()  # a group sits in its hierarchy's item and its own: read once
            files = [f for f in files if f[1] not in queued and not queued.add(f[1])]
            while files and not stop and not over(deadline):
                name, size, names, t0 = f"{a.prefix}_{batch:03d}", 0, [], time.time()
                while files and size < 1e9 and not over(deadline):
                    item, fname, fsize = files.pop(0)
                    url = f"https://archive.org/download/usenet-{item}/{urllib.parse.quote(fname)}"
                    code = fetch(url, pool / fname, fsize)
                    if code not in ("200", "429"):
                        time.sleep(120)
                        code = fetch(url, pool / fname, fsize)
                    if code != "200":
                        fails += 1
                        print(
                            "stop" if code == "429" or fails >= 3 else "fail",
                            top,
                            item,
                            fname,
                            code,
                            sep="\t",
                            file=log,
                            flush=True,
                        )
                        stop = code == "429" or fails >= 3
                        if stop:
                            break
                        continue
                    fails = 0
                    size += fsize
                    names.append((item, fname))
                    time.sleep(1)
                if not names:
                    break
                out = Path("data/raw/usenet_header_items") / name
                t1 = time.time()
                built = build(pool, out)
                for _item, fname in names:
                    (pool / fname).unlink()
                if built:  # the batch is not charged as read, and a human looks before more
                    print(
                        "stop",
                        top,
                        name,
                        f"build {built}",
                        sep="\t",
                        file=log,
                        flush=True,
                    )
                    stop = True
                    break
                ee = price(a.work, out)
                for item, fname in names:
                    print(
                        name,
                        top,
                        item,
                        fname,
                        size,
                        round(t1 - t0),
                        round(time.time() - t1),
                        round(ee, 1),
                        sep="\t",
                        file=log,
                        flush=True,
                    )
                batch += 1
                if ee < FLOOR * size / 1e9:
                    print("drop", top, name, round(ee, 1), size, sep="\t", file=log, flush=True)
                    break
            if stop:
                break
        print("done", time.strftime("%H:%M:%S", time.gmtime()), sep="\t", file=log, flush=True)


if __name__ == "__main__":
    main()
