"""`co.uk` answered where `uk` was refused. Is that a usable route?

The bulk probe found `matchType=domain` on a bare TLD blocked with 403 on every
variant, but `url=co.uk&matchType=domain` returned 200. Two readings, and they
differ by a factor of a million:

  (a) the block is on the label count, so any two-label name is allowed, and
      `co.uk` is being treated as an ordinary domain rather than as a suffix.
      Then it returns captures of the *host* `co.uk` and nothing under it, and
      it is worthless.

  (b) `matchType=domain` on `co.uk` genuinely returns everything under the
      public suffix, in which case one query enumerates the whole namespace.

The test distinguishes them directly: ask for `co.uk` with `matchType=domain`
and a high limit, then count how many distinct registrable domains come back.
Reading (a) predicts 1. Reading (b) predicts thousands.

    uv run python scripts/cdx_suffix_probe.py
"""

import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

sys.path.insert(0, "src")
from ark.canonical import to_registrable  # noqa: E402

UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
BASE = "https://web.archive.org/cdx/search/cdx"

SUFFIXES = ("co.uk", "org.uk", "ac.uk", "com.au", "co.nz", "co.za", "com.br")


def fetch(params: dict) -> tuple[str, list[str]]:
    url = f"{BASE}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=180) as fh:
            return "200", fh.read().decode("utf-8", "replace").splitlines()
    except urllib.error.HTTPError as exc:
        return f"HTTP{exc.code}", []
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{type(exc).__name__}", []


def main() -> None:
    status, rows = fetch({"url": "bbc.co.uk", "limit": 2})
    if status != "200":
        sys.exit(f"control failed ({status}); nothing below would mean anything")
    print("control OK\n")

    for suffix in SUFFIXES:
        status, rows = fetch(
            {
                "url": suffix,
                "matchType": "domain",
                "fl": "original,timestamp",
                "from": "1996",
                "to": "2001",
                "limit": 5000,
            }
        )
        if status != "200":
            print(f"{suffix:<10} {status}")
            time.sleep(4)
            continue
        doms = Counter()
        for line in rows:
            parts = line.split(" ")
            if not parts:
                continue
            dom = to_registrable(parts[0])
            if dom:
                doms[dom] += 1
        distinct = len(doms)
        verdict = (
            "ONE HOST ONLY, worthless"
            if distinct <= 2
            else f"MANY: {distinct:,} distinct registrable domains"
        )
        print(f"{suffix:<10} 200  {len(rows):,} rows  ->  {verdict}")
        if distinct > 2:
            print(f"           sample: {[d for d, _ in doms.most_common(6)]}")
        time.sleep(4)


if __name__ == "__main__":
    main()
