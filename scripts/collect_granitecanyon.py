"""Fetch Granite Canyon's own list of the zones its nameserver could not load.

**What this is, and why a free-DNS operator published it.** Granite Canyon ran free secondary
DNS. Like every such operator it refused to publish a customer list, but unlike the others it
published a nightly list of the zones its BIND could not load, which gives away the same names.
`docs/sources.md` records the transferable form: **when a service hides its inventory behind a
login, look for its error log.** secondary.com, zoneedit.com, xname.org and freedns.com all
refused; this one did not.

**Seven objects and there are no more.** Fourteen probes across 2001-01 to 2002-04 collapse onto
six distinct `ZoneRejects/` editions, and the 1999 prune list is a seventh, separate file. A
seventh reject edition dated 26-May-2002 exists and is deliberately not fetched: out of window,
so it cannot date a year. The predecessor `zoneRejects.txt` is 9 names at 2000-03-03 and HTTP 403
at every later capture.

**What dates one item.** Each reject edition stamps its own generation instant in its bytes
(`Rejected Zone List: 7-May-2001 22:11 GMT`) and the capture timestamp fixes when the file
existed, so a row is Granite Canyon's nameserver holding that zone in its configuration at that
instant. The zone name was typed by a customer into a submission form, so the corroboration split
applies and only already-held names earn a year.

**`id_` on every URL, deliberately**, so the Wayback banner and rewritten links never enter the
bytes we parse.

    uv run python scripts/collect_granitecanyon.py
"""

import argparse
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path("data/raw/granitecanyon")
UA = "internet-digital-ark/1.0 (research; ivaylo.staykov@student.hpi.uni-potsdam.de)"
HOST = "http://soa.granitecanyon.com"

# (capture timestamp, path, expected bytes at collection, output name). The expected
# size is the one measured on 2026-08-29 and is a floor, not an equality test: the
# Wayback replay of the same capture is stable but not byte-guaranteed.
OBJECTS = [
    ("20010601000000", "/stale_30Nov1999.txt", 205_787, "prune-19991130.txt"),
    ("20010223195457", "/ZoneRejects/", 193_389, "zonerejects-20010223.html"),
    ("20010508024101", "/ZoneRejects/", 212_935, "zonerejects-20010508.html"),
    ("20010611192639", "/ZoneRejects/", 215_340, "zonerejects-20010611.html"),
    ("20010626115208", "/ZoneRejects/", 222_405, "zonerejects-20010626.html"),
    ("20010901062251", "/ZoneRejects/", 245_087, "zonerejects-20010901.html"),
    ("20011204210150", "/ZoneRejects/", 272_710, "zonerejects-20011204.html"),
]


def fetch(url: str, tries: int, pause: float) -> bytes | None:
    """One object, retried, because web.archive.org answers roughly one request in five."""
    for attempt in range(1, tries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=240) as response:
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    time.sleep(min(float(retry_after), 300.0))
                return response.read()
        except urllib.error.HTTPError as error:
            # 429, 503 and 504 are the archive under load; honour its own delay.
            if error.code in (429, 503, 504):
                delay = error.headers.get("Retry-After")
                time.sleep(min(float(delay), 300.0) if delay else pause)
            elif error.code in (403, 404):
                print(f"    HTTP {error.code}, not retrying")
                return None
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        if attempt < tries:
            time.sleep(pause)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tries", type=int, default=8)
    ap.add_argument("--pause", type=float, default=30.0)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    missing = []
    for stamp, path, expected, name in OBJECTS:
        target = OUT / name
        if target.exists() and target.stat().st_size >= expected * 0.9:
            print(f"  already held: {name} ({target.stat().st_size:,} bytes)")
            continue
        url = f"https://web.archive.org/web/{stamp}id_/{HOST}{path}"
        print(f"  fetching {name} from {stamp}")
        body = fetch(url, args.tries, args.pause)
        if body is None:
            print("    FAILED: nothing returned")
            missing.append(name)
            continue
        # A size floor is NOT a content check. The Wayback "Machine" interstitial is
        # 154,263 bytes and cleared a floor set at half of 193,389, so all six reject
        # editions arrived byte-identical and looked like a successful collection.
        # Every real object here is plain text or a pre-formatted zone listing and
        # none of them is an HTML5 document.
        if b"<!DOCTYPE html>" in body[:200] or b"<title>Wayback Machine" in body[:2000]:
            print(f"    FAILED: got the Wayback interstitial, not the artifact ({len(body):,} B)")
            missing.append(name)
            continue
        if len(body) < expected * 0.5:
            print(f"    FAILED: {len(body):,} bytes, expected about {expected:,}")
            missing.append(name)
            continue
        target.write_bytes(body)
        print(f"    wrote {len(body):,} bytes")

    if missing:
        print(f"\n{len(missing)} of {len(OBJECTS)} objects missing: {', '.join(missing)}")
        return 1
    print(f"\nall {len(OBJECTS)} objects held under {OUT}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
