"""Rank open-repository datasets by how likely they are to carry dated 1996-2001 hosts.

The hunt has a shape. What pays is a custodian's own bulk artifact with a
machine-written date beside each row: Arquivo's `IA.cdxj`, the IA node host CDX, the
JISC host link graph. What does not pay is a paper about such an artifact. So this
asks every catalogue we can reach for the artifact shape, scores each hit on the
three things that decide whether it can pay, and drops anything the registers have
already answered.

**It fetches metadata only and never the artifact.** A hit is a lead to price, not a
source: `ark price-snapshot` still decides, and the register row still has to say
what dates one item.

    uv run python scripts/harness/dataset_discovery.py --out private/discovery.tsv
    uv run python scripts/harness/dataset_discovery.py --repos zenodo,re3data --limit 50
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

UA = "ark-research/1.0 (Internet Digital Ark; ivaylo.staykov@taktile.com)"

# The artifact shapes that have paid, and the ones that never have.
SHAPE = re.compile(
    r"\b(cdx|cdxj|warc|arc file|crawl index|capture index|link graph|hyperlink graph|"
    r"host graph|web graph|webgraph|hostnames?|host list|domain list|url list|"
    r"access log|server log|referer|web directory|site list|zone file|name server)\b",
    re.I,
)
BULK = re.compile(r"\b(bulk|dump|dataset|corpus|index|archive|collection|tranche|snapshot)\b", re.I)
# A year inside the window, written as a year and not as part of a longer number.
INWINDOW = re.compile(r"(?<!\d)(1996|1997|1998|1999|2000|2001)(?!\d)")
PRE96 = re.compile(r"(?<!\d)(199[0-5]|198\d)(?!\d)")
# Shapes that cannot date a host and have closed before.
DEAD = re.compile(
    r"\b(survey responses|questionnaire|interview|twitter|facebook|covid|genome|"
    r"protein|climate|satellite|rainfall|patient|clinical)\b",
    re.I,
)

QUERIES = [
    "web archive crawl index",
    "web archive host link graph",
    "historical web crawl hostnames",
    "early web 1996 dataset",
    "web domain dataset",
    "national web archive open data",
    "hyperlink graph 1996",
    "web server access logs 1998",
    "internet domain survey hosts",
    "wayback cdx index",
]


def _get(url, headers=None, tries=3):
    """One polite GET returning bytes, or None. Honours Retry-After."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                wait = int(e.headers.get("Retry-After") or 30)
                print(f"    {e.code}, Retry-After {wait}s", file=sys.stderr)
                time.sleep(min(wait, 120))
                continue
            print(f"    HTTP {e.code} {url[:90]}", file=sys.stderr)
            return None
        except Exception as e:  # noqa: BLE001
            print(f"    {type(e).__name__} {url[:90]}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    return None


def _rec(repo, ident, title, desc, url, doi=""):
    return {
        "repo": repo,
        "id": str(ident),
        "title": (title or "").strip().replace("\t", " ")[:300],
        "desc": re.sub(r"<[^>]+>", " ", desc or "").strip().replace("\t", " ")[:600],
        "url": url or "",
        "doi": doi or "",
    }


def zenodo(q, limit):
    u = "https://zenodo.org/api/records?" + urllib.parse.urlencode(
        {"q": q, "size": limit, "type": "dataset"}
    )
    b = _get(u)
    if not b:
        return []
    out = []
    for h in json.loads(b).get("hits", {}).get("hits", []):
        m = h.get("metadata", {})
        out.append(
            _rec(
                "zenodo",
                h.get("id"),
                m.get("title"),
                m.get("description"),
                h.get("links", {}).get("self_html", ""),
                m.get("doi", ""),
            )
        )
    return out


def datacite(q, limit):
    u = "https://api.datacite.org/dois?" + urllib.parse.urlencode(
        {"query": q, "page[size]": limit, "resource-type-id": "dataset"}
    )
    b = _get(u)
    if not b:
        return []
    out = []
    for h in json.loads(b).get("data", []):
        a = h.get("attributes", {})
        titles = a.get("titles") or [{}]
        descs = a.get("descriptions") or [{}]
        out.append(
            _rec(
                "datacite",
                h.get("id"),
                titles[0].get("title"),
                descs[0].get("description"),
                a.get("url", ""),
                a.get("doi", ""),
            )
        )
    return out


def figshare(q, limit):
    u = "https://api.figshare.com/v2/articles/search"
    body = json.dumps({"search_for": q, "limit": min(limit, 100), "item_type": 3}).encode()
    req = urllib.request.Request(
        u, data=body, headers={"User-Agent": UA, "Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        print(f"    figshare {type(e).__name__}", file=sys.stderr)
        return []
    return [
        _rec(
            "figshare",
            d.get("id"),
            d.get("title"),
            d.get("description", ""),
            d.get("url_public_html", ""),
            d.get("doi", ""),
        )
        for d in data
    ]


def dataverse(q, limit):
    u = "https://dataverse.harvard.edu/api/search?" + urllib.parse.urlencode(
        {"q": q, "type": "dataset", "per_page": min(limit, 100)}
    )
    b = _get(u)
    if not b:
        return []
    return [
        _rec(
            "dataverse",
            d.get("global_id"),
            d.get("name"),
            d.get("description"),
            d.get("url", ""),
            d.get("global_id", ""),
        )
        for d in json.loads(b).get("data", {}).get("items", [])
    ]


def openaire(q, limit):
    u = "https://api.openaire.eu/search/datasets?" + urllib.parse.urlencode(
        {"keywords": q, "size": min(limit, 50), "format": "json"}
    )
    b = _get(u)
    if not b:
        return []
    try:
        results = json.loads(b)["response"]["results"]["result"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return []
    if isinstance(results, dict):
        results = [results]
    out = []
    for r in results:
        try:
            meta = r["metadata"]["oaf:entity"]["oaf:result"]
        except (KeyError, TypeError):
            continue
        title = meta.get("title")
        if isinstance(title, list):
            title = title[0]
        if isinstance(title, dict):
            title = title.get("$", "")
        desc = meta.get("description")
        if isinstance(desc, list):
            desc = desc[0]
        if isinstance(desc, dict):
            desc = desc.get("$", "")
        pid = meta.get("originalId") or ""
        if isinstance(pid, list):
            pid = pid[0]
        out.append(_rec("openaire", pid, title, desc, "", ""))
    return out


def re3data(q, limit):
    """The catalogue of repositories, not of datasets: it names custodians to visit."""
    b = _get("https://www.re3data.org/api/v1/repositories?" + urllib.parse.urlencode({"query": q}))
    if not b:
        return []
    ids = re.findall(r"<id>([^<]+)</id>", b.decode("utf-8", "replace"))[:limit]
    names = re.findall(r"<name>([^<]+)</name>", b.decode("utf-8", "replace"))[:limit]
    links = re.findall(r'<link href="([^"]+)"', b.decode("utf-8", "replace"))[:limit]
    return [
        _rec("re3data", i, n, "", lk)
        for i, n, lk in zip(ids, names, links + [""] * len(ids), strict=False)
    ]


def archiveorg(q, limit):
    """archive.org item search. Allowed to a research lane: this is not the CDX index.

    The shape that has paid most is a custodian's own capture index deposited as an item,
    so this asks for items rather than for the web collection behind them.
    """
    u = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(
        {
            "q": q,
            "fl[]": "identifier",
            "rows": min(limit, 100),
            "page": 1,
            "output": "json",
        }
    )
    b = _get(u)
    if not b:
        return []
    try:
        docs = json.loads(b)["response"]["docs"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return []
    out = []
    for d in docs:
        ident = d.get("identifier", "")
        out.append(
            _rec(
                "archiveorg",
                ident,
                d.get("title") or ident,
                d.get("description") or "",
                f"https://archive.org/details/{ident}",
            )
        )
    return out


REPOS = {
    "zenodo": zenodo,
    "datacite": datacite,
    "figshare": figshare,
    "dataverse": dataverse,
    "openaire": openaire,
    "re3data": re3data,
    "archiveorg": archiveorg,
}


def register_text():
    """Everything the registers already answered, lowercased, for the seen-before screen."""
    parts = []
    for name in ("sources.md", "sources-closed.md", "approved-sources-list.md"):
        p = ROOT / "docs" / "registers" / name
        if p.exists():
            parts.append(p.read_text(encoding="utf-8", errors="replace").lower())
    return "\n".join(parts)


def already_known(rec, reg):
    """True when a register row already names this artifact."""
    for key in (rec["doi"], rec["url"]):
        k = (key or "").lower().strip()
        if len(k) > 12 and k in reg:
            return True
    title = rec["title"].lower()
    stop = ("dataset", "data", "archive", "web")
    words = [w for w in re.findall(r"[a-z0-9.\-]{4,}", title) if w not in stop]
    if len(words) >= 3:
        hits = sum(1 for w in words if w in reg)
        if hits >= max(3, int(len(words) * 0.7)):
            return True
    return False


def score(rec):
    """Expected yield, highest first. Every point is a reason the thing could pay."""
    t = f"{rec['title']} {rec['desc']}"
    if DEAD.search(t):
        return 0, "off-shape"
    pts, why = 0, []
    if SHAPE.search(t):
        pts += 5
        why.append("artifact-shape")
    if INWINDOW.search(t):
        pts += 4
        why.append("in-window-year")
    elif PRE96.search(t):
        pts += 2
        why.append("pre-1996-year")
    if BULK.search(t):
        pts += 1
        why.append("bulk-word")
    if re.search(r"\b(web archive|webarchive|crawl|wayback|heritrix|nutch)\b", t, re.I):
        pts += 2
        why.append("custodian-word")
    if re.search(r"\b(\d+(\.\d+)?\s?(gb|tb|million|billion))\b", t, re.I):
        pts += 1
        why.append("size-stated")
    return pts, ",".join(why) or "none"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", default=",".join(REPOS))
    ap.add_argument("--queries", default="")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--min-score", type=int, default=6)
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    repos = [r for r in args.repos.split(",") if r in REPOS]
    queries = [q for q in (args.queries.split("|") if args.queries else QUERIES) if q]
    reg = register_text()

    seen, rows = set(), []
    for repo in repos:
        for q in queries:
            print(f"  {repo} <- {q}", file=sys.stderr)
            for rec in REPOS[repo](q, args.limit):
                key = (rec["doi"] or rec["url"] or rec["title"]).lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                pts, why = score(rec)
                if pts < args.min_score:
                    continue
                rec["score"], rec["why"] = pts, why
                rec["known"] = "held" if already_known(rec, reg) else "new"
                rows.append(rec)
            time.sleep(args.delay)

    rows.sort(key=lambda r: (-r["score"], r["repo"]))
    header = ["score", "known", "repo", "why", "title", "doi", "url", "desc"]
    lines = ["\t".join(header)]
    lines += ["\t".join(str(r[h]) for h in header) for r in rows]
    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    new = [r for r in rows if r["known"] == "new"]
    print(f"{len(rows)} hits at score {args.min_score}+, {len(new)} not already in the registers")
    for r in new[:25]:
        print(f"  {r['score']:>2}  {r['repo']:<10} {r['title'][:95]}")
        if r["url"] or r["doi"]:
            print(f"      {r['url'] or r['doi']}")


if __name__ == "__main__":
    main()
