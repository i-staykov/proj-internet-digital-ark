"""Rank EVERY public suffix by measured headroom, rather than guessing which to try.

**Why systematic beats another guess.** `suffix_rank.py` was pointed at about 70
suffixes I chose by hand, and its top pick collapsed on measurement (C-40). The
Public Suffix List has roughly 9,000 entries, and the sweep works on any of them
that names a real namespace. Choosing by intuition is what produced the wrong
answer twice; enumerating the list and measuring each one cannot.

**What makes this affordable.** Two filters cut the list before a single request:

  weight    the right-most TLD must score >= 0.5 in the fixed model, since the
            metric pays for English share and a `.de` namespace is worth a sixth
            of a `.uk` one whatever its size
  era       the TLD must have existed in 1996-2001. Every `xn--` suffix and every
            2012-round gTLD is excluded by delegation date, which is a registry
            fact rather than a guess about names

What remains is a few hundred, and each costs two cheap requests: a page count and
one page sampled for its distinct-domain density. **Both are needed**: C-40 shows a
page count alone overstated `com.au` by more than tenfold, because a page measures
captures and the metric pays for domains.

    uv run python scripts/psl_rank.py --out data/raw/cdx_suffix/psl_ranked.tsv
"""

import argparse
import sys
import time
import urllib.parse
import urllib.request
from decimal import Decimal
from pathlib import Path

import duckdb

sys.path.insert(0, "src")
from ark.english_share import english_weights  # noqa: E402

UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
BASE = "https://web.archive.org/cdx/search/cdx"
PSL_URL = "https://publicsuffix.org/list/public_suffix_list.dat"

# gTLDs delegated in the 2012 round or later cannot hold a 1996-2001 domain. Listing
# the ones that DID exist is shorter and safer than listing the ones that did not.
ERA_GTLDS = {"com", "net", "org", "edu", "gov", "mil", "int", "arpa"}


def fetch_psl(cache: Path) -> list[str]:
    if not cache.exists():
        req = urllib.request.Request(PSL_URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as fh:
            cache.write_bytes(fh.read())
    out = []
    for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith(("*.", "!")):
            continue
        if "xn--" in line:
            continue
        out.append(line)
    return out


def ask(url: str, extra: dict) -> tuple[int, str]:
    params = {
        "url": url,
        "matchType": "domain",
        "from": "1996",
        "to": "2001",
        "filter": "statuscode:200",
    }
    params.update(extra)
    req = urllib.request.Request(
        f"{BASE}?{urllib.parse.urlencode(params)}", headers={"User-Agent": UA}
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as fh:
            return fh.status, fh.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return -1, str(exc)[:80]


def measure(suffix: str) -> tuple[int, int]:
    """(pages, distinct domains in one sampled page)."""
    code, body = ask(suffix, {"showNumPages": "true", "pageSize": "200"})
    if code != 200:
        return -1, 0
    try:
        pages = int(body.strip() or 0)
    except Exception:
        return 0, 0
    if pages <= 0:
        return 0, 0
    time.sleep(1.0)
    code, body = ask(suffix, {"fl": "original", "pageSize": "200", "page": "0"})
    if code != 200:
        return pages, 0
    depth = len(suffix.split(".")) + 1
    hosts = set()
    for line in body.splitlines():
        url = line.strip()
        if not url:
            continue
        host = url.split("//", 1)[-1].split("/", 1)[0].split(":")[0]
        parts = host.split(".")
        if len(parts) >= depth:
            hosts.add(".".join(parts[-depth:]))
    return pages, len(hosts)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="data/raw/cdx_suffix/psl_ranked.tsv")
    ap.add_argument("--min-weight", type=float, default=0.5)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    weights = english_weights()

    suffixes = fetch_psl(out.parent / "public_suffix_list.dat")
    print(f"{len(suffixes):,} suffixes in the list", file=sys.stderr)

    keep = []
    for s in suffixes:
        tld = s.rsplit(".", 1)[-1]
        w = weights.get(tld, Decimal(0))
        if w < Decimal(str(args.min_weight)):
            continue
        # A single-label suffix is a TLD, and only the era gTLDs and ccTLDs qualify.
        # ccTLDs are two letters by definition, which is what distinguishes them from
        # the 2012-round gTLDs without needing a delegation table.
        if "." not in s and s not in ERA_GTLDS and len(s) != 2:
            continue
        keep.append(s)
    print(f"{len(keep):,} pass the weight and era filters", file=sys.stderr)
    if args.limit:
        keep = keep[: args.limit]

    for _ in range(120):
        try:
            con = duckdb.connect("data/ark.duckdb", read_only=True)
            break
        except Exception:
            time.sleep(20)
    else:
        sys.exit("store stayed locked")

    rows = []
    with out.open("w", encoding="utf-8") as fh:
        fh.write("suffix\tweight\tpages\tdomains_per_page\theld\theadroom\tscore_ee\n")
        for i, suffix in enumerate(keep, 1):
            pages, per_page = measure(suffix)
            time.sleep(args.delay)
            if pages <= 0 or per_page <= 0:
                continue
            held = con.execute(
                "select count(distinct domain) from domain_year where domain like ?",
                [f"%.{suffix}"],
            ).fetchone()[0]
            w = weights.get(suffix.rsplit(".", 1)[-1], Decimal(0))
            est = pages * per_page
            headroom = max(est - held, 0)
            score = w * headroom
            rows.append((score, suffix, w, pages, per_page, held, headroom))
            fh.write(f"{suffix}\t{w}\t{pages}\t{per_page}\t{held}\t{headroom}\t{score:.0f}\n")
            fh.flush()
            if score > 1000:
                print(
                    f"  [{i}/{len(keep)}] {suffix:<20} pages={pages:>7,} "
                    f"dom/page={per_page:>4} held={held:>8,} SCORE={score:,.0f}",
                    file=sys.stderr,
                )

    rows.sort(reverse=True)
    print(f"\n{'suffix':<22}{'weight':>8}{'pages':>9}{'d/page':>8}{'held':>10}{'score EE':>12}")
    for score, suffix, w, pages, per_page, held, _room in rows[:30]:
        print(f"{suffix:<22}{w:>8.4f}{pages:>9,}{per_page:>8}{held:>10,}{score:>12,.0f}")
    print(f"\ntotal headroom across all measured suffixes: {sum(r[0] for r in rows):,.0f} EE")


if __name__ == "__main__":
    main()
