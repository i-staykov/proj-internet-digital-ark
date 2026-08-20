"""Price a remote CDXJ before downloading it, by sampling it at many offsets.

Written for Arquivo.pt's `IA.cdxj`: 50.93 GB, 1996-2008, and the source class
`arquivo_ia` is already approved master, so anything it yields can be banked
without asking anyone. The store holds only 28,247 evidence rows from it and the
file is not on disk, so it was never fully taken.

**Sampling many offsets rather than one.** A head sample proves what the head
holds; that mistake has cost this project twice. This reads N slices spread evenly
through the file and reports the in-window share, the TLD mix and the net-new rate
against the live store, which is what decides whether 50 GB is worth moving.

    uv run python scripts/cdxj_remote_sample.py <url> --slices 24
"""

import argparse
import json
import re
import sys
import time
import urllib.request
from collections import Counter
from decimal import Decimal

import duckdb

sys.path.insert(0, "src")
from ark.canonical import to_registrable  # noqa: E402
from ark.english_share import weight_of  # noqa: E402

UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
STAMP = re.compile(r"^\S+\s+(\d{14})\s+(\{.*\})$")


def get(url: str, start: int, length: int) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Range": f"bytes={start}-{start + length - 1}"}
    )
    with urllib.request.urlopen(req, timeout=180) as fh:
        return fh.read().decode("utf-8", "replace")


def size_of(url: str) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return int(fh.headers["Content-Range"].split("/")[1])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("url")
    ap.add_argument("--slices", type=int, default=20)
    ap.add_argument("--bytes", type=int, default=400_000)
    args = ap.parse_args()

    size = size_of(args.url)
    print(f"{args.url}\n  {size:,} bytes ({size / 1e9:.2f} GB)")

    years: Counter = Counter()
    tlds: Counter = Counter()
    pairs = set()
    lines = 0
    sampled = 0

    for i in range(args.slices):
        offset = int(size * i / args.slices)
        try:
            blob = get(args.url, offset, args.bytes)
        except Exception as exc:  # noqa: BLE001
            print(f"  slice {i}: {exc}")
            continue
        sampled += len(blob)
        for line in blob.splitlines()[1:-1]:
            m = STAMP.match(line)
            if not m:
                continue
            lines += 1
            stamp = m.group(1)
            years[stamp[:4]] += 1
            if not ("1996" <= stamp[:4] <= "2001"):
                continue
            try:
                rec = json.loads(m.group(2))
            except Exception:
                continue
            url = rec.get("url") or ""
            dom = to_registrable(url)
            if not dom:
                continue
            tlds[dom.rsplit(".", 1)[-1]] += 1
            pairs.add((dom, int(stamp[:4])))
        time.sleep(0.2)

    inwin = sum(v for k, v in years.items() if k.isdigit() and 1996 <= int(k) <= 2001)
    print(f"  sampled {sampled:,} bytes over {args.slices} slices, {lines:,} parsed lines")
    print(f"  in-window lines: {inwin:,} ({100 * inwin / max(lines, 1):.1f}%)")
    print(f"  years: {dict(sorted(years.items())[:14])}")
    print(f"  in-window TLDs: {tlds.most_common(10)}")
    print(f"  distinct in-window pairs in the sample: {len(pairs):,}")

    if not pairs:
        return
    for _ in range(90):
        try:
            con = duckdb.connect("data/ark.duckdb", read_only=True)
            break
        except Exception:
            time.sleep(20)
    else:
        sys.exit("store stayed locked")

    con.execute("create temp table probe(domain varchar, y integer)")
    con.executemany("insert into probe values (?, ?)", sorted(pairs))
    held = con.execute(
        """
        select count(*) from probe p
        where exists (select 1 from domain_year d
                      where d.domain = p.domain and d.assigned_year = p.y)
        """
    ).fetchone()[0]
    new = [
        (d, y)
        for d, y in pairs
        if not con.execute(
            "select 1 from domain_year where domain = ? and assigned_year = ?", [d, y]
        ).fetchone()
    ]
    ee = sum((weight_of(d) for d, _ in new), Decimal(0))
    print(f"  already held: {held:,}   NET-NEW: {len(new):,}  ({ee:,.1f} EE)")

    if sampled:
        scale = size / sampled
        print("\n  EXTRAPOLATION, and it is an extrapolation rather than a measurement:")
        print(f"    the sample is 1/{scale:,.0f} of the file")
        print(f"    projected net-new pairs: {len(new) * scale:,.0f}")
        print(f"    projected net-new EE   : {ee * Decimal(scale):,.0f}")
        print("    the true figure is LOWER: distinct pairs saturate as more is read,")
        print("    and the sample counts each slice's names as if disjoint.")


if __name__ == "__main__":
    main()
