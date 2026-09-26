"""How often a host-year a Usenet server header dates also carries a web capture in the store.

    uv run python scripts/round/header_promotion.py

Read-only; run it under the sync lock like any store reader. The header host-years come
from the lane's own journals, `data/raw/usenet_header_items/`, through its ingest reader, so
the count is the lane's. A host-year counts as captured when the store's row for that host
and year cites web evidence under the evidence rule's own predicate.

**Every share is a lower bound, the same-year one most.** The store keeps one
`hostname_year` row per host and year, so a header row written first keeps its place when a
capture of that host-year arrives later. A capture in another year does not compete with a
header row, so the shifted shares are not held down the same way and are not comparable.
"""

from __future__ import annotations

import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
JOURNALS = REPO / "data/raw/usenet_header_items"


def _pairs(path: str) -> list[tuple[str, int]]:
    from ark.hostnames import USENET_HEADER_FAMILY, usenet_item_rows

    rows = usenet_item_rows(Path(path), Counter(), USENET_HEADER_FAMILY)
    return sorted({(host, year) for host, _parent, year, _value, _url in rows})


def main() -> int:
    import tempfile

    from ark.db import connect_read_only_patiently
    from ark.evidence_types import web_evidence_sql

    shards = [str(p) for p in sorted(JOURNALS.rglob("*.jsonl.gz"))]
    if not shards:
        print(f"no header journals in {JOURNALS}", file=sys.stderr)
        return 1
    # 28 million lines parsed one at a time: the shards go to one process each
    with ProcessPoolExecutor(max_workers=min(8, len(shards))) as pool:
        pairs = sorted(set().union(*map(set, pool.map(_pairs, shards))))
    conn = connect_read_only_patiently(REPO / "data/ark.duckdb")
    conn.execute("SET enable_progress_bar = false")
    with tempfile.NamedTemporaryFile("w", suffix=".tsv", encoding="utf-8") as handle:
        handle.write("".join(f"{host}\t{year}\n" for host, year in pairs))
        handle.flush()
        conn.execute(
            "CREATE TEMP TABLE hdr AS SELECT * FROM read_csv(?, delim='\t', header=false, "
            "columns={'hostname': 'VARCHAR', 'y': 'INTEGER'})",
            [handle.name],
        )
    conn.execute(f"""
        CREATE TEMP TABLE web AS
        SELECT DISTINCT hy.hostname, hy.assigned_year AS y
        FROM hostname_year hy JOIN evidence e ON e.evidence_id = hy.evidence_id
        WHERE {web_evidence_sql("e")} AND hy.hostname IN (SELECT hostname FROM hdr)
    """)

    def one(query: str) -> int:
        return conn.execute(query).fetchone()[0]

    total = one("SELECT count(*) FROM hdr")
    same = one("SELECT count(*) FROM hdr JOIN web USING (hostname, y)")
    anywhere = one("SELECT count(*) FROM hdr WHERE hostname IN (SELECT hostname FROM web)")
    print(f"header-dated host-years: {total:,}")
    print(f"a capture the same year: {same:,} ({100 * same / total:.2f}%)")
    for k in (-3, -2, -1, 1, 2, 3):
        window = f"hdr.y + {k} BETWEEN 1996 AND 2001"
        base = one(f"SELECT count(*) FROM hdr WHERE {window}")
        hit = one(
            "SELECT count(*) FROM hdr JOIN web ON web.hostname = hdr.hostname"
            f" AND web.y = hdr.y + {k} WHERE {window}"
        )
        print(f"a capture {k:+d} years off: {hit:,} of {base:,} ({100 * hit / base:.2f}%)")
    print(f"a capture in any year: {anywhere:,} ({100 * anywhere / total:.2f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
