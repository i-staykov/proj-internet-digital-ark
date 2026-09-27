"""Apply the corroboration split to the chastity-list blacklist, before any ingest.

**Why this exists, and it is the junkfilter argument on a second artifact.** chastity-list
is a hand-maintained squidGuard blacklist: Roy-Magne Mo added each hostname himself. So the
DATE is a machine's and the NAME is a person's typing. Under the project's split, a name
already dated, by a year of ours or by his files naming it exactly, is real and the edition's
date settles its year; a name appearing only here has no independent evidence it ever
resolved, and parks in the candidate pool to earn its own year later.

**What dates the edition.** The tar member header tar wrote on every file in
`chastity-list_0.5.orig.tar.gz`, `Dec 14 2001`, corroborated from inside by 209 per-date
diff filenames spanning `20010813` to `20011201`, all in window. One edition, one year, so
this parser needs no date arithmetic: every row is 2001.

**The predicate is the same one used for junkfilter**, stated explicitly because this repo
holds two candidates: a domain is corroborated when `held.attested` finds it dated, by a year
of ours in `our_domain_year` or by a line of his files that is exactly the name. His
`www.x.com` does not corroborate `x.com`. The weaker test, presence in `domain`, would admit
names that are themselves only candidates, which is not what the corroboration split in
`docs/lore/laws.md` means by "once another source dates that domain".

**Only the base `domains` files are read.** The `urls` files are the same population one
path deeper and add 14,734 lines that collapse onto hosts the base already names; the diffs
are increments to the base rather than separate editions. Reading the base alone is what the
14,229.0 EE figure was measured on.

**Nothing is discarded.** Both lanes are written; the loader routes the uncorroborated half
to the candidate pool as `link_target`, which never dates a year. Filenames differ across
lanes because the bulk ledger keys on `path.name` alone.

    uv run python scripts/sources/blocklists/split_chastity.py            # report only
    uv run python scripts/sources/blocklists/split_chastity.py --write
"""

import argparse
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from ark import held  # noqa: E402
from ark.canonical import to_registrable  # noqa: E402
from ark.db import DEFAULT_DB_PATH, connect_read_only_patiently  # noqa: E402
from ark.english_share import weight_of  # noqa: E402

SRC = Path("data/raw/chastity/chastity-list-0.5/db")
OUT = Path("data/raw/chastity")
# The tar member header on every file in the orig tarball. One edition, one year.
STAMP = "20011214"


def names_in(paths: list[Path]) -> set[str]:
    """Canonical registrable domains across every category's base `domains` file."""
    out: set[str] = set()
    for path in paths:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            token = line.strip()
            if not token or token.startswith("#"):
                continue
            domain = to_registrable(token)
            if domain:
                out.add(domain)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="write the two lanes")
    ap.add_argument("--out", type=Path, default=OUT, help="lane directory (default %(default)s)")
    args = ap.parse_args()

    bases = sorted(SRC.glob("*/domains"))
    if not bases:
        print(f"no category `domains` files under {SRC}; unpack the orig tarball first")
        return 1
    print(f"{len(bases)} categories: {', '.join(p.parent.name for p in bases)}\n")

    names = names_in(bases)
    conn = connect_read_only_patiently(DEFAULT_DB_PATH)
    try:
        corroborated = held.attested(conn, names)
    finally:
        conn.close()
    print(
        f"{len(corroborated):,} of {len(names):,} names are dated by us "
        "or named exactly in his files"
    )

    keep = sorted(n for n in names if n in corroborated)
    park = sorted(n for n in names if n not in corroborated)
    dated_ee = sum((Decimal(weight_of(n.rsplit(".", 1)[-1])) for n in keep), Decimal(0))

    share = len(keep) / len(names) if names else 0.0
    print(f"\n{len(names):,} distinct registrable domains")
    print(f"  corroborated, so datable : {len(keep):,}  ({share:.1%})")
    print(f"  novel, so candidate only : {len(park):,}")
    print(f"\ngross EE of the dated lane (before removing pairs already held): {dated_ee:,.1f}")

    if args.write:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / f"chastity-dated.{STAMP}.txt").write_text("\n".join(keep) + "\n")
        (args.out / f"chastity-cand.{STAMP}.txt").write_text("\n".join(park) + "\n")
        print(f"\nwrote both lanes under {args.out}/")
    else:
        print("\nreport only. Pass --write to emit the two lanes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
