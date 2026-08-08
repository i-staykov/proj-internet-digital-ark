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

So: a domain another source already places in an annual file carries the issue
date as `dated_directory`, and a name appearing only here goes to the candidate
pool, where a capture can earn it a year later. That is the corroboration rule
the project applies to every free-text source, and it is what makes an OCR source
safe to use at all.

Read-only against the store.

    uv run python scripts/split_trade_press.py --write
"""

import argparse
import gzip
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402

from ark.journal import journal_writer, write_journal_line  # noqa: E402

STORE = ROOT / "data/ark.duckdb"
IN_DIR = ROOT / "data/raw/tradepress"
YEARS = range(1996, 2002)


def open_store(attempts: int = 60, pause: float = 15.0) -> duckdb.DuckDBPyConnection:
    """Wait out the ingest loop's writer rather than failing the split."""
    for attempt in range(attempts):
        try:
            return duckdb.connect(str(STORE), read_only=True)
        except duckdb.IOException:
            if attempt == attempts - 1:
                raise
            time.sleep(pause)
    raise AssertionError("unreachable")


def read_journals() -> dict[tuple[str, int], dict]:
    """Every (domain, year) the collector journalled, keeping the first issue that named it."""
    seen: dict[tuple[str, int], dict] = {}
    for path in sorted(IN_DIR.glob("tradepress_*.jsonl.gz")):
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
    args = ap.parse_args()

    seen = read_journals()
    if not seen:
        raise SystemExit(f"no journals in {IN_DIR}: run collect_trade_press.py first")

    conn = open_store()
    try:
        rows = conn.execute("SELECT DISTINCT domain FROM domain_year").fetchall()
        attested = {r[0] for r in rows}
        held = {
            (r[0], r[1])
            for r in conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall()
        }
    finally:
        conn.close()

    dated, candidates = [], []
    stats: Counter = Counter()
    for (domain, year), record in sorted(seen.items()):
        out = {
            "domain": domain,
            "year": year,
            "message_id": record.get("identifier", ""),
            "group": "tradepress",
            "url": record.get("url", ""),
        }
        if domain in attested:
            dated.append(out)
            stats["netnew_pairs"] += (domain, year) not in held
        else:
            candidates.append(out)

    print(f"in-window (domain, year) rows: {len(seen):,}")
    print(f"  corroborated, another source already dates the domain: {len(dated):,}")
    print(f"    of those, pairs the store does not yet hold        : {stats['netnew_pairs']:,}")
    print(f"  uncorroborated, candidate pool only                  : {len(candidates):,}")
    if not args.write:
        print("\ndry run; pass --write to create both journals")
        return

    for path, batch in (
        (IN_DIR / "tradepress_dated.jsonl.gz", dated),
        (IN_DIR / "tradepress_candidates.jsonl.gz", candidates),
    ):
        with journal_writer(path) as fh:
            for record in batch:
                write_journal_line(fh, record)
        print(f"wrote {path} ({len(batch):,} records)")
    print("\nnext:")
    for key in ("tradepress_dated", "tradepress_candidates"):
        print(f"  uv run ark ingest {key} data/raw/tradepress/{key}.jsonl.gz")


if __name__ == "__main__":
    main()
