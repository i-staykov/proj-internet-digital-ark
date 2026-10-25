"""The pool's CDX questions, best first: one line per registrable no CDX request ever asked.

A year is held when he or we date the name in it (`ark.held`, `domain_year`). Bracketed gaps
(a year missing between two held ones) first, then the 2001 edge (2000 held,
2001 not), then the undated pool (no year held), each by his English share of its TLD, ties
on a hash so numeric-prefix junk does not cluster. One question paid 1.249 EE on bracketed
gaps, 0.2645 on edge years and about 0.18 on the pool (`docs/lore/laws.md`). Asked means named
by a `data/raw/cdx/cdx_*` journal; the walk's own answers are its done set.

Written once, by the tick under the sync lock, as `data/queue/pool_questions.tsv` (`<tier>\\t
<domain>`); the walk asks it by line number, so a rebuild waits for the file to be deleted.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from ark import held
from ark.db import connect_read_only_patiently
from ark.english_share import english_weights
from ark.journal import queried_domains

DATA = Path(os.environ.get("ARK_WALK_DATA", Path(__file__).resolve().parents[2] / "data"))
OUT = DATA / "queue/pool_questions.tsv"
TIERS = """
WITH dated AS ({his} UNION ALL SELECT domain, assigned_year AS y FROM domain_year),
held AS (SELECT domain, bit_or(1 << (y - 1996)) AS m FROM dated GROUP BY 1)
SELECT CASE WHEN m IS NULL THEN 'pool'
            WHEN (m & 7) = 5 OR (m & 14) = 10 OR (m & 28) = 20 OR (m & 56) = 40 THEN 'gap'
            WHEN (m & 48) = 16 THEN 'edge' END AS tier, d.domain, d.tld
FROM domain d LEFT JOIN held USING (domain)
"""


def main() -> None:
    if OUT.exists():
        print(f"pool questions: {OUT.name} stands; delete it to rebuild")
        return
    asked = queried_domains(DATA / "raw/cdx", "cdx")
    weights, his = english_weights(), held.load()
    lines = "header=false, columns={'domain': 'VARCHAR'}, delim='\x01', quote='', escape=''"
    years = [f"SELECT domain, {y} AS y FROM read_csv('{p}', {lines})" for y, p in his.years.items()]
    with connect_read_only_patiently(DATA / "ark.duckdb") as conn:
        tiers = conn.execute(TIERS.format(his=" UNION ALL ".join(years))).fetchall()
    rows = [r for r in tiers if r[0] and r[1] not in asked]
    order = {"gap": 0, "edge": 1, "pool": 2}
    rows.sort(
        key=lambda r: (
            order[r[0]],
            -weights.get(r[2] or "", 0),
            hashlib.blake2b(r[1].encode(), digest_size=8).digest(),
        )
    )
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text("".join(f"{tier}\t{domain}\n" for tier, domain, _ in rows))
    os.replace(tmp, OUT)
    counts = {t: sum(r[0] == t for r in rows) for t in order}
    print(f"pool questions: {counts} never asked, {len(asked)} asked before")


if __name__ == "__main__":
    main()
