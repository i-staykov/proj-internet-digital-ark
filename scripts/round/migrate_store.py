"""Stage A rebuilds the store without his superseded rows and our duplicate rows, then swaps;
`deltas` gives every line two exports differ by its reason.

    caffeinate -i uv run python scripts/round/migrate_store.py stage-a --rehearse 1
    caffeinate -i uv run python scripts/round/migrate_store.py stage-a --run
    caffeinate -i uv run python scripts/round/migrate_store.py stage-a --swap
    caffeinate -i uv run python scripts/round/migrate_store.py stage-a --rollback
    uv run python scripts/round/migrate_store.py deltas BEFORE AFTER [--store DB] [--out CSV]

`evidence` keeps every row of his current release; one row per pair only his older releases
hold, the one `domain_year` cites or else the highest id; and of ours every row a record cites,
every row the provenance export re-points to, and the lowest id per (domain, subject, year,
type). A `domain_year` row citing an older release cites the current one instead. Every other
table is copied whole, ids and timestamps included.

`--run` writes `data/ark.stage_a.duckdb` beside the store, which it only ever opens read-only,
exports both into `data/migrate/stage_a/` and writes `report.json` there. `--swap` moves the
store to `data/ark.duckdb.pre-stage-a.bak` and the new file into its place, only when the report
says `swap_ready`; `--rollback` moves both back and checks the store's sha256. `--rehearse PCT`
runs every step, a swap and a rollback included, on the `hash(domain) % 100 < PCT` sample under
`data/migrate/stage_a/sample/`, and never writes the live store.

`deltas` diffs two `output/netnew` folders, and the `candidate_unverified.txt` beside each, by
`LC_ALL=C comm`, and classes each changed line from the store, read-only, and his held sets. It
writes `data/migrate/stage_b/deltas.csv`, prices each reason with his calculator into
`deltas.json` beside it, and exits 0 only when no line is unexplained.
"""

from __future__ import annotations

import argparse
import csv
import filecmp
import hashlib
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

import duckdb  # noqa: E402

from ark import held  # noqa: E402
from ark.baseline import CURRENT_BASELINE_MARKER, baseline_dir, calculator_path  # noqa: E402
from ark.checks import collect_checks, format_checks  # noqa: E402
from ark.db import connect_read_only_patiently, init_db  # noqa: E402
from ark.evidence_types import (  # noqa: E402
    ALL_TYPES,
    CANDIDATE_ONLY_TYPES,
    HIS_TYPE,
    exact_host_sql,
    qualifies_sql,
    web_evidence_exists,
    web_evidence_sql,
)
from ark.export import ATTESTED_NAME, CANDIDATES_PATH, STAMP_NAME, export_all  # noqa: E402
from ark.ingest import YEARS  # noqa: E402
from ark.metrics import _TABLE as METRICS_TABLE  # noqa: E402
from ark.provenance import SHIPPED  # noqa: E402

GIB = 1024**3
EXPECTED_MARKER = "merged260922"
# The live store's figures, which only `--run` is held to.
EXPECTED = {
    "current_rows": 62_660_166,
    "domain_year": 62_913_751,
    "repointed_at_most": 54_537_287,
    "ours_dropped": 12_285_321,
}
REFERENCE_MEMORY, CENSUS_MEMORY = "28GB", "16GB"
# The new file's indexes stay resident until each table's CHECKPOINT and count against the
# limit: about 9.5 GB for evidence at the live size, which 8GB cannot hold.
BUILD_MEMORY, BUILD_MEMORY_BYTES = "16GB", 16 * 10**9
MAX_BUILD_MINUTES, MAX_BUILD_RSS = 114, 24 * 10**9
# **Rows per INSERT, and it is a memory number, not a speed one.** `evidence` carries a PRIMARY
# KEY and a FOREIGN KEY on `domain`, so every inserted row costs an ART lookup and DuckDB holds a
# statement's index work until it commits: one unbatched insert of 2.67M rows cost 13 GiB and left
# the index unopenable for writing. Batched, the peak is bounded by this number, not by the table.
BATCH_ROWS = 2_000_000
# Every table a store holds, in foreign-key order. The census refuses a store with any other.
TABLES = (
    "source",
    "domain",
    "evidence",
    "domain_year",
    "hostname_year",
    "domain_language",
    "ingested_file",
    "run_metrics",
    "prior_merge_stats",
)
# What the two exports must match byte for byte. `source_contribution.csv` is compared by
# source with the columns the collapse moves masked.
COMPARED = ("netnew", "reports/year_growth.csv", "candidate_unverified.txt")
MASKED = ("evidence_rows", "domains_touched", "evidence_type")

HIS = f"evidence_type = '{HIS_TYPE}'"
OURS = f"evidence_type <> '{HIS_TYPE}'"
# The subject of a row: the last token of its value when that names the domain or a host under
# it, else the domain. Case is kept, so ISC hosts that differ only in case stay two rows.
_LAST_WORD = "regexp_extract(evidence_value, '([^ ]+)$', 1)"
SUBJECT = (
    f"CASE WHEN lower({_LAST_WORD}) = domain OR ends_with(lower({_LAST_WORD}), '.' || domain) "
    f"THEN {_LAST_WORD} ELSE domain END"
)


class Refused(Exception):
    """A precondition failed, so the step wrote nothing."""


@dataclass(frozen=True)
class Stage:
    store: Path  # the file being replaced, opened read-only until the swap
    new: Path
    bak: Path
    work: Path
    superseded: Path  # the orphan pairs, one row each, for their withdrawal
    baseline: Path  # his release, which both exports diff against
    temp: Path
    marker: str = CURRENT_BASELINE_MARKER
    live: bool = False  # held to EXPECTED
    floor_gib: int = 50
    footprint_gib: int = 30

    @classmethod
    def at(cls, root: Path) -> Stage:
        data = root / "data"
        return cls(
            store=data / "ark.duckdb",
            new=data / "ark.stage_a.duckdb",
            bak=data / "ark.duckdb.pre-stage-a.bak",
            work=data / "migrate/stage_a",
            superseded=data / "reports/his_superseded_only.csv",
            baseline=(root / baseline_dir()).resolve(),
            temp=data / "duckdb_tmp",
            live=True,
        )

    def sample(self) -> Stage:
        work = self.work / "sample"
        return replace(
            self,
            store=work / "ark.duckdb",
            new=work / "ark.stage_a.duckdb",
            bak=work / "ark.duckdb.pre-stage-a.bak",
            work=work,
            superseded=work / "his_superseded_only.csv",
            live=False,
            floor_gib=0,
            footprint_gib=0,
        )

    def record(self, name: str) -> Path:
        return self.work / f"{name}.json"

    def save(self) -> dict:
        return {k: str(v) if isinstance(v, Path) else v for k, v in vars(self).items()}

    @classmethod
    def load(cls, saved: dict) -> Stage:
        paths = {"store", "new", "bak", "work", "superseded", "baseline", "temp"}
        return cls(**{k: Path(v) if k in paths else v for k, v in saved.items()})


def write(path: Path, data: dict) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    return data


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    with path.open("rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def wal_files(path: Path) -> list[Path]:
    return sorted(path.parent.glob(path.name + ".wal*"))


def remove(path: Path) -> None:
    for each in (path, *wal_files(path)):
        each.unlink(missing_ok=True)


def one(conn: duckdb.DuckDBPyConnection, sql: str, params: list | None = None):
    return conn.execute(sql, params or []).fetchone()[0]


def loaded_jobs() -> list[str]:
    try:
        done = subprocess.run(["launchctl", "list"], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return []
    return [line.strip() for line in done.stdout.splitlines() if "com.ark" in line]


def holders(path: Path) -> list[str]:
    """Processes holding `path`. lsof prints nothing and exits 1 when there are none."""
    try:
        done = subprocess.run(["lsof", "--", str(path)], capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise Refused("lsof is missing, so no holder of the store can be ruled out") from exc
    return done.stdout.splitlines()[1:]


def quiet(*paths: Path) -> None:
    """Refuse while a launchd job is loaded, or anything holds or is writing one of `paths`."""
    if jobs := loaded_jobs():
        raise Refused(f"a launchd job is loaded: {jobs[0]}")
    for path in paths:
        if found := holders(path):
            raise Refused(f"{path.name} is open: {found[0]}")
        if wal := wal_files(path):
            raise Refused(f"{wal[0].name} exists")


def newest_credited_day() -> date | None:
    rounds = read(REPO / "data/baseline.json")["rounds"]
    days = [date.fromisoformat(r["date"]) for r in rounds if r.get("awarded_percent")]
    return max(days, default=None)


def settings(conn: duckdb.DuckDBPyConnection, stage: Stage, memory: str) -> None:
    """Set on each connection, since `ark.db` binds its own limit when it is imported."""
    stage.temp.mkdir(parents=True, exist_ok=True)
    for statement in (
        f"SET memory_limit='{memory}'",
        "SET threads=2",
        f"SET temp_directory='{stage.temp}'",
        f"SET max_temp_directory_size='{max(stage.footprint_gib, 4)}GiB'",
    ):
        conn.execute(statement)


def current_markers(stage: Stage) -> list[str]:
    return [f"{stage.marker}/{year}.txt" for year in YEARS]


def sql_list(values: list[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def preflight(stage: Stage) -> dict:
    quiet(stage.store)
    if stage.bak.exists():
        raise Refused(f"{stage.bak.name} exists: the store was swapped, so roll back first")
    if stage.live and CURRENT_BASELINE_MARKER != EXPECTED_MARKER:
        raise Refused(f"the baseline is {CURRENT_BASELINE_MARKER}, not {EXPECTED_MARKER}")
    if stage.marker != CURRENT_BASELINE_MARKER:
        raise Refused(f"the current release is {CURRENT_BASELINE_MARKER}, not {stage.marker}")
    missing = [y for y in YEARS if not (stage.baseline / f"{y}.txt").is_file()]
    if missing:
        raise Refused(f"his release lacks the files for {missing} under {stage.baseline}")
    st = stage.store.stat()
    need = (stage.floor_gib + stage.footprint_gib) * GIB + st.st_size
    free = shutil.disk_usage(stage.store.parent).free
    if free < need:
        raise Refused(f"{free / GIB:.1f} GiB free, the migration needs {need / GIB:.1f}")
    # prune.py frees the backup on a credited round dated after its mtime, which the move keeps,
    # so a store last written before the newest one would lose its backup to the next prune
    newest = newest_credited_day()
    if newest and datetime.fromtimestamp(st.st_mtime, UTC).date() <= newest:
        raise Refused(f"the store was last written before the round credited on {newest}")
    return {
        "store": str(stage.store),
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "inode": st.st_ino,
        "sha256": sha256(stage.store),
        "free_gib": round(free / GIB, 1),
        "need_gib": round(need / GIB, 1),
    }


def export_into(conn: duckdb.DuckDBPyConnection, out: Path, stage: Stage) -> list[dict]:
    """What `ark export` writes, every destination under `out`, then the integrity checks on
    those files."""
    shutil.rmtree(out, ignore_errors=True)
    export_all(
        conn,
        netnew_dir=out / "netnew",
        candidates_path=out / "candidate_unverified.txt",
        report_dir=out / "reports",
        provenance_dir=out / "provenance",
        baseline=stage.baseline,
    )
    return collect_checks(conn, out / "netnew", baseline=stage.baseline)


def reference(stage: Stage) -> dict:
    conn = connect_read_only_patiently(stage.store)
    try:
        settings(conn, stage, REFERENCE_MEMORY)
        checks = export_into(conn, stage.work / "before", stage)
    finally:
        conn.close()
    return {"checks": checks}


def next_ids(conn: duckdb.DuckDBPyConnection, catalog: str) -> dict[str, int]:
    """One past every id the old sequences issued, the ids of deleted rows included."""
    issued = dict(
        conn.execute(
            "SELECT sequence_name, coalesce(last_value, 0) FROM duckdb_sequences() "
            f"WHERE database_name = '{catalog}'"
        ).fetchall()
    )
    top = {
        "evidence_seq": one(conn, f"SELECT coalesce(max(evidence_id), 0) FROM {catalog}.evidence"),
        "source_seq": one(conn, f"SELECT coalesce(max(source_id), 0) FROM {catalog}.source"),
    }
    return {name: max(top[name], issued.get(name, 0)) + 1 for name in top}


def old_tables(conn: duckdb.DuckDBPyConnection) -> set[str]:
    rows = conn.execute("SELECT table_name FROM duckdb_tables() WHERE database_name = 'old'")
    return {r[0] for r in rows.fetchall()}


def census(stage: Stage) -> dict:
    db = stage.work / "census.duckdb"
    remove(db)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db))
    try:
        settings(conn, stage, CENSUS_MEMORY)
        conn.execute(f"ATTACH '{stage.store}' AS old (READ_ONLY)")
        return _census(conn, stage)
    finally:
        conn.close()


def _census(conn: duckdb.DuckDBPyConnection, stage: Stage) -> dict:
    tables = old_tables(conn)
    if unknown := tables - set(TABLES):
        raise Refused(f"the store holds tables this migration does not copy: {sorted(unknown)}")
    types = {
        r[0] for r in conn.execute("SELECT DISTINCT evidence_type FROM old.evidence").fetchall()
    }
    if unknown := types - set(ALL_TYPES):
        raise Refused(f"evidence types the schema refuses: {sorted(unknown)}")
    cur = sql_list(current_markers(stage))
    markers = dict(
        conn.execute(
            f"SELECT evidence_value, count(*) FROM old.evidence WHERE {HIS} GROUP BY 1 ORDER BY 1"
        ).fetchall()
    )
    current = {m: markers.get(m, 0) for m in current_markers(stage)}
    if not all(current.values()):
        raise Refused(f"a file of the current release holds no rows: {current}")
    current_rows = sum(current.values())
    if stage.live and current_rows != EXPECTED["current_rows"]:
        raise Refused(f"{current_rows:,} current-release rows, not {EXPECTED['current_rows']:,}")

    conn.execute(f"""
        CREATE TABLE cur AS SELECT evidence_id, domain, evidence_year
        FROM old.evidence WHERE {HIS} AND evidence_value IN ({cur})
    """)
    pairs = one(conn, "SELECT count(*) FROM (SELECT DISTINCT domain, evidence_year FROM cur)")
    if pairs != current_rows:
        raise Refused("the current release holds a pair twice")
    # a pair only his older releases hold keeps the row domain_year cites, else the highest id
    conn.execute(f"""
        CREATE TABLE orphan AS
        WITH only_old AS (
            SELECT o.evidence_id, o.domain, o.evidence_year FROM old.evidence o
            WHERE o.{HIS} AND o.evidence_value NOT IN ({cur})
              AND NOT EXISTS (SELECT 1 FROM cur c
                              WHERE c.domain = o.domain AND c.evidence_year = o.evidence_year)
        )
        SELECT p.domain, p.evidence_year,
               coalesce(max(p.evidence_id) FILTER (WHERE p.evidence_id = dy.evidence_id),
                        max(p.evidence_id)) AS evidence_id,
               coalesce(bool_or(p.evidence_id = dy.evidence_id), false) AS cited
        FROM only_old p
        LEFT JOIN old.domain_year dy
          ON dy.domain = p.domain AND dy.assigned_year = p.evidence_year
        GROUP BY 1, 2
    """)
    his_pairs = one(
        conn,
        f"SELECT count(*) FROM (SELECT DISTINCT domain, evidence_year FROM old.evidence "
        f"WHERE {HIS})",
    )
    orphan_pairs = one(conn, "SELECT count(*) FROM orphan")
    if his_pairs != current_rows + orphan_pairs:
        raise Refused(f"{his_pairs:,} pairs of his, not {current_rows:,} + {orphan_pairs:,}")

    conn.execute(f"""
        CREATE TABLE ours_lowest AS SELECT min(evidence_id) AS evidence_id FROM old.evidence
        WHERE {OURS} GROUP BY domain, {SUBJECT}, evidence_year, evidence_type
    """)
    # hostname_year cites only ours today; its ids are kept whatever they are, so none dangles
    conn.execute(f"""
        CREATE TABLE ours_cited AS
        SELECT dy.evidence_id FROM old.domain_year dy
        JOIN old.evidence e ON e.evidence_id = dy.evidence_id WHERE e.{OURS}
        UNION SELECT evidence_id FROM old.hostname_year
    """)
    # the rows `write_provenance` re-points domain_year to, by its own query
    conn.execute("USE old")
    conn.execute(f"""
        CREATE TABLE census.main.ours_repoint AS
        SELECT DISTINCT evidence_id FROM ({SHIPPED["domain_year"]})
    """)
    conn.execute("USE census")
    conn.execute("""
        CREATE TABLE keep AS SELECT evidence_id FROM (
            SELECT evidence_id FROM cur UNION SELECT evidence_id FROM orphan
            UNION SELECT evidence_id FROM ours_lowest UNION SELECT evidence_id FROM ours_cited
            UNION SELECT evidence_id FROM ours_repoint
        ) ORDER BY evidence_id
    """)
    # the join stays a pure equi-join, so it hashes; a condition on one side alone in its ON
    # turns it into a nested loop over 62.9M x 62.7M rows
    conn.execute(f"""
        CREATE TABLE dy_new AS
        SELECT d.rid, d.domain, d.assigned_year,
               CASE WHEN d.older AND c.evidence_id IS NOT NULL
                    THEN c.evidence_id ELSE d.evidence_id END AS evidence_id,
               d.verified_at, d.older AND c.evidence_id IS NOT NULL AS repointed
        FROM (
            SELECT dy.rowid AS rid, dy.domain, dy.assigned_year, dy.evidence_id, dy.verified_at,
                   e.{HIS} AND e.evidence_value NOT IN ({cur}) AS older
            FROM old.domain_year dy JOIN old.evidence e ON e.evidence_id = dy.evidence_id
        ) d
        LEFT JOIN cur c ON c.domain = d.domain AND c.evidence_year = d.assigned_year
        ORDER BY d.rid
    """)
    stage.superseded.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(f"""
        COPY (SELECT o.domain, o.evidence_year AS year, e.evidence_value AS marker,
                     o.evidence_id, o.cited
              FROM orphan o JOIN old.evidence e ON e.evidence_id = o.evidence_id
              ORDER BY o.domain, o.evidence_year)
        TO '{stage.superseded}' (HEADER true)
    """)
    keep = one(conn, "SELECT count(*) FROM keep")
    his_keep = one(
        conn, f"SELECT count(*) FROM keep k JOIN old.evidence e USING (evidence_id) WHERE e.{HIS}"
    )
    ours_rows = one(conn, f"SELECT count(*) FROM old.evidence WHERE {OURS}")
    figures = {
        "domain_year": one(conn, "SELECT count(*) FROM dy_new"),
        "repointed": one(conn, "SELECT count(*) FROM dy_new WHERE repointed"),
        "ours_dropped": ours_rows - (keep - his_keep),
    }
    if stage.live:
        # checked here, before the build, so a miss costs minutes rather than hours
        if figures["domain_year"] != EXPECTED["domain_year"]:
            raise Refused(f"{figures['domain_year']:,} domain_year rows, not the live count")
        if figures["repointed"] > EXPECTED["repointed_at_most"]:
            raise Refused(f"{figures['repointed']:,} re-pointed, more than every row of his")
    return {
        "tables": sorted(tables),
        "markers": markers,
        "current_rows": current_rows,
        "orphan_pairs": orphan_pairs,
        "orphan_cited": one(conn, "SELECT count(*) FROM orphan WHERE cited"),
        "his_pairs": his_pairs,
        "his_rows_before": sum(markers.values()),
        "his_rows_after": his_keep,
        "ours_rows": ours_rows,
        "ours_lowest": one(conn, "SELECT count(*) FROM ours_lowest"),
        "ours_cited": one(conn, "SELECT count(*) FROM ours_cited"),
        "ours_repoint": one(conn, "SELECT count(*) FROM ours_repoint"),
        "ours_kept": keep - his_keep,
        "keep": keep,
        **figures,
        # the issue's figure scaled a repeat rate measured on an older snapshot; reported only
        "ours_dropped_vs_issue": figures["ours_dropped"] - EXPECTED["ours_dropped"],
        "next_ids": next_ids(conn, "old"),
    }


def art_bytes(conn: duckdb.DuckDBPyConnection) -> int:
    return one(
        conn,
        "SELECT coalesce(sum(memory_usage_bytes), 0) FROM duckdb_memory() WHERE tag = 'ART_INDEX'",
    )


def windows(top: int | None, step: int = BATCH_ROWS) -> list[list[int]]:
    """Half-open windows [lo, lo + step) over 0..top."""
    return [] if top is None else [[lo, lo + step] for lo in range(0, top + 1, step)]


def write_tables(conn: duckdb.DuckDBPyConnection, next_id: dict, fills: dict) -> dict:
    """Fill the connection's own new file from the attached `old`, in foreign-key order, with a
    CHECKPOINT after each table. `fills` gives a table its SELECT and the parameter windows it
    runs over, one transaction each, so no statement holds more than a batch of index work; a
    table it leaves out is copied whole."""
    for name, start in next_id.items():
        conn.execute(f"CREATE SEQUENCE {name} START WITH {int(start)}")
    init_db(conn)
    conn.execute(METRICS_TABLE)
    # no automatic checkpoint inside a table, so its indexes are resident until the CHECKPOINT
    # below at every size, and what duckdb_memory() shows is what the live build will hold
    conn.execute("SET checkpoint_threshold='100GB'")
    present = old_tables(conn)
    art, seconds = {}, {}
    for table in (t for t in TABLES if t in present):
        started = time.monotonic()
        if table == "prior_merge_stats":
            # its schema is whatever read_csv_auto inferred from his CSV, so it is not in init_db
            conn.execute("CREATE TABLE prior_merge_stats AS SELECT * FROM old.prior_merge_stats")
        elif table in fills:
            select, params = fills[table]
            for window in params:
                conn.execute(f"INSERT INTO {table} BY NAME {select}", window)
                art[table] = max(art.get(table, 0), art_bytes(conn))
        else:
            conn.execute(f"INSERT INTO {table} BY NAME SELECT * FROM old.{table}")
        art[table] = max(art.get(table, 0), art_bytes(conn))
        conn.execute("CHECKPOINT")
        seconds[table] = round(time.monotonic() - started, 1)
    return {"art_bytes": art, "art_peak_bytes": max(art.values(), default=0), "seconds": seconds}


def by_rowid(conn: duckdb.DuckDBPyConnection, table: str, where: str = "true") -> tuple:
    select = f"SELECT * FROM old.{table} WHERE rowid >= ? AND rowid < ? AND {where} ORDER BY rowid"
    return select, windows(one(conn, f"SELECT max(rowid) FROM old.{table}"))


def build(stage: Stage) -> dict:
    plan = read(stage.record("census"))
    remove(stage.new)
    conn = duckdb.connect(str(stage.new))
    try:
        settings(conn, stage, BUILD_MEMORY)
        conn.execute(f"ATTACH '{stage.store}' AS old (READ_ONLY)")
        conn.execute(f"ATTACH '{stage.work / 'census.duckdb'}' AS plan (READ_ONLY)")
        # evidence in windows of BATCH_ROWS kept ids, read by id range so the old file's zone
        # maps skip everything outside it
        cuts = [
            r[0]
            for r in conn.execute(f"""
                SELECT evidence_id FROM (
                    SELECT evidence_id, row_number() OVER (ORDER BY evidence_id) AS n
                    FROM plan.keep) WHERE n % {BATCH_ROWS} = 0 ORDER BY 1
            """).fetchall()
        ]
        top = one(conn, "SELECT max(evidence_id) FROM plan.keep")
        bounds = [-1, *cuts] + ([top] if top is not None and (not cuts or top > cuts[-1]) else [])
        fills = {
            "domain": by_rowid(conn, "domain"),
            "evidence": (
                "SELECT e.* FROM old.evidence e WHERE e.evidence_id > ? AND e.evidence_id <= ? "
                "AND e.evidence_id IN (SELECT evidence_id FROM plan.keep "
                "WHERE evidence_id > ? AND evidence_id <= ?) ORDER BY e.evidence_id",
                [[lo, hi, lo, hi] for lo, hi in zip(bounds, bounds[1:], strict=False)],
            ),
            "domain_year": (
                "SELECT domain, assigned_year, evidence_id, verified_at FROM plan.dy_new "
                "WHERE rid >= ? AND rid < ? ORDER BY rid",
                windows(one(conn, "SELECT max(rid) FROM plan.dy_new")),
            ),
            "hostname_year": by_rowid(conn, "hostname_year"),
        }
        done = write_tables(conn, plan["next_ids"], fills)
    finally:
        conn.close()
    if wal := wal_files(stage.new):
        raise Refused(f"{wal[0].name} was left behind")
    return done | {"size": stage.new.stat().st_size}


def make_sample(live: Stage, stage: Stage, pct: int) -> dict:
    """A copy of the live store holding only the `hash(domain) % 100 < pct` sample, so the
    rehearsal runs every step and its swap on files of the same shape."""
    shutil.rmtree(stage.work, ignore_errors=True)
    stage.work.mkdir(parents=True)
    conn = duckdb.connect(str(stage.store))
    try:
        settings(conn, live, BUILD_MEMORY)
        conn.execute(f"ATTACH '{live.store}' AS old (READ_ONLY)")
        sampled = f"hash(domain) % 100 < {int(pct)}"
        top = one(conn, "SELECT max(evidence_id) FROM old.evidence")
        fills = {
            "domain": by_rowid(conn, "domain", sampled),
            "evidence": (
                "SELECT * FROM old.evidence WHERE evidence_id >= ? AND evidence_id < ? "
                f"AND {sampled} ORDER BY evidence_id",
                windows(top, BATCH_ROWS * 50),
            ),
            "domain_year": by_rowid(conn, "domain_year", sampled),
            "hostname_year": by_rowid(
                conn, "hostname_year", f"hash(parent_domain) % 100 < {int(pct)}"
            ),
            "domain_language": (f"SELECT * FROM old.domain_language WHERE {sampled}", [[]]),
        }
        done = write_tables(conn, next_ids(conn, "old"), fills)
    finally:
        conn.close()
    return done | {"size": stage.store.stat().st_size, "pct": pct}


def digest(conn: duckdb.DuckDBPyConnection, relation: str, columns: list[str]) -> list:
    cols = ", ".join(f'"{c}"' for c in columns)
    return list(
        conn.execute(
            f"SELECT count(*), coalesce(sum(hash({cols})::HUGEINT), 0) FROM {relation}"
        ).fetchone()
    )


def columns(conn: duckdb.DuckDBPyConnection, catalog: str, table: str) -> list[str]:
    rows = conn.execute(
        "SELECT column_name FROM duckdb_columns() WHERE database_name = ? AND table_name = ? "
        "ORDER BY column_name",
        [catalog, table],
    )
    return [r[0] for r in rows.fetchall()]


def files_under(root: Path) -> dict[str, str]:
    out = {}
    for rel in COMPARED:
        path = root / rel
        # The export stamp carries its write time, so it differs between any two exports.
        found = (
            sorted(p for p in path.rglob("*") if p.is_file() and p.name != STAMP_NAME)
            if path.is_dir()
            else [path]
        )
        for each in found:
            out[str(each.relative_to(root))] = sha256(each) if each.exists() else "missing"
    return out


def contribution(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return {
            row["source"]: {k: v for k, v in row.items() if k not in MASKED}
            for row in csv.DictReader(fh)
        }


def verify(stage: Stage) -> dict:
    plan, before = read(stage.record("census")), read(stage.record("reference"))
    conn = duckdb.connect()
    try:
        settings(conn, stage, REFERENCE_MEMORY)
        conn.execute(f"ATTACH '{stage.new}' AS fresh (READ_ONLY)")
        conn.execute(f"ATTACH '{stage.store}' AS old (READ_ONLY)")
        conn.execute(f"ATTACH '{stage.work / 'census.duckdb'}' AS plan (READ_ONLY)")
        conn.execute("USE fresh")
        results = _verify(conn, stage, plan, before)
    finally:
        conn.close()
    recorded = read(stage.record("preflight"))["sha256"]
    results["old_file_unchanged"] = {"ok": sha256(stage.store) == recorded}
    return {
        "checks": results,
        "swap_ready": all(r["ok"] for r in results.values()),
        "new_sha256": sha256(stage.new),
        "new_size": stage.new.stat().st_size,
    }


def _verify(conn: duckdb.DuckDBPyConnection, stage: Stage, plan: dict, before: dict) -> dict:
    out: dict[str, dict] = {}

    def check(name: str, ok: bool, **detail) -> None:
        out[name] = {"ok": bool(ok), **detail}

    tables = {
        r[0]
        for r in conn.execute(
            "SELECT table_name FROM duckdb_tables() WHERE database_name = 'fresh'"
        ).fetchall()
    }
    # the schema may add tables the old file lacked, never drop one it held
    check("tables", set(plan["tables"]) <= tables <= set(TABLES), fresh=sorted(tables))
    for table in (t for t in TABLES if t not in ("evidence", "domain_year")):
        if table in plan["tables"]:
            cols = columns(conn, "old", table)
            a, b = digest(conn, f"fresh.{table}", cols), digest(conn, f"old.{table}", cols)
            check(f"{table}_unchanged", a == b, rows=a[0])
    ev = columns(conn, "old", "evidence")
    kept = "(SELECT e.* FROM old.evidence e SEMI JOIN plan.keep k ON k.evidence_id = e.evidence_id)"
    a, b = digest(conn, "fresh.evidence", ev), digest(conn, kept, ev)
    on = "ON k.evidence_id = e.evidence_id"
    stray = one(conn, f"SELECT count(*) FROM fresh.evidence e ANTI JOIN plan.keep k {on}")
    lost = one(conn, f"SELECT count(*) FROM plan.keep k ANTI JOIN fresh.evidence e {on}")
    check(
        "evidence_is_the_keep_set",
        a == b and not stray and not lost and a[0] == plan["keep"],
        rows=a[0],
        stray=stray,
        lost=lost,
    )
    same = ["domain", "assigned_year", "verified_at"]
    check(
        "domain_year_pairs_unchanged",
        digest(conn, "fresh.domain_year", same) == digest(conn, "old.domain_year", same),
        rows=one(conn, "SELECT count(*) FROM fresh.domain_year"),
    )
    cited = ["domain", "assigned_year", "evidence_id", "verified_at"]
    check(
        "domain_year_cites_the_plan",
        digest(conn, "fresh.domain_year", cited) == digest(conn, "plan.dy_new", cited),
        repointed=plan["repointed"],
    )
    dangling = one(
        conn,
        """
        SELECT (SELECT count(*) FROM fresh.domain_year d
                ANTI JOIN fresh.evidence e ON e.evidence_id = d.evidence_id)
             + (SELECT count(*) FROM fresh.hostname_year h
                ANTI JOIN fresh.evidence e ON e.evidence_id = h.evidence_id)
    """,
    )
    check("no_dangling_id", dangling == 0, dangling=dangling)
    his_rows = one(conn, f"SELECT count(*) FROM fresh.evidence WHERE {HIS}")
    check("his_rows", his_rows == plan["current_rows"] + plan["orphan_pairs"], rows=his_rows)
    moved = one(
        conn,
        f"""
        SELECT count(*) FROM (
            (SELECT DISTINCT domain, evidence_year FROM old.evidence WHERE {HIS}
             EXCEPT SELECT DISTINCT domain, evidence_year FROM fresh.evidence WHERE {HIS})
            UNION ALL
            (SELECT DISTINCT domain, evidence_year FROM fresh.evidence WHERE {HIS}
             EXCEPT SELECT DISTINCT domain, evidence_year FROM old.evidence WHERE {HIS}))
    """,
    )
    check("his_pairs_unchanged", moved == 0, differ=moved, pairs=plan["his_pairs"])
    starts = dict(
        conn.execute(
            "SELECT sequence_name, start_value FROM duckdb_sequences() "
            "WHERE database_name = 'fresh'"
        ).fetchall()
    )
    check("sequences_past_the_old_ids", starts == plan["next_ids"], starts=starts)

    after = export_into(conn, stage.work / "after", stage)
    failed = [
        r["name"] for r in after if not r["ok"] or "no exported files" in r.get("skipped", "")
    ]
    check(
        "integrity_checks",
        not failed and after == before["checks"],
        failed=failed,
        report=format_checks(after),
    )
    old_files, new_files = files_under(stage.work / "before"), files_under(stage.work / "after")
    differ = sorted(
        k
        for k in old_files.keys() | new_files.keys()
        if old_files.get(k) != new_files.get(k) or old_files.get(k) == "missing"
    )
    check("exports_byte_identical", not differ, files=len(old_files), differ=differ)
    report = "reports/source_contribution.csv"
    was, now = (contribution(stage.work / side / report) for side in ("before", "after"))
    check(
        "source_contribution_masked",
        was == now,
        differ=sorted(s for s in was.keys() | now.keys() if was.get(s) != now.get(s)),
    )
    return out


def swap(stage: Stage) -> dict:
    report = read(stage.record("report"))
    if not report.get("swap_ready"):
        raise Refused(f"{stage.record('report')} does not say swap_ready")
    quiet(stage.store, stage.new)
    if stage.bak.exists():
        raise Refused(f"{stage.bak.name} already exists")
    if sha256(stage.store) != read(stage.record("preflight"))["sha256"]:
        raise Refused("the store changed after the preflight")
    if sha256(stage.new) != report["verify"]["new_sha256"]:
        raise Refused("the new file changed after it was verified")
    os.rename(stage.store, stage.bak)
    os.rename(stage.new, stage.store)
    return {"swapped": True, "bak": str(stage.bak)}


def rollback(stage: Stage) -> dict:
    if not stage.bak.exists():
        raise Refused(f"{stage.bak.name} is missing, so there is nothing to roll back to")
    if stage.store.exists():
        quiet(stage.store)
        if stage.new.exists():
            raise Refused(f"{stage.new.name} is in the way")
        os.rename(stage.store, stage.new)
    os.rename(stage.bak, stage.store)
    return {"rollback_restored": sha256(stage.store) == read(stage.record("preflight"))["sha256"]}


STEPS = {
    "preflight": preflight,
    "reference": reference,
    "census": census,
    "build": build,
    "verify": verify,
    "swap": swap,
    "rollback": rollback,
}


def peak_rss(usage) -> int:
    """ru_maxrss is bytes on macOS and KiB on Linux."""
    return usage.ru_maxrss * (1 if sys.platform == "darwin" else 1024)


def step(name: str, stage: Stage, isolate: bool) -> dict:
    """Run one step and write its record. Isolated, it runs in a child process of its own, so
    its peak RSS is its own and its memory goes back to the machine when it ends."""
    started = time.monotonic()
    if isolate:
        write(stage.work / "stage.json", stage.save())
        child = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "stage-a",
                "--step",
                name,
                "--stage",
                str(stage.work / "stage.json"),
            ]
        )
        _, status, usage = os.wait4(child.pid, 0)
        child.returncode = code = os.waitstatus_to_exitcode(status)
        rss = peak_rss(usage)
    else:
        write(stage.record(name), STEPS[name](stage))
        rss, code = peak_rss(resource.getrusage(resource.RUSAGE_SELF)), 0
    return {
        "step": name,
        "seconds": round(time.monotonic() - started, 1),
        "peak_rss_bytes": rss,
        "exit": code,
    }


def run(stage: Stage, isolate: bool, names: tuple[str, ...]) -> tuple[list, bool]:
    done = []
    for name in names:
        done.append(step(name, stage, isolate))
        if done[-1]["exit"]:
            return done, False
    return done, True


RUN = ("preflight", "reference", "census", "build", "verify")


def clear(stage: Stage) -> None:
    """What an earlier attempt left, so a rerun starts clean and its free space counts right."""
    if stage.bak.exists():
        raise Refused(f"{stage.bak.name} exists: the store was swapped, so roll back first")
    for path in (stage.new, stage.work / "census.duckdb"):
        remove(path)
    for name in (*RUN, "report", "swap", "rollback"):
        stage.record(name).unlink(missing_ok=True)
    for folder in ("before", "after"):
        shutil.rmtree(stage.work / folder, ignore_errors=True)


def stage_a_run(stage: Stage, isolate: bool = False) -> dict:
    clear(stage)
    steps, ok = run(stage, isolate, RUN)
    report = {"mode": "run", "steps": steps, "swap_ready": False}
    report |= {n: read(stage.record(n)) for n in RUN[2:] if stage.record(n).exists()}
    if ok:
        report["swap_ready"] = report["verify"]["swap_ready"]
    return write(stage.record("report"), report)


def stage_a_rehearse(live: Stage, pct: int, isolate: bool = False) -> dict:
    stage = live.sample()
    started = time.monotonic()
    pre = preflight(live)
    sample = make_sample(live, stage, pct)
    write(stage.work / "live_preflight.json", pre)
    write(stage.work / "sample_store.json", sample | {"seconds": round(time.monotonic() - started)})
    report = stage_a_run(stage, isolate)
    report |= {"mode": f"rehearse {pct}", "rollback_restored": False}
    if report["swap_ready"]:
        steps, ok = run(stage, isolate, ("swap", "rollback"))
        report["steps"] += steps
        report["rollback_restored"] = ok and read(stage.record("rollback"))["rollback_restored"]
    report["live_store_unchanged"] = sha256(live.store) == pre["sha256"]
    timed = {s["step"]: s for s in report["steps"] if not s["exit"]}
    if "build" in timed and "build" in report:
        # the census and the build scale with the store; both exports load his whole release
        scale = 100 / pct
        build, art = timed["build"], report["build"]["art_peak_bytes"]
        report["projection"] = {
            "build_minutes": round(build["seconds"] / 60 * scale, 1),
            "build_peak_rss_bytes": round(build["peak_rss_bytes"] + art * (scale - 1)),
            "build_index_bytes": round(art * scale),
            "census_minutes": round(timed["census"]["seconds"] / 60 * scale, 1),
            "measured_build_seconds": build["seconds"],
            "measured_build_peak_rss_bytes": build["peak_rss_bytes"],
            "measured_index_peak_bytes": art,
            "planned_minutes": [37, 114],
            "planned_rss_gb": [20.5, 28],
        }
        report["thresholds_hold"] = (
            report["projection"]["build_minutes"] <= MAX_BUILD_MINUTES
            and report["projection"]["build_peak_rss_bytes"] <= MAX_BUILD_RSS
            and report["projection"]["build_index_bytes"] <= BUILD_MEMORY_BYTES
        )
    for path in (stage.store, stage.new, stage.bak, stage.work / "census.duckdb"):
        remove(path)
    return write(stage.record("report"), report)


# `deltas`. His rows are named here as in stage A: that one of them no longer holds a pair is
# often why its line moved.
DELTAS_MEMORY = "8GB"
SKIPPED = ("export_stamp.json", "SHA256SUMS", "SHA256SUMS.stat", "candidates_unparsed.txt")
UNVERIFIED = CANDIDATES_PATH.name  # beside each netnew folder, not in it
PER_YEAR = (
    (re.compile(r"(\d{4})\.txt"), "registrable"),
    (re.compile(r"(\d{4})_hostnames\.txt"), "hostname"),
    (re.compile(r"(\d{4})-ISC\.txt"), "isc"),
)
NAMED = {
    "isc_candidates.txt": "isc",
    "candidate_additions.txt": "candidate",
    "header_candidates.txt": "header",
    ATTESTED_NAME: "attested",
}
# A csv row follows the line its key names: the family, and the file its year picks
FOLLOWS = {
    "evidence_manifest.csv": ("manifest", "{}.txt"),
    "hostnames_evidence_manifest.csv": ("manifest", "{}_hostnames.txt"),
    "isc_survey_provenance.csv": ("provenance", "{}-ISC.txt"),
    "header_candidates_provenance.csv": ("provenance", "header_candidates.txt"),
    "header_candidates_exclusions.csv": ("exclusions", "header_candidates.txt"),
}
CANDIDATE_FAMILIES = ("candidate", "header", "isc", "unverified")
PRICED = ("registrable", "hostname", *CANDIDATE_FAMILIES, "attested")
# What he scores: the annual files and the candidate pool. The other candidate lists are parts
# of the pool, and the attested list is never sent.
CLAIM_FAMILIES = ("registrable", "hostname", "candidate")
_CAND = f"c.family IN ({sql_list(list(CANDIDATE_FAMILIES))})"
_TYPES = sql_list(sorted(CANDIDATE_ONLY_TYPES))
# the rows of ours `held.our_domain_year` may cite
_ELIGIBLE = f"w.evidence_type <> '{HIS_TYPE}' AND w.evidence_type NOT IN ({_TYPES})"
_REG_ADDED = "c.family = 'registrable' AND c.change = 'added'"
_REG_REMOVED = "c.family = 'registrable' AND c.change = 'removed' AND NOT p.cited_his"
_HIS_ONLY = "c.family = 'attested' AND c.change = 'removed' AND p.cited_his AND NOT p.has_o"
# First match wins: (reason, condition, detail) over `chg c` and the facts joined to it
LINE_RULES = (
    ("unexplained", "c.change = 'changed'", "c.row"),
    (
        "unexplained",
        "c.change = 'added' AND c.family IN ('registrable', 'hostname') AND y.name IS NOT NULL",
        "'in his ' || c.year || '.txt'",
    ),
    ("unexplained", f"c.change = 'added' AND {_CAND} AND f.in_his", "'in his files'"),
    (
        "superseded-only",
        f"({_REG_ADDED} AND r.q_value IS NOT NULL OR {_HIS_ONLY}) AND s.marker IS NOT NULL",
        "'his row ' || s.marker || ' only'",
    ),
    (
        "released",
        f"{_REG_ADDED} AND r.his_value IS NOT NULL AND r.q_value IS NOT NULL",
        "'his row ' || r.his_value",
    ),
    (
        "converter roll-up",
        f"{_REG_REMOVED} AND r.q_value IS NULL AND p.cited_method = 'ia_cdx_collapsed_query' "
        "AND regexp_matches(p.cited_value, '^cdx capture [0-9]{4}$')",
        "'cited ' || p.cited_value",
    ),
    (
        "withdrawn",
        f"{_REG_REMOVED} AND r.q_value IS NULL AND NOT r.cited_exact",
        "'cited ' || p.cited_value",
    ),
    (
        "withdrawn",
        "c.family = 'hostname' AND c.change = 'removed' AND h.cited_value IS NOT NULL "
        "AND NOT h.cited_exact",
        "'cited ' || h.cited_value",
    ),
    (
        "candidate",
        f"{_CAND} AND c.change = 'removed' AND f.moved_file IS NOT NULL",
        "'moved to ' || f.moved_file",
    ),
    (
        "candidate",
        f"{_CAND} AND c.change = 'removed' AND f.claim_year IS NOT NULL",
        "'own capture in ' || f.claim_year",
    ),
    (
        "candidate",
        f"{_CAND} AND c.change = 'added' AND (f.web_before AND f.claim_year IS NULL "
        "OR f.host_web_before AND NOT f.host_now)",
        "'years withdrawn'",
    ),
    (
        "candidate",
        f"{_CAND} AND c.change = 'added' AND f.his_named AND f.claim_year IS NULL "
        "AND (c.family = 'candidate' OR NOT f.ody_named)",
        "'his roll-up only'",
    ),
    # our own exact capture dates the pair now, where the row it cited did not qualify
    (
        "re-cited",
        f"{_REG_ADDED} AND r.his_value IS NULL AND r.q_value IS NOT NULL "
        "AND NOT p.cited_his AND NOT r.cited_qualifies",
        "'own capture ' || r.q_value",
    ),
    # a pair only his rows dated leaves the attested list with them
    ("his row only", _HIS_ONLY, "'his row ' || p.cited_value"),
)


def family_of(name: str) -> tuple[str, int | None] | None:
    for pattern, family in PER_YEAR:
        if found := pattern.fullmatch(name):
            return family, int(found[1])
    if name in NAMED:
        return NAMED[name], None
    if name in FOLLOWS:
        return FOLLOWS[name][0], None
    return None


def _case(rules) -> str:
    whens = " ".join(f"WHEN {cond} THEN ['{reason}', {detail}]" for reason, cond, detail in rules)
    return f"CASE {whens} ELSE ['unexplained', c.row] END"


def _same(sides: dict[str, Path]) -> bool:
    return all(p.is_file() for p in sides.values()) and filecmp.cmp(*sides.values(), shallow=False)


def _missing(sides: dict[str, Path]) -> dict:
    gone = [side for side, path in sides.items() if not path.is_file()]
    return {"missing": gone[0]} if gone else {}


def _names(conn, file, family, year, sides, work, found) -> None:
    """`comm -13` and `-23` of one list of names into `chg`, each side checked for order first.
    The added lines are kept in `found`, to be checked against his files."""
    use = {side: path if path.is_file() else work / "empty" for side, path in sides.items()}
    for change, names, against in (
        ("added", use["after"], use["before"]),
        ("removed", use["before"], use["after"]),
    ):
        lines = work / change / file
        if not held.minus(names, against, lines):
            continue
        held.read_names(conn, "_lines", lines)
        if family == "attested":  # `YYYY<TAB>name`, compared as whole lines
            conn.execute(
                "INSERT INTO chg (file, family, year, name, change) SELECT ?, ?, "
                "TRY_CAST(split_part(name, chr(9), 1) AS INTEGER), split_part(name, chr(9), 2), ? "
                "FROM _lines",
                [file, family, change],
            )
        else:
            conn.execute(
                "INSERT INTO chg (file, family, year, name, change) SELECT ?, ?, ?, name, ? "
                "FROM _lines",
                [file, family, year, change],
            )
        if change == "added":
            found.setdefault((family, year), []).append(lines)


def _rows(conn, file, family, follows, sides) -> None:
    """The rows one csv gained and lost, each keyed by its first column and its year."""
    reader = "read_csv(?, header=true, all_varchar=true, delim=',', quote='\"', escape='\"')"
    present = [side for side, path in sides.items() if path.is_file()]
    for side in present:
        conn.execute(
            f"CREATE OR REPLACE TEMP TABLE _rows_{side} AS SELECT * FROM {reader}",
            [str(sides[side])],
        )
    for side in sides.keys() - present:
        conn.execute(
            f"CREATE OR REPLACE TEMP TABLE _rows_{side} AS SELECT * FROM _rows_{present[0]} "
            "WHERE false"
        )
    cols = {s: [d[0] for d in conn.execute(f"FROM _rows_{s} LIMIT 0").description] for s in sides}
    if cols["before"] != cols["after"]:
        conn.execute(
            "INSERT INTO chg (file, family, name, change, row) VALUES (?, ?, '', 'changed', ?)",
            [file, family, f"columns {cols['before']} became {cols['after']}"],
        )
        return
    quoted = ['"' + c.replace('"', '""') + '"' for c in cols["after"]]
    year_col = next(
        (q for c, q in zip(cols["after"], quoted, strict=True) if c.endswith("year")), None
    )
    year = f"TRY_CAST({year_col} AS INTEGER)" if year_col else "NULL::INTEGER"
    line = f"format(?, {year})" if "{}" in follows else "?"
    row = "concat_ws(' | ', " + ", ".join(f"coalesce({q}, '')" for q in quoted) + ")"
    for change, gained, lost in (("added", "after", "before"), ("removed", "before", "after")):
        conn.execute(
            f"INSERT INTO chg SELECT ?, ?, {year}, {quoted[0]}, ?, {line}, {row} "
            f"FROM (FROM _rows_{gained} EXCEPT ALL FROM _rows_{lost})",
            [file, family, change, follows],
        )


def _summary_ok(path: Path) -> bool:
    """A summary's `candidates` is the line count of the list it summarises."""
    listed = path.with_name(path.name.removesuffix("_summary.json") + ".txt")
    try:
        return json.loads(path.read_text(encoding="utf-8"))["candidates"] == held.lines(listed)
    except (OSError, KeyError, ValueError):
        return False


def _in_his(conn, his: held.Held, found: dict, work: Path) -> None:
    """`_yh(name, year)`: added annual lines his file for that year holds; `_in_his(name)`:
    added candidates any file of his holds. Both by `comm`, and both a bug in the export."""
    conn.execute("CREATE OR REPLACE TEMP TABLE _yh (name VARCHAR, year INTEGER)")
    for year in YEARS:
        parts = found.get(("registrable", year), []) + found.get(("hostname", year), [])
        if parts:
            held.union(parts, work / f"year_{year}.txt")
            held.intersect(work / f"year_{year}.txt", his.year(year), work / f"his_{year}.txt")
            held.read_names(conn, "_lines", work / f"his_{year}.txt", year)
            conn.execute("INSERT INTO _yh SELECT name, year FROM _lines")
    conn.execute("CREATE OR REPLACE TEMP TABLE _in_his (name VARCHAR)")
    parts = [p for (family, _), ps in found.items() if family in CANDIDATE_FAMILIES for p in ps]
    if parts:
        held.union(parts, work / "candidates.txt")
        for against in (his.all, his.candidates):
            held.intersect(work / "candidates.txt", against, work / "his_candidates.txt")
            held.read_names(conn, "_lines", work / "his_candidates.txt")
            conn.execute("INSERT INTO _in_his SELECT name FROM _lines")


def _facts(conn, superseded: Path) -> None:
    """What the store says about each changed key, one row per key, for the rules."""
    conn.execute(
        "CREATE OR REPLACE TEMP TABLE _sup AS SELECT domain, TRY_CAST(year AS INTEGER) AS year, "
        "min(marker) AS marker FROM read_csv(?, header=true, all_varchar=true) GROUP BY 1, 2",
        [str(superseded)],
    )
    # the pairs of the registrable, attested and manifest lines, and the row each cited before
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE _pair AS SELECT DISTINCT name AS domain, year FROM chg
        WHERE (family IN ('registrable', 'attested') OR file = 'evidence_manifest.csv')
          AND year IS NOT NULL
    """)
    conn.execute(f"""
        CREATE OR REPLACE TEMP TABLE _pf AS
        SELECT p.domain, p.year, e.{HIS} AS cited_his, e.evidence_value AS cited_value,
               e.acquisition_method AS cited_method, o.domain IS NOT NULL AS has_o
        FROM _pair p
        LEFT JOIN domain_year dy ON dy.domain = p.domain AND dy.assigned_year = p.year
        LEFT JOIN evidence e ON e.evidence_id = dy.evidence_id
        LEFT JOIN (
            SELECT DISTINCT w.domain, w.evidence_year FROM evidence w
            SEMI JOIN _pair p ON p.domain = w.domain AND p.year = w.evidence_year
            WHERE {_ELIGIBLE} AND w.evidence_value NOT LIKE 'cdx capture % www.' || w.domain
        ) o ON o.domain = p.domain AND o.evidence_year = p.year
    """)
    # for a registrable pair: his row, whether the row it cited captured exactly its domain, and
    # our lowest row that does
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE _rpair AS SELECT DISTINCT name AS domain, year FROM chg
        WHERE (family = 'registrable' OR file = 'evidence_manifest.csv') AND year IS NOT NULL
    """)
    conn.execute(f"""
        CREATE OR REPLACE TEMP TABLE _rf AS
        SELECT p.domain, p.year, h.his_value, q.q_value,
               {exact_host_sql("e", "p.domain")} AS cited_exact,
               {qualifies_sql("e", "p.domain")} AS cited_qualifies
        FROM _rpair p
        LEFT JOIN domain_year dy ON dy.domain = p.domain AND dy.assigned_year = p.year
        LEFT JOIN evidence e ON e.evidence_id = dy.evidence_id
        LEFT JOIN (
            SELECT w.domain, w.evidence_year, min(w.evidence_value) AS his_value FROM evidence w
            SEMI JOIN _rpair p ON p.domain = w.domain AND p.year = w.evidence_year
            WHERE w.{HIS} GROUP BY 1, 2
        ) h ON h.domain = p.domain AND h.evidence_year = p.year
        LEFT JOIN (
            SELECT w.domain, w.evidence_year, arg_min(w.evidence_value, w.evidence_id) AS q_value
            FROM evidence w
            SEMI JOIN _rpair p ON p.domain = w.domain AND p.year = w.evidence_year
            WHERE {_ELIGIBLE} AND {qualifies_sql("w", "w.domain")} GROUP BY 1, 2
        ) q ON q.domain = p.domain AND q.evidence_year = p.year
    """)
    conn.execute(f"""
        CREATE OR REPLACE TEMP TABLE _hf AS
        SELECT p.name AS hostname, p.year, e.evidence_value AS cited_value,
               {exact_host_sql("e", "p.name")} AS cited_exact
        FROM (SELECT DISTINCT name, year FROM chg WHERE family = 'hostname') p
        LEFT JOIN hostname_year hy ON hy.hostname = p.name AND hy.assigned_year = p.year
        LEFT JOIN evidence e ON e.evidence_id = hy.evidence_id
    """)
    # a candidate: before, a year the method screen passed; now, a claim year of its own
    conn.execute(
        f"CREATE OR REPLACE TEMP TABLE _cand AS SELECT DISTINCT name FROM chg c WHERE {_CAND}"
    )
    held.our_domain_year(conn, "_cand", "_cand_ody")
    conn.execute(f"""
        CREATE OR REPLACE TEMP TABLE _cf AS
        SELECT n.name, i.name IS NOT NULL AS in_his, m.file AS moved_file, k.year AS claim_year,
               wb.domain IS NOT NULL AS web_before, hb.hostname IS NOT NULL AS host_web_before,
               hn.hostname IS NOT NULL AS host_now, hr.domain IS NOT NULL AS his_named,
               od.domain IS NOT NULL AS ody_named
        FROM _cand n
        LEFT JOIN (SELECT DISTINCT name FROM _in_his) i ON i.name = n.name
        LEFT JOIN (SELECT name, min(file) AS file FROM chg
                   WHERE family IN ('registrable', 'hostname') AND change = 'added'
                   GROUP BY 1) m ON m.name = n.name
        LEFT JOIN (SELECT dy.domain, min(dy.assigned_year) AS year FROM _cand_ody dy
                   WHERE {web_evidence_exists("dy.evidence_id", "dy.domain")}
                   GROUP BY 1) k ON k.domain = n.name
        LEFT JOIN (SELECT DISTINCT dy.domain FROM domain_year dy
                   JOIN evidence e ON e.evidence_id = dy.evidence_id
                   WHERE dy.domain IN (SELECT name FROM _cand) AND {web_evidence_sql("e")}
                  ) wb ON wb.domain = n.name
        LEFT JOIN (SELECT DISTINCT hy.hostname FROM hostname_year hy
                   JOIN evidence e ON e.evidence_id = hy.evidence_id
                   WHERE hy.hostname IN (SELECT name FROM _cand) AND {web_evidence_sql("e")}
                  ) hb ON hb.hostname = n.name
        LEFT JOIN (SELECT DISTINCT hy.hostname FROM hostname_year hy
                   JOIN evidence e ON e.evidence_id = hy.evidence_id
                   WHERE hy.hostname IN (SELECT name FROM _cand)
                     AND {qualifies_sql("e", "hy.hostname")}
                  ) hn ON hn.hostname = n.name
        LEFT JOIN (SELECT DISTINCT domain FROM evidence
                   WHERE {HIS} AND domain IN (SELECT name FROM _cand)) hr ON hr.domain = n.name
        LEFT JOIN (SELECT DISTINCT domain FROM _cand_ody) od ON od.domain = n.name
    """)


def _classify(conn) -> None:
    """`cls`: `chg` with a reason and a detail per line. A csv row takes its key's line's."""
    conn.execute(f"""
        CREATE OR REPLACE TEMP TABLE cls AS
        SELECT c.* EXCLUDE (rd), rd[1] AS reason, rd[2] AS detail FROM (
            SELECT c.*, {_case(LINE_RULES)} AS rd FROM chg c
            LEFT JOIN _sup s ON s.domain = c.name AND s.year = c.year
            LEFT JOIN _pf p ON p.domain = c.name AND p.year = c.year
            LEFT JOIN _rf r ON r.domain = c.name AND r.year = c.year
            LEFT JOIN _hf h ON h.hostname = c.name AND h.year = c.year
            LEFT JOIN _cf f ON f.name = c.name
            LEFT JOIN _yh y ON y.name = c.name AND y.year = c.year
            WHERE c.follows IS NULL
        ) c
    """)
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE _cls_rows AS
        SELECT c.* EXCLUDE (rd), rd[1] AS reason, rd[2] AS detail FROM (
            SELECT c.*, CASE
                WHEN l.reason IS NOT NULL THEN [l.reason, l.detail]
                WHEN c.file = 'evidence_manifest.csv' AND r.his_value IS NULL
                     AND r.q_value IS NOT NULL AND NOT p.cited_his AND NOT r.cited_qualifies
                  THEN ['re-cited', CASE c.change WHEN 'added' THEN 'own capture ' || r.q_value
                                    ELSE 'cited ' || p.cited_value END]
                ELSE ['unexplained', c.row] END AS rd
            FROM chg c
            LEFT JOIN (SELECT file, name, change, reason, detail FROM cls
                       WHERE family <> 'attested') l
              ON l.file = c.follows AND l.name = c.name AND l.change = c.change
            LEFT JOIN _pf p ON p.domain = c.name AND p.year = c.year
            LEFT JOIN _rf r ON r.domain = c.name AND r.year = c.year
            WHERE c.follows IS NOT NULL
        ) c
    """)
    conn.execute("INSERT INTO cls SELECT * FROM _cls_rows")


def _price(conn, calculator: Path, priced_dir: Path, work: Path) -> list[dict]:
    """His calculator over each (reason, change, family, year) list, one file per year: it
    counts a name once per file, and a pair is the unit of an annual file."""
    shutil.rmtree(priced_dir, ignore_errors=True)
    groups = conn.execute(
        "SELECT reason, change, family, year, count(*) FROM cls "
        f"WHERE family IN ({sql_list(list(PRICED))}) GROUP BY ALL ORDER BY ALL"
    ).fetchall()
    priced = []
    for reason, change, family, year, lines in groups:
        stem = f"{family}_{year}" if year is not None else family
        rel = Path(reason.replace(" ", "-"), change, stem)
        path = (priced_dir / rel).with_suffix(".txt")
        path.parent.mkdir(parents=True, exist_ok=True)
        conn.execute(
            "CREATE OR REPLACE TEMP TABLE _group AS SELECT DISTINCT name FROM cls "
            "WHERE reason = ? AND change = ? AND family = ? AND year IS NOT DISTINCT FROM ? "
            "AND coalesce(name, '') <> ''",
            [reason, change, family, year],
        )
        conn.execute(
            f"COPY (SELECT name FROM _group ORDER BY name) TO '{path}' "
            "(HEADER false, QUOTE '', ESCAPE '', DELIMITER '\x01')"
        )
        scored = work / "scored" / rel
        subprocess.run(
            [sys.executable, str(calculator), str(path), "--output-dir", str(scored)],
            check=True,
            capture_output=True,
        )
        summary = read(scored / "summary.json")
        priced.append(
            {
                "reason": reason,
                "change": change,
                "family": family,
                "year": year,
                "lines": lines,
                "ee": Decimal(str(summary["equivalent_english_domains"])),
                "invalid": summary.get("invalid_records", 0),
            }
        )
    return priced


def _tally(counts: list[tuple], priced: list[dict], families: tuple[str, ...]) -> dict:
    """{reason: {added: {lines, ee}, removed: {lines, ee}, net_ee}} over `families`. A csv row
    is not a name, so a family of rows has lines and no EE."""
    ee: dict[tuple, Decimal] = {}
    for g in priced:
        key = (g["family"], g["reason"], g["change"])
        ee[key] = ee.get(key, Decimal(0)) + g["ee"]
    has_ee = all(f in PRICED for f in families)
    out: dict[str, dict] = {}
    for reason in sorted({r for f, r, _, _ in counts if f in families}):
        entry: dict = {}
        for change in ("added", "removed", "changed"):
            lines = sum(n for f, r, c, n in counts if f in families and r == reason and c == change)
            if change == "changed" and not lines:
                continue
            total = sum((ee.get((f, reason, change), Decimal(0)) for f in families), Decimal(0))
            entry[change] = {"lines": lines, "ee": _four(total) if has_ee else None}
        entry["net_ee"] = _four(entry["added"]["ee"] - entry["removed"]["ee"]) if has_ee else None
        out[reason] = entry
    return out


def _four(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))


def deltas(
    before: Path,
    after: Path,
    store: Path,
    out: Path,
    superseded: Path,
    baseline: Path | None = None,
) -> dict:
    """Give every line the export in AFTER differs from the one in BEFORE by its reason.

    Both folders are `output/netnew` copies from one store state, before and after a change to
    the export; `store` is that store, opened read-only. Writes `out` (file, family, year,
    name, change, reason, detail) sorted by file, name and year, `deltas.json` beside it, and
    his calculator's input lists under the folder named like `out`.
    """
    for side in (before, after):
        if not side.is_dir():
            raise Refused(f"{side} is not an export folder")
    if not superseded.is_file():
        raise Refused(f"{superseded} is missing; stage A writes it")
    calculator = calculator_path()
    if not calculator.is_file():
        raise Refused(f"his calculator is not at {calculator}")
    his = held.load(baseline)
    out.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".deltas-", dir=out.parent))
    try:
        conn = connect_read_only_patiently(store)
        try:
            settings(conn, replace(Stage.at(REPO), temp=work / "duckdb_tmp"), DELTAS_MEMORY)
            return _deltas(
                conn, {"before": before, "after": after}, out, superseded, his, work, calculator
            )
        finally:
            conn.close()
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _deltas(conn, folders, out, superseded, his, work, calculator) -> dict:
    (work / "empty").touch()
    conn.execute(
        "CREATE OR REPLACE TEMP TABLE chg (file VARCHAR, family VARCHAR, year INTEGER, "
        "name VARCHAR, change VARCHAR, follows VARCHAR, row VARCHAR)"
    )
    files: dict[str, dict] = {}
    skipped: list[str] = []
    summaries: dict[str, bool] = {}
    found: dict[tuple, list[Path]] = {}
    listed = {p.name for folder in folders.values() for p in folder.iterdir() if p.is_file()}
    for file in sorted(listed):
        sides = {side: folder / file for side, folder in folders.items()}
        known = family_of(file)
        if file in SKIPPED:
            skipped.append(file)
        elif file.endswith("_summary.json"):
            summaries |= {f"{s}/{file}": _summary_ok(p) for s, p in sides.items()}
        elif known is None:
            gone = _missing(sides)
            files[file] = {"family": "unknown", **gone}
            if not _same(sides):
                what = f"is missing {gone['missing']}" if gone else "differs"
                conn.execute(
                    "INSERT INTO chg (file, family, name, change, row) "
                    "VALUES (?, 'unknown', '', 'changed', ?)",
                    [file, f"deltas has no family for this file, and it {what}"],
                )
        else:
            family, year = known
            files[file] = {"family": family, **_missing(sides)}
            if _same(sides):
                continue
            if file in FOLLOWS:
                _rows(conn, file, family, FOLLOWS[file][1], sides)
            else:
                _names(conn, file, family, year, sides, work, found)
    sides = {side: folder.parent / UNVERIFIED for side, folder in folders.items()}
    if not any(p.is_file() for p in sides.values()):
        skipped.append(f"{UNVERIFIED}: beside neither folder")
    else:
        files[UNVERIFIED] = {"family": "unverified", **_missing(sides)}
        if not _same(sides):
            _names(conn, UNVERIFIED, "unverified", None, sides, work, found)

    _in_his(conn, his, found, work)
    _facts(conn, superseded)
    _classify(conn)
    part = out.with_name(out.name + ".part")
    conn.execute(f"""
        COPY (SELECT file, family, year, name, change, reason, detail
              FROM cls ORDER BY file, name, year, change, detail)
        TO '{part}' (HEADER true)
    """)
    os.replace(part, out)

    for file, change, lines, bad in conn.execute(
        "SELECT file, change, count(*), count(*) FILTER (WHERE reason = 'unexplained') "
        "FROM cls GROUP BY ALL"
    ).fetchall():
        entry = files[file]
        entry[change] = lines
        entry["unexplained"] = entry.get("unexplained", 0) + bad
    counts = conn.execute(
        "SELECT family, reason, change, count(*) FROM cls GROUP BY ALL"
    ).fetchall()
    priced = _price(conn, calculator, out.with_suffix(""), work)
    families = sorted({f for f, _, _, _ in counts})
    return write(
        out.with_suffix(".json"),
        {
            "his": his.marker,
            "lines": sum(n for *_, n in counts),
            "unexplained": sum(n for _, r, _, n in counts if r == "unexplained"),
            "claim_families": list(CLAIM_FAMILIES),
            "by_reason": _tally(counts, priced, CLAIM_FAMILIES),
            "by_family": {f: _tally(counts, priced, (f,)) for f in families},
            "by_file": {
                f: {"added": 0, "removed": 0, "unexplained": 0, **files[f]} for f in sorted(files)
            },
            "priced": priced,
            "invalid_records": sum(g["invalid"] for g in priced),
            "skipped": skipped,
            "summaries": summaries,
            "summaries_consistent": all(summaries.values()),
        },
    )


def deltas_main(argv: list[str], root: Path = REPO) -> int:
    ap = argparse.ArgumentParser(
        prog="migrate_store.py deltas", description=deltas.__doc__.split("\n\n")[0]
    )
    ap.add_argument("before", type=Path, help="netnew of the export before the change")
    ap.add_argument("after", type=Path, help="netnew of the export after it")
    ap.add_argument("--store", type=Path, help="the store both read; data/ark.duckdb")
    ap.add_argument("--out", type=Path, help="data/migrate/stage_b/deltas.csv")
    ap.add_argument("--superseded", type=Path, help="data/reports/his_superseded_only.csv")
    ap.add_argument("--baseline", type=Path, help="his release; where held looks by default")
    args = ap.parse_args(argv)
    # the paths given are the caller's, so they resolve before the chdir; the defaults are ours
    given = {k: v.resolve() if v is not None else None for k, v in vars(args).items()}
    os.chdir(root)
    try:
        summary = deltas(
            given["before"],
            given["after"],
            given["store"] or root / "data/ark.duckdb",
            given["out"] or root / "data/migrate/stage_b/deltas.csv",
            given["superseded"] or root / "data/reports/his_superseded_only.csv",
            given["baseline"],
        )
    except (Refused, held.HeldError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    shown = ("lines", "unexplained", "by_reason", "skipped", "summaries_consistent")
    print(json.dumps({k: summary[k] for k in shown}, indent=2, default=str))
    return 0 if summary["unexplained"] == 0 else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["deltas"]:
        return deltas_main(argv[1:])
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=["stage-a"])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--rehearse", type=int, metavar="PCT", help="rehearse on a sample")
    mode.add_argument("--run", action="store_true", help="census, build, verify; no swap")
    mode.add_argument("--swap", action="store_true", help="put the verified new file in place")
    mode.add_argument("--rollback", action="store_true", help="put the old file back")
    # one step in a child process, for the peak RSS of that step alone
    mode.add_argument("--step", choices=sorted(STEPS), help=argparse.SUPPRESS)
    ap.add_argument("--stage", type=Path, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.rehearse is not None and not 1 <= args.rehearse <= 100:
        ap.error("--rehearse takes a percentage from 1 to 100")
    os.chdir(REPO)
    try:
        if args.step:
            stage = Stage.load(read(args.stage))
            write(stage.record(args.step), STEPS[args.step](stage))
            return 0
        live = Stage.at(REPO)
        if args.rehearse is not None:
            report = stage_a_rehearse(live, args.rehearse, isolate=True)
            ok = report["swap_ready"] and report["rollback_restored"]
            ok = ok and report.get("thresholds_hold") and report["live_store_unchanged"]
        elif args.run:
            report = stage_a_run(live, isolate=True)
            ok = report["swap_ready"]
        elif args.swap or args.rollback:
            name = "swap" if args.swap else "rollback"
            report = write(live.record(name), STEPS[name](live))
            ok = report.get("swapped") or report.get("rollback_restored")
        else:
            ap.error("name one of --rehearse PCT, --run, --swap or --rollback")
    except (Refused, held.HeldError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    shown = {k: v for k, v in report.items() if k not in ("census", "build")}
    print(json.dumps(shown, indent=2, default=str))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
