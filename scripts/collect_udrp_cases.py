"""Fetch the WIPO UDRP case index for 1999-2001 as dated items.

Found on 2026-08-11 by asking what shape the sources that actually paid this round
have in common: registry creation dates, dated DNS surveys and a defacement mirror
are all **machine-generated records about whoever happened to be there**, not human
curation of who was notable. A domain-dispute docket is exactly that shape.

Each case is a dispute over a registered domain, decided by an arbitration panel
and published with its case number. A case numbered `D2000-0123` was filed in 2000,
which means the domain was registered and in dispute in 2000: the record is
authoritative about the year in a way a crawl is not, because it does not depend on
anyone having visited the site.

The year used is the **filing** year from the case number rather than the decision
date, which is the earlier and therefore safer claim: a case filed in late 2000 may
be decided in 2001, and the domain certainly existed at filing.

Non-IA host, so it spends no Internet Archive budget. Honest User-Agent, one
request every 1.5 s, 133 requests for the whole window.

**Measured 2026-08-11 against the live store:** 3,325 cases, 6,069 distinct
(domain, year) pairs over 6,041 domains, of which **only 680 are already held**.
88.8% absent is the highest share of any source measured on this project, and the
reason is structural rather than lucky: a disputed name is often a typosquat taken
down within weeks, which is the population a crawl never visits. Read as
`artifact_listing` it is 5,389 net-new pairs and 3,281.0 equivalent-English at mean
weight 0.6208; read with the corroboration split, 956 and 593.5. Which reading
applies is recorded as an open decision in `docs/key-decisions.md`.

Writes items only. Nothing here touches the store.
"""

import html
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
UA = (
    "InternetDigitalArk/1.0 (historical domain research, 1996-2001; "
    "contact ivaylo.staykov@taktile.com)"
)
LIST = (
    "https://www.wipo.int/amc/en/domains/casesx/list.jsp"
    "?prefix=D&year={year}&seq_min={lo}&seq_max={hi}"
)
CASE_RE = re.compile(r"\bD(\d{4})-(\d{4})\b")
HOST_RE = re.compile(
    r"\b([a-z0-9][a-z0-9\-]{0,62}(?:\.[a-z0-9][a-z0-9\-]{0,62})*\.[a-z]{2,6})\b", re.I
)
# Hosts that belong to the page furniture rather than to a dispute.
CHROME = {
    "wipo.int",
    "www.wipo.int",
    "accessiblebooksconsortium.org",
    "google.com",
    "gtm.js",
    "index.html",
    "list.jsp",
}


def fetch(url: str, tries: int = 4) -> str:
    for attempt in range(tries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503, 504) and attempt < tries - 1:
                time.sleep(10 * (attempt + 1))
                continue
            return ""
        except Exception:
            if attempt < tries - 1:
                time.sleep(5)
                continue
            return ""
    return ""


def text_of(page: str) -> str:
    body = re.sub(r"(?is)<script.*?</script>", " ", page)
    body = re.sub(r"(?is)<style.*?</style>", " ", body)
    body = re.sub(r"<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", html.unescape(body))


ROW_RE = re.compile(r"(?is)<tr[^>]*>(.*?)</tr>")
CELL_RE = re.compile(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>")


def cell_text(cell: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", cell))).strip()


def cases_in(page: str, year: int) -> dict[str, set[str]]:
    """{case number: {disputed domains}} taken from the table's SECOND COLUMN only.

    The row is `[case number, disputed domain(s), complainant, respondent, -, status]`,
    so the domain sits in its own structured field rather than in prose. That is what
    makes this source `artifact_listing` and not `dated_directory`: there is no
    transcription risk to guard against, in the same way Tucows' `creator` field
    carries none while a Usenet post's URL does.

    The first version took every hostname between one case number and the next, which
    swept in `www3.wipo.int` from the page furniture and would have swept in any host
    a party's name happened to contain. A structured column cannot do that.
    """
    out: dict[str, set[str]] = {}
    for row in ROW_RE.findall(page):
        cells = [cell_text(c) for c in CELL_RE.findall(row)]
        if len(cells) < 2:
            continue
        case = cells[0].strip()
        found = CASE_RE.fullmatch(case)
        if not found or int(found.group(1)) != year:
            continue
        hosts = set()
        for host in HOST_RE.findall(cells[1]):
            low = host.lower()
            if low in CHROME or low.endswith((".jsp", ".html", ".js", ".css")):
                continue
            hosts.add(low)
        if hosts:
            out.setdefault(case, set()).update(hosts)
    return out


def main() -> None:
    out = HERE / "items.jsonl"
    total_cases = 0
    total_hosts = 0
    with out.open("w", encoding="utf-8") as fh:
        for year in (1999, 2000, 2001):
            empty_streak = 0
            for lo in range(1, 2600, 60):
                page = fetch(LIST.format(year=year, lo=lo, hi=lo + 59))
                found = cases_in(page, year) if page else {}
                if not found:
                    empty_streak += 1
                    if empty_streak >= 2:
                        break
                    time.sleep(1.5)
                    continue
                empty_streak = 0
                for case, hosts in found.items():
                    fh.write(
                        json.dumps({"item": case, "year": year, "text": " ".join(sorted(hosts))})
                        + "\n"
                    )
                    total_cases += 1
                    total_hosts += len(hosts)
                print(f"  {year} seq {lo}-{lo + 59}: {len(found)} cases", flush=True)
                time.sleep(1.5)
    print(f"\nwrote {out}: {total_cases:,} cases, {total_hosts:,} host mentions")


if __name__ == "__main__":
    main()
