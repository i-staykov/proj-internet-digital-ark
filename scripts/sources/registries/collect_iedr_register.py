"""Fetch the archived IE Domain Registry register listing, one page per letter.

The IE Domain Registry, run by University College Dublin Computing Services, regenerated the
WHOLE `.ie` register as static pages at `/statistics/{0-9,a..z}-doms.html` and the Wayback
Machine captured them. Each page carries its own machine-written date line, so the artifact
dates itself and no corroboration split applies.

**Three fetch details, each of which produced a false negative before it was fixed.**

1. `https`, not `http`. Port 80 on `web.archive.org` refuses connections while 443 answers, and
   curl's message for that is "Couldn't connect to server", which reads like a dead archive.
2. Follow redirects. Wayback 302s each letter to its own nearest capture, so a fetch without
   redirects returns 302 and **zero bytes**, indistinguishable from a page that is not archived.
3. Retry. The archive refuses roughly half our connections on a bad day, so a single failure is
   not a negative result. Never run two copies of this at once: the second overwrites the first's
   pages with empty files, which is how three pages came back as 0 bytes mid-measurement.

Pages are written to `data/raw/iedr/` and read by `parse_iedr_register`, which drops any page whose
own date line falls outside 1996-2001. That is not a formality: `l-doms.html` resolves to a 28 March
2002 edition.

    uv run python scripts/sources/registries/collect_iedr_register.py
    uv run ark ingest iedr_register data/raw/iedr
"""

import argparse
import time
import urllib.error
import urllib.request
from pathlib import Path

STAMP = "20011224093813"
BASE = (
    "https://web.archive.org/web/{stamp}/http://www.domainregistry.ie/statistics/{letter}-doms.html"
)
LETTERS = ["0-9"] + [chr(c) for c in range(ord("a"), ord("z") + 1)]
OUT = Path("data/raw/iedr")
UA = "internet-digital-ark/1.0 (research; ivaylo.staykov@student.hpi.uni-potsdam.de)"


def fetch(url: str, tries: int, pause: float) -> bytes | None:
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as response:
                body = response.read()
            if body:
                return body
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        if attempt < tries:
            time.sleep(pause)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stamp", default=STAMP, help="Wayback stamp to resolve each letter against")
    ap.add_argument("--tries", type=int, default=8, help="attempts per page before giving up")
    ap.add_argument("--pause", type=float, default=6.0, help="seconds between attempts")
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between pages")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    got = missing = skipped = 0
    for letter in LETTERS:
        path = OUT / f"{letter}-doms.html"
        if path.exists() and path.stat().st_size:
            skipped += 1
            continue
        body = fetch(BASE.format(stamp=args.stamp, letter=letter), args.tries, args.pause)
        if body is None:
            print(f"{letter}: no bytes after {args.tries} attempts")
            missing += 1
            continue
        path.write_bytes(body)
        print(f"{letter}: {len(body):,} bytes")
        got += 1
        time.sleep(args.delay)

    print(f"fetched {got}, already held {skipped}, unreachable {missing}, into {OUT}")
    # A missing page is a smaller source, not a wrong one, so this is not an error exit.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
