"""Shared bulk ingester: one audited loader, one small parser per source.

A parser turns one source file into BulkRecord rows; the loader does the
rest identically for every source: canonicalization, set-based staging,
evidence rows and year assignments (or candidate routing, per the evidence
taxonomy), the per-source audit CSV, run metrics, and a per-file ledger
that makes re-runs no-ops.

Crash rules: each file commits alone, its ledger row is part of that
commit, and its audit rows reach the CSV only after the commit. A failing
file is logged and skipped; the rest of the run continues.
"""

import csv
import hashlib
import sqlite3
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO

import duckdb
import pyarrow as pa
from loguru import logger
from tqdm import tqdm

from ark import approvals
from ark.audit import FIELDS, change_reason
from ark.canonical import reject_reason, to_registrable
from ark.db import ensure_source
from ark.evidence_types import ALL_TYPES, CANDIDATE_ONLY_TYPES
from ark.ingest import YEARS
from ark.metrics import record_metrics
from ark.seed import CDX_TASK
from ark.work_queue import enqueue

DEFAULT_REPORT_DIR = Path("data/reports")
CHUNK_SIZE = 200_000
# the audit CSV keeps every dropped line but samples corrected lines per
# reason per file; exact totals always land in run_metrics
CORRECTED_SAMPLE_LIMIT = 100

_STAGE_SCHEMA = pa.schema(
    [
        ("domain", pa.string()),
        ("year", pa.int32()),
        ("evidence_value", pa.string()),
        ("evidence_url", pa.string()),
    ]
)


@dataclass(frozen=True)
class BulkRecord:
    """One evidence-bearing observation parsed out of a source file."""

    raw: str
    year: int
    evidence_value: str
    evidence_url: str | None = None


# a parser reads one file, updates its stats counter, and yields records
ParseFn = Callable[[Path, Counter], Iterator[BulkRecord]]


@dataclass(frozen=True)
class SourceSpec:
    """Everything the loader needs to know about one bulk source."""

    key: str
    source_name: str
    evidence_type: str
    acquisition_method: str
    parse: ParseFn

    def __post_init__(self) -> None:
        if self.evidence_type not in ALL_TYPES:
            raise ValueError(f"unknown evidence type: {self.evidence_type}")

    @property
    def is_candidate_only(self) -> bool:
        return self.evidence_type in CANDIDATE_ONLY_TYPES


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _flush_stage(conn: duckdb.DuckDBPyConnection, columns: dict[str, list]) -> None:
    conn.register("bulk_chunk", pa.table(columns, schema=_STAGE_SCHEMA))
    conn.execute(
        "INSERT INTO bulk_stage SELECT domain, year, evidence_value, evidence_url FROM bulk_chunk"
    )
    conn.unregister("bulk_chunk")
    for values in columns.values():
        values.clear()


def _stage_records(
    conn: duckdb.DuckDBPyConnection,
    spec: SourceSpec,
    path: Path,
    audit_rows: list[list],
    stats: Counter,
) -> None:
    """Parse one file, canonicalize every record, and fill the staging table.

    Audit rows are buffered by the caller and reach the CSV only after the
    file's transaction commits, so the CSV never lists an unledgered file.
    """
    marker = path.name
    sample_counts: Counter = Counter()
    columns: dict[str, list] = {name: [] for name in _STAGE_SCHEMA.names}
    for record in tqdm(spec.parse(path, stats), desc=marker, unit=" records", leave=False):
        stats["records"] += 1
        # the schema would reject these anyway; count instead of aborting the run
        if record.year not in YEARS:
            stats["out_of_window"] += 1
            continue
        domain = to_registrable(record.raw)
        if domain is None:
            stats["rejected"] += 1
            audit_rows.append(
                [record.raw, "", reject_reason(record.raw), "dropped", marker, record.year]
            )
            continue
        if domain != record.raw:
            stats["corrected"] += 1
            reason = change_reason(record.raw, domain)
            if sample_counts[reason] < CORRECTED_SAMPLE_LIMIT:
                sample_counts[reason] += 1
                audit_rows.append([record.raw, domain, reason, "valid", marker, record.year])
        columns["domain"].append(domain)
        columns["year"].append(record.year)
        columns["evidence_value"].append(record.evidence_value)
        columns["evidence_url"].append(record.evidence_url)
        if len(columns["domain"]) >= CHUNK_SIZE:
            _flush_stage(conn, columns)
    if columns["domain"]:
        _flush_stage(conn, columns)


def _enqueue_unverified(
    conn: duckdb.DuckDBPyConnection, queue_conn: sqlite3.Connection, source_id: int
) -> int:
    """Queue this source's domains that still lack any year assignment.

    Reads the durable evidence rows, not the staging table, so a crashed or
    skipped run can always be repaired by running the ingest again.
    """
    cursor = conn.execute(
        "SELECT DISTINCT e.domain FROM evidence e WHERE e.source_id = ? AND NOT EXISTS "
        "(SELECT 1 FROM domain_year dy WHERE dy.domain = e.domain)",
        [source_id],
    )
    added = 0
    while True:
        rows = cursor.fetchmany(100_000)
        if not rows:
            return added
        added += enqueue(queue_conn, CDX_TASK, (row[0] for row in rows))


def ingest_file(
    conn: duckdb.DuckDBPyConnection,
    spec: SourceSpec,
    source_id: int,
    path: Path,
    audit_fh: IO[str],
    discovered_round: int = 0,
) -> dict:
    """Ingest one source file; a file already in the ledger is skipped whole.

    A ledger hit with different file content is an error, never a silent
    skip: same name, same source, same bytes is the only skippable case.
    """
    marker = path.name
    sha256 = _sha256(path)
    ledgered = conn.execute(
        "SELECT sha256 FROM ingested_file WHERE source_name = ? AND file_name = ?",
        [spec.source_name, marker],
    ).fetchone()
    if ledgered:
        if ledgered[0] != sha256:
            raise ValueError(
                f"{marker}: ledgered with different content (sha256 mismatch); "
                "rename the file or clear its ledger row before re-ingesting"
            )
        logger.info(f"{marker}: already ingested, skipping")
        return {"file": marker, "skipped": True}

    stats: Counter = Counter()
    audit_rows: list[list] = []
    conn.execute(
        "CREATE TEMP TABLE IF NOT EXISTS bulk_stage "
        "(domain TEXT, year INTEGER, evidence_value TEXT, evidence_url TEXT)"
    )
    conn.execute("DELETE FROM bulk_stage")
    _stage_records(conn, spec, path, audit_rows, stats)

    conn.execute("BEGIN TRANSACTION")
    try:
        conn.execute(
            r"""
            INSERT OR IGNORE INTO domain (domain, tld, discovered_source, discovered_round)
            SELECT DISTINCT domain, regexp_replace(domain, '^[^.]+\.', ''), ?, ?
            FROM bulk_stage
            """,
            [source_id, discovered_round],
        )
        # one evidence row per (domain, year) per source: the earliest capture
        # in this file, skipping pairs this source already evidenced; the
        # struct keeps value and url from the same staged row
        last_evidence_id = conn.execute(
            "SELECT coalesce(max(evidence_id), 0) FROM evidence"
        ).fetchone()[0]
        stats["evidence_rows"] = conn.execute(
            """
            INSERT INTO evidence (domain, source_id, evidence_year, evidence_type,
                                  evidence_value, evidence_url, acquisition_method)
            SELECT s.domain, ?, s.year, ?, min(s.evidence_value),
                   arg_min({'u': s.evidence_url}, s.evidence_value)['u'], ?
            FROM bulk_stage s
            WHERE NOT EXISTS (
                SELECT 1 FROM evidence e
                WHERE e.domain = s.domain AND e.evidence_year = s.year AND e.source_id = ?
            )
            GROUP BY s.domain, s.year
            """,
            [source_id, spec.evidence_type, spec.acquisition_method, source_id],
        ).fetchone()[0]
        # candidate-only evidence is provenance; it must never assign a year
        if not spec.is_candidate_only:
            stats["year_rows"] = conn.execute(
                """
                INSERT OR IGNORE INTO domain_year (domain, assigned_year, evidence_id)
                SELECT domain, evidence_year, evidence_id
                FROM evidence WHERE source_id = ? AND evidence_id > ?
                """,
                [source_id, last_evidence_id],
            ).fetchone()[0]
        stats["unique_domains"] = conn.execute(
            "SELECT count(DISTINCT domain) FROM bulk_stage"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO ingested_file (source_name, file_name, sha256, record_rows) "
            "VALUES (?, ?, ?, ?)",
            [spec.source_name, marker, sha256, stats["records"]],
        )
        record_metrics(conn, "ingest", f"{spec.key}:{marker}", dict(stats))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    csv.writer(audit_fh).writerows(audit_rows)
    audit_fh.flush()
    conn.execute("DELETE FROM bulk_stage")
    return {"file": marker, "skipped": False, **stats}


def ingest_files(
    conn: duckdb.DuckDBPyConnection,
    spec: SourceSpec,
    paths: list[Path],
    queue_conn: sqlite3.Connection | None = None,
    report_dir: Path = DEFAULT_REPORT_DIR,
    discovered_round: int = 0,
) -> dict:
    """Ingest many files of one source; each file is its own resumable unit.

    Refuses before touching the store if this source class has no human approval
    behind it. Master-eligible evidence can create a year assignment, and deciding
    whether a source deserves that is a judgement about proof rather than a
    measurement, so it is not the agent's to make. Candidate-only evidence passes
    freely: it can never date a year.
    """
    approvals.check(spec.source_name, spec.evidence_type)
    kind = "candidate_only" if spec.is_candidate_only else "timestamped"
    source_id = ensure_source(conn, spec.source_name, kind)
    audit_path = report_dir / f"{spec.key}_audit.csv"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not audit_path.exists()
    totals: Counter = Counter()
    ordered = sorted(paths)
    with audit_path.open("a", encoding="utf-8", newline="") as fh:
        if write_header:
            csv.writer(fh).writerow(FIELDS)
            fh.flush()
        for index, path in enumerate(ordered, start=1):
            try:
                result = ingest_file(conn, spec, source_id, path, fh, discovered_round)
            except Exception as exc:
                totals["files_failed"] += 1
                logger.error(f"[{index}/{len(ordered)}] {path.name}: failed ({exc}); continuing")
                continue
            if result["skipped"]:
                totals["files_skipped"] += 1
            else:
                totals["files_ingested"] += 1
                totals.update(
                    {
                        k: v
                        for k, v in result.items()
                        if isinstance(v, int) and not isinstance(v, bool)
                    }
                )
            logger.info(f"[{index}/{len(ordered)}] {result}")
    # runs after every pass, even an all-skipped one, so a crash between a
    # file's commit and this point is repaired by simply re-running
    if spec.is_candidate_only and queue_conn is not None:
        totals["enqueued"] = _enqueue_unverified(conn, queue_conn, source_id)
    summary = dict(totals)
    record_metrics(conn, "ingest", spec.key, summary)
    logger.info(f"{spec.key}: {summary}")
    return summary
