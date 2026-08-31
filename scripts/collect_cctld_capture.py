"""Fetch the four capture-dated ccTLD register listings.

**Two of these four could not be found from the source register's description**, which is why
this file exists: the register named "NIC Malta `.mt` register" and "`.nu` `notrenewed.cfm`"
and kept no URL for either. Both cost a search to recover, and both recovered a rule:

- **A CDX `limit` is a false zero.** `notRenewed.cfm` read as absent from `nunames.nu` after a
  `limit=2000` listing returned no match. The page exists; the limit truncated the listing
  before reaching it. Ask for the exact path with `matchType=exact` before believing an absence.
- **A registry's listing may not be on the registry's host.** NIC Malta's directory sits under
  `um.edu.mt/nic/`, the university that ran the registry. `nic.org.mt` has 162 captures in the
  whole window and its largest object is a 3,908-byte GIF, so no query against the registry's
  own hostname could have found it.

**`id_` on every URL, with the slash**, so the Wayback banner never enters the parsed bytes.
The missing slash in `id_/` is what made an earlier collection return the same 154,263-byte
interstitial for seven different objects, so the content guard below is not optional.

    uv run python scripts/collect_cctld_capture.py
"""

import argparse
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path("data/raw/cctld_capture")
UA = "internet-digital-ark/1.0 (research; ivaylo.staykov@student.hpi.uni-potsdam.de)"

# (capture, url, output name, a string the real artifact must contain)
OBJECTS = [
    (
        "20010414064415",
        "http://www.saudinic.net.sa/cgi-bin/indexing.cgi?AllSA=AllSA",
        "saudinic-allsa-20010414.html",
        "registered domains under .SA",
    ),
    (
        "20011222202631",
        "http://www.nunames.nu/notRenewed.cfm",
        "nu-notrenewed-20011222.html",
        "Expired",
    ),
    (
        "19980120012100",
        "http://www.isoc.org.il/domains.html",
        "isocil-domains-19980120.html",
        "Internet Domains in Israel",
    ),
    (
        "19980525073234",
        "http://www.um.edu.mt/nic/dir/",
        "ummt-nicdir-19980525.html",
        "List of organizations registered in Malta",
    ),
]


def fetch(url: str, tries: int, pause: float) -> bytes | None:
    """One object, retried, because web.archive.org answers roughly one request in five."""
    for attempt in range(1, tries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=240) as response:
                delay = response.headers.get("Retry-After")
                if delay:
                    time.sleep(min(float(delay), 300.0))
                return response.read()
        except urllib.error.HTTPError as error:
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
    for stamp, original, name, must_contain in OBJECTS:
        target = OUT / name
        if target.exists() and must_contain.encode() in target.read_bytes():
            print(f"  already held: {name} ({target.stat().st_size:,} bytes)")
            continue
        print(f"  fetching {name} from {stamp}")
        body = fetch(f"https://web.archive.org/web/{stamp}id_/{original}", args.tries, args.pause)
        # A size floor is not a content check: assert on what the artifact must say.
        if body is None or must_contain.encode() not in body:
            got = "nothing" if body is None else f"{len(body):,} bytes without {must_contain!r}"
            print(f"    FAILED: {got}")
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
