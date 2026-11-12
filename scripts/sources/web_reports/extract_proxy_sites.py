"""Origin servers from public proxy and cache statistics pages, each with its file and line.

A caching proxy's log analyser wrote these pages from the proxy's own access log: the sites
table names every origin server the proxy fetched from in the report's period, with the
requests and the bytes. Read:

- pwebstats in proxy mode, "Number of Requests to all sites accessed by Server"
  (`<series>.<N>.total-remote-hosts.html`): `host : requests : bytes`. The page prints no
  period. Its summary page beside the hosts/ folder does, and is shown to be the same period by
  its ten busiest sites standing on the page row for row. When that summary is not held, the
  two summaries of the same numbered series nearest below and above date it, if every held
  summary of the series rises in date with its number and the two fall in one year;
- the ANU cache software's weekly "Number of Requests by Site" (`09JUL2000 - 15JUL2000`);
- squid access-summary text: `TIMESTAMP|FIRST`, `TIMESTAMP|LAST` (epoch seconds) and
  `SE|http://host|COUNT|<code> n`, `SE|http://host|BYTES|<code> n`.

    uv run python scripts/sources/web_reports/extract_proxy_sites.py OUT_DIR STORE [STORE ...]

A store holds a reader's pages under <host>/<path> and its receipts.receipts. Writes rows.jsonl
{host, year, file, pos, field: "proxy_origin", tier, source_file, line, raw_file, raw_line,
site, generator} and witness.txt.gz; `pos` is `line <n> period <first>-<last> requests <n>
bytes <n>`. One row per distinct (host, year). No row: zero bytes, an https or ftp key, a
`:443` or `:21` token, a first label `ftp`, a name `host_of` refuses, a period touching two
years. `tier` is "answered" when the requests average 2,000 bytes or the cache revalidated the
object (a proxy's own error page for a name that does not resolve stays under that), else
"low_bytes".
"""

import gzip
import json
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import extract_host_reports as ehr  # noqa: E402

TS = re.compile(r"^TIMESTAMP\|(FIRST|LAST)\s+(\d{9,10})(?:\.\d+)?\s*$", re.M)
SE = re.compile(r"^SE\|http://([^|/\s]+)/?\|(COUNT|BYTES)\|([A-Z_]+)\s+(\d+)\s*$")
ORIGIN = re.compile(r"HIT|REFRESH")  # served from its origin: a cached copy or a revalidation
ANU_STAMP = re.compile(r"\b(\d{2})([A-Z]{3})(\d{4}) - (\d{2})([A-Z]{3})(\d{4})\b")
ANU_ROW = re.compile(
    r"^.{0,21}\s([A-Za-z0-9][A-Za-z0-9.\-]*\.[A-Za-z]{2,})\s+([\d,]+)\s+([\d,]+\.\d+)\s*$"
)
NOT_WEB = re.compile(r":(?:443|21|563)$|^ftp\d*\.", re.I)
SERIES = re.compile(r"(.+)\.(\d+)(\.html?)$")


def num(text: str) -> int:
    return int(re.sub(r"[ .,]", "", text) or 0)


def day(d: str, mon: str, y: str) -> date:
    return date(int(y), ehr.MONTHS[mon.lower()[:3]], int(d))


def summary_span(page: Path) -> tuple[date, date, str] | None:
    """A pwebstats summary's period and the rows of its table of origin servers."""
    flat = ehr.TAG.sub(" ", page.read_bytes().decode("latin-1"))
    m = ehr.PWEB_STAMP.search(flat)
    if not m:
        return None
    try:
        start, end = day(*m.group(1, 2, 3)), day(*m.group(4, 5, 6))
    except (KeyError, ValueError):
        return None
    sites = flat.partition("Remote sites accessed by this server")[2].split("Protocols proxied")[0]
    return start, end, sites


def pweb_period(path: Path, mine: set) -> tuple[date, date, str] | None:
    name = path.name.replace(".total-remote-hosts", "")
    own = path.parent.parent / name
    got = summary_span(own) if own.exists() else None
    if got:
        top = [r.groups() for r in map(ehr.PWEB_ROW.match, got[2].splitlines()) if r][:10]
        if len(top) >= 5 and all(t in mine for t in top):
            note = f"{name}: its {len(top)} busiest sites stand on this page, requests and bytes"
            return got[0], got[1], note
        return None
    m = SERIES.match(name)
    if not m:
        return None
    held = []
    for page in path.parent.parent.glob(f"{m.group(1)}.*{m.group(3)}"):
        k = SERIES.match(page.name)
        span = summary_span(page) if k and k.group(1) == m.group(1) else None
        if span:
            held.append((int(k.group(2)), span[0], span[1], page.name))
    held.sort()
    lower = [h for h in held if h[0] < int(m.group(2))]
    upper = [h for h in held if h[0] > int(m.group(2))]
    rising = all(a[1] < b[1] for a, b in zip(held, held[1:], strict=False))
    if len(held) < 3 or not rising or not lower or not upper:
        return None
    lo, up = lower[-1], upper[0]
    return lo[1], up[2], f"{name} stands between {lo[3]} and {up[3]} of one numbered series"


def pweb_remote(text, lines, path):
    if "frequency of access to remote sites" not in text[:3000].lower():
        return
    rows = [(n, r) for n, r in enumerate(map(ehr.PWEB_ROW.match, lines), 1) if r]
    got = pweb_period(path, {r.groups() for _, r in rows})
    if got:
        for n, r in rows:
            yield r.group(1), got[0], got[1], num(r.group(2)), num(r.group(3)), False, n, got[2]


def anu(text, lines, path):
    m = ANU_STAMP.search(text[:3000])
    if not m or "Number of Requests by Site" not in text[:3000]:
        return
    try:
        start, end = day(*m.group(1, 2, 3)), day(*m.group(4, 5, 6))
    except (KeyError, ValueError):
        return
    for n, r in enumerate(map(ANU_ROW.match, lines), 1):
        if r:
            size = int(float(r.group(3).replace(",", "")) * 1e6)
            yield r.group(1), start, end, num(r.group(2)), size, False, n, m.group(0)


def access_summary(text, lines, path):
    stamps = {k: int(v) for k, v in TS.findall(text[:20000])}
    if len(stamps) != 2:
        return
    first, last = (datetime.fromtimestamp(stamps[k], UTC).date() for k in ("FIRST", "LAST"))
    seen = {}
    for n, r in enumerate(map(SE.match, lines), 1):
        if r:
            got = seen.setdefault(r.group(1), {"n": n, "COUNT": 0, "BYTES": 0, "origin": False})
            got[r.group(2)] += int(r.group(4))
            got["origin"] |= bool(ORIGIN.search(r.group(3))) and "NEGATIVE" not in r.group(3)
    stamp = f"TIMESTAMP|FIRST {stamps['FIRST']} LAST {stamps['LAST']}"
    for host, got in seen.items():
        yield host, first, last, got["COUNT"], got["BYTES"], got["origin"], got["n"], stamp


READERS = {
    "pwebstats-remote-sites": pweb_remote,
    "anu-cache-sites": anu,
    "squid-access-summary": access_summary,
}


def main(argv: list[str] | None = None) -> int:
    out, *stores = (Path(a) for a in (argv or sys.argv[1:]))
    out.mkdir(parents=True, exist_ok=True)
    best = {}
    for store in stores:
        for path in sorted(p for p in store.rglob("*") if p.is_file()):
            if path.name.startswith(("receipts.", "trees.")) or not ehr.page_url(path):
                continue
            text = path.read_bytes().decode("latin-1")
            lines = re.split(r"\r\n|\r|\n", text)
            for gen, reader in READERS.items():
                for token, start, end, reqs, size, origin, n, stamp in reader(text, lines, path):
                    host = None if NOT_WEB.search(token.strip()) else ehr.host_of(token, start.year)
                    if start.year != end.year or not host or size <= 0 or reqs <= 0:
                        continue
                    tier = "answered" if origin or size / reqs >= 2000 else "low_bytes"
                    old = best.get((host, start.year))
                    if old is None or (old[0] == "low_bytes" and tier == "answered"):
                        span = f"{start:%Y%m%d}-{end:%Y%m%d}"
                        pos = f"line {n} period {span} requests {reqs} bytes {size}"
                        rel = f"{store.name}/{path.relative_to(store)}"
                        best[(host, start.year)] = (
                            tier,
                            rel,
                            n,
                            pos,
                            stamp,
                            lines[n - 1],
                            gen,
                            path,
                        )
    order = sorted(best.items(), key=lambda kv: (kv[1][1], kv[1][2], kv[0]))
    with (out / "rows.jsonl").open("w") as rows, gzip.open(out / "witness.txt.gz", "wt") as wit:
        for i, ((host, year), (tier, rel, n, pos, stamp, verb, gen, path)) in enumerate(order, 1):
            wit.write(f"{year} {host} {rel}#{n} [{tier}] | {stamp} | {' '.join(verb.split())}\n")
            row = {
                "host": host, "year": year, "file": ehr.page_url(path), "pos": pos,
                "field": "proxy_origin", "tier": tier, "source_file": "witness.txt.gz", "line": i,
                "raw_file": f"raw/{rel}", "raw_line": n, "site": rel.split("/")[1],
                "generator": gen,
            }  # fmt: skip
            rows.write(json.dumps(row) + "\n")
    print(json.dumps({"rows": len(best)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
