"""Client hostnames from public web-server usage reports, each with its file and line.

A log analyser (Analog, getstats, pwebstats, Webalizer, http-analyze, WWWusage, WebStat) wrote
these pages from the server's own access log: the host table names the reverse-DNS name of every
client the server answered in the report's period. What dates one row is the report's own
machine-written period stamp (or, for getstats, the row's own last-access date). A report whose
period spans two calendar years dates nothing, except one begun in December that ends on
1 January, or a monthly one that ends by 7 January, which takes its December year and is marked
`straddle` so that it can be dropped.
WWWusage and WebStat print names reversed (`com.inktomisearch.j4019`); those are turned round
and marked `reversed`, and a name WebStat cut on the left (`...`) is refused.

    uv run python scripts/sources/web_reports/extract_host_reports.py RAW_ROOT OUT_DIR

raw_root holds one directory per site with the fetched pages (and the fetcher's receipts).
Writes rows.jsonl and witness.txt.gz under out_dir:
  rows.jsonl      {host, year, file, pos, field: "visitor_rdns", source_file: "witness.txt.gz",
                   line, site, raw_file, raw_line, generator[, straddle][, reversed]}; file is
                   the page's own URL or its Wayback replay URL, pos the line in that page
  witness.txt.gz  "<year> <site>/<file> line <n> [<generator>] <host> | <stamp> | <verbatim row>"
One row per distinct (host, year): the first report that names it.
"""

import gzip
import html
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from ark.delegation import existed
from ark.hostnames import _VALID_HOST

TAG = re.compile(r"<[^>]+>")
IPV4 = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
ANALOG_STAMP = re.compile(
    r"Analy[sz]ed\s+requests\s+from\s+(.{8,60}?)\s+to\s+(.{8,60}?)\s*(?:\(|<|$)", re.S | re.I
)
A_DATE = re.compile(
    r"(\d{1,2})[ \-/]([A-Za-z]{3})[a-z]*[ \-/,]+(\d{4})|([A-Za-z]{3})[a-z]*\s+(\d{1,2}),?\s+(\d{4})"
)
HOST_INTRO = re.compile(r"\b(?:Listing|Printing)\b[^.]{0,40}\bhosts\b", re.I)
ANALOG_ROW = re.compile(r"^\s*[\d,]+\s*:.*:\s*(\S+)\s*$")
GETSTATS_ROW = re.compile(r"^\s*(\d+)\s*:\s*(\d\d)/(\d\d)/(\d\d)\s*:\s*(?:\d+\s*:\s*)?(\S+)\s*$")
PWEB_STAMP = re.compile(
    r"[^\n(]{0,80}\((\d{1,2}) ([A-Za-z]{3}) (\d{4})\s*-\s*(\d{1,2}) ([A-Za-z]{3}) (\d{4})\)"
)
PWEB_ROW = re.compile(r"^\s*(\S+)\s+:\s+[\d,]+\s+:\s+[\d,]+\s*$")
WEBALIZER_STAMP = re.compile(r"Summary Period:\s*([A-Za-z]+)\s+(\d{4})")
WEBALIZER_OTHER = (
    r"Total (URLs?|Referrers|Search Strings|User Agents|Countries|Usernames|Entry|Exit)"
)
WEBALIZER_CELL = re.compile(r"<TD ALIGN=left[^>]*>(?:<FONT[^>]*>)?([^<\s]+)</FONT></TD></TR>", re.I)
HA_STAMP = re.compile(r"Summary period:\s*([A-Za-z]+)\s+(\d{4})")
HA_TITLE = re.compile(r"<TITLE>[^<]*\(([A-Za-z]+) (\d{4})\)\s*</TITLE>", re.I)
HA_ROW = re.compile(r"^\s*\d+\s+[\d.]+%\s+\d+\s+[\d.]+%\s+\d+\s+[\d.]+%\s+\|\s+(\S+)\s*$")
_DAY = r"([A-Za-z]{3})\s+(\d{1,2})\s+(\d{4})"
SPAN_STAMP = re.compile(rf"Summary (?:for )?Period:\s*{_DAY}\s+to\s+{_DAY}", re.I)
WWWUSAGE_ROW = re.compile(r"ALIGN=LEFT><B>([^<]+)</B>", re.I)
WEBSTAT_ROW = re.compile(r"^(\S+)\s+\d+\s+\d+\s+[\d.]+\s+[\d.]+\s*$")


def a_date(text: str) -> date | None:
    m = A_DATE.search(text)
    if not m:
        return None
    if m.group(1):
        d, mon, y = int(m.group(1)), m.group(2), int(m.group(3))
    else:
        mon, d, y = m.group(4), int(m.group(5)), int(m.group(6))
    mon = MONTHS.get(mon.lower())
    try:
        return date(y, mon, d) if mon else None
    except ValueError:
        return None


def period_year(start: date | None, end: date | None) -> tuple[int | None, bool]:
    """The one year a period dates, and whether it leaned over New Year."""
    if not start or not end or end < start:
        return None, False
    if start.year == end.year:
        return start.year, False
    if start.month == 12 and end.year == start.year + 1 and end.month == 1:
        if end.day == 1 or (end.day <= 7 and (end - start).days >= 28):
            return start.year, True
    return None, False


def span(text: str) -> tuple[int | None, bool, str]:
    m = SPAN_STAMP.search(TAG.sub(" ", text))
    if not m:
        return None, False, ""
    try:
        start = date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2)))
        end = date(int(m.group(6)), MONTHS[m.group(4).lower()], int(m.group(5)))
    except (KeyError, ValueError):
        return None, False, ""
    year, straddle = period_year(start, end)
    return year, straddle, " ".join(m.group(0).split())


def host_of(token: str, year: int) -> str | None:
    h = html.unescape(token).strip().rstrip(".").lower()
    if not h or IPV4.match(h) or "." not in h:
        return None
    if not _VALID_HOST.match(h) or not existed(h.rsplit(".", 1)[-1], year):
        return None
    labels = h.split(".")
    # the brief's quarantine: a suffix of 1 to 3 labels written twice in a row is a
    # misconfigured resolver's name (`x.example.com.example.com`), not a host
    if any(labels[-k:] == labels[-2 * k : -k] for k in (1, 2, 3) if len(labels) > 2 * k):
        return None
    return h


def turned(token: str) -> str:
    return ".".join(reversed(token.strip().split(".")))


def analog(lines, text, path):
    m = ANALOG_STAMP.search(TAG.sub(" ", text))
    if not m:
        return
    year, straddle = period_year(a_date(m.group(1)), a_date(m.group(2)))
    if year is None:
        return
    stamp = " ".join(m.group(0).split()).rstrip("(<").strip()
    inside = False
    for n, line in enumerate(lines, 1):
        flat = html.unescape(TAG.sub("", line)).replace("\xa0", " ")
        if HOST_INTRO.search(flat) and "virtual host" not in flat.lower():
            inside = True
            continue
        if inside and re.search(r"<h2|<hr|</pre", line, re.I):
            inside = False
            continue
        if not inside:
            continue
        r = ANALOG_ROW.match(flat)
        if r:
            yield r.group(1), year, straddle, n, stamp, flat, False


def getstats(lines, text, path):
    if "Last Access (M/D/Y)" not in text:
        return
    inside = False
    for n, line in enumerate(lines, 1):
        flat = html.unescape(TAG.sub("", line))
        if "Last Access (M/D/Y)" in flat:
            inside = flat.rstrip().endswith("Hostname")
            continue
        if not inside:
            continue
        r = GETSTATS_ROW.match(flat)
        if r:
            yy = int(r.group(4))
            yield (
                r.group(5),
                (1900 + yy if yy >= 90 else 2000 + yy),
                False,
                n,
                "row's own Last Access (M/D/Y)",
                flat,
                False,
            )


_STAMPS: dict[Path, dict | None] = {}
_URLS: dict[Path, dict] = {}


def page_url(path: Path) -> str:
    """Where a page was fetched: its Wayback replay URL with the capture's stamp, or the
    site's own URL, as the fetch receipts at the tree root record it; "" when they do not."""
    for root in path.parents:
        receipts = root / "receipts.receipts"
        if not receipts.exists():
            continue
        if root not in _URLS:
            found = {}
            for line in receipts.read_text().splitlines():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                where = r.get("path") or ""
                if r.get("replay"):
                    found[str(root / where)] = r["replay"]
                elif r.get("bytes") and "/raw/" in where:
                    found[str(root / where.split("/raw/", 1)[1])] = r.get("url", "")
            _URLS[root] = found
        return _URLS[root].get(str(path), "")
    return ""


def capture_stamps(path: Path) -> dict | None:
    """Capture instants by page for a tree read out of the Wayback Machine, None for a tree
    fetched from its own site: the reader's receipts sit at the tree root and name each
    page's replay URL."""
    for root in path.parents:
        receipts = root / "receipts.receipts"
        if not receipts.exists():
            continue
        if root not in _STAMPS:
            found = {}
            for line in receipts.read_text().splitlines():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                m = re.search(r"/web/(\d{14})", r.get("replay") or "")
                if m and r.get("path"):
                    found[str(root / r["path"])] = datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
            _STAMPS[root] = found or None
        return _STAMPS[root]
    return None


def pwebstats(lines, text, path):
    """A pwebstats host page carries no period; its summary page roger.<N>.html beside the
    hosts/ directory does, so the stamp is read there and the witness names both."""
    if "Frequency of Access: Hosts" not in text:
        return
    sibling = path.parent.parent / path.name.replace(".total-hosts", "")
    if not sibling.exists():
        return
    paired = ""
    stamps = capture_stamps(path)
    if stamps is not None:
        # two Wayback captures: the period page must have been taken within a week of the
        # host page, or a renumbered series could lend one week's dates to another's hosts
        a, b = stamps.get(str(path)), stamps.get(str(sibling))
        if not a or not b or abs((a - b).days) > 7:
            return
        paired = f" (captures {a:%Y%m%d} and {b:%Y%m%d})"
    m = PWEB_STAMP.search(TAG.sub(" ", sibling.read_bytes().decode("latin-1")))
    if not m:
        return
    try:
        start = date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
        end = date(int(m.group(6)), MONTHS[m.group(5).lower()], int(m.group(4)))
    except (KeyError, ValueError):
        return
    year, straddle = period_year(start, end)
    if year is None:
        return
    stamp = f"{sibling.name}: " + " ".join(m.group(0).split()) + paired
    for n, line in enumerate(lines, 1):
        flat = html.unescape(TAG.sub(" ", line))
        r = PWEB_ROW.match(flat)
        if r:
            yield r.group(1), year, straddle, n, stamp, flat, False


def http_analyze(lines, text, path):
    """http-analyze 1.9 lists hosts under "Total Transfers by Client Domain"; 2.x lists them only
    on its `lsites` page, whose column is headed Hostname, while its `sites` page (Overview)
    lists domains and is not read. The period is the month in the page title."""
    if "http-analyze" not in text or "(Overview)" in text:
        return
    m = HA_TITLE.search(text) or HA_STAMP.search(TAG.sub(" ", text))
    if not m or m.group(1)[:3].lower() not in MONTHS:
        return
    if not re.search(r"\|\s*Hostname", text) and not re.search(r"http-analyze 1\.", text):
        return
    year = int(m.group(2))
    stamp = " ".join(TAG.sub(" ", m.group(0)).split())
    for n, line in enumerate(lines, 1):
        if "<A " in line.upper() and "HREF" in line.upper():
            continue
        flat = html.unescape(TAG.sub("", line))
        r = HA_ROW.match(flat)
        if r:
            yield r.group(1), year, False, n, stamp, flat, False


def wwwusage(lines, text, path):
    if "DNS names are reversed" not in text:
        return
    year, straddle, stamp = span(text)
    if year is None:
        return
    inside = False
    for n, line in enumerate(lines, 1):
        if re.search(r"<H2", line, re.I):
            inside = bool(re.search(r"Total Transfers by Client Host", line, re.I))
            continue
        if not inside:
            continue
        r = WWWUSAGE_ROW.search(line)
        if r and not r.group(1).startswith("--"):
            yield (
                turned(r.group(1)),
                year,
                straddle,
                n,
                stamp,
                html.unescape(TAG.sub(" ", line)),
                True,
            )


def webstat(lines, text, path):
    if "Reversed Subdomain" not in text:
        return
    year, straddle, stamp = span(text)
    if year is None:
        return
    inside = False
    for n, line in enumerate(lines, 1):
        if re.search(r"<h2", line, re.I):
            inside = "Reversed Subdomain" in line
            continue
        if not inside:
            continue
        flat = html.unescape(TAG.sub("", line))
        r = WEBSTAT_ROW.match(flat)
        if r and not r.group(1).startswith("..."):
            yield turned(r.group(1)), year, straddle, n, stamp, flat, True


def webalizer(lines, text, path):
    """Webalizer's monthly page prints its top sites as a table, one cell a line, the hostname
    in the row's last cell; its all-sites page prints every site as one text line."""
    m = WEBALIZER_STAMP.search(TAG.sub(" ", text))
    if not m or m.group(1)[:3].lower() not in MONTHS:
        return
    year = int(m.group(2))
    stamp = " ".join(m.group(0).split())
    inside = False
    for n, line in enumerate(lines, 1):
        flat = html.unescape(TAG.sub(" ", line)).strip()
        if re.search(r"Total Sites|Hostname", flat):
            inside = True
            continue
        if re.search(WEBALIZER_OTHER, flat):
            inside = False
            continue
        if not inside:
            continue
        cell = WEBALIZER_CELL.search(line)
        if cell:
            yield cell.group(1), year, False, n, stamp, flat, False
            continue
        parts = flat.split()
        if len(parts) >= 3 and parts[0].isdigit():
            yield parts[-1], year, False, n, stamp, flat, False


WUSAGE_TITLE = re.compile(
    r"(?:Week|Month|Day|Year|Woche|Monat|Tag) (?:of|vom) (\d\d)[/.](\d\d)[/.](\d\d)"
    r" (?:to|bis) (\d\d)[/.](\d\d)[/.](\d\d)"
)
WUSAGE_SITES = re.compile(r"Top \d+ (?:of|von) \d+ Sites|Top \d+ Sites by Access Count", re.I)
WUSAGE_CELL = re.compile(r"<td[^>]*>\s*([A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z]{2,})\s*(?=<|$)", re.I)


def wusage(lines, text, path):
    """Classic wusage prints its busiest sites, up to a hundred, under "Top N of M Sites by
    Access Count"; the period is the page title, day and month in either order, the year last."""
    m = WUSAGE_TITLE.search(text[:2000])
    if not m:
        return
    y1, y2 = int(m.group(3)), int(m.group(6))
    if y1 != y2:
        return
    year = (1900 if y1 >= 90 else 2000) + y1
    stamp = " ".join(m.group(0).split())
    inside = False
    for n, line in enumerate(lines, 1):
        if re.search(r"<h3", line, re.I):
            inside = bool(WUSAGE_SITES.search(TAG.sub(" ", line)))
            if not inside:
                continue
        if not inside:
            continue
        for cell in WUSAGE_CELL.finditer(line):
            yield cell.group(1), year, False, n, stamp, html.unescape(TAG.sub(" ", line)), False


GENERATORS = (
    ("analog", analog),
    ("getstats", getstats),
    ("pwebstats", pwebstats),
    ("http-analyze", http_analyze),
    ("wwwusage", wwwusage),
    ("webstat", webstat),
    ("webalizer", webalizer),
    ("wusage", wusage),
)


def main(argv: list[str] | None = None) -> int:
    raw_root, out_dir = (Path(a) for a in (argv or sys.argv[1:])[:2])
    out_dir.mkdir(parents=True, exist_ok=True)
    seen: set[tuple[str, int]] = set()
    rows = (out_dir / "rows.jsonl").open("w")
    wit = gzip.open(out_dir / "witness.txt.gz", "wt", encoding="utf-8")
    wline = 0
    stats: dict[str, dict] = {}
    for site_dir in sorted(p for p in raw_root.iterdir() if p.is_dir()):
        st = stats.setdefault(
            site_dir.name,
            {
                "files": 0,
                "dated_files": 0,
                "rows": 0,
                "new_pairs": 0,
                "gen": {},
                "by_year": {},
                "empty": [],
            },
        )
        for path in sorted(
            p
            for p in site_dir.rglob("*")
            if p.is_file() and not p.name.startswith(("receipts.", "trees.", "live."))
        ):
            raw = path.read_bytes().decode("latin-1")
            lines = re.split(r"\r\n|\r|\n", raw)
            st["files"] += 1
            got = 0
            rel = f"{site_dir.name}/{path.relative_to(site_dir)}"
            for name, gen in GENERATORS:
                for token, year, straddle, n, stamp, flat, rev in gen(lines, raw, path):
                    if not 1996 <= year <= 2013:
                        continue
                    host = host_of(token, year)
                    if host is None:
                        continue
                    got += 1
                    if (host, year) in seen:
                        continue
                    seen.add((host, year))
                    wline += 1
                    verbatim = " ".join(flat.split())
                    wit.write(f"{year} {rel} line {n} [{name}] {host} | {stamp} | {verbatim}\n")
                    row = {
                        "host": host,
                        "year": year,
                        "file": page_url(path),
                        "pos": n,
                        "field": "visitor_rdns",
                        "source_file": "witness.txt.gz",
                        "line": wline,
                        "site": site_dir.name,
                        "raw_file": f"raw/{rel}",
                        "raw_line": n,
                        "generator": name,
                    }
                    if straddle:
                        row["straddle"] = True
                    if rev:
                        row["reversed"] = True
                    rows.write(json.dumps(row) + "\n")
                    st["new_pairs"] += 1
                    st["by_year"][year] = st["by_year"].get(year, 0) + 1
                if got:
                    st["gen"][name] = st["gen"].get(name, 0) + 1
                    break
            if got:
                st["dated_files"] += 1
                st["rows"] += got
            elif len(st["empty"]) < 6:
                st["empty"].append(str(path.relative_to(site_dir)))
    rows.close()
    wit.close()
    for site, st in stats.items():
        st["by_year"] = dict(sorted(st["by_year"].items()))
        print(site, json.dumps(st))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
