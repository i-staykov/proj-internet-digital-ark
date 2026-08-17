"""Ask the Wayback Machine for the DATA FILES of hosts the register wrote off as dead.

**The method this automates was proved twice on 2026-08-16 and it is not obvious.**
When a source is closed because its host is gone, the instinct is to re-probe the
host, and `reprobe_closed.py` does exactly that. It answers the wrong question. A
dead host's *pages* being unarchived says nothing about its *files*, and the
archive's coverage of the two is wildly different:

  `nw.com/zone/9701.domains.gz`     recorded as unrecoverable, intact in Wayback,
                                    worth 76,324 net-new pairs.
  `cybermetrics.wlv.ac.uk/database/` host does not resolve, and Wayback holds the
                                    whole directory including a 166 MB zip.

The belief that Wayback skips large binaries is wrong by two orders of magnitude in
both cases. So: CDX the host with `matchType=domain`, filter to things that look
like data rather than pages, and report what is sitting there.

**It reports, it does not fetch.** Every hit still needs the store-side saturation
check before a byte is downloaded, because a file can be available, dated, and 100%
already held: the Cybermetrics recovery died at 110 of 110 domains in one query,
after the download would already have been paid for.

    uv run python scripts/recover_dead_hosts.py                 # every dead host in the register
    uv run python scripts/recover_dead_hosts.py --host nw.com   # just one
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

CDX = "https://web.archive.org/cdx/search/cdx"
USER_AGENT = (
    "InternetDigitalArk/1.0 (historical domain research; contact ivaylo.staykov@taktile.com)"
)

# Extensions that are data rather than a rendered page. Deliberately generous: a
# 1990s research host served self-extracting .exe archives, and excluding them would
# have hidden the largest files on the one host this was first run against.
DATA_SUFFIX = re.compile(
    r"\.(gz|zip|7z|bz2|xz|tar|tgz|exe|csv|tsv|txt|dat|db|sql|json|jsonl|cdx|cdxj|rdf|xml|mdb)$",
    re.I,
)
PAGE_MIME = re.compile(r"html|image|css|javascript|font|video|audio", re.I)

# Documents and fonts, which are neither pages nor data. The first whole-register sweep
# reported 89 "data files" of which the great majority were conference PDFs on Yahoo
# Webscope, PostScript papers from a 1999 caching workshop, and Bootstrap glyph fonts
# on an Icelandic archive. A recovery tool that surfaces a reading list is a tool its
# reader learns to skim, which is the same failure as an alarm that cries wolf.
NOT_DATA_SUFFIX = re.compile(
    r"\.(pdf|ps|ps\.gz|ppt|pptx|doc|docx|rtf|ttf|woff2?|eot|otf|svg|ico|mp3|mp4|avi|mov)$",
    re.I,
)

# Below this a "data file" is a README, a redirect stub, or an error page. The
# 159-byte stub that fooled a checker for weeks is two orders of magnitude under it.
MIN_INTERESTING_BYTES = 20_000


def cdx_rows(host: str, timeout: float = 120.0, retries: int = 6) -> list[list[str]]:
    """Every distinct archived URL under a host, newest capture of each."""
    query = urllib.parse.urlencode(
        {
            "url": host,
            "matchType": "domain",
            "output": "text",
            "fl": "original,timestamp,mimetype,length,statuscode",
            "filter": "statuscode:200",
            "collapse": "urlkey",
            "limit": "5000",
        }
    )
    request = urllib.request.Request(f"{CDX}?{query}", headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                body = response.read().decode("utf-8", "replace")
            return [line.split(" ") for line in body.splitlines() if line.strip()]
        except (urllib.error.URLError, TimeoutError, OSError):
            # The archive refuses a large share of our connections outright; that is
            # measured at 12.34% and is why this retries rather than reporting a zero.
            if attempt == retries - 1:
                return []
            time.sleep(3 * (attempt + 1))
    return []


def interesting(rows: list[list[str]]) -> list[tuple[int, str, str, str]]:
    out = []
    for row in rows:
        if len(row) < 5:
            continue
        original, timestamp, mimetype, length = row[0], row[1], row[2], row[3]
        try:
            size = int(length)
        except ValueError:
            continue
        if size < MIN_INTERESTING_BYTES:
            continue
        if PAGE_MIME.search(mimetype):
            continue
        path = urllib.parse.urlsplit(original).path
        if NOT_DATA_SUFFIX.search(path):
            continue
        if not DATA_SUFFIX.search(path) and "octet-stream" not in mimetype:
            continue
        out.append((size, timestamp, mimetype, original))
    return sorted(out, reverse=True)


def dead_hosts() -> list[str]:
    """Hosts the register closed on availability, via the re-prober's own parser."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "reprobe_closed", ROOT / "scripts" / "reprobe_closed.py"
    )
    reprobe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reprobe)

    # `targets_in` is the re-prober's own extractor, reused rather than rewritten so
    # the two tools cannot disagree about which hosts the register considers dead.
    hosts: list[str] = []
    for entry in reprobe.screen.closed_leads():
        if entry.closed_on != "availability":
            continue
        for url in reprobe.targets_in(entry):
            host = urllib.parse.urlsplit(url).hostname or ""
            if host and host not in hosts:
                hosts.append(host)
    return hosts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", action="append", help="probe this host instead of the register")
    parser.add_argument("--min-bytes", type=int, default=MIN_INTERESTING_BYTES)
    args = parser.parse_args()

    hosts = args.host or dead_hosts()
    if not hosts:
        print("no availability-closed hosts in the register.")
        return

    print(f"asking Wayback for data files under {len(hosts)} host(s)\n")
    total = 0
    for host in hosts:
        rows = cdx_rows(host)
        hits = [h for h in interesting(rows) if h[0] >= args.min_bytes]
        if not hits:
            print(f"  {host:<42} {len(rows):>5} archived urls, no data files")
            continue
        total += len(hits)
        print(f"  {host:<42} {len(rows):>5} archived urls, {len(hits)} DATA FILES:")
        for size, timestamp, _mimetype, original in hits[:8]:
            print(f"      {size:>13,}  {timestamp}  {original}")
        if len(hits) > 8:
            print(f"      ... and {len(hits) - 8} more")
        time.sleep(2)

    print()
    if total:
        print(
            f"{total} candidate data file(s). NONE of this is a yield figure: check each "
            "against the live store BEFORE downloading. The one host this method was first "
            "run against measured 110 of 110 domains already held."
        )
    else:
        print("nothing. The register's availability closures hold for files as well as pages.")


if __name__ == "__main__":
    main()
