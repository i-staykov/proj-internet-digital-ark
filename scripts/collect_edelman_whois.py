"""Fetch Ben Edelman's 2002 whois transcriptions from the Berkman Center's archived space.

**Access, and the delay is the binding constraint.** `cyber.harvard.edu/robots.txt` was read
whole: `User-agent: *` disallows a list of specific paths, none of which is
`/archived_content`, no rule names Claude or any AI agent, and it sets **`Crawl-delay: 15`**.
Fifteen seconds between requests is honoured here, which is why this is a background job with
an absolute deadline rather than an inline fetch.

**The artifact.** Three families under `/archived_content/people/edelman/`: `invalid-whois/`
holding `nicgod-*.html`, `renewals/` holding `tina-*.html`, and `typo-domains/` holding
`list-*.html`. The pages carry "Last Updated: June 2, 2002" and transcribe registry whois
records, so the evidence is the registry's creation date as transcribed, not the page's own
date. Per rule 6 a creation date evidences its own year and no other.

**THE PARSING TRAP, measured and recorded before this collector existed.** An earlier pass
overstated this source by 47% by binding a name to a neighbouring record's date. Each `<p>`
block names its SUBJECT in `<b>` and then goes on to mention the redirect target and the
typo'd original in ordinary text. Only the `<b>` subject may take the block's creation date.
The parser, not this collector, has to hold that line, but it is recorded here too because
this is the file someone reads first.

    uv run python scripts/collect_edelman_whois.py --deadline-minutes 120
"""

import argparse
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://cyber.harvard.edu/archived_content/people/edelman/"
FAMILIES = {
    "invalid-whois": re.compile(r'href="(nicgod-[^"]+\.html?)"', re.I),
    "renewals": re.compile(r'href="(tina-[^"]+\.html?)"', re.I),
    "typo-domains": re.compile(r'href="(list-[^"]+\.html?)"', re.I),
}
OUT = Path("data/raw/edelman")
UA = "internet-digital-ark/1.0 (research; ivaylo.staykov@student.hpi.uni-potsdam.de)"
CRAWL_DELAY = 15.0


def get(url: str, tries: int = 4) -> bytes | None:
    for attempt in range(1, tries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt < tries:
                time.sleep(CRAWL_DELAY * attempt)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deadline-minutes", type=float, default=180.0)
    args = ap.parse_args()
    deadline = time.time() + args.deadline_minutes * 60

    OUT.mkdir(parents=True, exist_ok=True)
    wanted: list[tuple[str, str]] = []
    for family, pattern in FAMILIES.items():
        index = get(f"{BASE}{family}/")
        time.sleep(CRAWL_DELAY)
        if index is None:
            print(f"{family}: index unreachable")
            continue
        names = sorted(set(pattern.findall(index.decode("utf-8", "replace"))))
        print(f"{family}: {len(names)} pages")
        wanted.extend((family, n) for n in names)

    got = skipped = missing = 0
    for family, name in wanted:
        if time.time() >= deadline:
            print("deadline reached; remaining pages left for the next run")
            break
        target = OUT / f"edelman-{family}-{name}"
        if target.exists() and target.stat().st_size:
            skipped += 1
            continue
        body = get(f"{BASE}{family}/{name}")
        if body is None:
            missing += 1
            continue
        target.write_bytes(body)
        got += 1
        time.sleep(CRAWL_DELAY)

    print(f"fetched {got}, already held {skipped}, unreachable {missing}, into {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
