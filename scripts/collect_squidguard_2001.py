"""Fetch the 2001 squidGuard blacklists and flatten them into one ingestible directory.

**One request, and the host serves no robots.txt** (404, no rules):
`archive.debian.org/debian/pool/main/s/squidguard/squidguard_1.2.0.orig.tar.gz`, 1,852,659 bytes.
Inside it, `squidguard-1.2.0/samples/dest/blacklists.tar.gz` holds the lists. Licence is GPL v2,
verbatim in `squidguard-1.2.0/COPYING`, and `samples/dest/README` adds no data restriction beyond
warning that the lists are "entierly products of a dumb robot".

**Why the names are flattened.** The tree is `blacklists/<category>/{domains,urls,*.diff}`, so
eleven categories each hold a file called `domains`. The bulk ingest ledger keys on `path.name`
alone, so loading them as-is would ledger the first `domains` and then skip the other ten as already
ingested or fail on a hash mismatch. Every file is therefore written as
`squidguard-<category>-<basename>`, which keeps the category and any date in the name.

**What is dated how.** A base `domains` or `urls` file carries its own compile stamp,
`# This list was compiled in 19:44:45 on 2001.12.15 19:56:41.`, and that is what dates its names. A
diff carries the date in its filename instead, `domains.20011113.diff`. Every stamp in this edition
falls between 2001.12.15 and 2001.12.18, and every diff is dated in 2001, so the whole artifact is
in window. `expressions` files are regular expressions rather than names and are not copied.

    uv run python scripts/collect_squidguard_2001.py
    uv run ark ingest squidguard_blacklist data/raw/squidguard/*
"""

import argparse
import io
import re
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://archive.debian.org/debian/pool/main/s/squidguard/squidguard_1.2.0.orig.tar.gz"
INNER = "squidguard-1.2.0/samples/dest/blacklists.tar.gz"
OUT = Path("data/raw/squidguard")
UA = "internet-digital-ark/1.0 (research; ivaylo.staykov@student.hpi.uni-potsdam.de)"
# `blacklists/<category>/<file>`; anything deeper or shallower is not a list.
MEMBER = re.compile(r"^(?:\./)?blacklists/([a-z0-9-]+)/([A-Za-z0-9._-]+)$")
WANTED = re.compile(r"^(?:domains|urls)(?:\.\d{8}\.diff)?$")


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep", type=Path, default=None, help="save the outer tarball here")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    try:
        outer = fetch(URL)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"could not fetch {URL}: {exc}")
        return 1
    print(f"fetched {len(outer):,} bytes")
    if args.keep:
        args.keep.write_bytes(outer)

    with tarfile.open(fileobj=io.BytesIO(outer), mode="r:gz") as tar:
        member = tar.extractfile(INNER)
        if member is None:
            print(f"{INNER} is not in the tarball")
            return 1
        inner_bytes = member.read()

    written = skipped = 0
    with tarfile.open(fileobj=io.BytesIO(inner_bytes), mode="r:gz") as tar:
        for entry in tar.getmembers():
            if not entry.isfile():
                continue
            match = MEMBER.match(entry.name)
            if match is None or not WANTED.match(match.group(2)):
                skipped += 1
                continue
            handle = tar.extractfile(entry)
            if handle is None:
                skipped += 1
                continue
            target = OUT / f"squidguard-{match.group(1)}-{match.group(2)}"
            target.write_bytes(handle.read())
            written += 1

    print(f"wrote {written} list files into {OUT}, skipped {skipped} other members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
