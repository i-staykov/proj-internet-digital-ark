"""Admit `www.<parent registrable>` as its own hostname record (ADR-009, Ivo 2026-09-04).

C-55 refused it at ingest on 2026-09-02, reading his purpose for the unit as "one site, one
record". His section XI of 2026-09-04 says the opposite in his own words, and his benchmark
settles it: **1,450,310 of his names begin `www.` and 1,221,065 of those have the bare name in
the SAME year file, 114,875 of them from nobody but us.** The shape is native to his corpus.

**This is a backfill and not a re-collection**, which is the only reason it is cheap: every
lane already wrote the evidence row naming `www.<parent>` and only the `hostname_year` insert
refused it, so the rows are recovered from `evidence` rather than from the archive.

**What it will not do is assert a host it has not seen.** The row is created only where an
evidence value names that exact host, so a capture of `foo.com` never becomes a record for
`www.foo.com`. `ark check`'s `a_www_record_has_its_own_evidence` holds the same line afterwards.

    uv run python scripts/round/admit_www_of_parent.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from ark.db import connect  # noqa: E402
from ark.hostnames import WEB_FACING_HOST_SOURCES  # noqa: E402

WEB_FACING = ", ".join(f"'{name}'" for name in sorted(WEB_FACING_HOST_SOURCES))

# The space before `www.` is not decoration: every evidence value is `... <host>`, and without
# it `%www.foo.com` also matches a value whose host is `sub.mywww.foo.com`.
CANDIDATES = f"""
    SELECT 'www.' || e.domain AS hostname, e.domain AS parent,
           e.evidence_year AS year, min(e.evidence_id) AS evidence_id, min(s.name) AS lane
    FROM evidence e
    JOIN source s ON s.source_id = e.source_id
    WHERE s.name IN ({WEB_FACING})
      AND e.evidence_value LIKE '% www.' || e.domain
    GROUP BY 1, 2, 3
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    args = ap.parse_args()
    conn = connect()
    conn.execute(f"CREATE OR REPLACE TEMP TABLE wwwparent AS {CANDIDATES}")
    per_lane = conn.execute(
        """
        SELECT lane, count(*) FROM wwwparent w
        WHERE NOT EXISTS (SELECT 1 FROM hostname_year hy
                          WHERE hy.hostname = w.hostname AND hy.assigned_year = w.year)
        GROUP BY 1 ORDER BY 2 DESC
        """
    ).fetchall()
    total = sum(n for _, n in per_lane)
    for lane, n in per_lane:
        print(f"  {lane:32} {n:>10,}")
    print(f"  {'to admit':32} {total:>10,}")
    if args.dry_run:
        print("dry run: nothing written")
        return
    before = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]
    conn.execute(
        """
        INSERT OR IGNORE INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id)
        SELECT hostname, parent, year, evidence_id FROM wwwparent
        """
    )
    after = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]
    print(f"hostname_year {before:,} -> {after:,}  (+{after - before:,})")
    conn.close()


if __name__ == "__main__":
    main()
