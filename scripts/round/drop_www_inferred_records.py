"""Remove registrable domain-years that rest ONLY on a capture of `www.` in front of them.

**His ruling of 2026-09-06, and it runs both ways:** "The existence of the bare parent does not
automatically establish the www hostname, nor does the presence of www automatically establish the
bare hostname." We already enforced the first half. The second half we were breaking, because a
capture of `www.example.com` wrote the hostname record AND folded to a registrable year for
`example.com` through the registrable path, so one observation shipped as two records, one in
`additions/` and one in `hostnames/`. That is exactly the double count the sentence forbids.

Measured against `merged260906` on 2026-09-06: **47,004 domain-years** have www-only evidence.

**What this does NOT do.** The evidence rows stay. They are true observations of a real host and
they still carry the hostname record; only the inferred registrable year goes. That keeps the
provenance intact and is why `nothing_earned_is_left_unassigned` was amended to exempt evidence
naming a subdomain rather than being weakened.

**What it cannot see.** Registrable-grain evidence stores a bare timestamp with no host, so a
domain-year dated by an older domain-wide sweep cannot be attributed to a host at all. Those are
left alone and counted here as `unattributable`, because guessing would be worse than reporting
the limit. Sweeps have recorded the host since the `fl=timestamp,original` fix of 2026-09-05.

    uv run python scripts/round/drop_www_inferred_records.py [--apply]

Without `--apply` it counts and prints and writes nothing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from ark.db import connect, connect_read_only_patiently  # noqa: E402

# A domain-year is www-inferred when every one of its evidence rows names `www.<domain>`
# and none names anything else.
WWW_ONLY = """
    SELECT dy.domain, dy.assigned_year
    FROM domain_year dy JOIN evidence e ON e.evidence_id = dy.evidence_id
    GROUP BY 1, 2
    HAVING sum(CASE WHEN e.evidence_value LIKE 'cdx capture % www.' || dy.domain
                    THEN 1 ELSE 0 END) > 0
       AND sum(CASE WHEN e.evidence_value NOT LIKE 'cdx capture % www.' || dy.domain
                    THEN 1 ELSE 0 END) = 0
"""

UNATTRIBUTABLE = """
    SELECT count(*) FROM (
      SELECT dy.domain, dy.assigned_year
      FROM domain_year dy JOIN evidence e ON e.evidence_id = dy.evidence_id
      GROUP BY 1, 2
      HAVING sum(CASE WHEN e.evidence_value LIKE 'cdx capture %' THEN 1 ELSE 0 END) = 0
    )
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="delete the rows; default counts only")
    args = ap.parse_args()

    if not args.apply:
        conn = connect_read_only_patiently(patience_s=900)
        try:
            n = conn.execute(f"SELECT count(*) FROM ({WWW_ONLY})").fetchone()[0]
            blind = conn.execute(UNATTRIBUTABLE).fetchone()[0]
        finally:
            conn.close()
        print(f"domain-years resting only on a www.<domain> capture : {n:,}")
        print(f"domain-years whose evidence names no host at all    : {blind:,} (unattributable)")
        print("nothing written. Re-run with --apply to delete the first set.")
        return 0

    conn = connect()
    try:
        conn.execute(f"CREATE OR REPLACE TEMP TABLE www_only AS {WWW_ONLY}")
        n = conn.execute("SELECT count(*) FROM www_only").fetchone()[0]
        conn.execute(
            """
            DELETE FROM domain_year dy
            WHERE EXISTS (
              SELECT 1 FROM www_only w
              WHERE w.domain = dy.domain AND w.assigned_year = dy.assigned_year
            )
            """
        )
        left = conn.execute(f"SELECT count(*) FROM ({WWW_ONLY})").fetchone()[0]
    finally:
        conn.close()
    print(f"deleted {n:,} www-inferred domain-years; {left:,} remain (expect 0)")
    return 0 if left == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
