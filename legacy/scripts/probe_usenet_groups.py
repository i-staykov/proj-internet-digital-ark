"""Download a named sample of Usenet groups so their yield can be measured.

`fetch_usenet_groups.py` selects groups by name and takes them in bulk. This
takes an explicit list instead, which is what a probe needs: the question here
is not "which groups look like announcement forums" but "does a hierarchy we
have never touched pay for its bandwidth at all", and that is settled by taking
a handful of named groups and measuring them rather than by widening the filter
and hoping.

Files land beside the main corpus but under `data/raw/usenet_probe/`, so a probe
cannot be swept up by `ingest_new_usenet.sh` before it has been judged.

Usage:
    uv run python scripts/probe_usenet_groups.py uk.misc aus.general rec.travel.misc
    uv run python scripts/probe_usenet_groups.py --from-file groups.txt --out data/raw/usenet_probe
"""

import argparse
import json
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CATALOG = Path("data/raw/usenet_catalog.json")
DOWNLOAD_BASE = "https://archive.org/download"
USER_AGENT = "internet-digital-ark research crawler (contact: ivaylo.staykov@taktile.com)"


def hierarchy_of(group: str) -> str:
    return group.split(".", 1)[0]


def sizes(catalog: dict) -> dict[str, int]:
    """Map group name to archive size, so a probe can report cost per megabyte."""
    out: dict[str, int] = {}
    for files in catalog.values():
        for entry in files:
            name = entry["name"]
            if name.endswith(".mbox.zip"):
                out[name[: -len(".mbox.zip")]] = int(entry.get("size", 0))
    return out


def download(group: str, dest: Path) -> bool:
    """Fetch one archive through a temporary name, so partials are never read."""
    url = f"{DOWNLOAD_BASE}/usenet-{hierarchy_of(group)}/{group}.mbox.zip"
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=600) as response, tmp.open("wb") as fh:
            while chunk := response.read(1 << 20):
                fh.write(chunk)
    except Exception as exc:  # noqa: BLE001 - one bad group must not end the probe
        tmp.unlink(missing_ok=True)
        print(f"fail {group}: {exc}", flush=True)
        return False
    tmp.rename(dest)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("groups", nargs="*", help="group names, without the .mbox.zip suffix")
    parser.add_argument("--from-file", type=Path, help="file of group names, one per line")
    parser.add_argument("--out", type=Path, default=Path("data/raw/usenet_probe"))
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--max-mb", type=float, default=200.0, help="skip anything larger")
    # A probe of a dozen groups is latency-bound and serial is fine. A bulk run of
    # twelve thousand is latency-bound too, which is exactly why it must not be
    # serial: measured at 0.6 groups/s, A+B+C would have taken six hours to fetch
    # 77 GB that the link itself can carry in well under one.
    parser.add_argument("--workers", type=int, default=1, help="parallel downloads")
    args = parser.parse_args()

    groups = list(args.groups)
    if args.from_file:
        groups += [line.strip() for line in args.from_file.read_text().splitlines() if line.strip()]
    if not groups:
        raise SystemExit("no groups given")

    known = sizes(json.loads(args.catalog.read_text()))
    args.out.mkdir(parents=True, exist_ok=True)

    wanted: list[tuple[str, int]] = []
    for group in groups:
        size = known.get(group)
        if size is None:
            print(f"skip {group}: not in catalogue", flush=True)
            continue
        if size > args.max_mb * 1e6:
            print(f"skip {group}: {size / 1e6:.1f} MB over cap", flush=True)
            continue
        if (args.out / f"{group}.mbox.zip").exists():
            print(f"have {group}", flush=True)
            continue
        wanted.append((group, size))

    started = time.monotonic()
    taken = 0
    bytes_done = 0
    lock = threading.Lock()

    def fetch(item: tuple[str, int]) -> tuple[str, int, bool]:
        group, size = item
        return group, size, download(group, args.out / f"{group}.mbox.zip")

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        for _group, size, ok in pool.map(fetch, wanted):
            if not ok:
                continue
            with lock:
                taken += 1
                bytes_done += size
                elapsed = max(time.monotonic() - started, 1e-6)
                if taken % 25 == 0 or taken == len(wanted):
                    print(
                        f"got {taken:,}/{len(wanted):,}  {bytes_done / 1e9:.2f} GB  "
                        f"{taken / elapsed:.1f} groups/s  {bytes_done / 1e6 / elapsed:.1f} MB/s",
                        flush=True,
                    )
    print(f"downloaded {taken} of {len(groups)}", file=sys.stderr)


if __name__ == "__main__":
    main()
