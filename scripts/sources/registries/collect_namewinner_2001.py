"""Fetch namewinner.com's expiring-domain list, the 2001-10-26 capture.

**One in-window artifact exists and this is it.** `namewinner.com` has 21 captures of
`whole_list*.php` and only four carry content: the 2001-10-26 pair and the 2002-04 pair. Every
other capture is 373 to 415 bytes of empty or error page, including all four from December 2001.
So there is nothing to iterate over and no collector loop worth writing.

**`?del=tab` is the superset and it is plain TSV, not HTML** despite the `.php`: each row is
`NAME<TAB>25-OCT-01`. The `?del=none` capture of the same minute holds 16,125 of the same 20,943
names, so it is not worth fetching.

**Dotster's `rule_book.php` (capture `20011027003733`) calls it "our list of soon to be expiring
domain names"**, which is what makes the artifact a registrar statement that these names are
registered right now rather than a list of names somebody liked.

    uv run python scripts/sources/registries/collect_namewinner_2001.py
    uv run ark ingest namewinner_expiring data/raw/namewinner/*.tsv
"""

import argparse
import time
import urllib.error
import urllib.request
from pathlib import Path

CAPTURE = "20011026120205"
URL = f"https://web.archive.org/web/{CAPTURE}id_/http://namewinner.com/whole_list.php?del=tab"
OUT = Path("data/raw/namewinner") / f"namewinner-whole_list-{CAPTURE[:8]}.tsv"
UA = "internet-digital-ark/1.0 (research; ivaylo.staykov@student.hpi.uni-potsdam.de)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tries", type=int, default=8)
    ap.add_argument("--pause", type=float, default=30.0)
    args = ap.parse_args()

    if OUT.exists() and OUT.stat().st_size > 100_000:
        print(f"{OUT} already held ({OUT.stat().st_size:,} bytes)")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # web.archive.org answers roughly one request in five under load, so a single
    # attempt reads as a dead source when it is a busy one.
    for attempt in range(1, args.tries + 1):
        try:
            request = urllib.request.Request(URL, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=240) as response:
                body = response.read()
            if len(body) > 100_000:
                OUT.write_bytes(body)
                print(f"wrote {OUT} ({len(body):,} bytes)")
                return 0
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        if attempt < args.tries:
            time.sleep(args.pause)
    print(f"could not fetch {URL} after {args.tries} attempts")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
