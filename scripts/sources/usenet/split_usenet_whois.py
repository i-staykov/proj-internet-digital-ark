"""Split the pasted whois creation dates by corroboration, before any ingest.

The date here is the registry's own string, so it is not what the split guards
against. The NAME is: a person chose which record to paste and retyped or
reflowed it, and a mangled hostname carrying a real creation date would put an
invented domain into an annual file with a confident year attached.

So the same rule the rest of the Usenet routes take. A domain another source
already places in `domain_year` is real, and the pasted registry line settles
its creation year as `whois_creation`. A name appearing only here goes to the
candidate pool as `link_target` and dates nothing until it earns its own
evidence. Nothing is discarded.

Rule 6 is why the gain is smaller than the row count: a creation date evidences
its own year and no other, so a 1997 record on a name we already hold at 1997
adds nothing at all.

Read-only against the store.

    uv run python scripts/sources/usenet/split_usenet_whois.py
    uv run python scripts/sources/usenet/split_usenet_whois.py --write
"""

import argparse
import gzip
import json
import sys
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402

from ark.english_share import english_weights  # noqa: E402
from ark.journal import journal_writer, write_journal_line  # noqa: E402

STORE = ROOT / "data/ark.duckdb"
YEARS = range(1996, 2002)


def open_store(attempts: int = 80, pause: float = 15.0) -> duckdb.DuckDBPyConnection:
    """Wait out a running ingest rather than failing the split."""
    for attempt in range(attempts):
        try:
            return duckdb.connect(str(STORE), read_only=True)
        except duckdb.IOException:
            if attempt == attempts - 1:
                raise
            time.sleep(pause)
    raise AssertionError("unreachable")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--in-dir", type=Path, default=ROOT / "data/raw/usenet_whois")
    ap.add_argument("--out-prefix", default="usenet_whois")
    args = ap.parse_args()

    seen: dict[tuple[str, int], dict] = {}
    for path in sorted(args.in_dir.glob("usenet_whois_*.jsonl.gz")):
        if path.name.startswith(f"{args.out_prefix}_dated") or path.name.startswith(
            f"{args.out_prefix}_candidates"
        ):
            continue
        try:
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    domain, year = record.get("domain"), record.get("year")
                    if domain and year in YEARS:
                        seen.setdefault((domain, int(year)), record)
        except (OSError, EOFError):
            continue
    if not seen:
        raise SystemExit(f"no journals in {args.in_dir}")

    conn = open_store()
    try:
        attested = {
            r[0] for r in conn.execute("SELECT DISTINCT domain FROM domain_year").fetchall()
        }
        held = {
            (r[0], r[1])
            for r in conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall()
        }
    finally:
        conn.close()

    weights = english_weights()
    dated, candidates = [], []
    fresh_ee = Decimal(0)
    fresh = 0
    by_year: Counter = Counter()
    for (domain, year), record in sorted(seen.items()):
        out = {
            "domain": domain,
            "year": year,
            # the registry string the ingest quotes as the evidence value
            "created": record.get("created", ""),
            "message_id": record.get("message_id", ""),
            "group": record.get("group", "usenet"),
            "url": record.get("url", ""),
        }
        if domain in attested:
            dated.append(out)
            if (domain, year) not in held:
                fresh += 1
                by_year[year] += 1
                fresh_ee += weights.get(domain.rsplit(".", 1)[-1], Decimal(0))
        else:
            candidates.append(out)

    print(f"pasted whois creation dates, in-window (domain, year): {len(seen):,}")
    print(f"  corroborated -> whois_creation  : {len(dated):,}")
    print(f"    of those, not yet held        : {fresh:,}  worth {fresh_ee:,.1f} EE")
    print(f"    by year                       : {sorted(by_year.items())}")
    print(f"  seen only here -> candidates    : {len(candidates):,}")
    if not args.write:
        print("\ndry run; pass --write to create both journals")
        return

    for suffix, batch in (("dated", dated), ("candidates", candidates)):
        path = args.in_dir / f"{args.out_prefix}_{suffix}.jsonl.gz"
        with journal_writer(path) as fh:
            for record in batch:
                write_journal_line(fh, record)
        print(f"wrote {path} ({len(batch):,} records)")


if __name__ == "__main__":
    main()
