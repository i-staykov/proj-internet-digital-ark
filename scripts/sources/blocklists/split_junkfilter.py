"""Apply the corroboration split to junkfilter's editions, before any ingest.

**Why this exists.** `jf-domains` is a hand-maintained blocklist: a maintainer added each
spam-origin domain himself. So the DATE is excellent, three machine-written stamps agreeing,
and the NAME is a person's typing. Under the project's split, a name some other source
already dates is real and the edition's date settles its year; a name appearing only here
has no independent evidence it ever resolved and goes to the candidate pool to earn its own.

**The predicate, and there are two candidates in this repo so this one is stated explicitly.**
`split_expansion_journal.py` treats every row of the `domain` table as known, which includes
names that are themselves only candidates. That is too weak for a blocklist. Used here:
**a domain is corroborated when it already carries an assigned year in `domain_year`**, which
is the same test every source priced on 2026-08-26 was measured against, and it is what
CLAUDE.md means by "another source needs to date that domain first".

**Nothing is discarded.** Both halves are written; the loader routes the uncorroborated half
to the candidate pool as `link_target`, which never dates a year.

**Filenames are distinct across the two lanes on purpose.** The bulk ledger keys on
`path.name` alone, so `dated/junkfilter.19980508.txt` and `cand/junkfilter.19980508.txt`
would collide and the second would be skipped as already ingested. Hence
`junkfilter-dated.<date>.txt` and `junkfilter-cand.<date>.txt`.

    uv run python scripts/sources/blocklists/split_junkfilter.py            # report only
    uv run python scripts/sources/blocklists/split_junkfilter.py --write
"""

import argparse
import re
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from ark.canonical import to_registrable  # noqa: E402
from ark.db import DEFAULT_DB_PATH, connect_read_only_patiently  # noqa: E402
from ark.english_share import weight_of  # noqa: E402

SRC = Path("data/raw/junkfilter")
DATED = SRC / "dated"
CAND = SRC / "cand"
EDITION = re.compile(r"^jf-domains\.(\d{4})(\d{2})(\d{2})$")


def names_in(path: Path) -> set[str]:
    """Canonical registrable domains in one `|`-joined, backslash-escaped edition."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    out = set()
    for token in raw.replace("\\", "").split("|"):
        token = token.strip()
        if not token:
            continue
        domain = to_registrable(token)
        if domain:
            out.add(domain)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="write the two lanes")
    args = ap.parse_args()

    editions = sorted(p for p in SRC.glob("jf-domains.*") if EDITION.match(p.name))
    if not editions:
        print(f"no editions in {SRC}; run collect_junkfilter.py first")
        return 1

    conn = connect_read_only_patiently(DEFAULT_DB_PATH)
    corroborated = {
        row[0] for row in conn.execute("SELECT DISTINCT domain FROM domain_year").fetchall()
    }
    print(f"{len(corroborated):,} domains already carry an assigned year\n")

    if args.write:
        DATED.mkdir(parents=True, exist_ok=True)
        CAND.mkdir(parents=True, exist_ok=True)

    total_dated = total_cand = 0
    dated_ee = Decimal(0)
    for path in editions:
        match = EDITION.match(path.name)
        assert match is not None
        stamp = "".join(match.groups())
        names = names_in(path)
        keep = sorted(n for n in names if n in corroborated)
        park = sorted(n for n in names if n not in corroborated)
        total_dated += len(keep)
        total_cand += len(park)
        dated_ee += sum(weight_of(n.rsplit(".", 1)[-1]) for n in keep)
        print(f"  {stamp}: {len(names):,} names -> {len(keep):,} dated, {len(park):,} candidate")
        if args.write:
            (DATED / f"junkfilter-dated.{stamp}.txt").write_text("\n".join(keep) + "\n")
            (CAND / f"junkfilter-cand.{stamp}.txt").write_text("\n".join(park) + "\n")

    print(f"\ntotal across editions: {total_dated:,} dated rows, {total_cand:,} candidate rows")
    print(f"gross EE of the dated lane (before removing pairs already held): {dated_ee:,.1f}")
    if not args.write:
        print("\nreport only. Pass --write to emit the two lanes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
