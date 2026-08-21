"""Find bulk CDX or URL-index files on archive.org that cover 1996-2001.

**Why this angle is different from everything tried so far.** The register's closed
routes all query `web.archive.org` per domain, which is rate-limited, or fetch a
named dataset. But archive.org items that hold web crawls usually ship a `.cdx.gz`
beside their WARCs, and a CDX file is a bulk, self-dating capture index: exactly
the shape that made `dartmouth_nber_captures` pay 227,273 pairs. It is fetched from
`archive.org/download/`, a different service from the CDX endpoint the collectors
meter against, so it competes with nothing.

The trick is finding the ones whose captures are in window. Most ArchiveBot and
Wide Crawl items are 2010 or later, so the search is filtered by the item's own
date and then each candidate's file list is checked for an index file.

Read-only metadata queries. Prints candidates; decides nothing.

    uv run python scripts/ia_bulk_index_hunt.py
"""

import json
import sys
import time
import urllib.parse
import urllib.request

UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
INDEX_SUFFIXES = (".cdx", ".cdx.gz", ".cdxj", ".cdxj.gz", "-index.txt", ".surt", ".surt.gz")

QUERIES = (
    "mediatype:web AND date:[1996-01-01 TO 2002-12-31]",
    "collection:webcrawls AND date:[1996-01-01 TO 2002-12-31]",
    '"cdx" AND date:[1996-01-01 TO 2002-12-31]',
    'subject:"web crawl" AND date:[1996-01-01 TO 2002-12-31]',
    "collection:web AND year:[1996 TO 2001]",
    '"url index" OR "capture index" OR "host index"',
    'title:("crawl") AND year:[1996 TO 2002]',
    "collection:archiveteam_urls",
    '"surt" AND mediatype:data',
)


def get(url: str, timeout: int = 90):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return json.load(fh)


def search(q: str, rows: int = 60):
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(
        {"q": q, "rows": rows, "output": "json"}
    )
    url += "&fl%5B%5D=identifier&fl%5B%5D=title&fl%5B%5D=year&fl%5B%5D=item_size"
    try:
        return get(url)["response"]
    except Exception as exc:  # noqa: BLE001
        print(f"  ! {q!r}: {exc}", file=sys.stderr)
        return {"numFound": 0, "docs": []}


def index_files(identifier: str):
    try:
        meta = get(f"https://archive.org/metadata/{identifier}")
    except Exception:
        return []
    return [
        (f.get("name"), int(f.get("size") or 0))
        for f in meta.get("files", [])
        if f.get("name", "").lower().endswith(INDEX_SUFFIXES)
    ]


def main() -> None:
    seen = {}
    for q in QUERIES:
        r = search(q)
        print(f"{r['numFound']:>8}  {q}", file=sys.stderr)
        for d in r["docs"]:
            seen[d["identifier"]] = d
        time.sleep(1.0)

    print(f"\n{len(seen)} distinct items; checking each for an index file\n", file=sys.stderr)
    hits = []
    for i, (ident, doc) in enumerate(sorted(seen.items())):
        files = index_files(ident)
        if files:
            total = sum(s for _n, s in files)
            hits.append((total, ident, doc.get("year"), files))
            print(f"  {total / 1e6:9.1f} MB  {ident[:52]:<52} {doc.get('year', '?')}")
        if i % 25 == 0:
            time.sleep(0.5)

    hits.sort(reverse=True)
    print(f"\n{len(hits)} items carry an index file. Largest:")
    for total, ident, year, files in hits[:20]:
        print(f"  {total / 1e6:9.1f} MB  {ident}  ({year})")
        for n, s in files[:3]:
            print(f"      {s / 1e6:9.1f} MB  {n}")


if __name__ == "__main__":
    main()
