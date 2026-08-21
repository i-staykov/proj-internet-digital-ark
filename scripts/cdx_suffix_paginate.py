"""Can a public-suffix CDX query enumerate a whole namespace by pagination?

`url=co.uk&matchType=domain` returns real distinct registrable domains rather
than one host, which the suffix probe established. If that result paginates, then
**one endpoint enumerates every `.co.uk` the Internet Archive ever saw**, and this
project's binding constraint disappears: it is bounded by ~17,500 per-domain
queries a day, and a namespace holds millions of names.

Three things have to hold and each is tested here rather than assumed:

1. `showNumPages` reports a page count for a suffix, so the work is bounded.
2. Successive `page=N` values return DIFFERENT domains, not the same first page.
   This is the one that would silently produce a huge file of duplicates.
3. The rows carry in-window timestamps, so they are `cdx_timestamp` evidence and
   not merely a list of names.

    uv run python scripts/cdx_suffix_paginate.py co.uk --pages 3
"""

import argparse
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


def fetch(params: dict, timeout: int = 300) -> tuple[str, list[str]]:
    url = f"{BASE}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            return "200", fh.read().decode("utf-8", "replace").splitlines()
    except urllib.error.HTTPError as exc:
        return f"HTTP{exc.code}", []
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{type(exc).__name__}", []


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("suffix", nargs="?", default="co.uk")
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--page-size", type=int, default=5)
    args = ap.parse_args()

    status, rows = fetch({"url": "bbc.co.uk", "limit": 2})
    if status != "200":
        sys.exit(f"control failed ({status}); nothing below would mean anything")
    print("control OK")

    status, rows = fetch({"url": args.suffix, "matchType": "domain", "showNumPages": "true"})
    print(f"\nshowNumPages({args.suffix}): {status} {rows[:1]}")
    npages = int(rows[0]) if status == "200" and rows and rows[0].strip().isdigit() else None
    if npages:
        print(f"  -> {npages:,} pages at the default page size")

    seen_per_page = []
    for page in range(args.pages):
        status, rows = fetch(
            {
                "url": args.suffix,
                "matchType": "domain",
                "fl": "original,timestamp",
                "from": "1996",
                "to": "2001",
                "pageSize": args.page_size,
                "page": page,
            }
        )
        if status != "200":
            print(f"  page {page}: {status}")
            break
        doms = set()
        years: Counter = Counter()
        for line in rows:
            parts = line.split(" ")
            if len(parts) < 2:
                continue
            dom = to_registrable(parts[0])
            if dom:
                doms.add(dom)
            if len(parts[1]) == 14 and parts[1].isdigit():
                years[parts[1][:4]] += 1
        seen_per_page.append(doms)
        print(
            f"  page {page}: {len(rows):,} rows, {len(doms):,} distinct domains, "
            f"years {dict(sorted(years.items()))}"
        )
        time.sleep(4)

    if len(seen_per_page) >= 2:
        overlap = seen_per_page[0] & seen_per_page[1]
        union = set().union(*seen_per_page)
        print(f"\npage 0 and page 1 share {len(overlap):,} domains")
        print(f"union across {len(seen_per_page)} pages: {len(union):,} distinct domains")
        if len(overlap) > 0.9 * min(len(seen_per_page[0]), len(seen_per_page[1])):
            print("  -> PAGINATION IS NOT WORKING: pages repeat, so this cannot enumerate.")
        else:
            print("  -> pages are disjoint, so the namespace CAN be enumerated this way.")


if __name__ == "__main__":
    main()
