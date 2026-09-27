"""Shared bulk ingester: one audited loader, one small parser per source.

A parser turns one source file into BulkRecord rows; the loader does the rest identically
for every source: canonicalization, set-based staging, evidence rows and year assignments
(or candidate routing, per the evidence taxonomy), the per-source audit CSV, run metrics,
and a per-file ledger that makes re-runs no-ops.

Crash rules: each file commits alone, its ledger row is part of that commit, and its audit
rows reach the CSV only after the commit. A failing file is logged and skipped.

A class keeps one row per subject and year, the subject being the host a row names or else
its domain, whichever source repeats it; every row names the file it came from and where.
"""

import csv
import hashlib
import sqlite3
import tempfile
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO

import duckdb
import pyarrow as pa
from loguru import logger
from tqdm import tqdm

from ark import approvals, held
from ark.audit import FIELDS, change_reason
from ark.canonical import reject_reason, to_registrable
from ark.db import ensure_source
from ark.evidence_types import (
    ALL_TYPES,
    CANDIDATE_ONLY_TYPES,
    exact_host_expr,
    qualifies_sql,
    web_evidence_sql,
)
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
        ("record_location", pa.string()),
    ]
)
_CANDIDATE_LIST = ", ".join(f"'{t}'" for t in sorted(CANDIDATE_ONLY_TYPES))


@dataclass(frozen=True)
class BulkRecord:
    """One evidence-bearing observation parsed out of a source file. `location` is where in
    the file it sits; the loader writes `record <n>`, the parser's nth record, when it is None."""

    raw: str
    year: int
    evidence_value: str
    evidence_url: str | None = None
    location: str | None = None


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


def named_host_sql(alias: str) -> str:
    """The host a row names, or NULL: its capture's exact host, else a last token that is a
    host under its domain, the way each hostname lane ends its value (`... NS ns1.foo.com`)."""
    last = f"lower(regexp_extract({alias}.evidence_value, '([^ ]+)$', 1))"
    return (
        f"coalesce({exact_host_expr(alias)}, CASE WHEN regexp_matches({last}, '^[a-z0-9.-]+$') "
        f"AND ends_with({last}, '.' || {alias}.domain) THEN {last} END)"
    )


def subject_sql(alias: str) -> str:
    """What a row is about, the key its class keeps one row per: the host it names, else its
    domain."""
    return f"coalesce({named_host_sql(alias)}, {alias}.domain)"


def names_another_host_sql(alias: str) -> str:
    """A row that names a host other than its domain, `www.` included: it dates that host, never
    the registrable, so it writes no `domain_year`."""
    return f"coalesce({named_host_sql(alias)} <> {alias}.domain, false)"


def qualifies_own_sql(alias: str) -> str:
    """The XIII screen on a row's own subject: a web method's capture of the exact host."""
    return f"coalesce(({web_evidence_sql(alias)}) AND {exact_host_expr(alias)} IS NOT NULL, false)"


def held_rows_sql(
    keys: str, domain: str = "domain", year: str = "year", subject: str | None = None
) -> str:
    """`held(domain, evidence_year, subject, ships)`, the rows of one class at the (domain, year)
    pairs of `keys`, for a writer's one-row-per-subject test; `$type` names the class and
    `subject`, over `e`, what a row is about (`subject_sql` when None).

    Materialized, so the subject is computed only on the rows those pairs match and never on
    every row of `evidence`.
    """
    return f"""held AS MATERIALIZED (
        SELECT e.domain, e.evidence_year, {subject or subject_sql("e")} AS subject,
               {qualifies_own_sql("e")} AS ships
        FROM evidence e
        WHERE e.evidence_type = $type AND EXISTS (
            SELECT 1 FROM {keys} k WHERE k.{domain} = e.domain AND k.{year} = e.evidence_year)
    )"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _flush_stage(conn: duckdb.DuckDBPyConnection, columns: dict[str, list]) -> None:
    conn.register("bulk_chunk", pa.table(columns, schema=_STAGE_SCHEMA))
    conn.execute(
        "INSERT INTO bulk_stage "
        "SELECT domain, year, evidence_value, evidence_url, record_location FROM bulk_chunk"
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
    records = tqdm(spec.parse(path, stats), desc=marker, unit=" records", leave=False)
    for number, record in enumerate(records, 1):
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
        columns["record_location"].append(record.location or f"record {number}")
        if len(columns["domain"]) >= CHUNK_SIZE:
            _flush_stage(conn, columns)
    if columns["domain"]:
        _flush_stage(conn, columns)


def _enqueue_unverified(
    conn: duckdb.DuckDBPyConnection, queue_conn: sqlite3.Connection, source_id: int
) -> int:
    """Queue this source's domains that no year dates: no `domain_year` pair, and no line of
    his files naming the exact domain in any year. These are the names `held.attested` leaves.

    Reads the durable evidence rows, not the staging table, so a crashed or
    skipped run can always be repaired by running the ingest again. The names stay in the
    store and on disk, never in a Python set: a candidate-only source can hold millions.
    """
    conn.execute(
        "CREATE OR REPLACE TEMP TABLE _source_names AS "
        "SELECT DISTINCT domain AS name FROM evidence WHERE source_id = ?",
        [source_id],
    )
    try:
        if not conn.execute("SELECT count(*) FROM _source_names").fetchone()[0]:
            return 0
        his = held.load()
        with tempfile.TemporaryDirectory() as tmp:
            undated, queued = Path(tmp) / "undated.txt", Path(tmp) / "queued.txt"
            held.dump(
                conn,
                "SELECT name FROM _source_names "
                "WHERE name NOT IN (SELECT domain FROM domain_year) ORDER BY 1",
                undated,
            )
            held.minus(undated, his.all, queued)
            with queued.open(encoding="utf-8") as fh:
                return enqueue(queue_conn, CDX_TASK, (line.rstrip("\n") for line in fh))
    finally:
        conn.execute("DROP TABLE IF EXISTS _source_names")


def _date_pairs(conn: duckdb.DuckDBPyConnection, fresh: pa.Table) -> tuple[int, int]:
    """Date each pair a fresh row names the registrable of, and move a pair whose row fails the
    claim's test onto the lowest row that passes: the pair cites its best row, so a reader
    takes `domain_year` as it is. Returns (pairs added, pairs moved)."""
    if not fresh.num_rows:
        return 0, 0
    conn.register("fresh_rows", fresh)
    try:
        return _date_fresh_rows(conn)
    finally:
        conn.unregister("fresh_rows")


def _date_fresh_rows(conn: duckdb.DuckDBPyConnection) -> tuple[int, int]:
    added = conn.execute(
        f"""
        INSERT OR IGNORE INTO domain_year (domain, assigned_year, evidence_id)
        SELECT domain, evidence_year, min(evidence_id) FROM fresh_rows r
        WHERE NOT {names_another_host_sql("r")}
        GROUP BY domain, evidence_year
        """
    ).fetchone()[0]
    passing = f"SELECT count(*) FROM fresh_rows r WHERE {qualifies_sql('r', 'r.domain')}"
    if not conn.execute(passing).fetchone()[0]:
        return added, 0
    # the rows at the pairs a fresh row passes for are read first, so the test runs on those
    # and never on every row of `evidence`
    moved = conn.execute(
        f"""
        UPDATE domain_year SET evidence_id = best.evidence_id
        FROM (
            WITH pairs AS MATERIALIZED (
                SELECT DISTINCT r.domain, r.evidence_year FROM fresh_rows r
                WHERE {qualifies_sql("r", "r.domain")}
            ), at_pairs AS MATERIALIZED (
                SELECT w.evidence_id, w.domain, w.evidence_year, w.evidence_type,
                       w.evidence_value, w.evidence_url, w.acquisition_method
                FROM evidence w
                WHERE EXISTS (
                    SELECT 1 FROM pairs p
                    WHERE p.domain = w.domain AND p.evidence_year = w.evidence_year)
            )
            SELECT dy.domain, dy.assigned_year, min(w.evidence_id) AS evidence_id
            FROM domain_year dy
            JOIN at_pairs w ON w.domain = dy.domain AND w.evidence_year = dy.assigned_year
            WHERE w.evidence_type NOT IN ({_CANDIDATE_LIST})
              AND {qualifies_sql("w", "w.domain")}
              AND NOT EXISTS (
                SELECT 1 FROM at_pairs c
                WHERE c.evidence_id = dy.evidence_id AND {qualifies_sql("c", "dy.domain")})
            GROUP BY dy.domain, dy.assigned_year
        ) best
        WHERE domain_year.domain = best.domain AND domain_year.assigned_year = best.assigned_year
        """
    ).fetchone()[0]
    return added, moved


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
        "(domain TEXT, year INTEGER, evidence_value TEXT, evidence_url TEXT, "
        "record_location TEXT)"
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
        # one evidence row per (domain, year) from this file: a row that ships (a capture of
        # exactly that domain) first, then the lowest value; the struct keeps value, url and
        # location from the same staged row. A row of this class with the same subject and
        # year skips it, whichever source wrote it, unless the held row fails XIII and the
        # new one passes: an exact capture joins a host-less one
        fresh = conn.execute(
            f"""
            INSERT INTO evidence (domain, source_id, evidence_year, evidence_type,
                                  evidence_value, evidence_url, acquisition_method,
                                  source_file, record_location)
            WITH staged AS (
                SELECT b.domain, b.year, b.evidence_value, b.evidence_url, b.record_location,
                       {qualifies_sql("b", "b.domain")} AS ships
                FROM (SELECT *, $method::TEXT AS acquisition_method FROM bulk_stage) b
            ), picked AS (
                SELECT domain, year,
                       arg_min({{'v': evidence_value, 'u': evidence_url, 'l': record_location,
                                 'ships': ships}}, (NOT ships, evidence_value)) AS r
                FROM staged
                GROUP BY domain, year
            ), fresh AS (
                SELECT domain, year, r['v'] AS evidence_value, r['u'] AS evidence_url,
                       r['l'] AS record_location, $method::TEXT AS acquisition_method
                FROM picked
            ), {held_rows_sql("picked")}
            SELECT f.domain, $source_id, f.year, $type, f.evidence_value, f.evidence_url,
                   $method, $file, f.record_location
            FROM fresh f
            WHERE NOT EXISTS (
                SELECT 1 FROM held h
                WHERE h.domain = f.domain AND h.evidence_year = f.year
                  AND h.subject = {subject_sql("f")}
                  AND (h.ships OR NOT {qualifies_own_sql("f")})
            )
            RETURNING evidence_id, domain, evidence_year, evidence_value, evidence_url,
                      acquisition_method
            """,
            {
                "source_id": source_id,
                "type": spec.evidence_type,
                "method": spec.acquisition_method,
                "file": marker,
            },
        ).to_arrow_table()
        stats["evidence_rows"] = fresh.num_rows
        # candidate-only evidence is provenance; it must never assign a year
        if not spec.is_candidate_only:
            stats["year_rows"], stats["repointed"] = _date_pairs(conn, fresh)
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

    Refuses before touching the store if this source class has no human approval behind it.
    Master-eligible evidence can create a year assignment, and whether a source deserves
    that is a judgement about proof rather than a measurement. Candidate-only evidence
    passes freely: it can never date a year.
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
