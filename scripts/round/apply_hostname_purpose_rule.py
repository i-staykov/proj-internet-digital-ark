"""Apply the hostname purpose rule of 2026-09-02 to a store filled before it.

The reviewer accepted hostnames so that archived pages can be retrieved. Two rules
follow, both now enforced at ingest and by `ark check`: a hostname record needs an
observation of the host serving web content, and `www.<parent>` is the parent's own
site. A store filled before the rule holds rows that fail them; this removes exactly
those rows, keeps every evidence row (the parent's year still stands on it), prints
what went per source, and is idempotent.

    uv run scripts/round/apply_hostname_purpose_rule.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from ark.db import connect  # noqa: E402
from ark.hostnames import WEB_FACING_HOST_SOURCES  # noqa: E402

WEB_FACING = ", ".join(f"'{name}'" for name in sorted(WEB_FACING_HOST_SOURCES))
OFFENDING = f"""
    SELECT hy.hostname, hy.assigned_year, s.name AS source,
           CASE WHEN s.name NOT IN ({WEB_FACING}) THEN 'dns_listing'
                ELSE 'www_of_parent' END AS rule
    FROM hostname_year hy
    JOIN evidence e ON e.evidence_id = hy.evidence_id
    JOIN source s ON s.source_id = e.source_id
    WHERE s.name NOT IN ({WEB_FACING}) OR hy.hostname = 'www.' || hy.parent_domain
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="report, delete nothing")
    args = ap.parse_args()
    conn = connect()
    before = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]
    per_source = conn.execute(
        f"SELECT source, rule, count(*) FROM ({OFFENDING}) GROUP BY 1, 2 ORDER BY 3 DESC"
    ).fetchall()
    total = sum(n for _, _, n in per_source)
    print(f"hostname_year rows: {before:,}; failing the purpose rule: {total:,}")
    for source, rule, n in per_source:
        print(f"  {source:32} {rule:14} {n:>12,}")
    if args.dry_run or total == 0:
        return
    conn.execute(
        f"""
        DELETE FROM hostname_year
        WHERE (hostname, assigned_year) IN (SELECT hostname, assigned_year FROM ({OFFENDING}))
        """
    )
    after = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]
    print(f"deleted {before - after:,}; hostname_year now {after:,}; evidence rows untouched")


if __name__ == "__main__":
    main()
