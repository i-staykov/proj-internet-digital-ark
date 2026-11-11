"""From report index pages a probe found, the lists of their period pages for the replay reader.

    python index_to_trees.py <out.json> <max_year> <dest_dir> [...] [-- <receipts> ...]
Each <dest_dir> is a replay reader's folder (pages and receipts.receipts); a URL named in a
receipts file after `--` was asked before and is left out. For every page captured
up to <max_year>, the links that stay on the host and inside the page's own directory become asks
near the index capture's stamp; an http-analyze index also gets its 72 monthly host-list names of
1996 to 2001 (`www<YYYY>/lsites<MMYY>.html` and `sites<MMYY>.html`), which its frames hide.
"""

import collections
import json
import re
import sys
import urllib.parse
from pathlib import Path

out, max_year = sys.argv[1], sys.argv[2]
rest = sys.argv[3:]
cut = rest.index("--") if "--" in rest else len(rest)
asked = set()
for rec in rest[cut + 1 :]:
    try:
        for line in open(rec):
            try:
                asked.add(json.loads(line)["url"])
            except (json.JSONDecodeError, KeyError):
                pass
    except FileNotFoundError:
        pass
SKIP = re.compile(r"(?i)\.(gif|jpe?g|png|css|js|ico|zip|gz|pdf|ps|exe|tar)$")
trees = collections.defaultdict(dict)
for dest in rest[:cut]:
    dest = Path(dest)
    for line in (dest / "receipts.receipts").read_text().splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        m = re.search(r"/web/(\d{14})", r.get("replay") or "")
        if not r.get("path") or not m or m.group(1)[:4] > max_year:
            continue
        ts = m.group(1)
        base = (
            r["url"]
            if r["url"].endswith("/") or "." in r["url"].rsplit("/", 1)[-1]
            else r["url"] + "/"
        )
        root = urllib.parse.urljoin(base, ".")
        host = urllib.parse.urlsplit(base).netloc.lower()
        try:
            text = (dest / r["path"]).read_bytes()[:400000].decode("latin-1")
        except OSError:
            continue
        for link in re.finditer(r"(?i)(?:href|src)\s*=\s*[\"']?([^\"'\s>]+)", text):
            u = urllib.parse.urljoin(base, link.group(1).strip()).split("#")[0]
            p = urllib.parse.urlsplit(u)
            if p.netloc.lower() != host or p.scheme != "http" or "?" in u or SKIP.search(p.path):
                continue
            if (
                not u.startswith(root)
                or u.rstrip("/") == base.rstrip("/")
                or not u.isascii()
                or u in asked
            ):
                continue
            trees[host].setdefault(u, ts)
        if "http-analyze" in text.lower():
            for y in range(1996, 2002):
                for mth in range(1, 13):
                    mmyy = f"{mth:02d}{y % 100:02d}"
                    for u in (f"{root}www{y}/lsites{mmyy}.html", f"{root}sites{mmyy}.html"):
                        if u not in asked:
                            trees[host].setdefault(u, ts)
json.dump(
    {h: {"urls": [f"{u}\t{ts}" for u, ts in sorted(d.items())]} for h, d in trees.items()},
    open(out, "w"),
)
print(json.dumps({"trees": len(trees), "urls": sum(len(d) for d in trees.values())}))
