"""Which public suffixes are worth sweeping, ranked by expected equivalent-English?

The suffix sweep enumerates a whole namespace from one query, so the only question
is which namespaces to point it at. That is a ranking problem with two measurable
factors and no guesswork needed:

  weight        the TLD's English share in the fixed model, which is the metric
  headroom      how many domains under that suffix the store does NOT already hold

**Headroom is the factor that is easy to get wrong.** `.com` has the largest
population and the store already holds 6.1 million of them, so its marginal return
is far lower than its size suggests. A suffix where we hold almost nothing and the
weight is high is worth more per query even if the namespace is small.

This asks the CDX endpoint for each candidate's page count, which is one cheap
request per suffix and gives the true namespace size, then combines the three.

    uv run python scripts/suffix_rank.py
"""

import sys
import time
import urllib.parse
import urllib.request
from decimal import Decimal

import duckdb

sys.path.insert(0, "src")
from ark.english_share import english_weights  # noqa: E402

UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
BASE = "https://web.archive.org/cdx/search/cdx"

# Every suffix with weight >= 0.5 that plausibly existed in 1996-2001, plus the
# multi-label suffixes that are their own namespace. Modern gTLDs are excluded by
# delegation date, which is a registry fact rather than a guess about names.
CANDIDATES = (
    "com",
    "net",
    "org",
    "edu",
    "gov",
    "mil",
    "int",
    "co.uk",
    "org.uk",
    "ac.uk",
    "gov.uk",
    "ltd.uk",
    "plc.uk",
    "me.uk",
    "sch.uk",
    "nhs.uk",
    "com.au",
    "net.au",
    "org.au",
    "edu.au",
    "gov.au",
    "asn.au",
    "id.au",
    "ca",
    "on.ca",
    "qc.ca",
    "bc.ca",
    "ab.ca",
    "ie",
    "nz",
    "co.nz",
    "org.nz",
    "net.nz",
    "ac.nz",
    "govt.nz",
    "za",
    "co.za",
    "org.za",
    "ac.za",
    "us",
    "in",
    "co.in",
    "sg",
    "com.sg",
    "hk",
    "com.hk",
    "ph",
    "com.ph",
    "my",
    "com.my",
    "pk",
    "com.pk",
    "ng",
    "com.ng",
    "ke",
    "co.ke",
    "gh",
    "com.gh",
    "jm",
    "tt",
    "bb",
    "bs",
    "bz",
    "gi",
    "mt",
    "com.mt",
    "cy",
    "com.cy",
    "il",
    "co.il",
    "ac.il",
    "org.il",
)


def pages(suffix: str) -> int:
    q = urllib.parse.urlencode(
        {
            "url": suffix,
            "matchType": "domain",
            "from": "1996",
            "to": "2001",
            "filter": "statuscode:200",
            "showNumPages": "true",
            "pageSize": "200",
        }
    )
    req = urllib.request.Request(f"{BASE}?{q}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as fh:
            return int(fh.read().decode().strip() or 0)
    except Exception:
        return -1


def main() -> None:
    weights = english_weights()
    for _ in range(120):
        try:
            con = duckdb.connect("data/ark.duckdb", read_only=True)
            break
        except Exception:
            time.sleep(20)
    else:
        sys.exit("store stayed locked")

    held = {}
    for suffix in CANDIDATES:
        held[suffix] = con.execute(
            "select count(distinct domain) from domain_year where domain like ?",
            [f"%.{suffix}"],
        ).fetchone()[0]

    rows = []
    for suffix in CANDIDATES:
        w = weights.get(suffix.rsplit(".", 1)[-1], Decimal(0))
        if w < Decimal("0.4"):
            continue
        n = pages(suffix)
        time.sleep(1.5)
        if n <= 0:
            print(f"  {suffix:<10} pages={n} (skipped)", file=sys.stderr)
            continue
        # One page is 200 index rows; distinct domains per page runs about 20 on the
        # measured .uk sweeps, so this is a scale rather than a precise count.
        est_domains = n * 20
        headroom = max(est_domains - held[suffix], 0)
        rows.append((w * headroom, suffix, w, n, held[suffix], headroom))
        print(f"  {suffix:<10} pages={n:>9,} held={held[suffix]:>9,}", file=sys.stderr)

    rows.sort(reverse=True)
    print(f"\n{'suffix':<10}{'weight':>8}{'pages':>11}{'held':>11}{'headroom':>12}{'score EE':>13}")
    for score, suffix, w, n, h, room in rows:
        print(f"{suffix:<10}{w:>8.4f}{n:>11,}{h:>11,}{room:>12,}{score:>13,.0f}")


if __name__ == "__main__":
    main()
