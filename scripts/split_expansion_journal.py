"""Split an expansion journal into its corroborated and uncorroborated halves.

`ark download` marks a whole page curated or not, from the seed file. That is the
right unit for the assertion (the page either is an editorially maintained
catalogue or it is not) and the wrong unit for the risk, which is per name:
archived HTML carries typos, and a curated page can still list `arvard.edu`.

So a curated journal is split before ingest. Names some other source already
attests stay curated and are ingested as `expansion_directory`, where the page's
capture date evidences the year. Names appearing nowhere else are
written as ordinary links and ingested as `expansion_links`, which is
candidate-only, so they earn their year from their own capture instead.

Nothing is discarded, and both halves are hashed into the file ledger like any
other source file.

Usage:
    uv run python scripts/split_expansion_journal.py data/raw/expand/round4/expand_round4.jsonl.gz
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402

from ark.expand import split_by_corroboration  # noqa: E402
from ark.journal import journal_writer, open_journal, write_journal_line  # noqa: E402

STORE = Path("data/ark.duckdb")
# DuckDB takes one writer at a time and the maintain loop takes it every few
# seconds, so an unretried read here fails whenever a round is actually running,
# which is exactly when this script gets used. Cost of waiting is seconds.
LOCK_ATTEMPTS = 120
LOCK_PAUSE = 5.0


def read_records(path: Path) -> list[dict]:
    records = []
    with open_journal(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def open_store() -> duckdb.DuckDBPyConnection:
    """Read-only connection, waiting out whoever currently holds the write lock."""
    for attempt in range(LOCK_ATTEMPTS):
        try:
            return duckdb.connect(str(STORE), read_only=True)
        except duckdb.IOException:
            if attempt == LOCK_ATTEMPTS - 1:
                raise
            time.sleep(LOCK_PAUSE)
    raise AssertionError("unreachable")


def known_domains() -> set[str]:
    conn = open_store()
    try:
        return {row[0] for row in conn.execute("SELECT domain FROM domain").fetchall()}
    finally:
        conn.close()


def _sibling(path: Path, suffix: str) -> Path:
    stem = path.name.replace(".jsonl.gz", "")
    return path.with_name(f"{stem}_{suffix}.jsonl.gz")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("journal", type=Path, help="Expansion journal to split.")
    parser.add_argument("--write", action="store_true", help="Write the two journals.")
    args = parser.parse_args()

    records = [r for r in read_records(args.journal) if r.get("status") == 200]
    known = known_domains()
    corroborated, uncorroborated = split_by_corroboration(records, known)
    yes = {d for r in corroborated for d in r["domains"]}
    no = {d for r in uncorroborated for d in r["domains"]}
    print(f"captured pages: {len(records):,}")
    print(f"corroborated domains: {len(yes):,} -> expansion_directory (master-eligible)")
    print(f"uncorroborated domains: {len(no):,} -> expansion_links (candidate pool)")

    if not args.write:
        print("dry run; pass --write to create both journals")
        return
    out_yes, out_no = _sibling(args.journal, "corroborated"), _sibling(args.journal, "unverified")
    for path, batch in ((out_yes, corroborated), (out_no, uncorroborated)):
        if batch:
            with journal_writer(path) as fh:
                for record in batch:
                    write_journal_line(fh, record)
            print(f"wrote {path} ({len(batch):,} records)")
    print(
        f"next: uv run ark ingest expansion_directory {out_yes} --round N\n"
        f"      uv run ark ingest expansion_links     {out_no} --round N"
    )


if __name__ == "__main__":
    main()
