"""Answer "why is this domain in this year?" from the shipped Parquet export.

Ships inside `provenance/` as `trace.py`, so a reviewer can query the evidence
graph without installing a database, cloning the project, or writing SQL. The
only requirement is `uv`, which the rest of the delivery already needs:

    uv run --with duckdb --no-project python trace.py
    uv run --with duckdb --no-project python trace.py example.com
    uv run --with duckdb --no-project python trace.py example.com 1998

Run it from inside the folder that holds the Parquet files; the table names in
`LOAD.sql` are relative to it for the same reason.
"""

import sys
from pathlib import Path

TABLES = ("source", "domain", "evidence", "domain_year", "ingested_file")


def load(directory: Path):
    import duckdb

    conn = duckdb.connect()
    for table in TABLES:
        path = directory / f"{table}.parquet"
        if not path.exists():
            raise SystemExit(f"{path} not found; run this from inside the provenance folder")
        conn.execute(f"CREATE TABLE {table} AS SELECT * FROM read_parquet('{path}')")
    return conn


def summarise(conn) -> None:
    print("Provenance export loaded.\n")
    for table in TABLES:
        count = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"  {table:<16} {count:>12,} rows")
    example = conn.execute(
        """
        SELECT dy.domain, dy.assigned_year FROM domain_year dy
        JOIN evidence e ON e.evidence_id = dy.evidence_id
        WHERE e.evidence_type <> 'prior_reused' LIMIT 1
        """
    ).fetchone()
    if example:
        print(f"\nTry:  python trace.py {example[0]} {example[1]}")


def trace(conn, domain: str, year: int | None) -> None:
    """Print every observation supporting this domain, per year."""
    rows = conn.execute(
        """
        SELECT dy.assigned_year, s.name, e.evidence_type, e.evidence_value, e.evidence_url
        FROM domain_year dy
        JOIN evidence e ON e.domain = dy.domain AND e.evidence_year = dy.assigned_year
        JOIN source s ON s.source_id = e.source_id
        WHERE dy.domain = ? AND (? IS NULL OR dy.assigned_year = ?)
        ORDER BY dy.assigned_year, s.name
        """,
        [domain, year, year],
    ).fetchall()
    if not rows:
        held = conn.execute("SELECT 1 FROM domain WHERE domain = ?", [domain]).fetchone()
        if held:
            print(f"{domain}: in the dataset, but no year assigned (it is a candidate).")
        else:
            print(f"{domain}: not in the dataset.")
        return

    print(f"{domain}\n")
    current = None
    for assigned_year, source, kind, value, url in rows:
        if assigned_year != current:
            current = assigned_year
            print(f"  {assigned_year}")
        print(f"    {source:<18} {kind:<18} {value}")
        if url:
            print(f"    {'':<18} {'':<18} {url}")
    print(
        "\nEach line is one observation: which source saw this domain, what kind of\n"
        "evidence it is, and the artifact or timestamp it came from. A year is listed\n"
        "only where at least one observation supports that specific year."
    )


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    conn = load(Path(__file__).resolve().parent)
    if not args:
        summarise(conn)
        return
    year = int(args[1]) if len(args) > 1 else None
    trace(conn, args[0].strip().lower(), year)


if __name__ == "__main__":
    main()
