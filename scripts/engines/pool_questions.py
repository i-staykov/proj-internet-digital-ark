"""The pool's CDX questions, best first: one line per registrable no CDX request ever asked.

A year is held when he or we date the name in it (`ark.held`, `domain_year`). Gaps (a year
missing between two held ones, any width) first, then the 2001 edge (2000 held, 2001 not), then
the undated pool (no year held). Inside a tier, by his English share of the TLD times the TLD's
share of his names, so a weight-1 brand TLD he barely holds does not lead; ties on a hash, so
numeric-prefix junk does not cluster. One question paid 1.249 EE on bracketed gaps, 0.2645 on
edge years and about 0.18 on the pool (`docs/lore/laws.md`). Asked means named by a
`data/raw/cdx/cdx_*` journal; the walk's own answers are its done set, keyed by domain.

Written once, by the tick under the sync lock, as `data/queue/pool_questions.tsv`
(`<tier>\\t<domain>`), by DuckDB straight to the file; delete it to rebuild.
"""

from __future__ import annotations

import os
import tempfile
from collections import Counter
from pathlib import Path

from ark import held
from ark.db import connect_read_only_patiently
from ark.english_share import english_weights
from ark.journal import queried_domains

DATA = Path(os.environ.get("ARK_WALK_DATA", Path(__file__).resolve().parents[2] / "data"))
OUT = DATA / "queue/pool_questions.tsv"
LINES = "header=false, columns={'domain': 'VARCHAR'}, delim='\x01', quote='', escape=''"
QUESTIONS = """
WITH dated AS ({his} UNION ALL SELECT domain, assigned_year AS y FROM domain_year),
held AS (SELECT domain, bit_or(1 << (y - 1996)) AS m FROM dated GROUP BY 1),
share AS (SELECT regexp_extract(domain, '[^.]+$') AS tld, count(*) AS n
          FROM read_csv('{all}', {lines}) GROUP BY 1),
weight AS (SELECT * FROM (VALUES {weights}) w(tld, w)),
tiered AS (SELECT CASE WHEN m IS NULL THEN 'pool'
                       WHEN (m // (m & -m)) & (m // (m & -m) + 1) > 0 THEN 'gap'  -- a hole
                       WHEN (m & 48) = 16 THEN 'edge' END AS tier, d.domain, d.tld
           FROM domain d LEFT JOIN held USING (domain))
SELECT tier, domain FROM tiered LEFT JOIN weight USING (tld) LEFT JOIN share USING (tld)
WHERE tier IS NOT NULL AND domain NOT IN (SELECT domain FROM read_csv('{asked}', {lines}))
ORDER BY list_position(['gap', 'edge', 'pool'], tier), coalesce(w, 0) * coalesce(n, 0) DESC,
         hash(domain)
"""


def main() -> None:
    if OUT.exists():
        print(f"pool questions: {OUT.name} stands; delete it to rebuild")
        return
    his, asked = held.load(), sorted(queried_domains(DATA / "raw/cdx", "cdx"))
    years = [f"SELECT domain, {y} AS y FROM read_csv('{p}', {LINES})" for y, p in his.years.items()]
    weights = ", ".join(f"('{t}', {float(w)})" for t, w in english_weights().items())
    tmp = OUT.with_suffix(".tmp")
    with tempfile.NamedTemporaryFile("w", suffix=".txt") as fh:
        fh.write("".join(d + "\n" for d in asked))
        fh.flush()
        query = QUESTIONS.format(
            his=" UNION ALL ".join(years), all=his.all, lines=LINES, weights=weights, asked=fh.name
        )
        with connect_read_only_patiently(DATA / "ark.duckdb") as conn:
            conn.execute(f"COPY ({query}) TO '{tmp}' (HEADER false, DELIMITER '\t', QUOTE '')")
    os.replace(tmp, OUT)
    with open(OUT) as fh:
        counts = Counter(line.split("\t", 1)[0] for line in fh)
    print(f"pool questions: {dict(counts)} never asked, {len(asked)} asked before")


if __name__ == "__main__":
    main()
