"""The National Library of Australia's PANDORA title index, as candidate seeds.

One of the four directories under `data/raw/` that no file in the tree read, and
the reviewer's first priority names unprocessed files explicitly. It is
**seed-only and can never be anything else**: the index carries no date column of
any kind, so nothing in it can evidence a year. Writing it to an annual file would
be the DMOZ error in `SPEC.md` III.3.

**Why it is worth seeding anyway, and why the expectation is near zero.** The
reviewer asked for the candidate pool to be as large as practicable (III.2, IX),
and `.au` carries the highest English share in the table at 0.9904. Against that:
the index spans PANDORA's whole run rather than the window, so a large share of
its titles are simply later than 2001, and a 60-domain sample of it against the
working AWA endpoint returned **zero** in-window captures. So this grows the pool
and is not expected to grow the annual files. Both halves are the honest claim.

Measured 2026-08-10: 87,732 rows, 87,658 with a URL, 35,391 registrable domains,
of which **29,432 the store did not know at all**, 16,658 of them `.au`.

    uv run python scripts/seed_pandora_titles.py            # write the host list
    uv run ark seed data/raw/pandora-titles/pandora_hosts.txt

Or `just pandora-seed`, which does both.
"""

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ark.canonical import to_registrable  # noqa: E402

# `data/raw/pandora/` holds a byte-identical second copy of the same CSV; this
# reads the one that has its schema and crawl documentation beside it.
CSV_PATH = ROOT / "data/raw/pandora-titles/pandora-titles.csv"
OUT_PATH = ROOT / "data/raw/pandora-titles/pandora_hosts.txt"
URL_FIELD = "gathered_url"


def registrable_domains(path: Path) -> tuple[set[str], dict[str, int]]:
    """Distinct registrable domains from the index's `gathered_url` column.

    Read with `utf-8-sig`, because the file carries a BOM and without it the
    first header becomes `﻿tep_id` and `DictReader` silently returns no
    `tep_id` column at all.
    """
    stats = {"rows": 0, "with_url": 0, "unparsed": 0}
    out: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if URL_FIELD not in (reader.fieldnames or []):
            raise SystemExit(f"{path} has no {URL_FIELD} column: {reader.fieldnames}")
        for record in reader:
            stats["rows"] += 1
            url = (record.get(URL_FIELD) or "").strip()
            if not url:
                continue
            stats["with_url"] += 1
            name = to_registrable(url)
            if name:
                out.add(name)
            else:
                stats["unparsed"] += 1
    return out, stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=CSV_PATH)
    ap.add_argument("--out", type=Path, default=OUT_PATH)
    args = ap.parse_args()

    domains, stats = registrable_domains(args.csv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(sorted(domains)) + "\n", encoding="utf-8")
    print(
        f"{stats['rows']:,} rows, {stats['with_url']:,} with a URL, "
        f"{stats['unparsed']:,} URLs no registrable name could be read from"
    )
    print(f"wrote {args.out.relative_to(ROOT)}: {len(domains):,} distinct registrable domains")
    print("seed-only: the index carries no date column, so nothing here evidences a year")


if __name__ == "__main__":
    main()
