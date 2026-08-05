"""Measure whether archived web-ring member lists carry usable dated domains.

Named in the phase-2 feedback and never pursued. A web ring published a member
list per ring, and an archived copy of that list carries a capture date, which
is the same artifact shape `page_directory` already accepts: a curated listing
whose capture timestamp dates the sites on it.

This is a **deliberately small** probe. Two collection engines are already
querying `web.archive.org`, so it takes a handful of captures with a delay
between them rather than crawling: the question is whether the pages exist in
window and how many domains one carries, and twenty pages answer that.

Usage:
    uv run python scripts/probe_webrings.py --pattern 'webring.org/*' --pages 12
"""

import argparse
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402

from ark.canonical import to_registrable  # noqa: E402
from ark.english_share import weight_of  # noqa: E402

STORE = Path("data/ark.duckdb")
CDX = "https://web.archive.org/cdx/search/cdx"
USER_AGENT = "internet-digital-ark research crawler (contact: ivaylo.staykov@taktile.com)"
HREF_RE = re.compile(r'href=["\']https?://([^/"\'?\s]+)', re.IGNORECASE)


def fetch(url: str, retries: int = 3) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    delay = 5.0
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503, 504) and attempt < retries - 1:
                time.sleep(float(exc.headers.get("Retry-After") or delay))
                delay *= 2
                continue
            raise
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def captures(pattern: str, limit: int, match: str, contains: str | None) -> list[tuple[str, str]]:
    """(timestamp, original) for in-window 200 captures of a URL pattern.

    `matchType=domain` rather than `prefix`, because the member lists are not
    under a path prefix: WebRing served them as query strings off the site root,
    `webring.org/?ring=railring;list`. A prefix query on `www.webring.org/*`
    returns nothing at all, which reads exactly like "this source does not exist"
    and is the reason the first pass wrote the whole family off.
    """
    query = urllib.parse.urlencode(
        {
            "url": pattern,
            "matchType": match,
            "from": "1996",
            "to": "2001",
            "filter": "statuscode:200",
            "fl": "timestamp,original",
            "collapse": "urlkey",
            "limit": str(limit),
        }
    )
    body = fetch(f"{CDX}?{query}").decode("utf-8", errors="replace")
    rows = []
    for line in body.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        if contains and contains not in parts[1]:
            continue
        rows.append((parts[0], parts[1]))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", required=True, help="URL or host to query")
    parser.add_argument("--match", default="domain", choices=("domain", "prefix", "exact"))
    parser.add_argument("--contains", help="keep only captures whose URL holds this substring")
    parser.add_argument("--pages", type=int, default=12, help="captures to fetch")
    parser.add_argument("--delay", type=float, default=3.0, help="seconds between fetches")
    args = parser.parse_args()

    rows = captures(args.pattern, args.pages * 40, args.match, args.contains)
    print(f"{len(rows)} in-window captures listed for {args.pattern}", flush=True)
    if not rows:
        print("no in-window captures: nothing to measure")
        return

    pairs: set[tuple[str, int]] = set()
    fetched = 0
    for timestamp, original in rows[: args.pages]:
        url = f"https://web.archive.org/web/{timestamp}id_/{original}"
        try:
            body = fetch(url).decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001 - one dead capture must not end the probe
            print(f"  fail {timestamp} {original}: {exc}", flush=True)
            time.sleep(args.delay)
            continue
        fetched += 1
        year = int(timestamp[:4])
        found = {
            registrable
            for host in HREF_RE.findall(body)
            if (registrable := to_registrable(host.lower()))
        }
        for domain in found:
            pairs.add((domain, year))
        print(f"  {timestamp} {original[:70]} -> {len(found)} domains", flush=True)
        time.sleep(args.delay)

    print(f"\nfetched {fetched} captures, {len(pairs):,} pairs")
    print(f"over {len({d for d, _ in pairs}):,} domains")

    for _ in range(6):
        try:
            conn = duckdb.connect(str(STORE), read_only=True)
            break
        except duckdb.IOException:
            time.sleep(10)
    else:
        raise SystemExit("store stayed locked")
    try:
        held = {
            (d, y)
            for d, y in conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall()
        }
    finally:
        conn.close()

    new_pairs = pairs - held
    print(f"net-new pairs {len(new_pairs):,}")
    years = Counter(y for _, y in new_pairs)
    print("years: " + ", ".join(f"{y}:{years[y]}" for y in sorted(years)))
    total = sum((weight_of(d) for d, _ in new_pairs), Decimal(0))
    mean = total / len(new_pairs) if new_pairs else Decimal(0)
    print(f"equivalent-English {total:.4f} (mean weight {mean:.4f})")


if __name__ == "__main__":
    main()
