"""Collect dated domain mentions from archive.org's scanned computer trade press.

A 1997 issue of a computing magazine that prints `foo.com` is a dated artifact
attesting `foo.com` for 1997, in exactly the sense `page_directory` already
accepts: the publication year is a property of the item, not something recovered
from a crawl. That property is what reaches 1996-1998, where the Internet
Archive's own coverage is thinnest and every capture-based route necessarily
struggles.

`scripts/probe_texts_corpus.py` measured the idea on 5 August rather than arguing
it, and the measurement is the reason this collector is scoped the way it is:

    query                          items  reachable  net-new pairs  per item
    boardwatch                        34         27            216       8.0
    collection:computermagazines      40         11            116      10.5
    collection:magazine_rack          40         18              7       0.4
    subject:(internet) books          60          3              2       0.7

**The corpus is not the variable that matters; the subject matter is.** Same
script, same extractor, same store: 10.5 net-new pairs an item on computer
magazines against 0.4 on the general magazine rack, a 26-fold difference. The
general rack in window is Amiga user-group zines and laboratory newsletters,
which print almost no URLs. Books are worse and for a different reason: 57 of 60
sampled in-window items publish no downloadable text at all. So this collector is
pointed at computing and internet titles and nothing else, and widening it is not
an improvement.

Two traps, both already paid for once:

**Redirects.** `archive.org/download` answers 302 to a data node, so a fetch that
does not follow redirects records a zero-byte success and the item looks empty
rather than unreachable. A body under 2 KB is what a restricted item returns and
is treated as no text.

**OCR fabricates domains.** Optical recognition of a 1990s page reads `rn` as `m`
and `l` as `1`, and a permissive dot-rule regex over that output turns sentence
punctuation into hostnames. The pattern is therefore anchored to the TLDs the
metric actually rewards and every match goes through the pinned public suffix
list, never hand-written splitting. That bounds fabrication but does not remove
it, which is why the split in `split_trade_press.py` is not optional.

Writes a journal and never opens the store, so it runs safely beside the
collectors and the ingest loop.

    uv run python scripts/collect_trade_press.py --discover
    uv run python scripts/collect_trade_press.py --limit 500
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from probe_texts_corpus import SEARCH, domains_in, fetch, full_text  # noqa: E402

from ark.journal import journal_writer, write_journal_line  # noqa: E402

OUT_DIR = ROOT / "data/raw/tradepress"
CACHE = ROOT / "data/raw/texts/cache"
YEARS = range(1996, 2002)

# Computing and internet titles only, for the 26-fold reason in the docstring.
#
# Measured with `--discover` on 8 August rather than assumed, which corrected the
# first version of this list: `boardwatch`, `pcmag`, `wired-magazine` and
# `internet-magazines` are NOT collections and return zero as `collection:` terms.
# Boardwatch is reachable as a free-text term, which is how the 5 August probe
# found its 34 items and 8.0 net-new pairs each, so it appears here unprefixed.
# In-window counts: computermagazines 4,030, byte-magazine 49.
#
# Deliberately excluded: `magazine_rack` (34,287 items, measured 0.4 net-new pairs
# each) and `folkscanomy_computer` (518 items, measured 36 of 40 unreachable and 2
# net-new pairs from 40). Both are already in the rejected table of docs/sources.md
# and adding item count is not the same as adding yield.
DEFAULT_QUERY = "collection:computermagazines OR collection:byte-magazine OR boardwatch"


def enumerate_items(query: str, page_size: int = 500, max_pages: int = 40) -> list[dict]:
    """Every in-window item for the query, paginated.

    `probe_texts_corpus.search` takes a single page because a probe only needs a
    sample. A collector needs the corpus, and archive.org caps `rows`, so this
    walks pages until one comes back short.
    """
    items: list[dict] = []
    for page in range(1, max_pages + 1):
        params = urllib.parse.urlencode(
            {
                "q": f"({query}) AND mediatype:texts AND year:[1996 TO 2001]",
                "rows": str(page_size),
                "page": str(page),
                "output": "json",
            },
            doseq=True,
        )
        params += "&fl%5B%5D=identifier&fl%5B%5D=year&fl%5B%5D=title&fl%5B%5D=collection"
        payload = json.loads(fetch(f"{SEARCH}?{params}"))
        docs = payload["response"]["docs"]
        items.extend(docs)
        print(f"  page {page}: {len(docs)} items (running total {len(items):,})", flush=True)
        if len(docs) < page_size:
            break
        time.sleep(1.0)
    return items


def discover() -> None:
    """Which in-window computing text collections exist, and how big they are.

    Printed rather than acted on. The 5 August measurement showed the subject
    matter decides the yield, so a new collection is only worth adding after it
    has been probed with `probe_texts_corpus.py`, never on its item count.
    """
    for name in (
        "computermagazines",
        "boardwatch",
        "magazine_rack",
        "internet-magazines",
        "pcmag",
        "byte-magazine",
        "wired-magazine",
        "computer-and-video-games-magazine",
        "maccompendium",
        "linuxjournal",
        "drdobbs",
        "folkscanomy_computer",
    ):
        params = urllib.parse.urlencode(
            {
                "q": f"collection:{name} AND mediatype:texts AND year:[1996 TO 2001]",
                "rows": "0",
                "output": "json",
            }
        )
        try:
            payload = json.loads(fetch(f"{SEARCH}?{params}"))
            found = payload["response"]["numFound"]
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, KeyError) as exc:
            found = f"error: {type(exc).__name__}"
        print(f"  {name:<38} {found}")
        time.sleep(1.0)


def year_of(item: dict) -> int | None:
    raw = item.get("year")
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    text = str(raw or "")[:4]
    if text.isdigit() and int(text) in YEARS:
        return int(text)
    return None


def already_done() -> set[str]:
    """Identifiers any previous run journalled, so a rerun resumes rather than repeats."""
    seen: set[str] = set()
    for path in sorted(OUT_DIR.glob("tradepress_*.jsonl.gz")):
        try:
            import gzip

            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        seen.add(json.loads(line)["identifier"])
                    except (ValueError, KeyError):
                        continue
        except OSError:
            continue
    return seen


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--query", default=DEFAULT_QUERY)
    ap.add_argument("--limit", type=int, default=400, help="items to fetch this run")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--discover", action="store_true", help="list collection sizes and stop")
    args = ap.parse_args()

    if args.discover:
        print("in-window (1996-2001) item counts by collection:")
        discover()
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    print("enumerating the corpus")
    items = enumerate_items(args.query)
    done = already_done()
    fresh = [i for i in items if i.get("identifier") not in done and year_of(i)]
    print(f"{len(items):,} in-window items, {len(done):,} already journalled, {len(fresh):,} fresh")

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = OUT_DIR / f"tradepress_{stamp}.jsonl.gz"
    stats: Counter = Counter()
    pairs = 0
    with journal_writer(out) as fh:
        for n, item in enumerate(fresh[: args.limit], 1):
            identifier = item["identifier"]
            year = year_of(item)
            stats["items_tried"] += 1
            text = full_text(identifier, CACHE)
            if text is None:
                stats["no_text"] += 1
            else:
                stats["reachable"] += 1
                found = domains_in(text)
                stats["domains_found"] += len(found)
                for domain in sorted(found):
                    write_journal_line(
                        fh,
                        {
                            "domain": domain,
                            "year": year,
                            "identifier": identifier,
                            "collection": "tradepress",
                            "url": f"https://archive.org/details/{identifier}",
                        },
                    )
                    pairs += 1
            if n % 25 == 0:
                print(
                    f"  {n}/{min(len(fresh), args.limit)} items, "
                    f"{stats['reachable']} with text, {pairs:,} pairs",
                    flush=True,
                )
            time.sleep(args.delay)

    print(f"\nwrote {out}")
    print(f"  items tried      : {stats['items_tried']:,}")
    print(f"  full text present: {stats['reachable']:,}")
    print(f"  no text          : {stats['no_text']:,}")
    print(f"  (domain, year) rows written: {pairs:,}")
    print("\nnext: uv run python scripts/split_trade_press.py --write")


if __name__ == "__main__":
    main()
