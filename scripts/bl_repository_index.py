"""Enumerate the British Library repository's files by name, cheaply.

**Why this exists.** `ukwa_geoindex` was found by hand and measured at 77,749
equivalent-English, which is 12.6% of the 5% gate from a single free CC Public
Domain file. The obvious question is what else that repository holds, and until
now there was no way to ask: `/concern/` is behind a Cloudflare challenge and
`/catalog` is disallowed by robots.

**The cheap route.** `robots.txt` allows `/` for a generic agent and publishes
`https://bl.iro.bl.uk/resourcelist` as the intended enumeration mechanism, which
lists 39,158 `file_set` ids. A HEAD of `/downloads/<id>` returns **302** whose
`Location` carries `response-content-disposition=attachment; filename=<name>`. So
one redirect, followed nowhere, yields the filename. No S3 object is touched and
no payload is transferred.

Politeness, which is not optional after three refusals from another archive: an
honest User-Agent naming the project and a contact, a small worker count, a delay
between requests, and a hard stop on 429 or 503 rather than a backoff that keeps
hammering.

    uv run python scripts/bl_repository_index.py --limit 2000
    uv run python scripts/bl_repository_index.py            # the whole list

Writes `data/raw/bl/file_index.tsv` as `id<TAB>filename`, resumable: ids already
in the file are skipped, so an interrupted run costs only the requests in flight.
"""

import argparse
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from queue import Queue

UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
RESOURCELIST = "https://bl.iro.bl.uk/resourcelist"
OUT = Path("data/raw/bl/file_index.tsv")
FILESET = re.compile(r"concern/file_sets/([0-9a-f-]{36})")

_stop = threading.Event()
_lock = threading.Lock()


def fetch_resourcelist(cache: Path) -> list[str]:
    if not cache.exists():
        req = urllib.request.Request(RESOURCELIST, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=300) as fh:
            cache.write_bytes(fh.read())
    ids = FILESET.findall(cache.read_text(encoding="utf-8", errors="replace"))
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """The redirect IS the answer, so following it would fetch the payload."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_opener = urllib.request.build_opener(NoRedirect)


def filename_of(fid: str, timeout: float) -> tuple[str, str]:
    url = f"https://bl.iro.bl.uk/downloads/{fid}"
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method="HEAD")
    try:
        with _opener.open(req, timeout=timeout) as resp:
            return fid, f"HTTP{resp.status}"
    except urllib.error.HTTPError as exc:
        if exc.code in (429, 503):
            _stop.set()
            return fid, "THROTTLED"
        loc = exc.headers.get("Location") or ""
        match = re.search(r"filename%3D([^&]+)", loc) or re.search(r"filename=([^&;]+)", loc)
        if match:
            return fid, urllib.parse.unquote(urllib.parse.unquote(match.group(1)))
        return fid, f"HTTP{exc.code}"
    except Exception as exc:  # noqa: BLE001
        return fid, f"ERR:{type(exc).__name__}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="stop after N new ids")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--delay", type=float, default=0.25, help="seconds between requests")
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            if line:
                done.add(line.split("\t", 1)[0])
    print(f"{len(done):,} already indexed")

    ids = [i for i in fetch_resourcelist(OUT.parent / "resourcelist.xml") if i not in done]
    if args.limit:
        ids = ids[: args.limit]
    print(f"{len(ids):,} to ask")

    work: Queue = Queue()
    for i in ids:
        work.put(i)

    fh = OUT.open("a", encoding="utf-8")
    counter = {"n": 0}

    def worker() -> None:
        while not _stop.is_set():
            try:
                fid = work.get_nowait()
            except Exception:  # noqa: BLE001
                return
            fid, name = filename_of(fid, args.timeout)
            with _lock:
                fh.write(f"{fid}\t{name}\n")
                counter["n"] += 1
                if counter["n"] % 500 == 0:
                    fh.flush()
                    print(f"  {counter['n']:,}/{len(ids):,}", flush=True)
            time.sleep(args.delay)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(args.workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    fh.close()

    if _stop.is_set():
        print("STOPPED: the server returned 429 or 503. Re-run later; this is resumable.")
        sys.exit(1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
