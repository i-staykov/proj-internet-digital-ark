"""Assign master-eligible evidence whose (domain, year) has no `domain_year` row.

`nothing_earned_is_left_unassigned` is the invariant: a domain must not sit in the candidate
pool while the store already holds proof of one of its years. Measured against `merged260906`
on 2026-09-07 it failed on 64,302 evidence rows, in two classes and neither of them the www
regression that was found the same morning:

- 37,124 `prior_reused` rows, whose value is a baseline filename such as `merged260906/2001.txt`.
  The reviewer's own files say that domain held that year, so the assignment is a restatement of
  his baseline rather than a claim of ours, and it earns nothing.
- 27,060 `cdx_timestamp` rows whose value is a bare `cdx capture <year>` with no host. These are
  registrable-grain observations from the older domain-wide sweeps, made before the
  `fl=timestamp,original` fix of 2026-09-05 started recording which host answered.

**Evidence naming a subdomain is excluded, and that is the whole point.** A capture of
`www.example.com`, or of any other host beneath it, evidences that host and not the registrable
(his ruling of 2026-09-06, ADR-010). The exclusion here is written to match
`a_bare_record_is_not_inferred_from_www` exactly, so the two invariants cannot pull against each
other: whatever that check refuses, this one does not reinstate.

    uv run python scripts/round/assign_unassigned_evidence.py [--apply]

Without `--apply` it counts and prints and writes nothing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from ark.checks import _CANDIDATE_LIST  # noqa: E402
from ark.db import connect, connect_read_only_patiently  # noqa: E402

WHERE = f"""
    e.evidence_type NOT IN ({_CANDIDATE_LIST})
    AND e.evidence_value NOT LIKE 'cdx capture % %.' || e.domain
    AND NOT EXISTS (
      SELECT 1 FROM domain_year dy
      WHERE dy.domain = e.domain AND dy.assigned_year = e.evidence_year
    )
"""

BY_CLASS = f"""
    SELECT e.evidence_type, count(*) FROM evidence e WHERE {WHERE} GROUP BY 1 ORDER BY 2 DESC
"""

ASSIGN = f"""
    INSERT OR IGNORE INTO domain_year (domain, assigned_year, evidence_id)
    SELECT e.domain, e.evidence_year, min(e.evidence_id)
    FROM evidence e
    WHERE {WHERE}
    GROUP BY e.domain, e.evidence_year
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the rows; default counts only")
    args = ap.parse_args()

    if not args.apply:
        conn = connect_read_only_patiently(patience_s=900)
        try:
            rows = conn.execute(BY_CLASS).fetchall()
        finally:
            conn.close()
        total = sum(n for _, n in rows)
        for evidence_type, n in rows:
            print(f"  {evidence_type:<22} {n:>9,}")
        print(f"unassigned master-eligible evidence rows: {total:,}")
        print("nothing written. Re-run with --apply to assign them.")
        return 0

    conn = connect()
    try:
        before = conn.execute("SELECT count(*) FROM domain_year").fetchone()[0]
        conn.execute(ASSIGN)
        after = conn.execute("SELECT count(*) FROM domain_year").fetchone()[0]
        left = conn.execute(f"SELECT count(*) FROM evidence e WHERE {WHERE}").fetchone()[0]
    finally:
        conn.close()
    print(f"assigned {after - before:,} domain-years; {left:,} evidence rows remain (expect 0)")
    return 0 if left == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
