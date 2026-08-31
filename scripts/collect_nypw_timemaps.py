"""Fetch NYPW TimeMap parts and flatten each tarball into one ingestible CDX file.

**The artifact.** `https://archive.org/details/nypw_timemaps`, the Internet Archive's
"Not Your Parents' Web" TimeMaps, 26 yearly folders of tarballs. Each tarball holds one
`TM_x00o<YEAR>_<NNN>.txt` per sampled URI, and every line of one of those files is one
capture of that URI in eight space-delimited fields:

    https://4free.net/mousepads.shtml net,4free)/mousepads.shtml 20010124104200 \
        http://www.4free.net:80/mousepads.shtml text/html 200 NT5S4... 4009

Field 3 is Wayback's own 14-digit capture timestamp, written by the crawler, so a row
evidences the year it names and nothing else. The leading field is the URI that was
queried, which is why this is the `nypw_firstcdx` layout and not classic CDX: the
published example of a TimeMap row drops it and the two look alike at a glance.

**The folder year is the year of FIRST capture, not the year of the content**, so folder Y
can only add years Y+1..2001 to domains held at Y. The 1996 folder is therefore the
saturated head and the 2001 folder is held by construction; 1997-2000 is where the payload
is. That is what the 2026-08-24 closure got wrong by testing only 1996.

**Why the year filter lives here.** A TimeMap runs to 2021, and the in-window rows are a
small minority of the bytes. Writing the whole thing would put gigabytes on disk for
nothing, so out-of-window rows are dropped as they stream past. The line itself is copied
verbatim, and `parse_nypw_timemap` re-checks the window and the status independently.

**Terms, read in full before the first request.** The item is CC BY 4.0, stated in
`nypw_timemaps_readme.txt` ("You are free to share and adapt the material, provided that
appropriate credit is given"). `archive.org/robots.txt` is 238 bytes whole and disallows
only `/control/` and `/report/`; the download host the redirect lands on,
`ia800601.us.archive.org`, serves no robots.txt at all (404).

    uv run python scripts/collect_nypw_timemaps.py
    uv run ark ingest nypw_timemaps data/raw/nypw_timemaps/*.cdx.gz
"""

import argparse
import gzip
import re
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://archive.org/download/nypw_timemaps"
OUT = Path("data/raw/nypw_timemaps")
UA = "internet-digital-ark/1.0 (research; ivaylo.staykov@student.hpi.uni-potsdam.de)"
YEARS = range(1996, 2002)

# The three parts priced on 2026-09-01. The 2001 deeplinks part is here because it was
# measured, not because it pays: 108,863 of its 108,870 pairs were already held.
PARTS = (
    "2000/nypw_timemaps2000_deeplinks_part00o.tar.gz",
    "2000/nypw_timemaps2000_rootURLs_part02r.tar.gz",
    "2001/nypw_timemaps2001_deeplinks_part00o.tar.gz",
)
TIMEMAP = re.compile(r"(?:^|/)TM_[A-Za-z0-9]+_\d+\.txt$")


def fetch_to(url: str, path: Path) -> int:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=600) as response, path.open("wb") as out:
        shutil.copyfileobj(response, out, length=1 << 20)
    return path.stat().st_size


def in_window(line: str) -> bool:
    """True for a TimeMap row whose capture timestamp falls in 1996-2001."""
    parts = line.split()
    if len(parts) < 6:
        return False
    stamp = parts[2]
    return len(stamp) == 14 and stamp.isdigit() and int(stamp[:4]) in YEARS


def flatten(tarball: Path, destination: Path) -> tuple[int, int]:
    """Copy every in-window CDX row out of every TimeMap member into one gzip file."""
    read = kept = 0
    with tarfile.open(tarball, "r:gz") as tar, gzip.open(destination, "wt") as out:
        for entry in tar:
            if not entry.isfile() or not TIMEMAP.search(entry.name):
                continue
            handle = tar.extractfile(entry)
            if handle is None:
                continue
            with handle:
                for raw in handle:
                    read += 1
                    line = raw.decode("utf-8", errors="replace")
                    if in_window(line):
                        out.write(line if line.endswith("\n") else line + "\n")
                        kept += 1
    return read, kept


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parts", nargs="*", default=list(PARTS), help="paths under the item")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    failed = 0
    for part in args.parts:
        name = part.rsplit("/", 1)[-1].replace(".tar.gz", ".cdx.gz")
        destination = OUT / name
        if destination.exists():
            print(f"{name}: already written, skipping")
            continue
        with tempfile.TemporaryDirectory() as scratch:
            tarball = Path(scratch) / "part.tar.gz"
            try:
                size = fetch_to(f"{BASE}/{part}", tarball)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                print(f"could not fetch {part}: {exc}")
                failed += 1
                continue
            print(f"{part}: fetched {size:,} bytes")
            partial = destination.with_suffix(".partial")
            read, kept = flatten(tarball, partial)
            # A part that yields nothing in window is a parse failure, not a thin
            # part: every folder 1996-2001 is in window by construction. Saying so
            # here stops an empty file being renamed and then skipped as finished,
            # which is how a field-offset bug survived a whole run once.
            if not kept:
                print(f"{name}: {read:,} rows read and NONE in window, not written")
                partial.unlink()
                failed += 1
                continue
            # Rename only after a clean pass, so an interrupted run never leaves a
            # truncated file that the next run would take for finished and skip.
            partial.rename(destination)
        print(f"{name}: {read:,} rows read, {kept:,} in window")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
