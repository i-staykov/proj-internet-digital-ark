"""Build the archive-query list for the candidate pool, best English yield first.

Two populations can be sent to the CDX index, and they are disjoint:

- the **gap pool**, held domains with a bracketed missing year (`ark gaps`). A hit
  adds one pair to a domain that is already in the master files.
- the **candidate pool**, this script: domains carried in the store with no year
  at all. A hit turns a candidate into a dated domain, so it adds a name the
  master files do not have yet.

Both are worth querying, and the pool is the better buy under the reviewer's
equivalent-English metric: its per-domain English weight is higher and every hit
is a new name rather than a new year on an old one. So this list exists
separately from `gap_candidates.txt` and is never merged into it.

Ordering is by the English share of the domain's TLD, taken from the reviewer's
own `q2_tld_top_langs.json` under exactly his rule: right-most label, `lang ==
'eng'`, share as a fraction, zero when the model does not know the TLD. Ordering
by it means a run that never finishes the pool has still spent its requests where
the metric pays most. Inside one share tier the order is a content hash rather
than alphabetical, because alphabetical clusters the numeric-prefix junk
("0171.com", "1-800-...") that was never archived, and a truncated run would then
badly understate the real hit rate.

Share alone is not enough, and the first version of this list proved it twice.

The model is built from CC-MAIN-2024-10, so it scores today's brand gTLDs near
100% English, and the pinned PSL accepts them as registrable. Parse noise out of
Usenet headers and mail addresses (`stopspam.aol`, `redneck.nec`, `aaaa.aaa`)
therefore sorted to the very top of a list meant to hold the best targets, and a
three-domain probe of that head came back 3 for 3 with no capture. A TLD that did
not exist in the window cannot hold an in-window capture, so era eligibility is
the first sort key.

That still left the two-letter coincidences, which era eligibility cannot catch
because they are real ccTLDs: `what.ev.er`, `bother.co.ck`, and 241 forged
`.mil` hostnames (`dumicsamvfs.mil`, `zydagy.mil`) that the model scores near
100%. The signal that separates them is in the store, not in a guess about the
names: how many dated domains the whole collection holds for that TLD. Measured,
it splits cleanly. `.uk` 187,063, `.au` 78,952, `.nz` 24,365, `.gov` 1,017,
against `.mil` 69, `.gu` 69, `.vi` 67, `.bb` 64, `.ck` 54, `.gh` 53. A TLD that
contributes fewer than a thousand dated domains to a 10.2M-pair store cannot move
the equivalent-English score either way, so where it sits in the queue does not
matter and it belongs behind every TLD that can. This does demote genuinely tiny
ccTLDs along with the junk, which is the right call for the same reason: the
question is only what to spend the next thousand requests on.

Nothing is deleted. Ineligible and thinly-attested names go to the tail, because
the week will not reach them anyway and deleting rows on a judgement the store
cannot back is worse than leaving them last.

Domains any journal has already answered are dropped here rather than left for
the engine's own resume scan. The scan would skip them anyway, but it does so
after `-n` has been counted out, so leaving them in makes a batch of 1,200 query
far fewer than 1,200 new names.

Read-only. Writes the target list and nothing else.

    uv run python scripts/build_pool_candidates.py
"""

import hashlib
import json
import sys
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402

from ark.cdx import answered as cdx_answered  # noqa: E402
from ark.journal import queried_domains  # noqa: E402

STORE = Path("data/ark.duckdb")
MODEL = Path("feedback-phase-3/equivalent_english_domain_calculator/q2_tld_top_langs.json")
JOURNAL_DIR = Path("data/raw/cdx")
OUT = Path("data/raw/cdx/pool_candidates.txt")

# TLDs that could hold a capture between 1996 and 2001. The original gTLDs, plus
# the 2000 ICANN round, which was delegated from 2001 and so can only appear at
# the very end of the window. Every ccTLD is two letters and they were delegated
# through the 1990s, so length carries them without listing 250 codes.
ERA_GTLDS = frozenset({"com", "net", "org", "edu", "gov", "mil", "int", "arpa"})
ERA_2001 = frozenset({"biz", "info", "name", "pro", "aero", "coop", "museum"})


def in_window_era(tld: str) -> bool:
    """Whether the TLD existed in time to be captured in the window."""
    return len(tld) == 2 or tld in ERA_GTLDS or tld in ERA_2001


# Below this many dated domains in the whole store, a TLD cannot move the
# equivalent-English score whatever we find in it, so its place in the queue is
# not worth an argument and it goes behind the ones that can.
ATTESTED_MIN = 1000

# Domains the store holds with no in-window year. `domain_year` is the master
# table, so absence from it is exactly what "still only a candidate" means.
_POOL_SQL = """
SELECT d.domain
FROM domain d
WHERE NOT EXISTS (SELECT 1 FROM domain_year y WHERE y.domain = d.domain)
"""

# Dated domains per right-most label, which is the unit the reviewer's model and
# this ranking both key on. `domain.tld` holds the public suffix (`co.uk`), so it
# is the wrong column here and would report .uk as 28 rather than 187,063.
_ATTESTED_SQL = """
SELECT split_part(domain, '.', -1) AS tld, count(DISTINCT domain) AS dated
FROM domain_year
GROUP BY tld
"""


def english_weights(path: Path) -> dict[str, Decimal]:
    """TLD -> English primary-page-language share, the reviewer's own table."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(tld).lower(): Decimal(str(share)) / Decimal("100")
        for tld, lang, share in zip(raw["tld"], raw["lang"], raw["perc_of_tld"], strict=True)
        if tld and lang == "eng"
    }


def read_only_store(path: Path, attempts: int = 20) -> duckdb.DuckDBPyConnection:
    """Open the store for reading, waiting out the maintenance loop's writer.

    DuckDB takes a single writer per file and refuses every other opener while it
    is held, read-only included. The ingest loop holds it for seconds every 15
    minutes, so a retry lands rather than fails.
    """
    for attempt in range(attempts):
        try:
            return duckdb.connect(str(path), read_only=True)
        except duckdb.IOException:
            if attempt == attempts - 1:
                raise
            time.sleep(15)
    raise AssertionError("unreachable")


def spread(domain: str) -> bytes:
    """Deterministic tiebreak inside a share tier, stable across processes."""
    return hashlib.blake2b(domain.encode(), digest_size=8).digest()


def main() -> None:
    weights = english_weights(MODEL)
    conn = read_only_store(STORE)
    try:
        pool = [row[0] for row in conn.execute(_POOL_SQL).fetchall()]
        attested = dict(conn.execute(_ATTESTED_SQL).fetchall())
    finally:
        conn.close()

    answered = queried_domains(JOURNAL_DIR, "cdx", answered=cdx_answered)
    fresh = [d for d in pool if d not in answered]

    ranked = sorted(
        (
            (
                in_window_era(tld) and attested.get(tld, 0) >= ATTESTED_MIN,
                weights.get(tld, Decimal("0")),
                domain,
            )
            for domain, tld in ((d, d.rsplit(".", 1)[-1]) for d in fresh)
        ),
        key=lambda item: (not item[0], -item[1], spread(item[2])),
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for _worth, _weight, domain in ranked:
            fh.write(f"{domain}\n")

    head = [row for row in ranked if row[0]]
    equivalent = sum((w for _t, w, _d in head), Decimal("0"))
    by_tld: Counter = Counter(d.rsplit(".", 1)[-1] for _t, _w, d in head)
    print(f"pool with no assigned year   : {len(pool):,}")
    print(f"already answered by a query  : {len(pool) - len(fresh):,}")
    print(f"written to {OUT}: {len(ranked):,}")
    print(f"  in-window TLD, attested >= {ATTESTED_MIN}: {len(head):,} (queried first)")
    print(f"  everything else                  : {len(ranked) - len(head):,} (tail, not reached)")
    print(f"equivalent-English if every name in the head hits: {equivalent:.1f}")
    if head:
        print(f"mean English weight in the head: {equivalent / len(head):.4f}")
    print("\nhead TLDs by count (share, dated in store, equivalent-English):")
    for tld, count in by_tld.most_common(12):
        share = weights.get(tld, Decimal("0"))
        print(
            f"  .{tld:<8} {count:>8,}  {share * 100:>6.2f}%  "
            f"{attested.get(tld, 0):>10,}  {Decimal(count) * share:>10.1f}"
        )


if __name__ == "__main__":
    main()
