"""Apply the corroboration split to Granite Canyon's zone lists, before any ingest.

**Why this exists.** These are a free-DNS operator's own machine-written lists of the zones its
BIND was configured to serve and could not load. The DATE is excellent: each reject edition
stamps its own generation instant in its bytes, `Rejected Zone List:  7-May-2001 22:11 GMT`, and
the Wayback capture fixes when the file existed. But the zone NAME was typed by a customer into a
submission form, so under the project's split a name some other source already dates is real and
the edition's stamp settles its year, while a name appearing only here parks in the candidate pool
to earn its own.

**The held-fraction is why this source is worth having**, and it is the transferable part: 60.4%
on the 1999 prune list and 46.8% on the 2001 reject union, against 87 to 99% for authority
corpora, ~50% for blocklists and 98.4 to 99.6% for visitor logs. A zone is not a page, so no
crawler reaches it through a link and the artifact is not head-selected: these are people who had
a domain and no server. The population also does not collapse on the 2001 threshold, P(lacks 2001
| held) measuring com 0.5745 here against the store-wide 0.611.

**One lane pair per edition, because each edition carries its own date.** Six reject editions all
stamped 2001 and one prune list stamped 1999, so the year comes from the artifact and never from a
default. `to_registrable` drops `.in-addr.arpa` reverse zones and malformed rows on its own, which
matters because `.arpa` carries the highest weight in the model and `ark check` refuses it.

**Nothing is discarded.** Both lanes are written; the loader routes the uncorroborated half to the
candidate pool as `link_target`, which never dates a year.

    uv run python scripts/sources/registries/split_granitecanyon.py            # report only
    uv run python scripts/sources/registries/split_granitecanyon.py --write
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

SRC = Path("data/raw/granitecanyon")
# `<A HREF="00sec.com.txt">00sec.com</A>`: the anchor TEXT is the zone name.
_ANCHOR = re.compile(r"<A\s+HREF=\"[^\"]*\">([^<]+)</A>", re.I)
# The edition's own generation stamp, which is what dates its rows.
_STAMP = re.compile(r"Rejected Zone List:\s*(\d{1,2})-([A-Za-z]{3})-(\d{4})")
# `status.shtml` dates the prune list "29 November 1999", and the filename agrees.
PRUNE_YEAR = 1999


def reject_edition(path: Path) -> tuple[int, set[str]]:
    """One reject edition's year, read from its own bytes, and its zone names."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    stamp = _STAMP.search(raw)
    if stamp is None:
        raise SystemExit(f"{path.name} carries no `Rejected Zone List:` stamp; refusing to guess")
    year = int(stamp.group(3))
    names = {d for token in _ANCHOR.findall(raw) if (d := to_registrable(token.strip()))}
    return year, names


def prune_list(path: Path) -> tuple[int, set[str]]:
    """The 1999 prune list: one zone name per line, no markup."""
    names = {
        d
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if (d := to_registrable(line.strip()))
    }
    return PRUNE_YEAR, names


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="write the two lanes per edition")
    args = ap.parse_args()

    editions: list[tuple[str, int, set[str]]] = []
    prune = SRC / "prune-19991130.txt"
    if prune.is_file():
        year, names = prune_list(prune)
        editions.append(("19991130", year, names))
    for path in sorted(SRC.glob("zonerejects-*.html")):
        year, names = reject_edition(path)
        editions.append((path.stem.split("-", 1)[1], year, names))
    if not editions:
        print(f"nothing under {SRC}; run collect_granitecanyon.py first")
        return 1

    conn = connect_read_only_patiently(DEFAULT_DB_PATH)
    try:
        corroborated = {
            row[0] for row in conn.execute("SELECT DISTINCT domain FROM domain_year").fetchall()
        }
    finally:
        conn.close()
    print(f"{len(corroborated):,} domains already carry an assigned year\n")

    total_dated = total_cand = 0
    dated_ee = Decimal(0)
    for stamp, year, names in editions:
        keep = sorted(n for n in names if n in corroborated)
        park = sorted(n for n in names if n not in corroborated)
        total_dated += len(keep)
        total_cand += len(park)
        dated_ee += sum((Decimal(weight_of(n.rsplit(".", 1)[-1])) for n in keep), Decimal(0))
        held = len(keep) / len(names) if names else 0.0
        print(
            f"  {stamp} ({year}): {len(names):,} zones -> "
            f"{len(keep):,} dated ({held:.1%} held), {len(park):,} candidate"
        )
        if args.write:
            (SRC / f"granitecanyon-dated.{stamp}.txt").write_text("\n".join(keep) + "\n")
            (SRC / f"granitecanyon-cand.{stamp}.txt").write_text("\n".join(park) + "\n")

    print(f"\ntotal across editions: {total_dated:,} dated rows, {total_cand:,} candidate rows")
    print(f"gross EE of the dated lane (before removing pairs already held): {dated_ee:,.1f}")
    if not args.write:
        print("\nreport only. Pass --write to emit the lanes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
