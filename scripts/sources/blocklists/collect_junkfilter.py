"""Fetch junkfilter's dated `jf-domains` editions from the maintainer's own host.

**Not an archive fetch.** `junkfilter.zer0.org` is live and serves no `robots.txt` (404, no
rules), and `/pkg/` is an open directory index holding one directory per release, named by
ISO date. So this costs one listing request plus one file per edition, about 900 KB total,
and it does not spend an archive-client slot.

**What dates an edition, three ways agreeing.** The HTTP `last-modified` header on the file
(`Tue, 29 May 2001 07:10:09 GMT` for the 20010529 release), the directory name itself, and
the in-body `$Id: junkfilter,v 2.36 2001/05/28 20:00:08 gsutter Exp $` in the same release.
The header is recorded beside each file so the agreement is auditable rather than asserted.

**The format.** `jf-domains` is ONE line: `|`-joined, backslash-escaped literal hostnames,
`001\\.com\\.cn|002\\.com\\.cn|007software\\.com|...`. An earlier triage note guessed these
were escaped regexps with wildcards; that is refuted, 42,005 of 42,034 tokens are
domain-shaped.

**This source is human-typed and takes the corroboration split**, which is applied by
`split_junkfilter.py` before ingest rather than here. A maintainer added each spam-origin
domain by hand, so a name appearing only here has no independent evidence that it ever
resolved.

    uv run python scripts/sources/blocklists/collect_junkfilter.py
    uv run python scripts/sources/blocklists/split_junkfilter.py --write
"""

import argparse
import re
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://junkfilter.zer0.org/pkg/"
OUT = Path("data/raw/junkfilter")
UA = "internet-digital-ark/1.0 (research; ivaylo.staykov@student.hpi.uni-potsdam.de)"
# Release directories are named YYYYMMDD. Only in-window editions are wanted; the
# 2002 and 2003 releases exist and are deliberately skipped.
RELEASE = re.compile(r'href="((?:1996|1997|1998|1999|2000|2001)\d{4})/"')


def fetch(url: str, tries: int = 5, pause: float = 8.0) -> tuple[bytes, str] | None:
    """Return (body, last_modified) or None."""
    for attempt in range(1, tries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read(), response.headers.get("last-modified", "")
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt < tries:
                time.sleep(pause)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between fetches")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    listing = fetch(BASE)
    if listing is None:
        print(f"could not list {BASE}")
        return 1
    releases = sorted(set(RELEASE.findall(listing[0].decode("utf-8", "replace"))))
    print(f"{len(releases)} in-window releases: {', '.join(releases)}")

    stamps = OUT / "last-modified.txt"
    lines, got, missing = [], 0, 0
    for release in releases:
        target = OUT / f"jf-domains.{release}"
        if target.exists() and target.stat().st_size:
            lines.append(f"{release}\talready held")
            continue
        result = fetch(f"{BASE}{release}/jf-domains")
        if result is None:
            print(f"  {release}: no jf-domains")
            missing += 1
            continue
        body, modified = result
        target.write_bytes(body)
        lines.append(f"{release}\t{modified}\t{len(body)} bytes")
        print(f"  {release}: {len(body):,} bytes, last-modified {modified!r}")
        got += 1
        time.sleep(args.delay)

    # **The 1997 edition is not a directory, it is a tar member**, and it is worth the
    # extra fetch: 429 of the net-new pairs land in 1997, one of the thinnest years.
    # `junkfilter-4.13.tar.gz` carries `junkfilter/jf-domains` with member mtime
    # 1997-12-06, 43,879 bytes, which is the stamp the register recorded by hand.
    for name in ("junkfilter-4.13.tar.gz",):
        archive = OUT / "old" / name
        if not archive.exists():
            body = fetch(f"{BASE}old/{name}")
            if body is None:
                print(f"  {name}: unreachable, 1997 edition will be missing")
                continue
            archive.parent.mkdir(parents=True, exist_ok=True)
            archive.write_bytes(body[0])
        with tarfile.open(archive, "r:gz") as tar:
            try:
                member = tar.getmember("junkfilter/jf-domains")
            except KeyError:
                print(f"  {name}: no junkfilter/jf-domains member")
                continue
            handle = tar.extractfile(member)
            if handle is None:
                continue
            day = time.strftime("%Y%m%d", time.gmtime(member.mtime))
            target = OUT / f"jf-domains.{day}"
            target.write_bytes(handle.read())
            lines.append(f"{day}\ttar member mtime in {name}")
            print(f"  {day}: from {name}, member mtime {member.mtime}")

    stamps.write_text("\n".join(lines) + "\n")
    print(f"fetched {got}, missing {missing}; header stamps recorded in {stamps}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
