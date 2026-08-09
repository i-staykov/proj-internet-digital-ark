"""Re-read the trade-press OCR already on disk with the corrected extractor.

`probe_texts_corpus.DOMAIN_RE` used to require two labels before the TLD, so it
read `www.foo.com` and dropped `foo.com`, `http://foo.com/` and `bob@foo.com`.
Printed copy drops the `www.` constantly, so the collector never saw a third of
the addresses on the pages it had already downloaded.

This is the third time on this project that the win was in bytes already on disk
rather than in a new corpus, after the UUCP maps and the Usenet address forms, so
it takes the same shape: no request is sent, the cached `_djvu.txt` under
`data/raw/texts/cache` is re-read, and the output is a collector journal in
exactly the format `split_trade_press.py` already consumes.

The year comes from the same place it always did, the item's publication year, so
nothing new is claimed about dating. It is recovered here from the journals the
collector already wrote and from the probe item lists, because the cache is keyed
by identifier alone.

Writes a new journal name rather than rewriting an ingested one, because the
ingest ledger keys on content hash and would rightly refuse a changed file under
an old name.

    uv run python scripts/reextract_trade_press.py --write
    uv run python scripts/split_trade_press.py \
        --journal data/raw/tradepress/tradepress_reextract_<stamp>.jsonl.gz \
        --tag reextract --write
"""

import argparse
import gzip
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from probe_texts_corpus import domains_in  # noqa: E402

from ark.journal import journal_writer, write_journal_line  # noqa: E402

CACHE = ROOT / "data/raw/texts/cache"
JOURNAL_DIR = ROOT / "data/raw/tradepress"
PROBE_DIR = ROOT / "data/raw/texts"
YEARS = range(1996, 2002)


def known_years() -> dict[str, int]:
    """identifier -> publication year, from every record already written about these items.

    Two places hold it and neither is complete on its own: the collector journals
    cover the items that yielded at least one domain, and the probe item lists
    cover the sampled items including the ones that yielded none.
    """
    years: dict[str, int] = {}
    for path in sorted(PROBE_DIR.glob("*_items.json")):
        try:
            for record in json.loads(path.read_text()):
                year = record.get("year")
                if record.get("identifier") and isinstance(year, int) and year in YEARS:
                    years.setdefault(record["identifier"], year)
        except (OSError, ValueError):
            continue
    for path in sorted(JOURNAL_DIR.glob("tradepress_*.jsonl.gz")):
        try:
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    year = record.get("year")
                    if record.get("identifier") and year in YEARS:
                        years.setdefault(record["identifier"], int(year))
        except (OSError, EOFError):
            continue
    return years


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--cache", type=Path, default=CACHE)
    args = ap.parse_args()

    years = known_years()
    cached = sorted(args.cache.glob("*.txt.gz"))
    print(f"{len(cached):,} cached OCR texts, {len(years):,} identifiers with a known year")

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = JOURNAL_DIR / f"tradepress_reextract_{stamp}.jsonl.gz"
    stats: Counter = Counter()
    pairs: set[tuple[str, int]] = set()
    records: list[dict] = []

    for index, path in enumerate(cached, start=1):
        identifier = path.name[: -len(".txt.gz")]
        year = years.get(identifier)
        if year is None:
            stats["no_year"] += 1
            continue
        try:
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except (OSError, EOFError):
            stats["unreadable"] += 1
            continue
        stats["items_read"] += 1
        for domain in sorted(domains_in(text)):
            if (domain, year) in pairs:
                continue
            pairs.add((domain, year))
            records.append(
                {
                    "domain": domain,
                    "year": year,
                    "identifier": identifier,
                    "collection": "tradepress",
                    "url": f"https://archive.org/details/{identifier}",
                }
            )
        if index % 200 == 0:
            print(f"  {index}/{len(cached)} items, {len(pairs):,} pairs", flush=True)

    print(f"\nitems read           : {stats['items_read']:,}")
    print(f"skipped, year unknown: {stats['no_year']:,}")
    print(f"skipped, unreadable  : {stats['unreadable']:,}")
    print(f"(domain, year) rows  : {len(pairs):,}")
    print(f"distinct domains     : {len({d for d, _ in pairs}):,}")

    if not args.write:
        print("\ndry run; pass --write to create the journal")
        return

    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    with journal_writer(out) as fh:
        for record in records:
            write_journal_line(fh, record)
    print(f"\nwrote {out}")
    print("\nnext:")
    print(f"  uv run python scripts/split_trade_press.py --journal {out} --tag reextract --write")


if __name__ == "__main__":
    main()
