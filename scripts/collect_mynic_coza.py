"""Fetch MYNIC's fortnightly register listings and the CO.ZA suspension and deletion queues.

Two registry change reports, collected together because they are the same shape of artifact
and the same shape of collection: enumerate the captures from CDX, fetch each with `id_`, and
refuse anything that does not contain the text the real page must contain.

**MYNIC**, `mynic.net.my/my/stats/<month><year>-{1,2}.htm`. Only the `-1` and `-2` half-month
pages carry names; the bare-month pages are the statistics tables and are not fetched, though
they are what settled the corroboration split (see `docs/sources.md`). 35 pages fall in the
window; `dec2001-1.htm` has only a 318-byte empty capture and stays missing, which is recorded
rather than retried forever.

**CO.ZA**, `cgi-bin/warn.sh` and `cgi-bin/todel.sh` on **three hostnames**: `co.za`,
`posix.co.za` and `www.posix.co.za`. The `posix` host is not a duplicate of the registry's own,
and this is the part worth keeping: it is the company that administered CO.ZA, and its earliest
captures are 1997-12-21 and 1998-01-17, **earlier than any capture of `co.za` itself**. Asking
only the obvious hostname would have lost eleven of the twenty-two editions.

**A CDX `limit` is a false zero**, which cost a wasted conclusion elsewhere in this project, so
every listing here is asked for by exact path with `matchType=exact` and no limit.

    uv run python scripts/collect_mynic_coza.py
"""

import argparse
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = "internet-digital-ark/1.0 (research; ivaylo.staykov@student.hpi.uni-potsdam.de)"
CDX = "https://web.archive.org/cdx/search/cdx"
MYNIC_OUT = Path("data/raw/mynic")
COZA_OUT = Path("data/raw/coza")
# The half-month pages carry names; the bare-month pages are statistics tables.
_MYNIC_HALF = re.compile(r"/my/stats/([a-z0-9]+\d{4}-[12]\.htm)$", re.I)
# Out of window, so they cannot date a year.
MYNIC_SKIP = {"feb2002-1.htm", "feb2003-1.htm"}
COZA_HOSTS = ("co.za", "posix.co.za", "www.posix.co.za")


def get(url: str, tries: int, pause: float) -> bytes | None:
    """One request, retried, honouring the archive's own back-off."""
    for attempt in range(1, tries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=240) as response:
                delay = response.headers.get("Retry-After")
                if delay:
                    time.sleep(min(float(delay), 300.0))
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code in (429, 503, 504):
                delay = error.headers.get("Retry-After")
                time.sleep(min(float(delay), 300.0) if delay else pause)
            elif error.code in (403, 404):
                return None
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        if attempt < tries:
            time.sleep(pause)
    return None


def save(target: Path, url: str, must_contain: str, tries: int, pause: float) -> bool:
    """Fetch one object and keep it only if it contains what the real page must say."""
    if target.exists() and must_contain.encode() in target.read_bytes():
        return True
    body = get(url, tries, pause)
    # A size floor is not a content check: assert on the text, never on the byte count.
    if body is None or must_contain.encode() not in body:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    return True


def collect_mynic(tries: int, pause: float) -> list[str]:
    """Every in-window half-month listing page, one capture each."""
    rows = get(
        f"{CDX}?url=mynic.net.my/my/stats*&from=1996&to=2003"
        "&output=text&fl=timestamp,original,statuscode&collapse=urlkey",
        tries,
        pause,
    )
    if rows is None:
        print("  MYNIC: CDX did not answer")
        return ["mynic-cdx"]
    wanted: dict[str, tuple[str, str]] = {}
    for line in rows.decode(errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[2] != "200":
            continue
        half = _MYNIC_HALF.search(parts[1])
        if half is None:
            continue
        page = half.group(1).lower()
        if page in MYNIC_SKIP or page in wanted:
            continue
        wanted[page] = (parts[0], parts[1])
    print(f"  MYNIC: {len(wanted)} in-window half-month pages")
    missing = []
    for page, (stamp, original) in sorted(wanted.items()):
        url = f"https://web.archive.org/web/{stamp}id_/{original}"
        if save(MYNIC_OUT / page, url, "Domain Name Listing", tries, pause):
            continue
        print(f"    missing {page} (capture {stamp} carries no listing)")
        missing.append(page)
        time.sleep(1)
    return missing


def collect_coza(tries: int, pause: float) -> list[str]:
    """Both queues on all three hostnames, every status-200 capture."""
    captures: set[tuple[str, str]] = set()
    for host in COZA_HOSTS:
        for page in ("warn.sh", "todel.sh"):
            rows = get(
                f"{CDX}?url={host}/cgi-bin/{page}&matchType=exact&from=1996&to=2002"
                "&output=text&fl=timestamp,original,statuscode",
                tries,
                pause,
            )
            if rows is None:
                continue
            for line in rows.decode(errors="replace").splitlines():
                parts = line.split()
                if len(parts) >= 3 and parts[2] == "200":
                    captures.add((parts[0], parts[1]))
            time.sleep(1)
    print(f"  CO.ZA: {len(captures)} status-200 captures across {len(COZA_HOSTS)} hostnames")
    missing = []
    for stamp, original in sorted(captures):
        host = original.split("//", 1)[1].split(":", 1)[0].replace(".", "_")
        page = "warnsh" if "warn.sh" in original else "todelsh"
        url = f"https://web.archive.org/web/{stamp}id_/{original}"
        target = COZA_OUT / f"{host}-{page}-{stamp}.html"
        if save(target, url, "shortlisted for", tries, pause):
            continue
        print(f"    missing {target.name}")
        missing.append(target.name)
        time.sleep(1)
    return missing


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tries", type=int, default=6)
    ap.add_argument("--pause", type=float, default=20.0)
    args = ap.parse_args()

    missing = collect_mynic(args.tries, args.pause) + collect_coza(args.tries, args.pause)
    if missing:
        # Not a failure: dec2001-1.htm genuinely has only an empty capture.
        print(f"\n{len(missing)} object(s) unavailable: {', '.join(missing)}")
    print(f"\nMYNIC under {MYNIC_OUT}/, CO.ZA under {COZA_OUT}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
