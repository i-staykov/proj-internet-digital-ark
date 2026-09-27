"""Split the trade-press journal into a dated-evidence half and a candidate half.

Same rule as Usenet and Tucows, and here it is least optional of the three. The
year is sound: it is the publication date of a scanned issue, a property of the
artifact. The *domain* is the risky half, because it arrives through optical
character recognition of a 1990s page, which reads `rn` as `m` and `l` as `1` and
breaks hostnames across line ends.

The 5 August measurement put a number on it. Of Boardwatch's 216 net-new pairs,
84 were on domains the store already attests in an annual file and 123 were names
seen nowhere else, not even in the candidate pool. A fabricated domain lands in
that second group by construction, so admitting it on OCR's word alone would put
invented names into the annual files.

So: a domain already dated, by a year of ours or by a line of his files that is
exactly the name, carries the issue date as `dated_directory`, and a name appearing
only here goes to the candidate pool, where a capture can earn it a year later.
That is the corroboration rule the project applies to every free-text source, and
it is what makes an OCR source safe to use at all.

Read-only against the store.

    uv run python scripts/sources/trade_press/split_trade_press.py --write

`--journal` and `--tag` exist because the ingest ledger keys on content hash. The
first corpus was split into `tradepress_dated.jsonl.gz` and ingested under that
name, so rewriting that path with a second corpus folded in would be refused with
an sha256 mismatch, and rightly. A later corpus is therefore split from its own
journals into its own output names, and the two ingests stay separately
attributable:

    uv run python scripts/sources/trade_press/split_trade_press.py \\
        --journal data/raw/tradepress/tradepress_20260808T172417Z.jsonl.gz \\
        --tag american --write
"""

import argparse
import gzip
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ark import held  # noqa: E402
from ark.db import connect_read_only_patiently  # noqa: E402
from ark.english_share import weight_of  # noqa: E402
from ark.journal import journal_writer, write_journal_line  # noqa: E402

STORE = ROOT / "data/ark.duckdb"
IN_DIR = ROOT / "data/raw/tradepress"
YEARS = range(1996, 2002)


def title_of(identifier: str) -> str:
    """Which magazine an item is, from its identifier.

    Reporting only, and prefix rules rather than a metadata lookup because the
    identifier already carries the answer for every item in the American corpus.
    Anything unrecognised falls through to `other`, which is the whole of the
    first, hobbyist corpus.
    """
    lower = identifier.lower()
    if lower.startswith("sim_computerworld"):
        return "Computerworld (microfilm)"
    if lower.startswith("computerworld"):
        return "Computerworld (scanned)"
    if lower.startswith("macworld"):
        return "Macworld"
    if lower.startswith("macaddict"):
        return "MacAddict"
    if lower.startswith("bub_gb"):
        return "Google Books weekly"
    return "other"


def read_journals(paths: list[Path]) -> dict[tuple[str, int], dict]:
    """Every (domain, year) the collector journalled, keeping the first issue that named it."""
    seen: dict[tuple[str, int], dict] = {}
    for path in paths:
        try:
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    domain, year = record.get("domain"), record.get("year")
                    if not domain or year not in YEARS:
                        continue
                    seen.setdefault((domain, int(year)), record)
        except (OSError, EOFError):
            continue
    return seen


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    ap.add_argument(
        "--journal",
        type=Path,
        action="append",
        help="a collector journal to split; repeatable, defaults to every journal in the directory",
    )
    ap.add_argument(
        "--tag",
        default="",
        help="suffix for the output names, so a later corpus does not overwrite an ingested file",
    )
    ap.add_argument(
        "--out", type=Path, default=IN_DIR, help="journal directory (default %(default)s)"
    )
    args = ap.parse_args()

    paths = args.journal or sorted(IN_DIR.glob("tradepress_*.jsonl.gz"))
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise SystemExit(f"no such journal: {missing[0]}")

    seen = read_journals(paths)
    if not seen:
        raise SystemExit(f"no journals in {IN_DIR}: run collect_trade_press.py first")

    domains = {domain for domain, _ in seen}
    conn = connect_read_only_patiently(STORE)
    try:
        attested = held.attested(conn, domains)
        known = held.known_years(conn, domains)
    finally:
        conn.close()

    dated, candidates = [], []
    stats: Counter = Counter()
    by_title: dict[str, Counter] = {}
    ee_by_title: dict[str, Decimal] = {}
    for (domain, year), record in sorted(seen.items()):
        identifier = record.get("identifier", "")
        out = {
            "domain": domain,
            "year": year,
            "message_id": identifier,
            "group": "tradepress",
            "url": record.get("url", ""),
        }
        title = title_of(identifier)
        counts = by_title.setdefault(title, Counter())
        counts["rows"] += 1
        if domain in attested:
            dated.append(out)
            counts["corroborated"] += 1
            if (domain, year) not in known:
                stats["netnew_pairs"] += 1
                counts["netnew"] += 1
                ee_by_title[title] = ee_by_title.get(title, Decimal(0)) + weight_of(domain)
        else:
            candidates.append(out)

    print(f"in-window (domain, year) rows: {len(seen):,}")
    print(f"  corroborated, dated by us or named exactly in his files: {len(dated):,}")
    print(f"    of those, pairs neither we nor his files date yet    : {stats['netnew_pairs']:,}")
    print(f"  uncorroborated, candidate pool only                    : {len(candidates):,}")

    # The number the metric pays for, per title, because "which magazine was
    # worth reading" is not answerable from the totals and was the question the
    # first corpus got wrong.
    print(f"\n{'title':<28}{'rows':>10}{'corrob.':>10}{'net-new':>10}{'net-new EE':>14}")
    total_ee = Decimal(0)
    for title in sorted(by_title, key=lambda t: -ee_by_title.get(t, Decimal(0))):
        counts = by_title[title]
        ee = ee_by_title.get(title, Decimal(0))
        total_ee += ee
        print(
            f"{title:<28}{counts['rows']:>10,}{counts['corroborated']:>10,}"
            f"{counts['netnew']:>10,}{ee:>14.2f}"
        )
    print(
        f"{'TOTAL':<28}{len(seen):>10,}{len(dated):>10,}{stats['netnew_pairs']:>10,}{total_ee:>14.2f}"
    )
    print("\nEE here is the split's own estimate; `uv run ark stats` across the ingest decides.")

    if not args.write:
        print("\ndry run; pass --write to create both journals")
        return

    suffix = f"_{args.tag}" if args.tag else ""
    written = []
    for name, batch in (("tradepress_dated", dated), ("tradepress_candidates", candidates)):
        path = args.out / f"{name}{suffix}.jsonl.gz"
        with journal_writer(path) as fh:
            for record in batch:
                write_journal_line(fh, record)
        print(f"wrote {path} ({len(batch):,} records)")
        written.append((name, path))
    print("\nnext:")
    for key, path in written:
        print(f"  uv run ark ingest {key} {path}")


if __name__ == "__main__":
    main()
