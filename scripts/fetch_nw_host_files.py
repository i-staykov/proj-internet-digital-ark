"""Fetch the Network Wizards per-TLD host files out of the 1996 `nw.com` Wayback crawl.

The crawl that gave us the `.domains` lists also captured `9607.hosts/`, `9701.hosts/`
and `9707.hosts/`: 583 files, one per TLD, each holding `IP hostname` pairs from that
survey walk. Only `9607.hosts/org.gz` had ever been fetched. They carry the same
evidence as the `.domains` lists, `artifact_listing` dated by the survey, and
`parse_isc_survey` already reads the `IP hostname` form, so all this has to do is
land them under a filename whose `YYMM` code the date rule can read.

Resumable: a file already on disk is skipped, so an interrupted run costs nothing.
Polite: three connections, a pause between requests, and a long back-off on 429/503.

    uv run python scripts/fetch_nw_host_files.py
    uv run ark ingest isc_survey data/raw/isc_survey/*.gz

Note the redirect. `http://web.archive.org/web/<ts>id_/<url>` answers 302 for these,
so the fetch has to follow it; a run that does not follow redirects silently writes
583 empty files.
"""

import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data/raw/isc_survey"
CDX = (
    "https://web.archive.org/cdx/search/cdx?url=nw.com/zone&matchType=prefix"
    "&fl=timestamp,original,statuscode,length&collapse=urlkey&limit=2000"
)
USER_AGENT = "ark-research/1.0 (internet history project; contact via repository)"
WORKERS = 3
REQUEST_PAUSE = 0.3
BACKOFF_CODES = (429, 503, 504)
ATTEMPTS = 5
# a Wayback error page is far smaller than any real gzip member
MIN_BODY = 20

_HOST_FILE = re.compile(r"zone/(9\d{3})\.hosts/([a-z0-9-]+)\.gz$")


def get(url: str, timeout: int = 300) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read()


def captures() -> list[tuple[str, str, str, str]]:
    """The (timestamp, url, survey, tld) of every 200-status per-TLD host file."""
    found = []
    for line in get(CDX, timeout=120).decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) < 4 or parts[2] != "200":
            continue
        match = _HOST_FILE.search(parts[1])
        if match:
            found.append((parts[0], parts[1], match.group(1), match.group(2)))
    return found


def fetch_one(capture: tuple[str, str, str, str]) -> str:
    timestamp, original, survey, tld = capture
    dest = OUT_DIR / f"wb_nw_{survey}_{tld}.gz"
    if dest.exists() and dest.stat().st_size:
        return "have"
    url = f"http://web.archive.org/web/{timestamp}id_/{original}"
    for attempt in range(ATTEMPTS):
        try:
            body = get(url)
            if len(body) < MIN_BODY:
                return "tiny"
            dest.write_bytes(body)
            time.sleep(REQUEST_PAUSE)
            return "ok"
        except urllib.error.HTTPError as error:
            if error.code not in BACKOFF_CODES:
                return f"http{error.code}"
            time.sleep(20 * (attempt + 1))
        except Exception:  # noqa: BLE001 - one bad capture must not end the run
            time.sleep(10 * (attempt + 1))
    return "failed"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    found = captures()
    if not found:
        # a CDX zero from a prefix query is worthless without a control, see sources.md
        raise SystemExit("no host-file captures returned; re-check the CDX query first")
    print(f"{len(found)} per-TLD host files captured", flush=True)
    outcomes: dict[str, int] = {}
    started = time.time()
    with ThreadPoolExecutor(WORKERS) as pool:
        for done, result in enumerate(pool.map(fetch_one, found), 1):
            outcomes[result] = outcomes.get(result, 0) + 1
            if done % 50 == 0:
                print(f"  {done}/{len(found)} {time.time() - started:.0f}s {outcomes}", flush=True)
    print(f"done in {time.time() - started:.0f}s: {outcomes}")
    if outcomes.get("failed"):
        print("re-run to retry the failures; files already on disk are skipped", file=sys.stderr)


if __name__ == "__main__":
    main()
