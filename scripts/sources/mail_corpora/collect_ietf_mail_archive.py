"""Relay hostnames from the `Received: ... by <host>` clause of the IETF mail archive.

Writes the `{item, year, text}` shards `ark ingest-ietf-header-hostnames` reads, the same
shape `build_apache_header_pool.py` writes for lists.apache.org.

    uv run python scripts/sources/mail_corpora/collect_ietf_mail_archive.py plan
    uv run python scripts/sources/mail_corpora/collect_ietf_mail_archive.py sweep

**This is C-83's class at a second host, not a new class.** Ivo approved the `by` clause
alone on 2026-09-09 for the receiving MTA's own name, and the reading here is that lane's
own code: `BOUNDARY`, `unfold`, `by_hosts` and `IN_WINDOW` are imported from
`build_apache_header_pool.py` rather than re-typed, so an ietf.org figure is comparable to
the Apache one. The `from` clause, the parenthesised reverse-DNS and `Message-ID` hosts are
not read here either, for the reasons that lane's docstring gives.

**What dates one item** is the message's own RFC 822 `Date:` header, cross-checked against
the `YYYY-MM` the archive filed the month under. A message whose `Date:` year disagrees with
its partition is DROPPED rather than assigned to either, the same rule the Apache lane runs.
On the fleet's 13.61% sample that was 2,158 of 39,385 messages, 5.5%.

**This corpus is TWO mailbox formats and reading it as one loses 89 MB of it.** The
`ietf-mail-archive` months are mbox, delimited by a `From <envelope> <ctime>` line. The
`concluded-wg-ietf-mail-archive` months are MMDF, delimited by a line of four `\\x01` bytes
with no `From ` line anywhere in the file. Running the Apache mbox boundary alone over
`822ext/1996-08` returned 0 messages from 247,156 bytes that hold 52 of them, silently,
which is the boundary defect `docs/lore/traps.md` already paid for once. MMDF writes a
delimiter both before and after every message, so a message is counted at flush and only
when its header block is non-empty, never at the boundary itself.

**A month file is read off the socket and never written to disk.** The partition is 1.49 GB
across 4,850 in-window list-months and none of it is an artifact we keep: `curl` writes into
a pipe, the parser reads lines as they arrive, and what lands on disk is the derived
`{item, year, text}` shard. That is the same rule the CDX collectors run under and it is why
this lane does not need a `data/raw` budget.

**One connection, because six drew a 429 inside a minute.** Measured by the fleet's scout on
2026-09-09: six parallel listing requests were throttled within the minute, while one
connection with a pause did 130 listings in 97 seconds untouched. `robots.txt` (read
2026-09-10) disallows only `/admin/` and `/search/` and states no crawl delay, so the delay
here is the measured one and not a stated one.

Both modes are resumable, because `plan` is about 20 minutes of listings and `sweep` is
hours: `plan` caches one TSV per list directory and re-reads it instead of re-fetching, and
`sweep` appends each finished stem to `swept.txt` and skips what is already there.
"""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location(
    "apache_header_pool", ROOT / "scripts/sources/mail_corpora/build_apache_header_pool.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
BOUNDARY, unfold, by_hosts, IN_WINDOW = _mod.BOUNDARY, _mod.unfold, _mod.by_hosts, _mod.IN_WINDOW

from ark.usenet import message_year  # noqa: E402

HOST = "www.ietf.org"
BASE = f"https://{HOST}/ietf-ftp"
# Both halves of the partition. The concluded working groups are the MMDF half.
TREES = ("ietf-mail-archive", "concluded-wg-ietf-mail-archive")
USER_AGENT = "ark-research/1.0 (+historical domain census; ivaylo.staykov@taktile.com)"
# robots.txt states no crawl delay; this is the scout's measured safe rate, 130 in 97 s.
CRAWL_DELAY = 0.75

OUT_DIR = ROOT / "data/raw/ietf_mail_archive"
LIST_CACHE = OUT_DIR / "lists"
PLAN = OUT_DIR / "plan.tsv"
SWEPT = OUT_DIR / "swept.txt"
STATS = OUT_DIR / "sweep.stats"
ITEMS_DIR = ROOT / "data/raw/ietf_header_items"

# nginx autoindex rows. A directory ends in `/`; a month file is `YYYY-MM` (1996 to 1998) or
# `YYYY-MM.mail` (1998 on), and the size column is rounded to K or M by the server.
DIR_ROW = re.compile(r'<a href="([^"/?][^"?]*)/">')
# The K/M/G form leads the alternation: `\d+` would otherwise match the `40` of `40K` and
# silently under-read every rounded size by three orders of magnitude.
FILE_ROW = re.compile(r'<a href="([^"/?][^"?]*)">[^<]*</a>\s+\S+\s+\S+\s+(\d+\.?\d*[KMG]|\d+)')
MONTH_FILE = re.compile(r"^(?P<month>(?:199[6-9]|200[01])-(?:0[1-9]|1[0-2]))(?P<ext>\.mail)?$")
MMDF = re.compile("^\x01\x01\x01\x01\\s*$")

STAT_KEYS = (
    "messages",
    "in_window",
    "with_hosts",
    "no_by_host",
    "undated",
    "out_of_window",
    "year_disagrees",
    "records",
)


def sized(token: str) -> int:
    """The listing's own size column, rounded by nginx to K or M. Used only to rank work."""
    scale = {"K": 1024, "M": 1024**2, "G": 1024**3}.get(token[-1].upper())
    return int(float(token[:-1]) * scale) if scale else int(token)


def fetch(url: str, timeout: int = 120) -> bytes:
    """One GET, then the crawl delay. The sleep is AFTER the request, so a retry also waits."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
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
                print(f"  give up on {url}: HTTP {exc.code}", flush=True)
                return None
            # Honour Retry-After when the server states one, else back off.
            time.sleep(max(wait, CRAWL_DELAY * attempt * 4))
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == attempts:
                print(f"  give up on {url}: {type(exc).__name__} {exc}", flush=True)
                return None
            time.sleep(CRAWL_DELAY * attempt * 4)
    return None


def months_of(tree: str, listname: str) -> list[tuple[str, int]]:
    """`(filename, listed bytes)` for one list directory's in-window months, cached on disk."""
    cache = LIST_CACHE / f"{tree}__{listname}.tsv"
    if cache.is_file():
        return [
            (name, int(size))
            for name, size in (ln.split("\t") for ln in cache.read_text().split("\n") if ln)
        ]
    page = fetch_with_retry(f"{BASE}/{tree}/{listname}/")
    found: list[tuple[str, int]] = []
    if page is not None:
        for name, size in FILE_ROW.findall(page.decode("utf-8", "replace")):
            name = html.unescape(name)
            if MONTH_FILE.match(name):
                found.append((name, sized(size)))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("".join(f"{n}\t{s}\n" for n, s in sorted(found)))
    return found


def plan() -> int:
    """Write `plan.tsv`: one row per in-window list-month, worst-covered year first.

    The order matters and is the finding's own `next`: 2001 was 7.95% swept and 2000
    12.17%, against 31.19% for 1997, so an interrupted sweep should have spent its hours
    where the partition is thinnest rather than where it is already read.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[str, str, int]] = []
    for tree in TREES:
        page = fetch_with_retry(f"{BASE}/{tree}/")
        if page is None:
            print(f"{tree}: root listing unreadable, nothing planned for it", flush=True)
            continue
        lists = sorted({html.unescape(d) for d in DIR_ROW.findall(page.decode("utf-8", "replace"))})
        print(f"{tree}: {len(lists)} list directories", flush=True)
        for i, listname in enumerate(lists, 1):
            for name, size in months_of(tree, listname):
                where = f"{tree}/{listname}/{name}"
                rows.append((f"{BASE}/{where}", f"{HOST}/{where}", size))
            if i % 100 == 0:
                print(f"  {i}/{len(lists)} lists, {len(rows)} months so far", flush=True)
    # Thinnest year first, then largest month, so the earliest hours buy the most coverage.
    rows.sort(key=lambda r: (-int(r[1].rsplit("/", 1)[1][:4]), -r[2]))
    PLAN.write_text("".join(f"{u}\t{s}\t{b}\n" for u, s, b in rows))
    print(f"plan: {len(rows)} list-months, {sum(r[2] for r in rows):,} listed bytes -> {PLAN}")
    return 0


def new_stats() -> dict:
    return dict.fromkeys(STAT_KEYS, 0)


def rows_of(stream, stem: str, partition_year: int, stats: dict):
    """Yield `{item, year, text}` for one list-month, mbox or MMDF."""
    header: list[str] = []
    in_headers = False
    index = 0

    def flush() -> dict | None:
        nonlocal header, index
        block_lines, header = header, []
        if not block_lines:
            return None
        index += 1
        stats["messages"] += 1
        block = unfold(block_lines)
        date_line = None
        for line in block.split("\n"):
            if line[:5].lower() == "date:":
                date_line = line
                break
        year = message_year(date_line.split(":", 1)[1]) if date_line else None
        if year is None:
            stats["undated"] += 1
            return None
        if year not in IN_WINDOW:
            stats["out_of_window"] += 1
            return None
        if year != partition_year:
            # The archive filed it under a different year than its own Date: header claims.
            # One of the two is wrong and nothing here says which, so the message is dropped.
            stats["year_disagrees"] += 1
            return None
        stats["in_window"] += 1
        hosts = by_hosts(block)
        if not hosts:
            stats["no_by_host"] += 1
            return None
        stats["with_hosts"] += 1
        stats["records"] += len(set(hosts))
        return {"item": f"{stem}#{index}", "year": year, "text": " ".join(sorted(set(hosts)))}

    for raw in stream:
        line = raw.rstrip("\r\n")
        if MMDF.match(line) or (not in_headers and BOUNDARY.match(line)):
            row = flush()
            if row is not None:
                yield row
            in_headers = True
            continue
        if in_headers:
            if not line.strip():
                in_headers = False
            else:
                header.append(line)
    row = flush()
    if row is not None:
        yield row


def fetch_month(url: str):
    """curl one list-month into a pipe. Nothing is written to disk: the parser reads the socket."""
    return subprocess.Popen(
        [
            "curl",
            "-s",
            "-S",
            "--fail",
            "-A",
            USER_AGENT,
            "--max-filesize",
            "1G",
            "--max-time",
            "600",
            "--retry",
            "2",
            "--retry-delay",
            "5",
            url,
        ],
        stdout=subprocess.PIPE,
    )  # noqa: S603


class CountingLines:
    """Decoded lines off a pipe, counting raw bytes as they pass: `fetched_bytes` is what the
    socket delivered, not what the directory index advertised."""

    def __init__(self, raw):
        self.raw = raw
        self.n = 0

    def __iter__(self):
        for chunk in self.raw:
            self.n += len(chunk)
            yield chunk.decode("utf-8", "replace")


def sweep(limit: int | None) -> int:
    if not PLAN.is_file():
        print(f"no plan at {PLAN}: run `plan` first")
        return 1
    ITEMS_DIR.mkdir(parents=True, exist_ok=True)
    done = set(SWEPT.read_text().split("\n")) if SWEPT.is_file() else set()
    work = [ln.split("\t") for ln in PLAN.read_text().split("\n") if ln.strip()]
    work = [row for row in work if row[1] not in done]
    if limit is not None:
        work = work[:limit]
    print(f"sweep: {len(work)} list-months to read, {len(done)} already swept", flush=True)
    for i, (url, stem, _listed) in enumerate(work, 1):
        stats = new_stats()
        # One shard per list directory, so a shard stays small enough to re-read and the
        # ingest's per-shard idempotency lines up with the unit this loop resumes on.
        shard = ITEMS_DIR / (stem.rsplit("/", 2)[-2] + ".jsonl")
        month = MONTH_FILE.match(stem.rsplit("/", 1)[1])
        if month is None:
            continue
        proc = fetch_month(url)
        stream = CountingLines(proc.stdout)
        with shard.open("a", encoding="utf-8") as out:
            for row in rows_of(stream, stem, int(month["month"][:4]), stats):
                out.write(json.dumps(row) + "\n")
        proc.wait()
        stats["curl_rc"] = proc.returncode
        stats["fetched_bytes"] = stream.n
        with STATS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"stem": stem, **stats}) + "\n")
        # Only a clean curl counts as swept, so a month cut off mid-transfer is read again.
        if proc.returncode == 0:
            with SWEPT.open("a", encoding="utf-8") as fh:
                fh.write(stem + "\n")
        if i % 50 == 0:
            print(f"  {i}/{len(work)} months", flush=True)
        time.sleep(CRAWL_DELAY)
    print(f"swept {len(work)} list-months into {ITEMS_DIR}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=("plan", "sweep"))
    ap.add_argument("--limit", type=int, help="sweep at most this many list-months this run")
    args = ap.parse_args()
    return plan() if args.mode == "plan" else sweep(args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
