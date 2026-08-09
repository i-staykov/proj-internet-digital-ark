"""1996-1997 Yahoo! directory category pages, read for the sites they list.

The 8 August assessment of search-engine directory trees measured the family on
`dir.yahoo.com`, whose slice holds no 1996 and no 1997 captures at all, and it
measured it on code that could not see Yahoo's links. Both halves are now fixed,
so the family is re-measured here on the part of it that was never enumerated.

**Why 1996-1997 and not the rest.** Yahoo moved the catalogue to `dir.yahoo.com`
later; in the first two window years it lived under `www.yahoo.com/<Category>/`.
That population matters out of proportion to its size because 1996 is the store's
thinnest year by a wide margin, and a 1996 `.com` pair scores exactly the same
equivalent-English as a 2001 one.

**Where the value actually comes from, which is the opposite of the usual.** Every
other directory family here was scored on novelty and died of it: a curated list
selects for authority and authoritative names are what a CDX-derived baseline holds
first. This one is scored on YEARS. The store holds 8.0M domains but only 644k 1996
pairs, so roughly 92% of already-held domains have no 1996 assignment at all. A
Yahoo page listing names the store already knows is therefore the GOOD case, not
the bad one: each already-known name gains a 1996 or 1997 pair, and it is exactly
those names that survive the corroboration split.

**Why this walks the tree instead of enumerating it.** The obvious route is a CDX
prefix sweep. It does not work here: `www.yahoo.com/*` is one of the largest key
ranges in the index and the server gives up on it at a flat 60 s every time, as
does `www.yahoo.com/Business_and_Economy/*`. Measured 8 August, a full per-category
sweep produced nothing in 45 minutes. So pages are reached by walking the archived
catalogue itself, which costs strictly less: `web/<stamp>id_/<url>` served through
the nearest-capture redirect returns the real capture timestamp in the redirect
target and the stored bytes in the same request, so one archive request per page
buys the date, the content and the next level's links at once. A separate
enumeration would have cost one request per page on top of that and bought only
the list.

**Why pages are ranked by size.** The rule the WebRing work arrived at: on this
archive a page's stored length is what separates a real listing from a navigation
stub. Here the length is observed directly rather than read from CDX. Ranking
decides which children are worth descending into; it never decides what is
reported, because the first pass at this family quoted 21,000 EE from hand-picked
pages and measured 9,503 once the sample was drawn honestly.

**Evidence.** A Yahoo category page is a curated catalogue, so its capture date is
item-level evidence for the sites it lists, and records are written `curated`. That
assertion survives only for names another source already attests: run the journal
through `scripts/split_expansion_journal.py`, which sends everything else to the
candidate pool. Do not skip the split.

    uv run python scripts/collect_yahoo_directory.py --budget 20 --write
    uv run python scripts/collect_yahoo_directory.py --budget 1500 --workers 3 --write
"""

import argparse
import queue
import random
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import IO

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ark.cdx import (  # noqa: E402
    _RETRYABLE,
    _THROTTLE_STATUSES,
    REFUSED,
    USER_AGENT,
    RateGovernor,
)
from ark.expand import _HrefCollector, outbound_domains  # noqa: E402
from ark.journal import journal_writer, write_journal_line  # noqa: E402

OUT_DIR = ROOT / "data/raw/yahoo96"
SNAPSHOT = "https://web.archive.org/web"
FIRST, LAST = 1996, 1997

# One target date per naming era. Yahoo renamed its categories mid-window
# (`Business_and_Economy` in 1996 is `Business` in 1997) and both spellings have
# captures, so the walk starts twice and lets the redirect find the nearer one.
STARTS = [
    ("19961201000000", "http://www.yahoo.com/"),
    ("19970901000000", "http://www.yahoo.com/"),
]

# Yahoo's own machinery rather than catalogue branches. `bin` is the CGI tree and
# the `home*` paths are the front page's own furniture.
NOT_CATEGORIES = {"bin", "homet", "homem", "homeb", "headlines", "docs", "text", "picks", "search"}

_TIMESTAMP_LENGTH = 14


def snapshot_request(stamp: str, url: str) -> str:
    """Ask for the capture nearest a date, in the original stored bytes."""
    return f"{SNAPSHOT}/{stamp}id_/{url}"


def fetch_capture(stamp: str, url: str, timeout: float) -> tuple[int, str, str]:
    """Return (status, captured stamp, body) for the capture nearest `stamp`.

    The real capture date is not known in advance and is not worth a CDX request:
    Wayback redirects a dated request to the nearest capture, and the timestamp is
    in the URL it lands on. Reading it off the redirect is what makes the walk cost
    one request per page rather than two.
    """
    request = urllib.request.Request(
        snapshot_request(stamp, url), headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (https)
            body = response.read().decode("utf-8", "replace")
            landed = response.geturl()
            return response.status, captured_stamp(landed), body
    except urllib.error.HTTPError as exc:
        return exc.code, "", ""
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, "", ""


def fetch_through(gov: RateGovernor, stamp: str, url: str, timeout: float) -> tuple[int, str, str]:
    """One paced request, retrying only what a retry can fix.

    Same policy as `ark.cdx._fetch_retrying`, which cannot be reused directly
    because this route needs the landed URL as well as the body.
    """
    status, captured, body = 0, "", ""
    for attempt in range(3):
        gov.wait()
        status, captured, body = fetch_capture(stamp, url, timeout)
        if status == 200:
            gov.on_success()
            break
        if status in _THROTTLE_STATUSES:
            gov.on_throttle(refused=status == REFUSED)
        elif status not in _RETRYABLE:
            break
        if attempt >= 2:
            break
    return status, captured, body


def captured_stamp(landed_url: str) -> str:
    """The 14-digit capture stamp out of the URL a snapshot request landed on."""
    for part in landed_url.split("/"):
        digits = part.removesuffix("id_")
        if len(digits) == _TIMESTAMP_LENGTH and digits.isdigit():
            return digits
    return ""


def child_paths(html: str, page_url: str) -> list[str]:
    """Catalogue branches linked from a page, as absolute yahoo.com URLs.

    A branch is a directory path on Yahoo's own host. Query strings are the search
    form and the `bin` tree is CGI, so neither is a page of the catalogue.
    """
    collector = _HrefCollector()
    try:
        collector.feed(html)
    except Exception:  # noqa: BLE001 - a malformed page must not end the walk
        pass
    found: dict[str, None] = {}
    for href in collector.hrefs:
        parsed = urllib.parse.urlparse(urllib.parse.urljoin(page_url, href.strip()))
        if not parsed.netloc.endswith("yahoo.com") or parsed.query:
            continue
        segments = [s for s in parsed.path.split("/") if s]
        if not segments or not parsed.path.endswith("/") or segments[0] in NOT_CATEGORIES:
            continue
        if any("." in segment for segment in segments):
            continue
        found[f"http://www.yahoo.com{parsed.path}"] = None
    return list(found)


def walk(
    budget: int,
    workers: int,
    pause: float,
    timeout: float,
    seed: int,
    starts: list[tuple[str, str]],
    journal: IO[str] | None = None,
) -> list[dict]:
    """Breadth-first walk of the archived catalogue, one archive request per page.

    Frontier order is by the size of the page that revealed a branch, largest
    first, because a fat parent is where the fat children are. Ties are broken
    randomly from a fixed seed so a run replays exactly.

    Records are written as they are found rather than at the end, and the reason
    is not tidiness. Measured 8 August, archive.org refused this address for
    minutes at a stretch while two CDX engines shared it, and a walk holding an
    hour of answers in memory is an hour that a Ctrl-C throws away. The engines
    are worth more than this walk, so stopping it must always be cheap.
    """
    rng = random.Random(seed)
    gov = RateGovernor(delay=pause, max_delay=20.0)
    lock = threading.Lock()
    seen: set[str] = set()
    records: list[dict] = []
    stats: Counter = Counter()
    # (-parent size, jitter, target stamp, url); heap order via a sorted list is
    # not worth a dependency for a frontier this small, so use a PriorityQueue
    frontier: queue.PriorityQueue = queue.PriorityQueue()
    for stamp, url in starts:
        seen.add(f"{stamp[:4]}|{url}")
        frontier.put((0, rng.random(), stamp, url))

    def worker() -> None:
        while True:
            with lock:
                if len(records) >= budget:
                    return
            try:
                _, _, stamp, url = frontier.get(timeout=15.0)
            except queue.Empty:
                return
            status, captured, body = fetch_through(gov, stamp, url, timeout)
            year = int(captured[:4]) if captured else 0
            in_window = status == 200 and FIRST <= year <= LAST
            domains = outbound_domains(body, url) if in_window else []
            with lock:
                if len(records) >= budget:
                    return
                stats["fetched"] += 1
                stats["ok" if in_window else "unusable"] += 1
                stats["domains"] += len(domains)
                record = {
                    "domain": url,
                    "page_url": url,
                    "status": status if in_window else 0,
                    "timestamp": captured or None,
                    "year": year or None,
                    "curated": True,
                    "domains": domains,
                }
                records.append(record)
                if journal is not None:
                    write_journal_line(journal, record)
                print(
                    f"  [{len(records)}/{budget}] {captured or '-'} {url} "
                    f"{len(body):,}b -> {len(domains)} domains",
                    flush=True,
                )
            if not in_window:
                continue
            for child in child_paths(body, url):
                key = f"{stamp[:4]}|{child}"
                with lock:
                    if key in seen:
                        continue
                    seen.add(key)
                frontier.put((-len(body), rng.random(), stamp, child))

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    usable = [len(r["domains"]) for r in records if r["status"] == 200]
    usable.sort()
    by_year = Counter(r["year"] for r in records if r["status"] == 200)
    print(
        f"pages fetched: {stats['fetched']}, in-window 200s {stats['ok']}, "
        f"domains {stats['domains']}, "
        f"mean {stats['domains'] / max(stats['ok'], 1):.2f}, "
        f"median {usable[len(usable) // 2] if usable else 0}, "
        f"zero-yield {sum(1 for n in usable if n == 0)}/{len(usable)}, "
        f"capture years {dict(sorted(by_year.items()))}"
    )
    return records


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--budget", type=int, default=20, help="Pages to fetch, one request each.")
    ap.add_argument("--workers", type=int, default=2, help="Concurrent fetches; keep it modest.")
    ap.add_argument("--pause", type=float, default=1.0, help="Starting seconds between requests.")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--seed", type=int, default=1996, help="Tie-break seed, so a run replays.")
    ap.add_argument(
        "--target",
        default="",
        help="Aim the walk at one 14-digit date instead of both naming eras. "
        "Worth doing: the two years are worth very different amounts.",
    )
    ap.add_argument(
        "--start-url",
        default="http://www.yahoo.com/",
        help="Branch to walk from. The catalogue is very uneven, so starting inside "
        "the industry indexes is a different strategy, not a different sample.",
    )
    ap.add_argument("--out", type=Path, default=None, help="Journal to write.")
    ap.add_argument("--write", action="store_true", help="Write the journal.")
    args = ap.parse_args()

    starts = [(args.target, args.start_url)] if args.target else STARTS
    started = time.time()
    if not args.write:
        walk(args.budget, args.workers, args.pause, args.timeout, args.seed, starts)
        print(f"walked in {time.time() - started:.0f}s")
        print("dry run; pass --write to journal")
        return

    out = args.out or OUT_DIR / "yahoo96_expand.jsonl.gz"
    # `journal_writer` publishes under the real name however the run ends, so a
    # walk stopped early leaves a complete journal of a shorter walk
    with journal_writer(out) as fh:
        walk(args.budget, args.workers, args.pause, args.timeout, args.seed, starts, fh)
    print(f"walked in {time.time() - started:.0f}s")
    print(f"wrote {out}")
    print(f"next: uv run python scripts/split_expansion_journal.py {out} --write")


if __name__ == "__main__":
    main()
