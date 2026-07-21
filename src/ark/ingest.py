"""Load the provided legacy baseline into the provenance store.

The legacy year files are the prior researchers' verified output. They are
read-only input here: every line passes through the same canonicalizer as
all other sources, mismatches are counted and sampled for review, and the
files themselves are never rewritten.
"""

from pathlib import Path

import duckdb
import pyarrow as pa
from loguru import logger
from tqdm import tqdm

from ark.canonical import to_registrable
from ark.db import ensure_source

YEARS = range(1996, 2002)
MERGE_STATS_FILENAME = "merge_stats_new0714.csv"
DEFAULT_REPORT_PATH = Path("data/reports/ingest_mismatches.txt")
# review file keeps at most this many examples per category per file
SAMPLE_LIMIT = 50
CHUNK_SIZE = 200_000


def _append_samples(report_path: Path, title: str, samples: list[str]) -> None:
    if not samples:
        return
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("a", encoding="utf-8") as fh:
        fh.write(f"## {title}\n")
        fh.writelines(f"{line}\n" for line in samples)
        fh.write("\n")


def _flush_chunk(conn: duckdb.DuckDBPyConnection, chunk: list[str]) -> None:
    conn.register("chunk_tbl", pa.table({"domain": chunk}))
    conn.execute("INSERT INTO stage SELECT domain FROM chunk_tbl")
    conn.unregister("chunk_tbl")


def ingest_year_file(
    conn: duckdb.DuckDBPyConnection,
    path: Path,
    year: int,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> dict[str, int | str | bool]:
    """Canonicalize one legacy year file into domain/evidence/domain_year rows."""
    marker = path.name
    stats: dict[str, int | str | bool] = {
        "file": marker,
        "year": year,
        "skipped": False,
        "lines": 0,
        "ok": 0,
        "changed": 0,
        "rejected": 0,
        "blank": 0,
    }

    # a file already carrying evidence rows was fully ingested before
    already = conn.execute(
        "SELECT count(*) FROM evidence WHERE evidence_type = 'prior_reused' AND evidence_value = ?",
        [marker],
    ).fetchone()[0]
    if already:
        stats["skipped"] = True
        logger.info(f"{marker}: already ingested, skipping")
        return stats

    source_id = ensure_source(conn, "prior_task", "timestamped")
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS stage (domain TEXT)")
    conn.execute("DELETE FROM stage")

    changed_samples: list[str] = []
    rejected_samples: list[str] = []
    chunk: list[str] = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in tqdm(fh, desc=marker, unit=" lines"):
            stats["lines"] += 1
            raw = line.strip()
            if not raw:
                stats["blank"] += 1
                continue
            domain = to_registrable(raw)
            if domain is None:
                stats["rejected"] += 1
                if len(rejected_samples) < SAMPLE_LIMIT:
                    rejected_samples.append(raw)
                continue
            stats["ok"] += 1
            if domain != raw:
                stats["changed"] += 1
                if len(changed_samples) < SAMPLE_LIMIT:
                    changed_samples.append(f"{raw} -> {domain}")
            chunk.append(domain)
            if len(chunk) >= CHUNK_SIZE:
                _flush_chunk(conn, chunk)
                chunk = []
    if chunk:
        _flush_chunk(conn, chunk)

    before = conn.execute(
        "SELECT count(*) FROM domain_year WHERE assigned_year = ?", [year]
    ).fetchone()[0]
    conn.execute(
        r"""
        INSERT OR IGNORE INTO domain (domain, tld, discovered_source)
        SELECT DISTINCT domain, regexp_replace(domain, '^[^.]+\.', ''), ?
        FROM stage
        """,
        [source_id],
    )
    conn.execute(
        """
        INSERT INTO evidence (domain, source_id, evidence_year, evidence_type,
                              evidence_value, acquisition_method)
        SELECT DISTINCT domain, ?, ?, 'prior_reused', ?, 'prior_task'
        FROM stage
        """,
        [source_id, year, marker],
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO domain_year (domain, assigned_year, evidence_id)
        SELECT e.domain, e.evidence_year, e.evidence_id
        FROM evidence e
        WHERE e.evidence_type = 'prior_reused' AND e.evidence_value = ?
        """,
        [marker],
    )
    after = conn.execute(
        "SELECT count(*) FROM domain_year WHERE assigned_year = ?", [year]
    ).fetchone()[0]
    stats["unique_domains"] = conn.execute("SELECT count(DISTINCT domain) FROM stage").fetchone()[0]
    stats["year_rows"] = after - before
    conn.execute("DELETE FROM stage")

    _append_samples(report_path, f"{marker}: changed by canonicalization", changed_samples)
    _append_samples(report_path, f"{marker}: rejected", rejected_samples)
    logger.info(str(stats))
    return stats


def load_merge_stats(conn: duckdb.DuckDBPyConnection, csv_path: Path) -> None:
    """Keep the prior researchers' per-year stats as the reference format."""
    conn.execute(
        "CREATE OR REPLACE TABLE prior_merge_stats AS SELECT * FROM read_csv_auto(?)",
        [str(csv_path)],
    )


def ingest_legacy(
    conn: duckdb.DuckDBPyConnection,
    legacy_dir: Path,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> list[dict[str, int | str | bool]]:
    """Ingest all six year files and the merge stats. Idempotent per file."""
    missing = [year for year in YEARS if not (legacy_dir / f"{year}.txt").is_file()]
    if missing:
        raise FileNotFoundError(f"missing year files in {legacy_dir}: {missing}")

    all_stats = [
        ingest_year_file(conn, legacy_dir / f"{year}.txt", year, report_path) for year in YEARS
    ]

    csv_path = legacy_dir / MERGE_STATS_FILENAME
    if csv_path.is_file():
        load_merge_stats(conn, csv_path)
    else:
        logger.warning(f"{MERGE_STATS_FILENAME} not found in {legacy_dir}, skipping")
    return all_stats
