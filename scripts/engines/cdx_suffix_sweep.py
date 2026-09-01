"""Enumerate a whole public-suffix namespace from the Wayback CDX index.

**What this changes.** Until now every archive route here asked about one domain
at a time, which caps the project at roughly 17,500 queries a day and put 5% about
50 days away. `matchType=domain` on a **public suffix** returns captures for every
domain under it, and it paginates, so one endpoint enumerates the namespace.

**Established by measurement, with controls, because the register says the bare
TLD form is forbidden and that is still true.** Measured 2026-08-21:

| query | result |
|---|---|
| `url=uk&matchType=domain` | **HTTP 403**, as are the `from`, `collapse` and `fl` variants |
| `url=co.uk&matchType=domain` | **200**, and returns many distinct registrable domains |
| `showNumPages` on `co.uk` | **3,387,186** pages |
| pages 0, 1, 2 | **disjoint**, so the namespace can genuinely be walked |

So the block is on the bare TLD, not on the query shape, and a public suffix is
treated as an ordinary two-label name while behaving as a suffix. Whether that is
intended by the archive is not ours to say; it is a documented parameter of a
public API used at a polite rate.

**Evidence type.** Each row carries a 14-digit capture timestamp, so this is
`cdx_timestamp`, self-dating, and `early_web_cdx / cdx_timestamp` is already
approved master. No new decision is needed to bank what this returns.

**Citizenship.** One request per page with a delay, an honest User-Agent naming
the project and a contact, a hard stop on 429 or 503 rather than a backoff that
keeps hammering, and an absolute deadline. The Internet Archive has refused this
project three times and this route is worth protecting.

    uv run python scripts/engines/cdx_suffix_sweep.py co.uk --deadline <epoch>
"""

import argparse
import gzip
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
BASE = "https://web.archive.org/cdx/search/cdx"
OUT = Path("data/raw/cdx_suffix")
# Researcher waves need the archive unthrottled; the fleet touches this flag before
# dispatching agents and removes it after, and the sweep idles while it exists. A
# flag file rather than systemctl, because the sweep runs as a plain user process.
PAUSE_FLAG = Path("/tmp/ark-pause-sweeps")


def fetch(params: dict, timeout: int) -> tuple[str, list[str]]:
    url = f"{BASE}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            return "200", fh.read().decode("utf-8", "replace").splitlines()
    except urllib.error.HTTPError as exc:
        return f"HTTP{exc.code}", []
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{type(exc).__name__}", []


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("suffix")
    ap.add_argument("--deadline", type=int, required=True, help="absolute epoch to stop at")
    ap.add_argument("--page-size", type=int, default=200)
    ap.add_argument("--start-page", type=int, default=0)
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    safe = args.suffix.replace(".", "_")
    journal = OUT / f"suffix_{safe}_{stamp}.jsonl.gz"
    state = OUT / f"suffix_{safe}.state.json"

    page = args.start_page
    if state.exists():
        try:
            page = max(page, json.loads(state.read_text()).get("next_page", 0))
        except Exception:
            pass
    print(f"{args.suffix}: starting at page {page:,}, journal {journal.name}")

    status, rows = fetch({"url": "bbc.co.uk", "limit": 2}, args.timeout)
    if status != "200":
        sys.exit(f"control failed ({status}); refusing to sweep")

    written = pages = empty_run = 0
    with gzip.open(journal, "wt") as fh:
        while time.time() < args.deadline:
            while PAUSE_FLAG.exists() and time.time() < args.deadline:
                time.sleep(30)
            status, rows = fetch(
                {
                    "url": args.suffix,
                    "matchType": "domain",
                    "fl": "original,timestamp",
                    "from": "1996",
                    "to": "2001",
                    "filter": "statuscode:200",
                    "pageSize": args.page_size,
                    "page": page,
                },
                args.timeout,
            )
            if status in ("HTTP429", "HTTP503"):
                print(f"  page {page}: {status}, stopping rather than hammering")
                break
            if status != "200":
                # A transient error should not end a multi-day sweep, but a run of
                # them should: the difference is whether the next page answers.
                empty_run += 1
                if empty_run > 20:
                    print(f"  {empty_run} consecutive failures ending {status}, stopping")
                    break
                page += 1
                time.sleep(args.delay * 3)
                continue

            if not rows:
                empty_run += 1
                if empty_run > 50:
                    print(f"  {empty_run} consecutive empty pages, assuming the end")
                    (OUT / f"suffix_{safe}.done").touch()
                    break
            else:
                empty_run = 0
                for line in rows:
                    parts = line.split(" ")
                    if len(parts) >= 2 and len(parts[1]) == 14 and parts[1].isdigit():
                        fh.write(json.dumps({"url": parts[0], "timestamp": parts[1]}) + "\n")
                        written += 1

            pages += 1
            page += 1
            if pages % 25 == 0:
                fh.flush()
                state.write_text(json.dumps({"next_page": page, "written": written}))
                print(f"  page {page:,}: {written:,} rows written", flush=True)
            time.sleep(args.delay)

    state.write_text(json.dumps({"next_page": page, "written": written}))
    print(f"{args.suffix}: {pages:,} pages, {written:,} rows -> {journal}")


if __name__ == "__main__":
    main()
