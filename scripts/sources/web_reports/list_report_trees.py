"""Find usage-report trees in a crawl's URL list, for `wayback_trees.py` to read.

A crawl of 2001 walked the statistics pages web servers left public, and its URL list names
them where no search engine or CDX query does: LAW's `webbase-2001.urls.gz` (118M URLs) holds
488 http-analyze trees and 60 pwebstats trees. Two shapes carry every client host of a period:

  http-analyze  `<tree>/www<YYYY>/[dir/]lsites<MMYY>.html` (2.x, the list of sites) and
                `<tree>/sites<MMYY>.html` (1.9); a 2.x month seen only through another of its
                pages (`stats`, `files`, `sites`) is asked for its `lsites` page all the same.
  pwebstats     `<tree>/hosts/<name>.<N>.total-hosts.html`, and for a proxy cache
                `...total-remote-hosts.html`; its period is on `<tree>/<name>.<N>.html`.

Writes {tree: {"urls": [...]}}, each list in probe order: the best-attested page of the latest,
earliest and middle period first, since a tree the archive never crawled lacks all three.

    uv run python scripts/sources/web_reports/list_report_trees.py URLS.gz http-analyze OUT.json
    uv run python scripts/sources/web_reports/list_report_trees.py URLS.gz pwebstats OUT.json
"""

import collections
import gzip
import json
import re
import sys

HA_PAGE = re.compile(
    r"^(https?://[^/]+)(/.*?/?)((?:l|r)?sites|lfiles|lrefers|lagents|stats|files|days|nav|topurl"
    r"|topdom|totals)(\d{2})(\d{2})\.html?$",
    re.I,
)
HA_YEAR_DIR = re.compile(r"/www(?:19|20)\d\d/", re.I)
LISTS = {"lsites", "sites", "rsites", "lfiles", "lrefers", "lagents"}
PWEB_PAGE = re.compile(
    r"^(https?://[^/]+)(/.*?)/hosts/([^/]+?)\.(\d+)\.(total-hosts|total-remote-hosts)\.html?$",
    re.I,
)
WANTED = re.compile(r"/www(?:19|20)\d\d/|sites\d{4}\.html?$|total-(?:remote-)?hosts\.html?$", re.I)


def clean(line: str) -> str | None:
    url = line.strip().replace("\\/", "/")
    if not url or " " in url or '"' in url:
        return None
    return re.sub(r"/\./", "/", re.sub(r"/[^/]+/\.\./", "/", url))


def probe_first(best: list[str], urls: list[str]) -> list[str]:
    order: list[str] = []
    for url in [best[0], best[-1], best[len(best) // 2], *urls]:
        if url not in order:
            order.append(url)
    return order


def http_analyze(urls) -> dict:
    trees: dict = collections.defaultdict(lambda: collections.defaultdict(set))
    for url in urls:
        m = HA_PAGE.match(url)
        if not m:
            continue
        base, folder, kind, mm, yy = (
            m.group(1).lower(),
            m.group(2),
            m.group(3).lower(),
            *m.groups()[3:],
        )
        if not "01" <= mm <= "12":
            continue
        tree = base + re.sub(r"/www(?:19|20)\d\d/.*$", "/", folder, flags=re.I)
        trees[tree][(base + folder, mm + yy)].add(kind)
    out = {}
    for tree, months in trees.items():
        kinds = set().union(*months.values())
        two = bool(HA_YEAR_DIR.search(next(iter(months))[0])) or bool(kinds & {"lsites", "lfiles"})
        cands = []
        for (folder, mmyy), seen in months.items():
            year = (1900 if mmyy[2:] >= "90" else 2000) + int(mmyy[2:])
            if not 1996 <= year <= 2001:
                continue
            if two:
                rank = 0 if "lsites" in seen else 1 if seen & LISTS else 2
                cands.append((rank, -year, mmyy, f"{folder}lsites{mmyy}.html"))
            elif "sites" in seen:
                cands.append((0, -year, mmyy, f"{folder}sites{mmyy}.html"))
        if cands:
            cands.sort()
            best = [c[3] for c in cands if c[0] == cands[0][0]]
            out[tree] = {"urls": probe_first(best, [c[3] for c in cands])}
    return out


def pwebstats(urls) -> dict:
    trees: dict = collections.defaultdict(dict)
    for url in urls:
        m = PWEB_PAGE.match(url)
        if m:
            trees[m.group(1).lower() + m.group(2) + "/"][
                (m.group(5) != "total-hosts", -int(m.group(4)))
            ] = url
    out = {}
    for tree, pages in trees.items():
        ordered = [pages[k] for k in sorted(pages)]
        clients = [pages[k] for k in sorted(pages) if not k[0]] or ordered
        out[tree] = {"urls": probe_first(clients, ordered)}
    return out


def main(argv: list[str] | None = None) -> int:
    listing, shape, dest = (argv or sys.argv[1:])[:3]
    with gzip.open(listing, "rt", encoding="latin-1") as fh:
        urls = [u for u in (clean(line) for line in fh if WANTED.search(line)) if u]
    trees = {"http-analyze": http_analyze, "pwebstats": pwebstats}[shape](urls)
    with open(dest, "w") as fh:
        json.dump(trees, fh)
    print(json.dumps({"trees": len(trees), "urls": sum(len(t["urls"]) for t in trees.values())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
