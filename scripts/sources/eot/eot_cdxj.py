"""Read the End of Term web archive's CDXJ indexes into 2002 to 2013 hostname journals.

The nine parts (eotarchive S3, CC0; 2004: 2, 2008: 3, 2012: 4, 22.8 GB compressed) stream
through `scripts/harness/fetch.py --to -`, the one download path (robots, cap, sha256), and
never touch the disk. A line is `<surt> <14-digit stamp> {json}`: the crawler's stamp dates
the capture, kept when the JSON's status is 2xx or 3xx and the year is 2002 to 2013, one row
per (host, year), the earliest, as `{url, timestamp, status}` in
`data/raw/extended/eot_cdxj/eot_<part>.jsonl.gz`. The journal lands only when the receipt's
sha256 is the part's own, so a cut stream books nothing; a part with a journal is done, and
a failed one is retried after the others, three times at most (`.eot_<part>.failed`).

One part a run, none while the tick is held: the tick starts it after the bank as its own
user unit, `ark-eot`, so it outlives the tick (`scripts/harness/scheduled_sync.sh`). Peak disk
is one part's journal.

    uv run python scripts/sources/eot/eot_cdxj.py
"""

from __future__ import annotations

import gzip
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from ark.hostnames import host_of

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data/raw/extended/eot_cdxj"
URL = "https://eotarchive.s3.amazonaws.com/eot-index/collections/EOT-20{yy}/indexes/{part}.cdxj.gz"
PARTS = {  # each part's sha256, from the 10-18 read's receipts
    "eot04-cdx-00000": "32012123d16b88a592fbeead61d990b1b11cb6fd1fb4e680c135b5f0b2f521db",
    "eot04-cdx-00001": "7b3a826a4e0b20f0f0600e428f401eb06851ddd11dc255444a18f50041173d0c",
    "eot08-cdx-00000": "8e6fcb6efb09803a204cbfb6602514ea84c8e874d124c870a43be5aa0c5574cd",
    "eot08-cdx-00001": "92127ca9bd0cda280ec0d7a739648107731d43fa89ed076d9be87750bb369257",
    "eot08-cdx-00002": "29dd66f2c2720bbfcde1133c833b570cd9a189deb81687234c6538295a36aa69",
    "eot12-cdx-00000": "9e725795e64bd96b7657fab15da8331a540ec6f57537c504693285981734930d",
    "eot12-cdx-00001": "08f1740b7727df5db76b9509c2f6d38b80778c9bd28e768c7eb3c9d611e6249a",
    "eot12-cdx-00002": "6410840f6fabaa1f1fc17ced380d2475153ace884dec4241a9f042422a966561",
    "eot12-cdx-00003": "db0f59c7049ce66cadfaa4683ab1b421d966993ac1d2c6b7fef053d9294580e1",
}
YEARS = {str(y).encode() for y in range(2002, 2014)}
LINE = re.compile(rb"^\S+ (\d{14}) ")
STATUS = re.compile(rb'"status": ?"?([23]\d\d)')
URL_FIELD = re.compile(rb'"url": ?"((?:[^"\\]|\\.)*)"')
WARC = re.compile(rb'"filename": ?"([^"]*)"')


def earliest(lines, warcs: set | None = None) -> tuple[dict, int]:
    """(host, year) -> (timestamp, url, status), the earliest 2xx or 3xx capture a year, and
    how many urls did not decode, skipped; every line's WARC into `warcs`, given one."""
    keep: dict = {}
    broken = 0
    for raw in lines:
        if warcs is not None and (warc := WARC.search(raw)):
            warcs.add(warc.group(1))
        m = LINE.match(raw)
        if not m or m.group(1)[:4] not in YEARS or not (status := STATUS.search(raw)):
            continue
        if not (url := URL_FIELD.search(raw, m.end())):
            continue
        try:
            ts, original = m.group(1).decode(), json.loads(b'"' + url.group(1) + b'"')
        except ValueError:
            broken += 1
            continue
        host = host_of(original)
        if host and ((host, ts[:4]) not in keep or ts < keep[(host, ts[:4])][0]):
            keep[(host, ts[:4])] = (ts, original, status.group(1).decode())
    return keep, broken


def read(part: str) -> str:
    url = URL.format(yy=part[3:5], part=part)
    fetch = [sys.executable, str(REPO / "scripts/harness/fetch.py"), url, "--to", "-"]
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen([*fetch, "--max-bytes", "5G"], stdout=subprocess.PIPE, stderr=err)
        try:
            warcs: set = set()
            keep, broken = earliest(io.BufferedReader(gzip.GzipFile(fileobj=proc.stdout)), warcs)
        except (OSError, EOFError) as exc:  # a cut gzip stream
            proc.kill()
            keep, broken, warcs = {}, 0, set()
            print(f"{part}: stream broke, {exc}")
        proc.wait()
        err.seek(0)
        receipt = json.loads((err.read().decode().strip().splitlines() or ["{}"])[-1])
    OUT.mkdir(parents=True, exist_ok=True)
    if proc.returncode or receipt.get("sha256") != PARTS[part]:
        why = f"{part}: not booked, fetch exit {proc.returncode}, sha256 {receipt.get('sha256')}"
        with open(OUT / f".eot_{part}.failed", "a") as fh:
            fh.write(why + "\n")
        return why
    tmp = OUT / f".eot_{part}.tmp"
    with gzip.GzipFile(tmp, "wb", mtime=0) as raw, io.TextIOWrapper(raw) as fh:
        for ts, original, status in sorted(keep.values()):
            fh.write(json.dumps({"url": original, "timestamp": ts, "status": status}) + "\n")
    # the WARCs the part indexes, which #413's per-WARC CDX files are measured against
    (OUT / f".eot_{part}.warcs.gz").write_bytes(gzip.compress(b"\n".join(sorted(warcs)), mtime=0))
    os.replace(tmp, OUT / f"eot_{part}.jsonl.gz")
    return f"{part}: {len(keep)} host-years from {receipt['bytes']} bytes, {broken} urls broken"


def failures(part: str) -> int:
    marker = OUT / f".eot_{part}.failed"
    return len(marker.read_text().splitlines()) if marker.exists() else 0


def main() -> None:
    if subprocess.run(["bash", str(REPO / "scripts/harness/hold.sh"), "holds"]).returncode == 0:
        return print("eot: held")
    todo = [p for p in PARTS if not (OUT / f"eot_{p}.jsonl.gz").exists() and failures(p) < 3]
    print(read(min(todo, key=failures)) if todo else "eot: every part read or given up")


if __name__ == "__main__":
    main()
