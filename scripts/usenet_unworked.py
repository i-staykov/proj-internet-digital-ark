"""Which Usenet groups on local disk have no evidence in the store?

19,681 archives sit under `data/raw/usenet*`, and the store's evidence names only
13,536 groups. The remainder was downloaded in phase 4 and never split, which is
110.8 GB of dated corpus on local disk needing no download and no approval, since
`usenet_announce / dated_directory` has been master since phase 4.

**Ordered by the group's NAME, not by its size**, which is the same correction
The retired group fetcher recorded making it: "ordering by size put dead
vanity archives at the head of the queue". Sorting 110.8 GB by size puts
`alt.sex.erotica` and `alt.anonymous.messages` first, and those announce nothing.
The first pass here did exactly that and was measured at about 0.2 EE per MB,
against 3.25 for `microsoft.public`, so this is a 15x ordering decision rather
than a tidy one.

Read-only against the store.

    uv run python scripts/usenet_unworked.py > data/raw/usenet/unworked.txt
"""

import sys
import time
from pathlib import Path

import duckdb

# Announcement and commerce groups first, which is where announced URLs live.
# Short tokens are matched as whole dot-separated components, because
# `talk.bizarre` contains "biz" and announces nothing.
SUBSTRING_TOKENS = (
    "announce",
    "net-happenings",
    "commerce",
    "marketplace",
    "entrepreneur",
    "business",
    "internet",
    "hosting",
    "advertis",
    "promotion",
    "providers",
    "webmaster",
    "ecommerce",
    "infosystems",
)
COMPONENT_TOKENS = frozenset(
    {"www", "web", "biz", "ads", "market", "isp", "domain", "shopping", "homepage", "comp"}
)
# Adult and binaries groups are the largest thing a size sort catches and they are
# advertising traffic rather than website announcements. Ranked last rather than
# dropped, so the decision stays reversible and nothing is silently discarded.
DEPRIORITISE = ("alt.sex", "alt.binaries", "alt.showbiz", "alt.anonymous")


def rank(group: str) -> int:
    """0 is worked first. Lower is better."""
    lowered = group.lower()
    if lowered.startswith(DEPRIORITISE):
        return 3
    if any(t in lowered for t in SUBSTRING_TOKENS):
        return 0
    if set(lowered.split(".")) & COMPONENT_TOKENS:
        return 1
    return 2


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
        group = p.name.removesuffix(".mbox.zip")
        if group not in seen:
            rows.append((rank(group), -p.stat().st_size, p))

# Within a rank, largest first: the ordering that matters is the rank, and size is
# a reasonable tie-break once the population is already the right one.
rows.sort()
for _r, _s, p in rows:
    print(p)

by_rank: dict[int, list[int]] = {}
for r, s, _p in rows:
    by_rank.setdefault(r, []).append(-s)
print(f"# {len(rows):,} archives, {sum(-s for _r, s, _p in rows) / 1e9:.1f} GB", file=sys.stderr)
for r in sorted(by_rank):
    n = len(by_rank[r])
    gb = sum(by_rank[r]) / 1e9
    print(f"#   rank {r}: {n:>6,} archives, {gb:>6.1f} GB", file=sys.stderr)
