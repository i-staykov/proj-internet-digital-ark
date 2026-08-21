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

import argparse
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


# Fallback when `--probe` is off. Deliberately low: `com.au` measured about 1.5 and
# the `.uk` suffixes about 20, so a middling default is wrong for both and a low one
# at least fails towards under-claiming.
DEFAULT_DENSITY = 3.0


def probe_density(suffix: str) -> float:
    """Distinct registrable domains in one page of this namespace.

    A page count measures captures; the metric pays for domains. The ratio varies by
    an order of magnitude between namespaces, so it is sampled rather than assumed.
    """
    q = urllib.parse.urlencode(
        {
            "url": suffix,
            "matchType": "domain",
            "from": "1996",
            "to": "2001",
            "filter": "statuscode:200",
            "fl": "original",
            "pageSize": "200",
            "page": "1",
        }
    )
    req = urllib.request.Request(f"{BASE}?{q}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as fh:
            body = fh.read().decode("utf-8", "replace")
    except Exception:
        return DEFAULT_DENSITY
    hosts = set()
    for line in body.splitlines():
        url = line.strip()
        if not url:
            continue
        host = url.split("//", 1)[-1].split("/", 1)[0].split(":")[0]
        parts = host.split(".")
        depth = len(suffix.split(".")) + 1
        if len(parts) >= depth:
            hosts.add(".".join(parts[-depth:]))
    return max(len(hosts), 1) / 1.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--probe",
        action="store_true",
        help="sample one page per suffix to measure domains per page rather than assume it",
    )
    args = ap.parse_args()

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
        # **Domains per page is measured, not assumed, and the assumption was wrong.**
        # The first version used a flat 20 domains per 200-row page, taken from the
        # `.uk` sweeps. Measured on `com.au`: 56,872 capture rows yielded 435 distinct
        # in-window pairs, about 1.5 domains per page, because that namespace is a few
        # sites crawled deeply rather than many sites crawled once. Estimating headroom
        # from page count alone therefore overstated `com.au` by more than tenfold.
        #
        # A page count measures CAPTURES, and what the metric pays for is DOMAINS. The
        # ratio between them is a property of how a namespace was crawled, so it has to
        # come from a sample of that namespace. `--probe` takes one page per suffix and
        # counts the distinct domains in it, which costs one extra request and removes
        # the guess.
        per_page = probe_density(suffix) if args.probe else DEFAULT_DENSITY
        est_domains = int(n * per_page)
        headroom = max(est_domains - held[suffix], 0)
        rows.append((w * headroom, suffix, w, n, held[suffix], headroom))
        print(f"  {suffix:<10} pages={n:>9,} held={held[suffix]:>9,}", file=sys.stderr)

    rows.sort(reverse=True)
    print(f"\n{'suffix':<10}{'weight':>8}{'pages':>11}{'held':>11}{'headroom':>12}{'score EE':>13}")
    for score, suffix, w, n, h, room in rows:
        print(f"{suffix:<10}{w:>8.4f}{n:>11,}{h:>11,}{room:>12,}{score:>13,.0f}")


if __name__ == "__main__":
    main()
