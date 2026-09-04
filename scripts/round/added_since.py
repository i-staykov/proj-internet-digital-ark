"""What this round has added, out of the store, without running an export.

**Why this is not `round_figures.py`.** That command answers "what would ship", which needs the
exported files and therefore a 20-minute export that rewrites 4 GB of provenance. During a long
collection run the question is different and asked often: what have the lanes added since the
round opened. That is a store query, it takes seconds, and it does not disturb a running fold
loop because it opens read-only and waits its turn.

The window is `data/baseline.json`'s `round_since`, so this and the round figures cannot disagree
about when the round began, which is the mistake `traps.md` records: a figure is comparable only
to a figure over the same window.

Both halves are filtered through the export's own two predicates, so a row counted here is a row
that would ship: net-new against his annual files, and past the `.arpa` and TLD-delegation rules.

    uv run python scripts/round/added_since.py [--since 'YYYY-MM-DD HH:MM:SS+00']
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from ark import export  # noqa: E402
from ark.baseline import CURRENT_ROUND_SINCE  # noqa: E402
from ark.db import DEFAULT_DB_PATH, connect_read_only_patiently  # noqa: E402
from ark.english_share import english_weights  # noqa: E402

GATE_EE = Decimal("1151473.65")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", default=CURRENT_ROUND_SINCE, help="window start, his clock")
    ap.add_argument("--by-source", action="store_true", help="split the hostname half by lane")
    args = ap.parse_args()

    weights = english_weights()
    conn = connect_read_only_patiently(DEFAULT_DB_PATH, patience_s=2700)
    try:
        export.load_baseline_hostnames(conn)
        # **Grouped by (hostname, YEAR), because a record is a hostname-year and not a
        # hostname.** Grouping by the name alone undercounted by every host held in more
        # than one year, which is most of them: 962,234 against 962,824 on the first run of
        # this script, and the gap grows with the corpus.
        hosts = conn.execute(f"""
            SELECT hy.hostname, hy.assigned_year, min(s.name) AS lane FROM hostname_year hy
            JOIN evidence e ON e.evidence_id = hy.evidence_id
            JOIN source s ON s.source_id = e.source_id
            WHERE e.ingested_at >= TIMESTAMPTZ '{args.since}'
              AND {export.NOT_IN_BASELINE_HOSTNAME}
              AND {export.HOSTNAME_SHIPPING_FILTER}
            GROUP BY 1, 2
        """).fetchall()
        pairs = conn.execute(f"""
            SELECT DISTINCT dy.domain, dy.assigned_year FROM domain_year dy
            WHERE dy.verified_at >= TIMESTAMPTZ '{args.since}'
              AND {export._NOT_IN_BASELINE}
              AND {export._shipping_filter("dy.")}
        """).fetchall()
    finally:
        conn.close()

    def priced(names: list[str]) -> Decimal:
        return sum((weights.get(n.rsplit(".", 1)[-1], Decimal(0)) for n in names), Decimal(0))

    host_ee = priced([h for h, _, _ in hosts])
    pair_ee = priced([d for d, _ in pairs])
    total = host_ee + pair_ee
    print(f"added since {args.since}\n")
    print(f"  hostnames    : {len(hosts):>10,} records  {host_ee:>16,.4f} EE")
    print(f"  registrables : {len(pairs):>10,} records  {pair_ee:>16,.4f} EE")
    print(f"  together     : {len(hosts) + len(pairs):>10,} records  {total:>16,.4f} EE")
    print(f"  share of the 5% gate ({GATE_EE:,.2f}) : {total / GATE_EE * 100:.2f}%")

    if args.by_source:
        lanes: dict[str, list[int | Decimal]] = {}
        for host, _year, lane in hosts:
            weight = weights.get(host.rsplit(".", 1)[-1], Decimal(0))
            row = lanes.setdefault(lane, [0, Decimal(0)])
            row[0] += 1
            row[1] += weight
        print("\n  by lane")
        for lane, (count, ee) in sorted(lanes.items(), key=lambda kv: -kv[1][1]):
            print(f"    {lane:32} {count:>10,}  {ee:>16,.4f} EE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
