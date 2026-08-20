"""Which Usenet groups on local disk have no evidence in the store?

19,681 archives sit under `data/raw/usenet*`, and the store's evidence names only
13,536 groups. The remainder was downloaded in phase 4 and never split, which is
110.8 GB of dated corpus on local disk needing no download and no approval, since
`usenet_announce / dated_directory` has been master since phase 4.

Writes the archive paths, largest first, so an interrupted run has taken the
valuable part. Read-only against the store.

    uv run python scripts/usenet_unworked.py > data/raw/usenet/unworked.txt
"""

import sys
import time
from pathlib import Path

import duckdb

for _ in range(120):
    try:
        con = duckdb.connect("data/ark.duckdb", read_only=True)
        break
    except Exception:
        time.sleep(20)
else:
    sys.exit("store stayed locked")

seen = {
    r[0]
    for r in con.execute(
        """
        select distinct split_part(e.evidence_value, ' ', 1)
        from evidence e join source s on s.source_id = e.source_id
        where s.name in ('usenet_announce', 'usenet_mention')
        """
    ).fetchall()
}

rows = []
for root in (Path("data/raw/usenet"), Path("data/raw/usenet_new")):
    if not root.exists():
        continue
    for p in root.rglob("*.mbox.zip"):
        if p.name.removesuffix(".mbox.zip") not in seen:
            rows.append((p.stat().st_size, p))

rows.sort(reverse=True)
for _size, p in rows:
    print(p)

total = sum(s for s, _ in rows)
print(
    f"# {len(rows):,} archives, {total / 1e9:.1f} GB, none of whose groups the store names",
    file=sys.stderr,
)
