"""Header lane over whole usenet-* items outside the group catalogue, by top in a given order.

The run behind a `sample_usenet_header_items.py` price: for each named top, every unread item
under it, every `.mbox.zip` it holds, one download at a time with `/` kept 70 GiB free, about
1 GB per batch and one top per batch, extracted by `build_usenet_header_pool.py` into
`data/raw/usenet_header_items/<prefix>_NNN/`, which the bank folds, the zips deleted. After each
batch its journals are priced on the candidate track through the ingest's own reader; a top whose
batch pays under 300 EE per GB is dropped. A 429 ends the run, any other failure is retried once
after 120 s and three failed files in a row end it; no batch starts at or after `--until` (UTC
HH:MM, the next one). `log.tsv` in WORKDIR keeps every file read, so a restart skips them.

    uv run python scripts/sources/usenet/run_usenet_header_items.py WORKDIR SEEN.json a_v \\
        netscape,sybase,gnu --until 06:45
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.parse
from collections import Counter
from pathlib import Path

from sample_usenet_header_items import BUILD, UA, get, items

from ark.hostnames import USENET_HEADER_FAMILY, usenet_item_rows

FLOOR = 300


def fetch(url: str, dst: Path) -> str:
    """The HTTP code; the file is removed unless it came whole."""
    code = subprocess.run(
        ["curl", "-sSL", "-A", UA, "-o", dst, "-w", "%{http_code}", url],
        capture_output=True,
        text=True,
    ).stdout
    if code != "200":
        dst.unlink(missing_ok=True)
    return code


def price(work: Path, out: Path) -> float:
    """Candidate EE of one batch's journals against the fleet snapshot."""
    path = work / "batch.items.jsonl"
    with open(path, "w") as fh:
        for shard in sorted(out.glob("*.jsonl.gz")):
            for host, _parent, year, _value, _url in usenet_item_rows(
                shard, Counter(), USENET_HEADER_FAMILY
            ):
                fh.write(json.dumps({"host": host, "year": year}) + "\n")
    ark = Path(sys.executable).with_name("ark")
    cmd = [
        ark,
        "price-snapshot",
        "--snapshot",
        "output/fleet_snapshot",
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
    seen = {
        ".".join(g.split(".")[: i + 1])
        for g in json.loads(a.seen.read_text())
        for i in range(g.count(".") + 1)
    }
    unread = [
        x["identifier"][7:]
        for x in items(a.work / "items.json")
        if x.get("item_size") and x["identifier"][7:] not in seen
    ]
    logp = a.work / "log.tsv"
    rows = [line.rstrip("\n").split("\t") for line in open(logp)] if logp.exists() else []
    done = {r[3] for r in rows if r[0].startswith(a.prefix)}
    batch = len({r[0] for r in rows if r[0].startswith(a.prefix)})
    now, (hh, mm) = time.time(), (int(x) for x in a.until.split(":"))
    deadline = now - now % 86400 + hh * 3600 + mm * 60
    deadline += 86400 if deadline <= now else 0  # an hour already past today means tomorrow's
    fails, stop = 0, False
    with open(logp, "a") as log:
        for top in a.tops.split(","):
            files = []
            for item in sorted(i for i in unread if i.split(".")[0] == top):
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
            while files and not stop and time.time() < deadline:
                name, size, names, t0 = f"{a.prefix}_{batch:03d}", 0, [], time.time()
                while files and size < 1e9:
                    item, fname, fsize = files.pop(0)
                    while shutil.disk_usage("/").free < 70 * 2**30 + 2 * fsize:
                        time.sleep(60)
                    url = f"https://archive.org/download/usenet-{item}/{urllib.parse.quote(fname)}"
                    code = fetch(url, pool / fname)
                    if code not in ("200", "429"):
                        time.sleep(120)
                        code = fetch(url, pool / fname)
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
                built = subprocess.run(
                    ["nice", sys.executable, BUILD, pool, out, "1"], capture_output=True
                )
                for _item, fname in names:
                    (pool / fname).unlink()
                if (
                    built.returncode
                ):  # the batch is not charged as read, and a human looks before more
                    print(
                        "stop",
                        top,
                        name,
                        f"build {built.returncode}",
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
