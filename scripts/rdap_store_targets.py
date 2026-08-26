"""Build the RDAP target list from the STORE, which is the population that pays.

**The measurement that decided this, and it reversed my first attempt.** Pointing
RDAP at domains the store has never seen returns 100% net-new but only **1.02%
in-window**, worth 6.3 equivalent-English per thousand queries. The raw list
returns 36.4% in-window with 11.4% of those net-new, worth **25.7 per thousand**.
A domain the store has never seen is precisely a domain that did not exist in
1996-2001, so filtering for novelty filters out the value.

**So the population is store domains that have never been RDAP-queried**: names
some era source already attested, which are therefore real and era-relevant, but
whose registry creation year the store does not hold. 12,873,029 of the store's
14.8 million qualify.

**Ordered by English weight**, because throughput is finite and a `.uk` hit is
worth 1.6x a `.com` one and 7x a `.de` one.

**Excluded, and each for a measured reason.** `.gov`, `.mil`, `.edu` and `.int`
are dropped: C-27 measured 584,646 of them in the candidate pool returning a 0.14%
capture rate against 48.70% for everything else, because they are anti-harvester
munging carried in from Usenet. Domains already holding all six years are dropped
because a creation date cannot add a seventh.

**And era eligibility is a hard gate ahead of the weight**, reusing
`build_pool_candidates.in_window_era` rather than inventing a second rule. Ordering
on weight alone put `0.box` and `0.in-addr.arpa` at the head of the first list:
`.arpa` scores 1.0000 and `.box` and `.dot` are modern gTLDs that could not have
existed in 1996-2001, so the highest-weight names were the ones guaranteed to
return nothing.

    uv run python scripts/rdap_store_targets.py --out data/raw/rdap/store_targets.txt
"""

import argparse
import gzip
import json
import sys
import time
from pathlib import Path

import duckdb

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_pool_candidates import in_window_era  # noqa: E402

from ark.english_share import english_weights  # noqa: E402

# Restricted registries whose pool entries are fabricated, per C-27. `.arpa` joins
# them because no website ever sat under it in the window and it scores 1.0000,
# which makes it the single most dangerous TLD to sort by weight. Kept as a named
# list rather than a name-shape rule, because the justification is registry
# closure and not how the strings look.
SKIP_TLDS = ("gov", "mil", "edu", "int", "arpa")

# **Measured queries per second, per registry, because the ranking is EE per SECOND
# and not EE per query.** This is the correction that mattered most here. Ordering
# on weight alone put `.er` and `.gu` first at 0.2 q/s; adding a volume floor moved
# `.au` to the front at 11 q/s. Verisign answers at 65 q/s, so `.com` at weight
# 0.6321 is worth 41 weighted domains a second against `.au`'s 10.9 at weight
# 0.9904, and `.com` is also 4.49 million of the six-million list.
#
# Unmeasured registries take DEFAULT_RATE, which is deliberately pessimistic: an
# unknown registry is far more likely to be slow than fast, and the cost of
# underrating a fast one is a later reorder while the cost of overrating a slow one
# is hours of a three-day window.
RATE = {
    "com": 65.0,
    "net": 65.0,
    "org": 40.0,
    "au": 11.0,
    "uk": 11.0,
    "nz": 8.0,
    "ca": 8.0,
    "us": 8.0,
    "za": 5.0,
    "ie": 5.0,
}
DEFAULT_RATE = 3.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="data/raw/rdap/store_targets.txt")
    ap.add_argument("--max", type=int, default=6_000_000)
    ap.add_argument(
        "--min-tld",
        type=int,
        default=20_000,
        help="skip TLDs the store holds fewer of; they cannot repay a slow registry",
    )
    args = ap.parse_args()

    queried: set[str] = set()
    for path in sorted(Path("data/raw/rdap").glob("rdap*.jsonl.gz*")):
        try:
            with gzip.open(path, "rt") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    dom = rec.get("domain")
                    if dom:
                        queried.add(dom)
        except EOFError:
            pass
        except Exception:
            continue
    print(f"already queried: {len(queried):,}")

    for _ in range(120):
        try:
            con = duckdb.connect("data/ark.duckdb", read_only=True)
            break
        except Exception:
            time.sleep(20)
    else:
        sys.exit("store stayed locked")

    con.execute("create temp table done(domain varchar)")
    if queried:
        con.executemany("insert into done values (?)", [(d,) for d in queried])
    con.execute("create index if not exists done_ix on done(domain)")

    weights = english_weights()
    # Only era-eligible TLDs reach the weight table, so the gate is applied by the
    # join itself rather than by a second filter that could drift away from it.
    eligible = {
        t: v for t, v in weights.items() if in_window_era(t) and t not in SKIP_TLDS and v > 0.05
    }
    print(f"era-eligible weighted TLDs: {len(eligible):,}")
    con.execute("create temp table w(tld varchar, weight double, score double)")
    con.executemany(
        "insert into w values (?, ?, ?)",
        [(t, float(v), float(v) * RATE.get(t, DEFAULT_RATE)) for t, v in eligible.items()],
    )

    # **A volume floor, and it is about THROUGHPUT rather than about value.** Ordering
    # on weight alone put `.er`, `.gu` and `.nr` at the head: they score 1.0000 in the
    # model, the store holds a handful of each, and their registries answer in about
    # five seconds. Measured, that head ran at **0.2 queries a second** against 65 for
    # the same code on Verisign, a 300x difference decided entirely by which registry
    # was asked. A TLD the store barely holds cannot repay a slow registry, so
    # `--min-tld` drops it, and `score` then sorts on equivalent-English per second.
    rows = con.execute(
        """
        with pool as (
            select d.domain, regexp_extract(d.domain, '([^.]+)$') as tld
            from domain d
            where not exists (select 1 from done q where q.domain = d.domain)
              and (select count(*) from domain_year y where y.domain = d.domain) < 6
        ),
        sized as (
            select p.*, count(*) over (partition by p.tld) as tld_n from pool p
        )
        select s.domain
        from sized s
        join w on w.tld = s.tld
        where s.tld_n >= ?
        order by w.score desc, s.domain
        limit ?
        """,
        [args.min_tld, args.max],
    ).fetchall()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(r[0] for r in rows) + "\n", encoding="utf-8")
    print(f"wrote {out}: {len(rows):,} store domains never RDAP-queried, weight-ordered")


if __name__ == "__main__":
    main()
