"""Read the bare addresses in the Usenet bodies, the form nothing has ever read.

`domains_in_message` reads http(s) URLs, `www.` hosts and the `From:` header.
`collect_usenet_addresses.py` added `ftp://`, `mailto:` and typed email addresses.
All of those are anchored on a scheme, a `www.` label or an `@`. **The plain
`foo.com` written in running prose is read by none of them**, and in 1996-1999
that was an ordinary way to write down an address.

The reason it was refused is on the record and it is a real one: a bare name in
prose is often a company name, a file name or half an email address rather than
a site. What changes the answer is that **the corroboration split is the evidence
wall, not the pattern**. Every row here passes `split_by_corroboration`, so a
(domain, year) becomes a dated master record only when an independent lineage
already places that domain in `domain_year`. A string that is not a registered
domain cannot clear that, so it lands in the candidate pool and asserts nothing.

The same fix on the trade-press corpus on 8 August returned 816 net-new pairs and
509.84 equivalent-English from bytes already on disk, and the gained names were
654 `.com`, 72 `.net` and 57 `.org`.

Guards, all in `ark.usenet`: a TLD allowlist, a lookbehind that keeps the match
out of URLs and email addresses, a lookahead that refuses `end.Company`, greedy
labels so `foo.com.au` stays whole, an all-digits rule that refuses version
strings, and **body text only** so `Path:`, `Xref:` and `Newsgroups:` cannot turn
news servers and vanity newsgroup names into announced websites.

Every pair the existing extractor would already have found in the same message is
subtracted before it is written, so the journal holds the marginal set only.

Writes a journal, never opens the store, uses no network.

    uv run python scripts/collect_usenet_bare.py --sample 350 --workers 10
    uv run python scripts/collect_usenet_bare.py --workers 10
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

from ark.journal import journal_writer, write_journal_line  # noqa: E402
from ark.usenet import (  # noqa: E402
    bare_domains_in_body,
    body_of,
    domains_in_message,
    iter_messages,
    message_year,
)

USENET = ROOT / "data/raw/usenet"
OUT_DIR = ROOT / "data/raw/usenet_bare"
YEARS = range(1996, 2002)

_FROM = re.compile(rb"(?mi)^From:[ \t]*(.+)")
_DATE = re.compile(rb"(?mi)^Date:[ \t]*(.+)")


def pairs_in_archive(path: Path) -> tuple[str, set[tuple[str, int]], dict]:
    """(group, bare pairs no existing extractor sees, stats). Runs in a worker.

    Picklable and taking everything it needs as an argument, because macOS spawns
    workers rather than forking them and a global never reaches the child.
    """
    stats: Counter = Counter()
    extra: set[tuple[str, int]] = set()
    try:
        for raw in iter_messages(path):
            stats["messages"] += 1
            head = raw[:4000]
            match = _DATE.search(head)
            year = message_year(match.group(1).decode("latin-1", "replace")) if match else None
            if year not in YEARS:
                continue
            stats["in_window"] += 1
            text = raw.decode("latin-1", "replace")
            sender = _FROM.search(head)
            from_header = sender.group(1).decode("latin-1", "replace") if sender else ""
            # the whole message, deliberately wider than production, so anything
            # the shipped extractor could conceivably reach is subtracted
            current = set(domains_in_message(text, from_header))
            wider = set(bare_domains_in_body(body_of(raw)))
            new = wider - current
            if new:
                stats["messages_with_bare_hosts"] += 1
            for domain in new:
                extra.add((domain, year))
    except Exception as exc:  # noqa: BLE001
        # one unreadable archive must not void the batch around it
        stats[f"failed_{type(exc).__name__}"] += 1
        print(f"  skip {path.name}: {type(exc).__name__}: {exc}", flush=True)
    return path.stem.replace(".mbox", ""), extra, dict(stats)


def select(archives: list[Path], sample: int) -> list[Path]:
    """An evenly spaced sample of the sorted corpus.

    Even spacing rather than a random draw, because the archives are sorted by
    group name and the hierarchy is what varies: a stride walks `alt.*` through
    `comp.*` to `uk.*` in proportion, and it is reproducible without a seed.
    """
    if sample <= 0 or sample >= len(archives):
        return archives
    stride = len(archives) / sample
    return [archives[int(i * stride)] for i in range(sample)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--sample", type=int, default=0, help="evenly spaced N archives, 0 for all")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--tag", default="", help="suffix for the journal name")
    args = ap.parse_args()

    archives = sorted(USENET.glob("*.mbox.zip"))
    chosen = select(archives, args.sample)
    total_bytes = sum(p.stat().st_size for p in chosen)
    print(
        f"{len(chosen):,} of {len(archives):,} archives, {total_bytes / 1e9:.1f} GB, "
        f"{args.workers} workers"
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    suffix = f"_{args.tag}" if args.tag else ""
    out = args.out_dir / f"usenet_bare{suffix}_{stamp}.jsonl.gz"

    totals: Counter = Counter()
    written = 0
    seen: set[tuple[str, int]] = set()
    started = time.time()
    with journal_writer(out) as fh, ProcessPoolExecutor(max_workers=args.workers) as pool:
        for n, (group, extra, stats) in enumerate(
            pool.map(pairs_in_archive, chosen, chunksize=1), 1
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
                        # the archive ordinal, which is what lets a sample be fitted
                        # against archives processed rather than extrapolated linearly
                        "n": n,
                    },
                )
                written += 1
            if n % 50 == 0 or n == len(chosen):
                elapsed = max(time.time() - started, 1)
                print(
                    f"  {n:,}/{len(chosen):,} archives, {written:,} pairs, "
                    f"{n / elapsed * 3600:,.0f} archives/h",
                    flush=True,
                )

    print(f"\nwrote {out}")
    print(f"  messages {totals['messages']:,}, in window {totals['in_window']:,}")
    print(f"  in-window messages carrying a bare host: {totals['messages_with_bare_hosts']:,}")
    print(f"  distinct (domain, year) no existing extractor sees: {written:,}")
    failures = {k: v for k, v in totals.items() if k.startswith("failed_")}
    print(f"  archive failures: {failures or 'none'}")
    print(f"\nnext: uv run python scripts/project_usenet_bare.py --journal {out}")


if __name__ == "__main__":
    main()
