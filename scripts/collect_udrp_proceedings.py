"""ICANN's consolidated list of UDRP proceedings, as a dated evidence journal.

**How this source was found**, which is more reusable than the source. Instead of
listing places to look, ask what the sources that actually paid this round have in
common: registry creation dates, dated DNS survey shards and a defacement mirror are
all **machine-generated records about whoever happened to be there**, not human
curation of who was notable. Every family that has failed on measurement here selects
for authority, five of them now. So the generative question is not "where is another
list" but **"what else recorded everyone, with a date, for its own reasons"**.

A domain-dispute docket is that shape. A proceeding exists only because the domain
was registered and someone filed a complaint about it, so the record attests
existence in that year **without depending on a crawler having visited the site**,
which is the property that makes 1996-1997 hard to reach any other way.

**One request.** ICANN publishes every proceeding across all five providers that
heard cases in the window in a single 3.3 MB table, with an explicit commencement
date and the disputed name in its own column. Not `web.archive.org`, so it spends no
archive budget.

**Measured 2026-08-11 against the live store:** 5,305 in-window proceedings
(WIPO 3,246, NAF 1,743, DeC 173, eRes 110, CPR 33), 8,800 distinct (domain, year)
pairs over 8,769 domains, of which **only 1,086 are already held**. 87.7% absent is
the highest share of any source measured on this project, and it is structural rather
than lucky: a disputed name is often a typosquat taken down within weeks, which is
exactly the population a crawl never visits.

**Evidence type `artifact_listing`, master, no corroboration split.** See ADR-002 for
the reasoning and `docs/sources.md` for the measured figures under both readings.

**ICANN's own caveat, carried through rather than hidden:** the page describes itself
as "an incomplete list of UDRP proceedings". So this is a floor, not a census, and the
providers' own search tools hold cases this table omits.

    uv run python scripts/collect_udrp_proceedings.py
    uv run ark ingest udrp_proceedings data/raw/udrp/udrp_proceedings.jsonl.gz
"""

import argparse
import gzip
import html
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ark.canonical import to_registrable  # noqa: E402

LIST_URL = "https://www.icann.org/udrp/proceedings-list.htm"
OUT = ROOT / "data/raw/udrp/udrp_proceedings.jsonl.gz"
UA = (
    "InternetDigitalArk/1.0 (historical domain research, 1996-2001; "
    "contact ivaylo.staykov@taktile.com)"
)
YEARS = range(1996, 2002)
ROW_RE = re.compile(r"(?is)<tr[^>]*>(.*?)</tr>")
CELL_RE = re.compile(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>")
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
# Hostnames inside the domain column only. The column holds one or more disputed
# names and nothing else, so this does not need the defensive anchoring a prose
# extractor does.
HOST_RE = re.compile(
    r"\b([a-z0-9][a-z0-9\-]{0,62}(?:\.[a-z0-9][a-z0-9\-]{0,62})*\.[a-z]{2,6})\b", re.I
)


def cell_text(cell: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", cell))).strip()


def rows_of(page: str) -> list[list[str]]:
    return [[cell_text(c) for c in CELL_RE.findall(row)] for row in ROW_RE.findall(page)]


def records_in(page: str, stats: Counter):
    """Yield one journal record per (domain, proceeding) inside the window.

    The columns are `Date Commenced | Date Decided | Proceeding Number |
    Domain Name(s) | Case Type | Status`. The **commencement** date supplies the
    year, deliberately rather than the decision date: a case commenced late in 2000
    may be decided in 2001, and the domain certainly existed when the complaint was
    filed, so the earlier date is the safer claim.
    """
    for cells in rows_of(page):
        if len(cells) < 4:
            continue
        found = DATE_RE.match(cells[0])
        if not found:
            continue
        stats["rows_with_a_date"] += 1
        year = int(found.group(1))
        if year not in YEARS:
            stats["out_of_window"] += 1
            continue
        proceeding = cells[2].strip()
        if not proceeding:
            stats["no_proceeding_number"] += 1
            continue
        stats["in_window_proceedings"] += 1
        seen: set[str] = set()
        for raw in HOST_RE.findall(cells[3]):
            domain = to_registrable(raw.lower())
            if not domain or domain in seen:
                continue
            seen.add(domain)
            stats["records"] += 1
            yield {
                "domain": domain,
                "year": year,
                "proceeding": proceeding,
                "commenced": cells[0],
                "url": LIST_URL,
            }
        if not seen:
            stats["no_domain_in_column"] += 1


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        raise SystemExit(f"could not fetch {url}: {exc}") from exc


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument(
        "--from-file",
        type=Path,
        default=None,
        help="parse a saved copy of the list instead of fetching, for replay",
    )
    args = ap.parse_args()

    page = (
        args.from_file.read_text(encoding="utf-8", errors="replace")
        if args.from_file
        else fetch(LIST_URL)
    )
    stats: Counter = Counter()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.out, "wt", encoding="utf-8") as fh:
        for record in records_in(page, stats):
            fh.write(json.dumps(record) + "\n")
    print(f"wrote {args.out.relative_to(ROOT)}")
    for key in sorted(stats):
        print(f"  {key:24} {stats[key]:>8,}")
    print("\nICANN calls this an incomplete list of proceedings, so it is a floor.")
    print("next: uv run ark ingest udrp_proceedings " + str(args.out.relative_to(ROOT)))


if __name__ == "__main__":
    main()
