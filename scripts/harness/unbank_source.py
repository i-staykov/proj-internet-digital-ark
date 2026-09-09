"""Take one source's rows back out of the store, for the one case that needs it.

**Why this exists at all, given that nothing else in the project deletes evidence.** The
standing rule's fourth condition is that `ark check` passes AFTER the ingest, which can only
be tested by ingesting. Reverting the `Decision:` line on a red gate and leaving the rows
behind is worse than not automating the decision: every later sync starts red, the preflight
refuses, and the loop stops until someone repairs the store by hand. So the ingest that a red
gate condemns is undone here, and the pair is atomic in the only sense available: the line and
the rows go together.

**What it deletes, in foreign-key order**: the `hostname_year` and `domain_year` rows whose
evidence belongs to this source, then that evidence, then the source's `ingested_file`
receipts so the same journal can be read again. It leaves the `source` row and the `domain`
rows: a domain nothing dates is a candidate, which is a true statement about it, and the
source row is referenced by `domain.discovered_source`.

**What it costs, honestly.** A `domain_year` whose evidence row is this source's is deleted
even when another source could have dated that year, because the assignment names one
evidence row and that row is going. The next ingest of the other source re-derives it. That
is a real if small loss, and it is the price of not leaving a red store behind.

It is not a general undo: it refuses unless `--write` is given, it names every count before
and after, and `just sync` calls it only on the red-gate path.

    uv run python scripts/harness/unbank_source.py isc_survey --write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from ark.db import connect_patiently  # noqa: E402
from ark.sources import SOURCES  # noqa: E402

TABLES = ("hostname_year", "domain_year")


def source_names(keys: list[str]) -> list[str]:
    """Spec keys as the store names them. An unknown key is passed through as itself."""
    return [SOURCES[k].source_name if k in SOURCES else k for k in keys]


def counts(conn, name: str) -> dict[str, int]:
    row = conn.execute("SELECT source_id FROM source WHERE name = ?", [name]).fetchone()
    if row is None:
        return {}
    source_id = row[0]
    out = {"evidence": 0, "domain_year": 0, "hostname_year": 0, "ingested_file": 0}
    out["evidence"] = conn.execute(
        "SELECT count(*) FROM evidence WHERE source_id = ?", [source_id]
    ).fetchone()[0]
    for table in TABLES:
        out[table] = conn.execute(
            f"SELECT count(*) FROM {table} WHERE evidence_id IN "  # noqa: S608 - fixed names
            "(SELECT evidence_id FROM evidence WHERE source_id = ?)",
            [source_id],
        ).fetchone()[0]
    out["ingested_file"] = conn.execute(
        "SELECT count(*) FROM ingested_file WHERE source_name = ?", [name]
    ).fetchone()[0]
    return out


def unbank(conn, name: str) -> dict[str, int]:
    """Delete this source's rows, children first.

    One statement per commit rather than one transaction for all of them: DuckDB checks a
    foreign key against the state at the start of the transaction, so deleting a
    `domain_year` row and its `evidence` row together fails on the reference that is itself
    being removed. So the caller checks the counts afterwards and says so if anything is
    left, which is the guarantee this can actually give.
    """
    row = conn.execute("SELECT source_id FROM source WHERE name = ?", [name]).fetchone()
    if row is None:
        return {}
    source_id = row[0]
    before = counts(conn, name)
    for table in TABLES:
        conn.execute(
            f"DELETE FROM {table} WHERE evidence_id IN "  # noqa: S608 - fixed names
            "(SELECT evidence_id FROM evidence WHERE source_id = ?)",
            [source_id],
        )
    conn.execute("DELETE FROM evidence WHERE source_id = ?", [source_id])
    conn.execute("DELETE FROM ingested_file WHERE source_name = ?", [name])
    return before


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sources", nargs="+", help="spec keys or source names")
    ap.add_argument("--write", action="store_true", help="without it, only the counts")
    ap.add_argument("--db", type=Path, default=None)
    args = ap.parse_args(argv)

    conn = connect_patiently(args.db) if args.db else connect_patiently()
    try:
        for name in source_names(args.sources):
            if not args.write:
                held = counts(conn, name)
                print(f"unbank: {name} holds {held or 'nothing: no such source in the store'}")
                continue
            gone = unbank(conn, name)
            if not gone:
                print(f"unbank: {name} is not in the store, nothing removed")
                continue
            print(
                f"unbank: {name} removed, {gone['evidence']:,} evidence rows, "
                f"{gone['domain_year']:,} domain years, {gone['hostname_year']:,} hostname years, "
                f"{gone['ingested_file']:,} file receipts"
            )
            left = counts(conn, name)
            if any(left.values()):
                print(f"unbank: {name} STILL holds {left}, which is a bug", file=sys.stderr)
                return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
