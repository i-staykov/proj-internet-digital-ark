"""Publish the list of collector journals this store has actually ingested.

**The problem.** The fleet fills its disk with journals it has already handed over, and
nothing of the fleet's can know which ones are safe to remove: it never opens the store. Age
is not an answer, because a journal the bank never pulled is still the only copy of its records.

**The authority is the sha256 in `ingested_file`.** That row is written by the ingest itself,
against the bytes it read, so a match proves this store holds the records of that exact
content, not merely of a file with the same name. A journal whose bytes changed after ingest
does not match and is not removable, which is the safe direction.

The receipt is a two-column file, name and digest, and it only ever grows. The bank writes
it beside the staged snapshot, where the fleet's cleanup reads it and removes what matches.

    uv run python scripts/harness/ack_journals.py [--out PATH]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ark.db import connect_read_only_patiently

REPO = Path(__file__).resolve().parents[2]
STORE = REPO / "data/ark.duckdb"
DEFAULT_OUT = REPO / "output/journal_acks.tsv"
# The shapes a collector writes. Anything else in the ledger is a source artifact we fetched,
# not a journal the fleet wrote, and it is not this file's business.
JOURNAL_SUFFIXES = (".jsonl.gz", ".jsonl")


def acks(store: Path = STORE) -> list[tuple[str, str]]:
    """Every ingested journal as (file name, sha256), newest ingest first. A writer held
    past a minute raises, which the sync reads as a skipped ack."""
    conn = connect_read_only_patiently(store, patience_s=60)
    try:
        clause = " OR ".join(f"file_name LIKE '%{s}'" for s in JOURNAL_SUFFIXES)
        return conn.execute(
            f"""
            SELECT DISTINCT file_name, sha256 FROM ingested_file
            WHERE ({clause}) AND sha256 IS NOT NULL AND length(sha256) = 64
            ORDER BY file_name
            """
        ).fetchall()
    finally:
        conn.close()


def write(rows: list[tuple[str, str]], out: Path) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f"{name}\t{digest}\n" for name, digest in rows)
    out.write_text(body, encoding="utf-8")
    out.chmod(0o644)  # the fleet's cleanup reads it by path
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    out = args.out if args.out.is_absolute() else Path.cwd() / args.out
    count = write(acks(), out)
    print(f"{count:,} ingested journals -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
