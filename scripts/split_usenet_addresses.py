"""Split the recovered Usenet addresses by corroboration, exactly as Usenet is split.

These come from the same messages as `usenet_announce` and `usenet_mention` and
carry the same risk: a human typed the address. So they take the same rule. A
domain another source already places in an annual file carries the post's date as
`dated_directory`; a name appearing only here goes to the candidate pool and
earns its year from a capture.

The 120-archive sample measured on 8 August put 12,512 of 14,581 net-new pairs on
domains never seen anywhere, so the split is not a formality here: it is most of
the volume. Quoting the pre-split figure would overstate the source by about
seven times, which is the error that sank three of four source verdicts the same
morning.

Read-only against the store.

    uv run python scripts/split_usenet_addresses.py --write
"""

import argparse
import gzip
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402

from ark.english_share import english_weights  # noqa: E402
from ark.journal import journal_writer, write_journal_line  # noqa: E402

STORE = ROOT / "data/ark.duckdb"
IN_DIR = ROOT / "data/raw/usenet_addr"
YEARS = range(1996, 2002)


def open_store(attempts: int = 80, pause: float = 15.0) -> duckdb.DuckDBPyConnection:
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
    args = ap.parse_args()

    seen: dict[tuple[str, int], dict] = {}
    for path in sorted(IN_DIR.glob("usenet_addr_*.jsonl.gz")):
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
        raise SystemExit(f"no journals in {IN_DIR}")

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

    weights = english_weights()
    dated, candidates = [], []
    fresh_ee = Decimal(0)
    fresh = 0
    for (domain, year), record in sorted(seen.items()):
        out = {
            "domain": domain,
            "year": year,
            "message_id": record.get("message_id", ""),
            "group": record.get("group", "usenet"),
            "url": record.get("url", ""),
        }
        if domain in attested:
            dated.append(out)
            if (domain, year) not in held:
                fresh += 1
                fresh_ee += weights.get(domain.rsplit(".", 1)[-1], Decimal(0))
        else:
            candidates.append(out)

    print(f"recovered (domain, year) rows: {len(seen):,}")
    print(f"  corroborated -> dated_directory : {len(dated):,}")
    print(f"    of those, not yet held        : {fresh:,}  worth {fresh_ee:,.1f} EE")
    print(f"  seen only here -> candidates    : {len(candidates):,}")
    if not args.write:
        print("\ndry run; pass --write to create both journals")
        return

    for name, batch in (("usenet_addr_dated", dated), ("usenet_addr_candidates", candidates)):
        path = IN_DIR / f"{name}.jsonl.gz"
        with journal_writer(path) as fh:
            for record in batch:
                write_journal_line(fh, record)
        print(f"wrote {path} ({len(batch):,} records)")


if __name__ == "__main__":
    main()
