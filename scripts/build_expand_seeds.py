"""Turn the CDX engine's own hits into the next round of expansion seeds.

**This is the edge that closes the discovery loop.** Page expansion has existed here
since round 1, but every round of it was fed by a seed list a human chose: Yahoo
categories, the WWW Virtual Library, a curated directory. That makes it a source, and
sources run out. Feeding it from the engine's own output instead makes it a *cycle*:

    pool candidate -> CDX says it was live in 1996-2001 -> fetch that capture
      -> read the domains its page names -> those become pool candidates -> repeat

Every domain the engine dates is, by construction, a site that existed in the window,
and the sites a period page links to are overwhelmingly period sites too. So the
population this produces is far better targeted than any list of guessed names, and it
regenerates itself: each round's hits are the next round's seeds. It cannot exhaust
while the engine keeps finding anything.

**Ranking is a proxy and is labelled as one.** What a seed is worth is the number of
domains on its page that we do not already hold, times their English share, and none of
that is knowable before fetching. Two things are knowable and both correlate with it:
links are local, so an English-region page mostly names English-region domains, which
makes the seed's own TLD weight a usable stand-in for its harvest's weight; and a site
captured in several in-window years was a real, maintained site rather than a parked
name, so its page carries more links. Replace this with the measured net-new-per-page
once the loop has produced enough journals to measure it.

**Seed the page, not the site.** The first pilot seeded each dated domain's home page and
returned 0.1 net-new names per page: 11 of 27 captured home pages carried no outbound
link at all, because a small site of the period links inward and nowhere else. So a
second CDX query per domain asks which of its pages the archive holds, and the seeds are
the ones whose path looks like a page of links. That query is cheap, costs no page fetch,
and replaces the two wasted ones the first version spent per domain: IA folds
`http://www.x.com/` and `http://x.com/` onto the same key, which the pilot confirmed by
harvesting both forms and getting identical domains back.

**What the loop is actually worth, measured rather than assumed.** Growing the pool is
not the binding constraint: it already holds 2.5M names nobody has queried, against an
engine that clears about 600 an hour. The constraint is the pool's *quality*, and on that
this route is the best we have. Hit rate by where a candidate came from, over 27,955
answered queries: `ukwa_link_target`, names harvested from a link graph, **90.4%**;
`tucows_mention` 85.8%; `usenet_mention` 38.9%; the pool as a whole 46.0%. Names that a
period page linked to are roughly twice as likely to be datable as the pool average, so
the loop earns its place by what it feeds the queue, not by how much.
"""

import argparse
import gzip
import json
import re
import sys
import urllib.parse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ark.cdx import CDX_ENDPOINT, RateGovernor, _fetch_retrying, http_fetch  # noqa: E402
from ark.english_share import english_weights, weight_of  # noqa: E402

CDX_DIR = Path("data/raw/cdx")
EXPAND_DIR = Path("data/raw/expand")
DEFAULT_OUT = EXPAND_DIR / "loop" / "seeds.txt"
YEARS = range(1996, 2002)

# Paths that a page of outbound links tends to have. Crude on purpose: the point is to
# rank, not to classify, and the cost of a wrong guess is one fetch.
LINK_RICH = re.compile(
    r"(link|favou?rite|friend|resource|hotlist|bookmark|webring|/ring|related|cool|"
    r"sites|search|dir/|directory|index)",
    re.I,
)
# Not pages. A capture of a GIF costs a fetch and yields nothing.
NOT_A_PAGE = re.compile(
    r"\.(gif|jpe?g|png|bmp|zip|exe|pdf|css|js|ico|mp3|wav|au|class|tar|gz|ram|mov)$", re.I
)


def hit_domains(directory: Path, recent: int | None) -> dict[str, set[int]]:
    """Domains with an in-window capture, newest journals first."""
    journals = sorted(directory.glob("cdx_*.jsonl*"), reverse=True)
    journals = [p for p in journals if not p.name.endswith(".part")]
    if recent:
        journals = journals[:recent]
    hits: dict[str, set[int]] = defaultdict(set)
    for path in journals:
        opener = gzip.open if path.suffix == ".gz" else open
        try:
            with opener(path, "rt") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    years = [y for y in (record.get("years") or []) if y in YEARS]
                    if record.get("status") == 200 and years:
                        hits[record["domain"]].update(years)
        except (OSError, EOFError, gzip.BadGzipFile):
            continue
    return hits


def already_expanded(root: Path) -> set[str]:
    """Page URLs any expansion round has already settled, so none is fetched twice.

    Scans every round, not only this loop's own folder: rounds 1 to 5 were seeded from
    curated directories and their pages would otherwise be re-fetched here.
    """
    seen: set[str] = set()
    for path in root.rglob("expand*.jsonl*"):
        if path.name.endswith(".part"):
            continue
        opener = gzip.open if path.suffix == ".gz" else open
        try:
            with opener(path, "rt") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    if record.get("status") == 200 and record.get("page_url"):
                        seen.add(record["page_url"])
        except (OSError, EOFError, gzip.BadGzipFile):
            continue
    return seen


def pages_url(host: str, first: int, last: int, limit: int = 300) -> str:
    """Which pages of one host the archive holds, one CDX key range.

    `collapse=urlkey` returns each distinct URL once rather than every capture of it,
    which is what makes this one cheap query instead of thousands of rows.
    """
    query = urllib.parse.urlencode(
        {
            "url": host,
            "matchType": "host",
            "from": str(first),
            "to": str(last),
            "filter": "statuscode:200",
            "fl": "original",
            "collapse": "urlkey",
            "limit": str(limit),
        }
    )
    return f"{CDX_ENDPOINT}?{query}"


def rank_pages(urls: list[str], per_domain: int) -> list[str]:
    """The most link-looking pages first, the root as the fallback every site has."""
    scored = []
    for url in urls:
        if NOT_A_PAGE.search(url):
            continue
        path = urllib.parse.urlparse(url).path or "/"
        is_root = path in ("", "/", "/index.html", "/index.htm")
        # A deep path is likelier to be one page of content; a shallow named one is
        # likelier to be the site's link list.
        score = (2 if LINK_RICH.search(path) else 0) + (1 if is_root else 0)
        scored.append((-score, path.count("/"), len(url), url))
    scored.sort()
    return [row[3] for row in scored[:per_domain]]


def discover_pages(
    domains: list[str], per_domain: int, workers: int, delay: float
) -> dict[str, list[str]]:
    """One CDX query per domain, asking what it has rather than guessing."""
    governor = RateGovernor(delay=delay, max_delay=5.0)
    fetch = http_fetch(70.0)
    found: dict[str, list[str]] = {}

    def ask(domain: str) -> tuple[str, list[str]]:
        status, body = _fetch_retrying(
            pages_url(domain, min(YEARS), max(YEARS)), fetch, governor, 3
        )
        if status != 200:
            return domain, []
        urls = [line.strip() for line in body.splitlines() if line.strip().startswith("http")]
        return domain, rank_pages(urls, per_domain)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(ask, d): d for d in domains}
        for future in as_completed(futures):
            try:
                domain, urls = future.result()
            except Exception:  # noqa: BLE001 - one bad host must not end the build
                continue
            if urls:
                found[domain] = urls
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cdx-dir", type=Path, default=CDX_DIR)
    parser.add_argument("--expand-dir", type=Path, default=EXPAND_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--recent", type=int, default=0, help="Only the newest N CDX journals (0 = all)."
    )
    parser.add_argument("--limit", type=int, default=4000, help="Most seeds to write.")
    parser.add_argument("--domains", type=int, default=600, help="Domains to ask CDX about.")
    parser.add_argument("--per-domain", type=int, default=2, help="Seed pages per domain.")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument(
        "--roots-only",
        action="store_true",
        help="Skip page discovery and seed each domain's root. Measured at 0.1 net-new "
        "names per page, so this is here for comparison rather than for use.",
    )
    args = parser.parse_args()

    hits = hit_domains(args.cdx_dir, args.recent or None)
    done = already_expanded(args.expand_dir)
    weights = english_weights()

    scored = []
    for domain, years in hits.items():
        # Capped: the difference between a one-year and a three-year site is real, the
        # difference between five and six is noise.
        score = weight_of(domain, weights) * min(len(years), 3)
        scored.append((score, domain))
    scored.sort(key=lambda row: (-row[0], row[1]))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.roots_only:
        seeds = [f"http://{d}/" for _s, d in scored if f"http://{d}/" not in done][: args.limit]
        args.out.write_text("\n".join(seeds) + "\n" if seeds else "")
        print(f"hit domains {len(hits):,}; wrote {len(seeds):,} root seeds to {args.out}")
        return 0

    # Ask about more domains than we need seeds for: a domain whose only captures are
    # images contributes nothing, and that is not knowable before asking.
    ask_about = [d for _s, d in scored][: args.domains]
    pages = discover_pages(ask_about, args.per_domain, args.workers, args.delay)

    seeds = []
    for _score, domain in scored:
        for url in pages.get(domain, []):
            if url not in done and len(seeds) < args.limit:
                seeds.append(url)
    args.out.write_text("\n".join(seeds) + "\n" if seeds else "")

    link_rich = sum(1 for url in seeds if LINK_RICH.search(urllib.parse.urlparse(url).path or "/"))
    print(
        f"hit domains {len(hits):,}; pages already settled {len(done):,}; "
        f"asked CDX about {len(ask_about):,} domains, {len(pages):,} answered with pages; "
        f"wrote {len(seeds):,} seeds ({link_rich:,} link-looking) to {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
