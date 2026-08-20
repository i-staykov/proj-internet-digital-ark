"""Are the Arquivo.pt CDXJ collections really all out of window?

**Why re-ask a closed question.** The register closed everything except `AWP*` and
`IA` on 2026-08-15 by taking 206 ranged reads of 120,001 bytes each and finding no
in-window row. Every one of those reads was at the HEAD of a file. Five days later
the geoindex taught the same lesson twice: `host-linkage.tsv.gz` looked sorted for
2.4x longer than the check that cleared it, and nine of the geoindex's twelve
members are sharded while the one that was checked is not. **A head sample proves
what the head holds and nothing else.**

So this reads the head, the middle and the tail of each collection, and it carries
a positive control: `IA.cdxj` and `Roteiro.cdxj` are known in-window and ingested,
so if they do not show in-window rows the probe is broken rather than the
hypothesis confirmed.

    uv run python scripts/arquivo_window_probe.py --limit 40
"""

import argparse
import re
import urllib.error
import urllib.request
from collections import Counter

BASE = "https://arquivo.pt/datasets/cdxj/"
UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
STAMP = re.compile(rb"\s(\d{14})\s")
CHUNK = 200_000


def size_of(name: str) -> int:
    req = urllib.request.Request(BASE + name, headers={"User-Agent": UA}, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as fh:
        return int(fh.headers.get("Content-Length") or 0)


def slice_years(name: str, start: int, length: int) -> Counter:
    req = urllib.request.Request(
        BASE + name,
        headers={"User-Agent": UA, "Range": f"bytes={start}-{start + length - 1}"},
    )
    years: Counter = Counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as fh:
            blob = fh.read()
    except urllib.error.HTTPError as exc:
        years[f"HTTP{exc.code}"] += 1
        return years
    except Exception as exc:  # noqa: BLE001
        years[f"ERR:{type(exc).__name__}"] += 1
        return years
    for m in STAMP.finditer(blob):
        years[m.group(1)[:4].decode()] += 1
    return years


def probe(name: str) -> dict:
    try:
        size = size_of(name)
    except Exception as exc:  # noqa: BLE001
        return {"name": name, "error": str(exc)}
    spots = {
        "head": 0,
        "quarter": max(size // 4, 0),
        "middle": max(size // 2, 0),
        "tail": max(size - CHUNK, 0),
    }
    out = {"name": name, "size": size, "spots": {}}
    for label, offset in spots.items():
        years = slice_years(name, offset, CHUNK)
        out["spots"][label] = years
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args()

    req = urllib.request.Request(BASE, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as fh:
        page = fh.read().decode("utf-8", "replace")
    names = re.findall(r'href="([^"]+\.cdxj[^"]*)"', page)

    # Controls first and always: two collections known to be in window and ingested.
    controls = [n for n in ("IA.cdxj", "Roteiro.cdxj") if n in names]
    rest = [n for n in names if n not in controls]
    if args.only:
        rest = [n for n in rest if n in args.only]
    if args.limit:
        rest = rest[: args.limit]

    print("== CONTROLS: known in-window, so these MUST show 1996-2001 ==")
    for n in controls + rest:
        if n == rest[0] if rest else False:
            print("\n== TEST ==")
        r = probe(n)
        if "error" in r:
            print(f"  {n:<28} ERROR {r['error']}")
            continue
        inwin = 0
        allyears = Counter()
        for years in r["spots"].values():
            for y, c in years.items():
                allyears[y] += c
                if y.isdigit() and 1996 <= int(y) <= 2001:
                    inwin += c
        span = sorted(y for y in allyears if y.isdigit())
        flag = "  <-- IN WINDOW" if inwin else ""
        print(
            f"  {n:<28} {r['size'] / 1e9:7.2f} GB  years {span[0] if span else '?'}"
            f"-{span[-1] if span else '?'}  in-window rows {inwin:,}{flag}"
        )


if __name__ == "__main__":
    main()
