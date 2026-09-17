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
from ark.metrics import record_metrics

YEARS = range(1996, 2002)
MERGE_STATS_FILENAME = "merge_stats_new0714.csv"
DEFAULT_REPORT_PATH = Path("data/reports/ingest_mismatches.txt")
# review file keeps at most this many examples per category per file
SAMPLE_LIMIT = 50
CHUNK_SIZE = 200_000
# **Rows per INSERT into `evidence`, and it is a memory number, not a speed one.**
# `evidence` carries a PRIMARY KEY and a FOREIGN KEY on `domain`, so every inserted row
# costs an ART lookup, and DuckDB holds the whole statement's index work until it
# commits. On 2026-09-17 loading `merged260911-4` that cost 13 GiB on 1997's 2.67M rows
# and died there ("Failed to commit: failed to allocate data of size 32.0 KiB"), with
# 2001's 43M rows still to come, against an `evidence` table already holding 444M rows.
# The abort then left the index in a state DuckDB refused to open for writing at all
# ("Corrupted ART index"), so the store had to be restored from the pre-load backup.
# Batched, the peak is bounded by this number rather than by the size of a year file.
BATCH_ROWS = 2_000_000


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
    marker_prefix: str = "",
) -> dict[str, int | str | bool]:
    """Canonicalize one legacy year file into domain/evidence/domain_year rows.

    `marker_prefix` namespaces the evidence marker, which is what makes a SECOND
    baseline ingestable. The marker is otherwise the file name alone, so a later
    release's `1996.txt` looks like the one already ingested and is skipped as
    already done: quietly, behind six reassuring "already ingested" lines. Pass
    the release name to keep the two distinct.
    """
    marker = f"{marker_prefix}/{path.name}" if marker_prefix else path.name
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
    # Numbered once so the batches below are disjoint and stable. `SELECT DISTINCT` was
    # inside each of the three inserts and ran three times over the year file; here it
    # runs once, into a table that can spill.
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE stage_d AS
        SELECT row_number() OVER () AS rid, domain FROM (SELECT DISTINCT domain FROM stage)
        """
    )
    to_write = conn.execute("SELECT count(*) FROM stage_d").fetchone()[0]
    # Every batch is its own transaction, so a failure part way leaves the marker's rows
    # half written. The skip at the top of this function reads a non-zero count as a
    # finished load, so that half would be invisible and permanent. Undo it instead: the
    # marker is unique to this release and this year, so deleting by it takes back
    # exactly what this call wrote and nothing else.
    written = conn.execute("SELECT coalesce(max(evidence_id), 0) FROM evidence").fetchone()[0]
    try:
        for low in range(0, to_write, BATCH_ROWS):
            window = [low, low + BATCH_ROWS]
            conn.execute(
                r"""
                INSERT OR IGNORE INTO domain (domain, tld, discovered_source)
                SELECT domain, regexp_replace(domain, '^[^.]+\.', ''), ?
                FROM stage_d WHERE rid > ? AND rid <= ?
                """,
                [source_id, *window],
            )
            conn.execute(
                """
                INSERT INTO evidence (domain, source_id, evidence_year, evidence_type,
                                      evidence_value, acquisition_method)
                SELECT domain, ?, ?, 'prior_reused', ?, 'prior_task'
                FROM stage_d WHERE rid > ? AND rid <= ?
                """,
                [source_id, year, marker, *window],
            )
            now_at = conn.execute("SELECT coalesce(max(evidence_id), 0) FROM evidence").fetchone()[
                0
            ]
            conn.execute(
                """
                INSERT OR IGNORE INTO domain_year (domain, assigned_year, evidence_id)
                SELECT e.domain, e.evidence_year, e.evidence_id
                FROM evidence e
                WHERE e.evidence_type = 'prior_reused' AND e.evidence_value = ?
                  AND e.evidence_id > ? AND e.evidence_id <= ?
                """,
                [marker, written, now_at],
            )
            written = now_at
    except Exception:
        logger.error(f"{marker}: failed part way, taking back the rows this load wrote")
        conn.execute(
            "DELETE FROM domain_year WHERE evidence_id IN "
            "(SELECT evidence_id FROM evidence WHERE evidence_type = 'prior_reused' "
            "AND evidence_value = ?)",
            [marker],
        )
        conn.execute(
            "DELETE FROM evidence WHERE evidence_type = 'prior_reused' AND evidence_value = ?",
            [marker],
        )
        raise
    after = conn.execute(
        "SELECT count(*) FROM domain_year WHERE assigned_year = ?", [year]
    ).fetchone()[0]
    stats["unique_domains"] = to_write
    stats["year_rows"] = after - before
    conn.execute("DELETE FROM stage")

    _append_samples(report_path, f"{marker}: changed by canonicalization", changed_samples)
    _append_samples(report_path, f"{marker}: rejected", rejected_samples)
    logger.info(str(stats))
    record_metrics(conn, "ingest-legacy", marker, stats)
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
    marker_prefix: str = "",
) -> list[dict[str, int | str | bool]]:
    """Ingest all six year files and the merge stats. Idempotent per file.

    Pass `marker_prefix` when loading a later baseline release, so its evidence
    rows do not collide with an earlier release that used the same file names.
    """
    missing = [year for year in YEARS if not (legacy_dir / f"{year}.txt").is_file()]
    if missing:
        raise FileNotFoundError(f"missing year files in {legacy_dir}: {missing}")

    all_stats = [
        ingest_year_file(conn, legacy_dir / f"{year}.txt", year, report_path, marker_prefix)
        for year in YEARS
    ]

    csv_path = legacy_dir / MERGE_STATS_FILENAME
    if csv_path.is_file():
        load_merge_stats(conn, csv_path)
    else:
        logger.warning(f"{MERGE_STATS_FILENAME} not found in {legacy_dir}, skipping")
    return all_stats
