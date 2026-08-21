"""Enumerate the Alexa crawl collections on archive.org that fall inside 1996-2001.

**Why this is a different shape from everything else tried.** Every archive route
in the register queries `web.archive.org` one domain at a time and is rate-limited
to about 17,500 queries a day. These items are the *original Alexa crawls* that the
Wayback Machine was built from, and each ships its own `.cdx.gz`: a bulk capture
index, roughly 600 MB compressed, listing every URL the crawl saw with its
timestamp. One file is worth more raw captures than a week of per-domain querying,
and it comes from `archive.org/download/`, which is a different service.

The evidence type is `cdx_timestamp`, self-dating, and already approved master, so
this needs no new decision from anyone.

**The obvious objection, and why it has to be measured rather than argued.** Law 1
in `docs/discovery.md` says an Internet-Archive-derived corpus cannot be net-new
against an IA-derived baseline. The stated exception is a *bulk projection* of IA
holdings, which is what `dartmouth_nber_captures` was and why it paid 227,273
pairs. Whether these files are that exception is an empirical question about
overlap, and `--sample` answers it on one file before anything is bulk-fetched.

    uv run python scripts/alexa_crawl_index.py --list
    uv run python scripts/alexa_crawl_index.py --sample <identifier>
"""

import argparse
import gzip
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from decimal import Decimal
from pathlib import Path

UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
COLLECTIONS = ("20thcenturyweb", "alexa_1999", "greencrawl", "alexacrawls")
OUT = Path("data/raw/alexa")


def get(url: str, timeout: int = 180):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return json.load(fh)


def enumerate_items(collection: str, limit: int) -> list[dict]:
    """In-window items, via the scrape API which pages properly."""
    out: list[dict] = []
    cursor = None
    while len(out) < limit:
        params = {
            "q": f"collection:{collection} AND year:[1996 TO 2001]",
            "fields": "identifier,year,item_size",
            "count": 1000,
        }
        if cursor:
            params["cursor"] = cursor
        url = "https://archive.org/services/search/v1/scrape?" + urllib.parse.urlencode(params)
        try:
            page = get(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {collection}: {exc}", file=sys.stderr)
            break
        out.extend(page.get("items", []))
        cursor = page.get("cursor")
        if not cursor:
            break
        time.sleep(0.4)
    return out[:limit]


def cdx_files(identifier: str) -> list[tuple[str, int]]:
    try:
        meta = get(f"https://archive.org/metadata/{identifier}")
    except Exception:
        return []
    return [
        (f["name"], int(f.get("size") or 0))
        for f in meta.get("files", [])
        if f.get("name", "").endswith(".cdx.gz") and not f["name"].endswith(".arc.os.cdx.gz")
    ]


def sample(identifier: str) -> None:
    """Fetch one item's main CDX and measure what it would add."""
    files = cdx_files(identifier)
    if not files:
        sys.exit(f"{identifier} has no main .cdx.gz")
    name, size = max(files, key=lambda f: f[1])
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / name
    if not dest.exists():
        print(f"fetching {name} ({size / 1e6:.0f} MB)")
        subprocess.run(
            [
                "curl",
                "-sSL",
                "-A",
                UA,
                "--retry",
                "5",
                "--retry-delay",
                "20",
                "--retry-all-errors",
                "--max-time",
                "3600",
                "-o",
                str(dest),
                f"https://archive.org/download/{identifier}/{name}",
            ],
            check=False,
        )
    print(f"{dest}: {dest.stat().st_size / 1e6:.0f} MB")

    sys.path.insert(0, "src")
    from ark.canonical import to_registrable
    from ark.english_share import weight_of

    pairs: set[tuple[str, int]] = set()
    years: Counter = Counter()
    lines = 0
    with gzip.open(dest, "rt", errors="replace") as fh:
        for line in fh:
            parts = line.split(" ")
            if len(parts) < 3:
                continue
            lines += 1
            stamp = parts[1]
            if len(stamp) != 14 or not stamp.isdigit():
                continue
            years[stamp[:4]] += 1
            year = int(stamp[:4])
            if not (1996 <= year <= 2001):
                continue
            dom = to_registrable(parts[2])
            if dom:
                pairs.add((dom, year))

    print(f"  {lines:,} index lines, years {dict(sorted(years.items())[:10])}")
    print(f"  distinct in-window pairs: {len(pairs):,}")
    if not pairs:
        return

    import duckdb

    for _ in range(120):
        try:
            con = duckdb.connect("data/ark.duckdb", read_only=True)
            break
        except Exception:
            time.sleep(20)
    else:
        sys.exit("store stayed locked")
    con.execute("create temp table probe(domain varchar, y integer)")
    con.executemany("insert into probe values (?, ?)", sorted(pairs))
    new = con.execute(
        """
        select p.domain, p.y from probe p
        where not exists (select 1 from domain_year d
                          where d.domain = p.domain and d.assigned_year = p.y)
        """
    ).fetchall()
    ee = sum((weight_of(d) for d, _ in new), Decimal(0))
    print(f"  already held : {len(pairs) - len(new):,}")
    print(f"  NET-NEW      : {len(new):,}  ({100 * len(new) / len(pairs):.1f}%)  {ee:,.1f} EE")
    tld = Counter(d.rsplit(".", 1)[-1] for d, _ in new)
    print(f"  top TLDs     : {tld.most_common(8)}")
    mb = dest.stat().st_size / 1e6
    print(f"  {ee / Decimal(mb):,.1f} EE per MB downloaded")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--limit", type=int, default=3000)
    ap.add_argument("--sample")
    args = ap.parse_args()

    if args.sample:
        sample(args.sample)
        return

    OUT.mkdir(parents=True, exist_ok=True)
    seen: dict[str, dict] = {}
    for c in COLLECTIONS:
        items = enumerate_items(c, args.limit)
        print(f"{c}: {len(items):,} in-window items", file=sys.stderr)
        for it in items:
            seen[it["identifier"]] = it
    print(f"\n{len(seen):,} distinct in-window items", file=sys.stderr)
    total = sum(int(i.get("item_size") or 0) for i in seen.values())
    print(f"total item size: {total / 1e12:.2f} TB", file=sys.stderr)
    with (OUT / "items.json").open("w") as fh:
        json.dump(sorted(seen.values(), key=lambda i: i["identifier"]), fh, indent=1)
    for ident in sorted(seen):
        print(ident)


if __name__ == "__main__":
    main()
