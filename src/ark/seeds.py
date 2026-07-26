"""The auxiliary seed pool: hostnames and URLs, not registered domains.

Brief III.8 fixes the registered domain as the counting unit, so `foo.com`,
`www.foo.com` and `shop.foo.com` are one line in the annual files. That is the
right unit for counting and the wrong unit for downloading: a crawler handed
`foo.com` never sees the pages that only ever existed at `shop.foo.com`. Brief I
asks for historical URL seeds alongside the domain lists, and III.2 names an
auxiliary seed pool as a legitimate home for data that carries no year evidence
of its own.

This module rebuilds that lost granularity without a second parser. Every bulk
parser already yields `BulkRecord.raw`, the value exactly as the source wrote it,
before canonicalization; the annual files keep the canonical form and the seed
pool keeps the raw one. Reusing the same parsers is the point: a seed can never
disagree with the evidence it came from, because both are read from one pass over
one file.

Only seeds whose raw form differs from the registered domain are kept, since a
raw value equal to the domain adds nothing a year file does not already carry.

Shipped, under `output/seeds/`:
  `download_seeds.txt`     the download list: one distinct raw hostname or URL
                           per line, sorted
  `download_seeds.csv`     the same seeds with the registered domain, the year
                           the source dates them to, and the source name

Intermediate, under `data/seeds/parts/`: one CSV per source, so re-running a
source replaces only its own rows. Not shipped, because the two files above
already hold everything in it.
"""

import csv
from collections import Counter
from pathlib import Path

import duckdb
from loguru import logger

from ark.bulk import SourceSpec
from ark.canonical import to_registrable
from ark.ingest import YEARS

SEED_DIR = Path("output/seeds")
PARTS_DIR = Path("data/seeds/parts")
SEED_LIST_NAME = "download_seeds.txt"
SEED_TABLE_NAME = "download_seeds.csv"
PART_COLUMNS = ["seed", "domain", "year"]
TABLE_COLUMNS = ["seed", "domain", "year", "source"]


def write_source_part(spec: SourceSpec, paths: list[Path], parts_dir: Path = PARTS_DIR) -> Counter:
    """Extract one source's raw hostnames and URLs into its own part file."""
    parts_dir.mkdir(parents=True, exist_ok=True)
    stats: Counter = Counter()
    seen: set[tuple[str, int]] = set()

    with (parts_dir / f"{spec.key}.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(PART_COLUMNS)
        for path in sorted(paths):
            parse_stats: Counter = Counter()
            for record in spec.parse(path, parse_stats):
                stats["records"] += 1
                if record.year not in YEARS:
                    continue
                domain = to_registrable(record.raw)
                if domain is None:
                    stats["unusable"] += 1
                    continue
                if record.raw == domain:
                    # already the counting unit, so the year files hold it
                    stats["no_extra_granularity"] += 1
                    continue
                key = (record.raw, record.year)
                if key in seen:
                    stats["duplicate"] += 1
                    continue
                seen.add(key)
                writer.writerow([record.raw, domain, record.year])
                stats["seeds"] += 1
    logger.info(f"seeds {spec.key}: {dict(stats)}")
    return stats


def combine_parts(
    conn: duckdb.DuckDBPyConnection | None = None,
    seed_dir: Path = SEED_DIR,
    parts_dir: Path = PARTS_DIR,
) -> dict[str, int]:
    """Merge every part file into the two shipped seed files.

    Given a store connection, also reports how many seeds belong to domains the
    baseline did not have, which is the figure that says whether the pool is
    worth downloading.
    """
    parts = sorted(parts_dir.glob("*.csv"))
    if not parts:
        return {"parts": 0, "seeds": 0}
    seed_dir.mkdir(parents=True, exist_ok=True)

    # One connection reads the part files directly, so millions of seeds are
    # never carried between two connections in Python. Doing that with
    # executemany once took minutes and held the store's write lock throughout.
    owned = conn is None
    db = duckdb.connect(":memory:") if owned else conn
    union = " UNION ALL ".join(
        f"SELECT seed, domain, year, '{p.stem}' AS source FROM read_csv_auto('{p}')" for p in parts
    )
    db.execute(f"CREATE OR REPLACE TEMP TABLE seed_pool AS SELECT * FROM ({union})")

    table_path = seed_dir / SEED_TABLE_NAME
    # Always quote the seed: URLs legitimately contain commas, and a reader that
    # sniffs its quoting from the first rows would otherwise decide this file has
    # none, then split those URLs into extra columns.
    db.execute(
        f"COPY (SELECT seed, domain, year, source FROM seed_pool "
        f"ORDER BY seed, year, source) TO '{table_path}' (HEADER true, FORCE_QUOTE (seed))"
    )
    list_path = seed_dir / SEED_LIST_NAME
    db.execute(
        f"COPY (SELECT DISTINCT seed FROM seed_pool ORDER BY seed) TO '{list_path}' (HEADER false)"
    )

    result = {
        "parts": len(parts),
        "rows": db.execute("SELECT count(*) FROM seed_pool").fetchone()[0],
        "seeds": db.execute("SELECT count(DISTINCT seed) FROM seed_pool").fetchone()[0],
        "domains": db.execute("SELECT count(DISTINCT domain) FROM seed_pool").fetchone()[0],
    }
    if not owned:
        result["domains_not_in_baseline"] = db.execute(
            """
            SELECT count(*) FROM (SELECT DISTINCT domain FROM seed_pool) sd
            WHERE NOT EXISTS (
                SELECT 1 FROM evidence e
                WHERE e.domain = sd.domain AND e.evidence_type = 'prior_reused'
            )
            """
        ).fetchone()[0]

    db.execute("DROP TABLE IF EXISTS seed_pool")
    if owned:
        db.close()
    logger.info(f"seed pool: {result}")
    return result
