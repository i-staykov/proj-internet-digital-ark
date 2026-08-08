"""Extract the addresses the Usenet parser never looked at, across the whole corpus.

`domains_in_message` reads http(s) URLs, bare `www.` hosts and the `From:` header.
Three anchored things in the same messages it has never looked at:

    ftp://host/...          a real service address, and in 1996 often the only
                            address a software vendor published
    mailto:user@host        an explicit link rather than prose
    user@host in the body   typed, but anchored by `@` and a rewarded TLD

This is **not** the generic token scan already measured and rejected on
`alt.bbs.lists`, which found 1,972 invisible tokens worth at most 193
equivalent-English and visibly contaminated (`ads.my`, `article.pl`, `lol.ie`).
Every pattern here is anchored to a scheme, an `@`, or both, and every match goes
through the pinned public suffix list. The `From:` header is already accepted as
evidence on the argument that a mail system validated it; a body address is the
same string in the same message, typed by the same person.

Measured on a random 120-archive sample (2.17 GB, 3,263,224 messages, 1,377,441
in window) on 8 August: the current extractor found 109,299 pairs of which 21,574
net-new, and these patterns found **54,154 more pairs of which 14,581 net-new,
worth 10,188.6 equivalent-English**. 12,512 of those net-new pairs sit on domains
never seen anywhere, so they are candidate-only under the corroboration split and
the immediately-dated remainder is the smaller half.

**The linear extrapolation from that sample is 1.9M equivalent-English and it is
certainly wrong.** The corpus repeats the same addresses across groups, and this
project has already published a Usenet projection of 6.9 points that delivered
3.69. The sample is 0.58% of the corpus, so the honest position is that the shape
is proven and the total is not, which is why this walks the whole corpus and
measures rather than scaling the sample.

Writes a journal, never opens the store, uses no network.

    uv run python scripts/collect_usenet_addresses.py --workers 10
"""

import argparse
import re
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ark.canonical import to_registrable  # noqa: E402
from ark.journal import journal_writer, write_journal_line  # noqa: E402
from ark.usenet import INFRASTRUCTURE, domains_in_message, iter_messages, message_year  # noqa: E402

USENET = ROOT / "data/raw/usenet"
OUT_DIR = ROOT / "data/raw/usenet_addr"
YEARS = range(1996, 2002)

_FTP = re.compile(r"ftp://([A-Za-z0-9.-]+)")
_MAILTO = re.compile(r"mailto:\s*[^@\s]+@([A-Za-z0-9.-]+)")
# Anchored on both sides: a local part, an `@`, and a host that must end in a TLD
# the metric actually rewards. A generic dot rule over the same text fabricates
# domains out of sentence punctuation.
_ADDR = re.compile(
    r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\."
    r"(?:com|net|org|edu|gov|mil|uk|au|ca|nz|ie|za|us|de|fr|nl|se|it|jp))\b",
    re.IGNORECASE,
)
_FROM = re.compile(rb"(?mi)^From:[ \t]*(.+)")
_DATE = re.compile(rb"(?mi)^Date:[ \t]*(.+)")


def pairs_in_archive(path: Path) -> tuple[str, set[tuple[str, int]], dict]:
    """(group, pairs the current extractor misses, stats). Picklable, runs in a worker."""
    stats: Counter = Counter()
    extra: set[tuple[str, int]] = set()
    try:
        for raw in iter_messages(path):
            stats["messages"] += 1
            match = _DATE.search(raw[:4000])
            year = message_year(match.group(1).decode("latin-1", "replace")) if match else None
            if year not in YEARS:
                continue
            stats["in_window"] += 1
            text = raw.decode("latin-1", "replace")
            sender = _FROM.search(raw[:4000])
            from_header = sender.group(1).decode("latin-1", "replace") if sender else ""
            current = set(domains_in_message(text, from_header))
            wider: set[str] = set()
            for pattern in (_FTP, _MAILTO, _ADDR):
                for host in pattern.findall(text):
                    domain = to_registrable(host)
                    if domain and domain not in INFRASTRUCTURE:
                        wider.add(domain)
            for domain in wider - current:
                extra.add((domain, year))
    except Exception as exc:  # noqa: BLE001
        # One unreadable archive must not void the batch around it, which is the
        # lesson from the six hours a `Header` object cost on 6 August.
        stats[f"failed_{type(exc).__name__}"] += 1
        print(f"  skip {path.name}: {type(exc).__name__}: {exc}", flush=True)
    return path.stem.replace(".mbox", ""), extra, dict(stats)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="stop after N archives, 0 for all")
    args = ap.parse_args()

    archives = sorted(USENET.glob("*.mbox.zip"))
    if args.limit:
        archives = archives[: args.limit]
    total_bytes = sum(p.stat().st_size for p in archives)
    print(f"{len(archives):,} archives, {total_bytes / 1e9:.1f} GB, {args.workers} workers")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = OUT_DIR / f"usenet_addr_{stamp}.jsonl.gz"

    totals: Counter = Counter()
    written = 0
    seen: set[tuple[str, int]] = set()
    started = time.time()
    with journal_writer(out) as fh, ProcessPoolExecutor(max_workers=args.workers) as pool:
        for n, (group, extra, stats) in enumerate(
            pool.map(pairs_in_archive, archives, chunksize=1), 1
        ):
            totals.update(stats)
            for domain, year in sorted(extra):
                if (domain, year) in seen:
                    continue
                seen.add((domain, year))
                write_journal_line(
                    fh,
                    {
                        "domain": domain,
                        "year": year,
                        "message_id": group,
                        "group": group,
                        "url": f"https://archive.org/details/usenet-{group.split('.')[0]}",
                    },
                )
                written += 1
            if n % 250 == 0:
                rate = n / max(time.time() - started, 1) * 3600
                print(
                    f"  {n:,}/{len(archives):,} archives, {written:,} pairs, "
                    f"{rate:,.0f} archives/h",
                    flush=True,
                )

    print(f"\nwrote {out}")
    print(f"  messages {totals['messages']:,}, in window {totals['in_window']:,}")
    print(f"  distinct (domain, year) the current extractor misses: {written:,}")
    failures = {k: v for k, v in totals.items() if k.startswith("failed_")}
    print(f"  archive failures: {failures or 'none'}")
    print("\nnext: uv run python scripts/split_usenet_addresses.py --write")


if __name__ == "__main__":
    main()
