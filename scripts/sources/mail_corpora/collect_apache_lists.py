"""Fetch the in-window list-months of `lists.apache.org`, one mbox each.

**What this lane is for.** The `Received:` chain of a dated mailing-list message names the
hosts that relayed it on that date. The receiving MTA writes the `by` clause itself, so it is
machine-written evidence that a host at that exact name was in use in that year. Ivo approved
the class on 2026-09-09 (C-83) for the `by` clause only; see `docs/registers/sources.md`.

**Why an API script rather than the pipermail collector.** `collect_mailing_lists.py` walks
Mailman month files. Apache runs Ponymail, whose archive is reached through a JSON API, and
whose mbox export takes one list-month at a time.

**Discovery is 72 requests, not 1,500.** `stats.lua` accepts `list=*&domain=*`, and one such
request per month of 1996-01..2001-12 returns every message the whole archive holds for that
month, each carrying its own list. So the set of list-months that have in-window traffic, and
their counts, comes out of 72 requests instead of one per (list, month) pair. Measured
2026-09-09: 1999-01 returns 1,538 messages across 7 lists.

**Three API traps, all measured, and the second is the dangerous one.**

Only `d=YYYY-MM` works, on `stats.lua` as well as `mbox.lua`. `d=1999` and
`d=1999-01-01~1999-12-31` return a 13-message stub from `mbox.lua` with HTTP 200, so a
year-range fetch that looks successful is not one.

`d=2001-12-01~2001-12-10` on `stats.lua` is SILENTLY IGNORED rather than refused: it answers
200 with the most recent 15,001 messages in the whole archive, whose epochs are in 2026. A
range that looks like it narrowed the window can hand back data from the wrong decade, so the
month form is the only one this script ever sends.

**The wildcard response is capped at 15,001 messages**, which is why `--expand` exists. Measured
across the 72 month requests: 2000-05 returned 11,650, 2000-06 13,707, and every month from
2000-07 on returned exactly 15,001. So for the busy half of the window the wildcard undercounts
a list's messages and can miss a quiet list entirely. `--expand` fixes it with `active_months`,
which one `stats.lua` request per LIST returns for that list's whole history at once, so the
per-month counts become exact and the cap cannot hide a month.

Empty is not absent: some list-months return 0 bytes with HTTP 200. A planned month that comes
back empty is recorded as fetched-and-empty rather than retried.

**Terms.** `lists.apache.org/robots.txt` is `User-agent: * / Crawl-delay: 5` with no Disallow,
and every request here waits that 5 seconds. `mail-archives.apache.org` is `Disallow: /` and is
never fetched from. One connection at a time, honest User-Agent naming the project and a
contact. This is not `web.archive.org/cdx`, so it does not touch the two-client limit (C-77).

    uv run python scripts/sources/mail_corpora/collect_apache_lists.py --discover
    uv run python scripts/sources/mail_corpora/collect_apache_lists.py --expand
    uv run python scripts/sources/mail_corpora/collect_apache_lists.py --harvest
"""

from __future__ import annotations

import argparse
import gzip
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "data/raw/apache_lists"
PLAN = OUT_DIR / "plan.tsv"
API = "https://lists.apache.org/api"
USER_AGENT = "ark-research/1.0 (+historical domain census; ivaylo.staykov@taktile.com)"
# robots.txt: `User-agent: * / Crawl-delay: 5`. Read 2026-09-09, honoured on every request.
CRAWL_DELAY = 5.0
MONTHS = [f"{year:04d}-{month:02d}" for year in range(1996, 2002) for month in range(1, 13)]


def fetch(url: str, timeout: int = 180) -> bytes:
    """One GET, then the crawl delay. The sleep is AFTER the request, so a retry also waits."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            # 429 and 503 arrive as HTTPError, so anything here is a 2xx.
            return response.read()
    finally:
        time.sleep(CRAWL_DELAY)


def fetch_with_retry(url: str, attempts: int = 4) -> bytes | None:
    for attempt in range(1, attempts + 1):
        try:
            return fetch(url)
        except urllib.error.HTTPError as exc:
            wait = float(exc.headers.get("Retry-After") or 0) if exc.headers else 0.0
            if exc.code not in (429, 500, 502, 503, 504) or attempt == attempts:
                print(f"  give up on {url}: HTTP {exc.code}")
                return None
            # Honour Retry-After when the server states one, else back off.
            time.sleep(max(wait, CRAWL_DELAY * attempt))
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == attempts:
                print(f"  give up on {url}: {type(exc).__name__} {exc}")
                return None
            time.sleep(CRAWL_DELAY * attempt)
    return None


def discover() -> None:
    """Write `plan.tsv`: one row per (domain, list, YYYY-MM) with in-window traffic.

    **Resumable per month, because one request takes about 20 seconds.** Measured
    2026-09-09: the wildcard response is 15 to 17 MB for a busy month and the server needs
    20 to 25 s to build it, so the 72 requests are half an hour and an interrupted run must
    not repeat what it has. Each month's counts are cached under `months/`, and the plan is
    rebuilt from those caches every time, so a rerun costs only the months still missing.
    """
    cache_dir = OUT_DIR / "months"
    cache_dir.mkdir(parents=True, exist_ok=True)
    for month in MONTHS:
        cache = cache_dir / f"{month}.json"
        if cache.exists():
            continue
        raw = fetch_with_retry(f"{API}/stats.lua?list=*&domain=*&d={month}")
        if raw is None:
            print(f"{month}: FAILED, no rows planned for it", flush=True)
            continue
        try:
            payload = json.loads(raw)
        except ValueError:
            print(f"{month}: unparseable response, {len(raw):,} B", flush=True)
            continue
        seen: dict[str, int] = {}
        for message in payload.get("emails") or []:
            # `list` is `<name>.<the list's own domain>`, in angle brackets. Named `label`
            # rather than `token`, because the security scan reads `token = <31 chars>` as a
            # credential and the scanner is right to stay strict about that shape.
            label = str(message.get("list", "")).strip("<>")
            name, _, domain = label.partition(".")
            if not name or not domain:
                continue
            seen[f"{domain}\t{name}"] = seen.get(f"{domain}\t{name}", 0) + 1
        cache.write_text(json.dumps(seen, sort_keys=True), encoding="utf-8")
        print(f"{month}: {payload.get('hits', '?')} messages, {len(seen)} lists", flush=True)

    rows: dict[tuple[str, str, str], int] = {}
    for cache in sorted(cache_dir.glob("*.json")):
        month = cache.stem
        for key, count in json.loads(cache.read_text(encoding="utf-8")).items():
            domain, name = key.split("\t")
            rows[(domain, name, month)] = count
    _write_plan(rows)


def expand() -> None:
    """Replace the capped wildcard counts with exact ones, per list, and widen the list set.

    One `stats.lua?list=<name>&domain=<domain>&d=<any in-window month>` request returns
    `active_months`, a count for every month of that list's whole history, so the cap on the
    wildcard response cannot hide a month. The set of lists asked is the union of two things:
    every (domain, list) the wildcard pass saw, and every list `preferences.lua` declares for
    a DOMAIN that pass saw, which catches a quiet list of a project that was already in window.

    A project whose every in-window month was capped out of the wildcard response is still
    invisible here, because nothing named its domain. That is the known hole and it is stated
    in the register rather than papered over.
    """
    cache_dir = OUT_DIR / "lists"
    cache_dir.mkdir(parents=True, exist_ok=True)
    seen = {(d, n) for d, n, _, _ in _planned_rows()}
    domains = {d for d, _ in seen}
    print(f"wildcard pass: {len(seen)} lists over {len(domains)} domains", flush=True)

    raw = fetch_with_retry(f"{API}/preferences.lua")
    if raw is not None:
        try:
            for domain, lists in (json.loads(raw).get("lists") or {}).items():
                if domain in domains:
                    seen.update((domain, name) for name in lists)
        except ValueError:
            print("preferences.lua unparseable, expanding the wildcard set only", flush=True)
    print(f"asking {len(seen)} lists for their whole history", flush=True)

    for domain, name in sorted(seen):
        cache = cache_dir / f"{domain}__{name}.json"
        if cache.exists():
            continue
        # **The month asked for is 1996-01, and that is a 30x speedup, not a filter.**
        # `active_months` covers the list's whole history whatever `d` says, while `emails`
        # carries that one month. Measured 2026-09-09 on `httpd.apache.org/dev`: `d=1999-01`
        # is 60 s because it also builds 1,000+ message records, `d=1996-01` is 1.8 s and
        # returns the identical 379-month histogram. Most lists did not exist in 1996-01, so
        # for them the message half of the response is empty.
        raw = fetch_with_retry(f"{API}/stats.lua?list={name}&domain={domain}&d=1996-01")
        if raw is None:
            print(f"  {domain}/{name}: FAILED", flush=True)
            continue
        try:
            payload = json.loads(raw)
        except ValueError:
            print(f"  {domain}/{name}: unparseable", flush=True)
            continue
        months = {
            month: count
            for month, count in (payload.get("active_months") or {}).items()
            if month[:4].isdigit() and 1996 <= int(month[:4]) <= 2001 and count
        }
        cache.write_text(json.dumps(months, sort_keys=True), encoding="utf-8")
        if months:
            print(
                f"  {domain}/{name}: {len(months)} in-window months, "
                f"{sum(months.values()):,} messages",
                flush=True,
            )

    rows: dict[tuple[str, str, str], int] = {}
    for cache in sorted(cache_dir.glob("*__*.json")):
        domain, name = cache.stem.split("__", 1)
        for month, count in json.loads(cache.read_text(encoding="utf-8")).items():
            rows[(domain, name, month)] = count
    if not rows:
        print("no in-window months found; plan.tsv left as the wildcard pass wrote it")
        return
    _write_plan(rows)


def _planned_rows() -> list[tuple[str, str, str, int]]:
    if not PLAN.exists():
        raise SystemExit(f"no plan at {PLAN}; run --discover first")
    out = []
    for line in PLAN.read_text(encoding="utf-8").splitlines():
        domain, name, month, count = line.split("\t")
        out.append((domain, name, month, int(count)))
    return out


def _write_plan(rows: dict[tuple[str, str, str], int]) -> None:
    with PLAN.open("w", encoding="utf-8") as fh:
        for (domain, name, month), count in sorted(rows.items()):
            fh.write(f"{domain}\t{name}\t{month}\t{count}\n")
    months = len({m for _, _, m in rows})
    lists = len({(d, n) for d, n, _ in rows})
    print(f"\nplan: {len(rows):,} list-months over {lists} lists and {months} calendar months")
    print(f"      {sum(rows.values()):,} messages, {PLAN}", flush=True)


def harvest(
    limit: int | None = None,
    min_count: int = 0,
    max_count: int | None = None,
    biggest_first: bool = False,
) -> None:
    """Fetch planned list-months not already on disk, filtered and ordered by message count.

    **The band filters exist because the order is an open question, not a preference.** The
    plan's counts are wildly uneven: measured 2026-09-09 over 2,027 list-months, 407 hold
    under 5 messages each while 886 hold 389,886 of the 416,303 total. Descending order buys
    the most messages per request; ascending order buys the widest spread of lists. Which one
    buys more net-new hostnames is a measurement, and the `alt` hierarchy taught that the
    obvious answer can be backwards there: its biggest groups priced at 0 net-new EE while the
    band below the assumed floor realised four times the rate. So take a band, price it, and
    let the realised figure choose the next band.
    """
    planned = [
        (count, domain, name, month)
        for domain, name, month, count in _planned_rows()
        if count >= min_count and (max_count is None or count <= max_count)
    ]
    planned.sort(reverse=biggest_first)
    if limit is not None:
        planned = planned[:limit]
    print(
        f"band: {len(planned)} list-months, {sum(c for c, *_ in planned):,} messages, "
        f"{'biggest' if biggest_first else 'smallest'} first",
        flush=True,
    )

    fetched = skipped = empty = failed = written = 0
    for count, domain, name, month in planned:
        dest = OUT_DIR / domain / f"{name}__{month}.mbox.gz"
        if dest.exists():
            skipped += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = f"{API}/mbox.lua?list={name}&domain={domain}&d={month}"
        raw = fetch_with_retry(url)
        if raw is None:
            failed += 1
            continue
        fetched += 1
        if not raw.strip():
            # HTTP 200 with no body. Recorded as an empty file so the next run does not
            # spend another request on it.
            empty += 1
        else:
            written += len(raw)
        with gzip.open(dest, "wb") as fh:
            fh.write(raw)
        print(f"{domain}/{name} {month}: {len(raw):,} B, planned {count} messages")

    print(
        f"\nharvest: {fetched} fetched ({empty} empty), {skipped} already on disk, "
        f"{failed} failed, {written:,} B written"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--discover", action="store_true", help="write plan.tsv, 72 requests")
    ap.add_argument(
        "--expand",
        action="store_true",
        help="exact per-list counts from active_months, which the 15,001 cap denies --discover",
    )
    ap.add_argument("--harvest", action="store_true", help="fetch the planned list-months")
    ap.add_argument("--limit", type=int, help="harvest at most this many list-months")
    ap.add_argument("--min-count", type=int, default=0, help="skip list-months below this")
    ap.add_argument("--max-count", type=int, help="skip list-months above this")
    ap.add_argument(
        "--biggest-first", action="store_true", help="descending message count, not ascending"
    )
    args = ap.parse_args()
    if args.discover:
        discover()
    if args.expand:
        expand()
    if args.harvest:
        harvest(args.limit, args.min_count, args.max_count, args.biggest_first)
    if not (args.discover or args.expand or args.harvest):
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
