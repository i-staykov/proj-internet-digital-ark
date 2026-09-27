"""Stage A rebuilds the store without his superseded rows and our duplicate rows, then swaps;
`deltas` gives every line two exports differ by its reason.

    caffeinate -i uv run python scripts/round/migrate_store.py stage-a --rehearse 1
    caffeinate -i uv run python scripts/round/migrate_store.py stage-a --run
    caffeinate -i uv run python scripts/round/migrate_store.py stage-a --swap
    caffeinate -i uv run python scripts/round/migrate_store.py stage-a --rollback
    uv run python scripts/round/migrate_store.py deltas BEFORE AFTER [--store DB] [--out CSV]
    uv run python scripts/round/migrate_store.py lane-deltas [--only K1,K2] [--witness-lines]

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

`lane-deltas` runs each lane in `LANES` twice on one store and one input: `before` answers
`held.attested` and `held.known_years` by table membership, `after` by held. It gives every name
whose answer moved its reason from the store in `data/migrate/stage_b/lane_deltas.csv`, writes
`lane_deltas.json` beside it, and exits 0 only when every lane whose input is on disk ran and
nothing is unexplained.
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
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

import duckdb  # noqa: E402
import pyarrow as pa  # noqa: E402

from ark import held  # noqa: E402
from ark.baseline import CURRENT_BASELINE_MARKER, baseline_dir, calculator_path  # noqa: E402
from ark.canonical import to_registrable  # noqa: E402
from ark.checks import collect_checks, format_checks  # noqa: E402
from ark.db import connect_read_only_patiently, init_db  # noqa: E402
from ark.english_share import weight_of  # noqa: E402
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


# `lane-deltas`. A lane asks held two questions. `before` answers them by the table the lane
# tested, restricted to the names asked, and `after` by held, so the two runs write the same
# outputs but for the names whose answer moved. His rows are named here to say why each moved.
LANE_ROOT = Path("data/migrate/stage_b/lanes")  # <lane>/{before,after}/, <lane>/<mode>.{log,json}
LANE_CSV = Path("data/migrate/stage_b/lane_deltas.csv")
LANE_JSON = Path("data/migrate/stage_b/lane_deltas.json")
SUPERSEDED_CSV = Path("data/reports/his_superseded_only.csv")
LANE_MEMORY = "8GB"
MODES = ("before", "after")
LANE_COLUMNS = (
    "lane",
    "script",
    "domain",
    "weight",
    "records_moved",
    "before",
    "after",
    "reason",
    "witness",
)
ROLLED, SUPERSEDED = "his_rolled_up_hostname", "his_superseded_release"
CANDIDATE_ONLY, UNEXPLAINED = "candidate_only_name", "unexplained"
# membership of `_lane_names`, the names one call asked
LEGACY = {
    "domain_year": (
        "SELECT DISTINCT dy.domain FROM domain_year dy JOIN _lane_names n ON n.name = dy.domain"
    ),
    "domain": "SELECT DISTINCT d.domain FROM domain d JOIN _lane_names n ON n.name = d.domain",
}
LEGACY_PAIRS = (
    "SELECT dy.domain, dy.assigned_year FROM domain_year dy "
    "JOIN _lane_names n ON n.name = dy.domain"
)
# split_usenet's last batch, bulk082403: lines 9221 to 9266 of its ledger of archives done,
# each the name of a file in that folder
BULK = Path("data/raw/usenet_bulk")
BULK_BATCH = (9220, 9266)


@dataclass(frozen=True)
class Lane:
    """A lane's last run. In `argv`, `{out}` is the run's own output folder and `{batch}` the
    usenet batch. An `inputs` pattern that matches nothing leaves the lane unrun."""

    script: str
    argv: tuple[str, ...]
    inputs: tuple[str, ...]
    legacy: str = "domain_year"  # the table the lane tested
    previous: str | None = None  # where it writes by default, compared for information only
    labels: tuple[str, str] = ("dated", "candidate")

    @property
    def files(self) -> bool:
        return "{out}" in self.argv


OUT_ARG = ("--out", "{out}")
SOURCES = "scripts/sources"
TRADEPRESS = "data/raw/tradepress/tradepress_reextract_20260808T191538Z.jsonl.gz"
# the only sample400 journal; the recorded command names its journal as <file>
SAMPLE400 = "data/raw/usenet_bare/usenet_bare_sample400_20260808T181656Z.jsonl.gz"
EXPANSION = "data/raw/expand/round4/expand_round4.jsonl.gz"
LANES = {
    # first, the three whose raw input a prune may free
    "rtfm": Lane(
        f"{SOURCES}/usenet/split_rtfm_faqs.py",
        ("--write", "--tag", "reextract", *OUT_ARG),
        ("data/raw/rtfm/rtfm.mit.edu/pub/usenet-by-group",),
        previous="data/raw/rtfm",
    ),
    # one worker: a pool would pickle functions of runpy's temporary __main__
    "usenet": Lane(
        f"{SOURCES}/usenet/split_usenet.py",
        ("{batch}", "--write", "--tag", "bulk082403", "--out-dir", "{out}", "--workers", "1"),
        ("{batch}",),
        previous="data/raw/usenet",
    ),
    "measure": Lane(
        f"{SOURCES}/usenet/measure_usenet_yield.py", ("{batch}",), ("{batch}",), legacy="domain"
    ),
    "chastity": Lane(
        f"{SOURCES}/blocklists/split_chastity.py",
        ("--write", *OUT_ARG),
        ("data/raw/chastity/chastity-list-0.5/db/*/domains",),
        previous="data/raw/chastity",
    ),
    "junkfilter": Lane(
        f"{SOURCES}/blocklists/split_junkfilter.py",
        ("--write", *OUT_ARG),
        ("data/raw/junkfilter/jf-domains.*",),
        previous="data/raw/junkfilter",
    ),
    "tucows": Lane(
        f"{SOURCES}/directories/split_tucows.py",
        ("--write", *OUT_ARG),
        ("data/raw/tucows/tucows_1996_2001.json",),
        previous="data/raw/tucows",
    ),
    "urlmerchant": Lane(
        f"{SOURCES}/directories/split_urlmerchant.py",
        ("--write", "--tag", "b1", *OUT_ARG),
        ("data/raw/urlmerchant/pages/_domains_*.html",),
        previous="data/raw/urlmerchant",
    ),
    "enron": Lane(
        f"{SOURCES}/mail_corpora/collect_enron.py",
        ("--write", *OUT_ARG),
        ("data/raw/source_probe_260806/enron.tar.gz",),
        previous="data/raw/enron",
    ),
    # never --harvest, which downloads
    "maillists": Lane(
        f"{SOURCES}/mail_corpora/collect_mailing_lists.py",
        ("--write", "--host", "gnome", "--host", "python", *OUT_ARG),
        ("data/raw/maillists/gnome", "data/raw/maillists/python"),
        previous="data/raw/maillists",
    ),
    "fac": Lane(
        f"{SOURCES}/mail_corpora/split_fac.py",
        ("--write", *OUT_ARG),
        ("data/raw/fac/header-*.csv",),
        previous="data/raw/fac",
    ),
    "jeb": Lane(
        f"{SOURCES}/mail_corpora/split_jeb_mail.py",
        ("--write", *OUT_ARG),
        ("data/raw/jeb_bush/jeb_bush_anchored.jsonl.gz",),
        previous="data/raw/jeb_bush",
    ),
    "cctld": Lane(
        f"{SOURCES}/registries/split_cctld_capture.py",
        ("--write", *OUT_ARG),
        ("data/raw/cctld_capture/*.html",),
        previous="data/raw/cctld_capture",
    ),
    "granitecanyon": Lane(
        f"{SOURCES}/registries/split_granitecanyon.py",
        ("--write", *OUT_ARG),
        ("data/raw/granitecanyon/prune-19991130.txt", "data/raw/granitecanyon/zonerejects-*.html"),
        previous="data/raw/granitecanyon",
    ),
    # the default glob would read its own old outputs back
    "tradepress": Lane(
        f"{SOURCES}/trade_press/split_trade_press.py",
        ("--write", "--journal", TRADEPRESS, "--tag", "american_bare", *OUT_ARG),
        (TRADEPRESS,),
        previous="data/raw/tradepress",
    ),
    "usenet_addr": Lane(
        f"{SOURCES}/usenet/split_usenet_addresses.py",
        ("--write", "--in-dir", "data/raw/usenet_addr", "--out-prefix", "usenet_addr", *OUT_ARG),
        ("data/raw/usenet_addr/usenet_*.jsonl.gz",),
        previous="data/raw/usenet_addr",
    ),
    "usenet_bare": Lane(
        f"{SOURCES}/usenet/split_usenet_addresses.py",
        ("--write", "--in-dir", "data/raw/usenet_bare", "--out-prefix", "usenet_bare", *OUT_ARG),
        ("data/raw/usenet_bare/usenet_*.jsonl.gz",),
        previous="data/raw/usenet_bare",
    ),
    "whois": Lane(
        f"{SOURCES}/usenet/split_usenet_whois.py",
        ("--write", *OUT_ARG),
        ("data/raw/usenet_whois/usenet_whois_usenet_*",),
        previous="data/raw/usenet_whois",
    ),
    "project_bare": Lane(
        f"{SOURCES}/usenet/project_usenet_bare.py",
        ("--journal", SAMPLE400, "--archives", "400"),
        (SAMPLE400,),
    ),
    "uucp": Lane(
        f"{SOURCES}/usenet/split_uucp_maps.py",
        ("--write", *OUT_ARG),
        ("data/raw/usenet/comp.mail.maps.mbox.zip",),
        previous="data/raw/uucp",
    ),
    "expansion": Lane(
        "scripts/engines/split_expansion_journal.py",
        (EXPANSION, "--write", *OUT_ARG),
        (EXPANSION,),
        legacy="domain",
        previous="data/raw/expand/round4",
        labels=("corroborated", "unverified"),
    ),
}


class Absent(Exception):
    """A lane's input is not on disk, so the lane is not run."""


def usenet_batch(root: Path) -> list[str]:
    ledger = root / BULK / ".processed"
    lo, hi = BULK_BATCH
    lines = ledger.read_text(encoding="utf-8").splitlines() if ledger.is_file() else []
    names = [n.strip() for n in lines[lo:hi] if n.strip()]
    if len(names) != hi - lo:
        raise Absent(f"{BULK / '.processed'} lines {lo + 1} to {hi}")
    return [str(BULK / n) for n in names]


def _size(path: Path) -> dict:
    if path.is_dir():
        files = [p for p in path.rglob("*") if p.is_file()]
        return {"bytes": sum(p.stat().st_size for p in files), "files": len(files)}
    return {"bytes": path.stat().st_size}


def lane_inputs(lane: Lane, root: Path) -> tuple[list[str], list[dict]]:
    """The usenet batch when the lane reads it, and every input with its size. `Absent` names
    the first one missing."""
    batch = usenet_batch(root) if "{batch}" in lane.argv + lane.inputs else []
    found = []
    for pattern in lane.inputs:
        paths = [root / p for p in batch] if pattern == "{batch}" else sorted(root.glob(pattern))
        missing = [p for p in paths if not p.exists()]
        if missing or not paths:
            raise Absent(str(missing[0].relative_to(root)) if missing else pattern)
        found += [{"path": str(p.relative_to(root)), **_size(p)} for p in paths]
    return batch, found


def lane_argv(lane: Lane, out: str, batch: list[str]) -> list[str]:
    argv: list[str] = []
    for arg in lane.argv:
        argv += batch if arg == "{batch}" else [arg.replace("{out}", out)]
    return argv


def _as_table(conn: duckdb.DuckDBPyConnection, name: str, data: pa.Table) -> None:
    conn.register(f"{name}_in", data)
    try:
        conn.execute(f"CREATE OR REPLACE TEMP TABLE {name} AS SELECT DISTINCT * FROM {name}_in")
    finally:
        conn.unregister(f"{name}_in")


def _names_table(names: list[str]) -> pa.Table:
    return pa.table({"name": pa.array(names, pa.string())})


def _exit_code(code) -> int:
    if code is None or isinstance(code, int):
        return code or 0
    print(code, file=sys.stderr)
    return 1


def lane_run(spec: dict) -> int:
    """One run of one lane, alone in this process. Every call of `held.attested` and
    `held.known_years` is answered both ways and both answers are recorded; `before` returns
    table membership of the names asked, `after` held's answer. The script then runs as
    `python <script> <argv>` runs it."""
    baseline = Path(spec["baseline"])
    held.HELD_ROOT = Path(spec["held_root"])
    held.his_dir = lambda: baseline
    real_attested, real_known = held.attested, held.known_years
    calls: list[dict] = []

    def ask(conn, names: list, sql: str) -> list[tuple]:
        _as_table(conn, "_lane_names", _names_table(names))
        return conn.execute(sql).fetchall()

    def answer(fn: str, names: list, legacy: set, real: set) -> set:
        calls.append(
            {
                "fn": fn,
                "names": len(set(names)),
                "legacy_only": sorted(legacy - real),
                "real_only": sorted(real - legacy),
            }
        )
        return legacy if spec["mode"] == "before" else real

    def attested(conn, names, his=None):
        names = list(names)
        real = real_attested(conn, names, his)
        legacy = {d for (d,) in ask(conn, names, LEGACY[spec["legacy"]])}
        return answer("attested", names, legacy, real)

    def known_years(conn, names, his=None):
        names = list(names)
        real = real_known(conn, names, his)
        return answer("known_years", names, set(ask(conn, names, LEGACY_PAIRS)), real)

    held.attested, held.known_years = attested, known_years
    script = Path(spec["script"])
    if spec["out"]:
        Path(spec["out"]).mkdir(parents=True, exist_ok=True)
    sys.argv = [str(script), *spec["argv"]]
    sys.path.insert(0, str(script.parent))
    try:
        runpy.run_path(str(script), run_name="__main__")
        code = 0
    except SystemExit as done:
        code = _exit_code(done.code)
    except Exception:
        traceback.print_exc()
        code = 1
    sys.stdout.flush()
    write(Path(spec["record"]), {**spec, "exit": code, "calls": calls})
    return code


def run_child(root: Path, spec: dict, base: Path) -> dict:
    """`lane-run` in a child process, which writes `<mode>.log`; its seconds and peak RSS are
    its own, as `step` measures them."""
    mode = spec["mode"]
    path = base / f"{mode}.spec.json"
    write(path, spec)
    started = time.monotonic()
    with (base / f"{mode}.log").open("w", encoding="utf-8") as log:
        child = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "lane-run",
                "--lane",
                spec["lane"],
                "--mode",
                mode,
                "--spec",
                str(path),
            ],
            cwd=root,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        _, status, usage = os.wait4(child.pid, 0)
    child.returncode = code = os.waitstatus_to_exitcode(status)
    path.unlink()
    return {
        "seconds": round(time.monotonic() - started, 1),
        "peak_rss_bytes": peak_rss(usage),
        "exit": code,
    }


_LINES = (
    "(SELECT line FROM read_csv(?, header=false, delim='\x01', quote='', escape='', "
    "auto_detect=false, strict_mode=false, new_line='\\n', columns={'line': 'VARCHAR'}) "
    "WHERE coalesce(line, '') <> '')"
)
_AFTER_TAB = (
    "CASE WHEN contains(line, chr(9)) THEN substr(line, strpos(line, chr(9)) + 1) ELSE '' END"
)


def load_items(conn: duckdb.DuckDBPyConnection, mode: str, rel: str, path: Path) -> None:
    """One output file as `items(mode, file, domain, rest)`: each line of a `.txt` is a name, a
    `.tsv` line is keyed by its first field, and a journal record by its `domain`, or once for
    each of its `domains` with the rest of the record. Records are compared as decompressed
    lines, and a blank line is no item."""
    head, args = "INSERT INTO items SELECT ?, ?,", [mode, rel, str(path)]
    if rel.endswith((".jsonl", ".jsonl.gz")):
        conn.execute(
            f"{head} coalesce(line ->> 'domain', ''), line FROM {_LINES} "
            "WHERE coalesce(json_type(line -> 'domains'), '') <> 'ARRAY'",
            args,
        )
        conn.execute(
            f"""{head} unnest(from_json(line -> 'domains', '["VARCHAR"]')),
            json_merge_patch(line, '{{"domains": null}}') FROM {_LINES}
            WHERE json_type(line -> 'domains') = 'ARRAY'""",
            args,
        )
    elif rel.endswith(".tsv"):
        conn.execute(f"{head} split_part(line, chr(9), 1), {_AFTER_TAB} FROM {_LINES}", args)
    elif rel.endswith(".txt"):
        conn.execute(f"{head} line, '' FROM {_LINES}", args)
    else:
        conn.execute(f"{head} '', line FROM {_LINES}", args)


def lane_diff(conn: duckdb.DuckDBPyConnection, base: Path) -> tuple[dict, dict]:
    """Per output file, the items of each run and those only one run holds; per domain, how many
    items only `before` and only `after` hold."""
    conn.execute(
        "CREATE OR REPLACE TEMP TABLE items (mode VARCHAR, file VARCHAR, domain VARCHAR, "
        "rest VARCHAR)"
    )
    files: dict[str, dict] = {}
    for mode in MODES:
        folder = base / mode
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            rel = str(path.relative_to(folder))
            files.setdefault(
                rel, dict.fromkeys(("before", "after", "only_before", "only_after"), 0)
            )
            load_items(conn, mode, rel, path)
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE moved AS
        SELECT 'before' AS side, * FROM (
            SELECT file, domain, rest FROM items WHERE mode = 'before'
            EXCEPT ALL SELECT file, domain, rest FROM items WHERE mode = 'after')
        UNION ALL
        SELECT 'after' AS side, * FROM (
            SELECT file, domain, rest FROM items WHERE mode = 'after'
            EXCEPT ALL SELECT file, domain, rest FROM items WHERE mode = 'before')
    """)
    for file, mode, n in conn.execute(
        "SELECT file, mode, count(*) FROM items GROUP BY ALL"
    ).fetchall():
        files[file][mode] = n
    for file, side, n in conn.execute(
        "SELECT file, side, count(*) FROM moved GROUP BY ALL"
    ).fetchall():
        files[file][f"only_{side}"] = n
    moved = conn.execute(
        "SELECT domain, count(*) FILTER (WHERE side = 'before'), "
        "count(*) FILTER (WHERE side = 'after') FROM moved GROUP BY 1"
    ).fetchall()
    return files, {d: (b, a) for d, b, a in moved}


def previous_check(conn: duckdb.DuckDBPyConnection, previous: Path, before: Path) -> dict:
    """For information, per file of the `before` run: the names the file of that name the lane
    last wrote holds and `before` does not, and the reverse. The store has grown since, so both
    move; a large first count says the last input was misread."""
    out: dict = {}
    for path in sorted(p for p in before.rglob("*") if p.is_file()):
        rel = str(path.relative_to(before))
        if not (previous / rel).is_file():
            out[rel] = "absent"
            continue
        load_items(conn, "previous", rel, previous / rel)
        counts = conn.execute(
            """
            WITH p AS (SELECT DISTINCT domain FROM items WHERE mode = 'previous' AND file = ?),
                 b AS (SELECT DISTINCT domain FROM items WHERE mode = 'before' AND file = ?)
            SELECT (SELECT count(*) FROM p ANTI JOIN b USING (domain)),
                   (SELECT count(*) FROM b ANTI JOIN p USING (domain))
            """,
            [rel, rel],
        ).fetchone()
        out[rel] = dict(zip(("previous_only", "before_only"), counts, strict=True))
        conn.execute("DELETE FROM items WHERE mode = 'previous'")
    return out


def lane_reasons(
    conn: duckdb.DuckDBPyConnection, names: list[str], pairs: list, marker: str, legacy: str
) -> tuple[dict[str, tuple[str, str]], dict[str, int]]:
    """Why each lost name and pair lost its answer, with the row of his that says so. A row of
    his current release means a line of that file rolls up to the name without being it, since
    `all.txt` would hold it otherwise; a row of an older release alone means only that release
    held it. A name the lane found in `domain` with no row of his is a candidate of ours."""
    current = f"{marker}/"
    reasons: dict[str, tuple[str, str]] = {}
    if names:
        _as_table(conn, "_lane_lost", _names_table(names))
        found = conn.execute(
            f"""
            SELECT l.name, h.current_file, h.older_file, d.domain IS NOT NULL
            FROM _lane_lost l
            LEFT JOIN (
                SELECT e.domain,
                       max(e.evidence_value) FILTER (WHERE starts_with(e.evidence_value, ?))
                         AS current_file,
                       max(e.evidence_value) FILTER (WHERE NOT starts_with(e.evidence_value, ?))
                         AS older_file
                FROM evidence e SEMI JOIN _lane_lost l ON l.name = e.domain
                WHERE e.{HIS} GROUP BY 1
            ) h ON h.domain = l.name
            LEFT JOIN domain d ON d.domain = l.name
            """,
            [current, current],
        ).fetchall()
        for name, now, older, in_domain in found:
            if now:
                reasons[name] = (ROLLED, now)
            elif older:
                reasons[name] = (SUPERSEDED, older)
            elif legacy == "domain" and in_domain:
                reasons[name] = (CANDIDATE_ONLY, "")
            else:
                reasons[name] = (UNEXPLAINED, "")
    if not pairs:
        return reasons, {}
    domains, years = zip(*pairs, strict=True)
    _as_table(
        conn,
        "_lane_pairs",
        pa.table({"domain": pa.array(domains, pa.string()), "year": pa.array(years, pa.int32())}),
    )
    by_pair = conn.execute(
        f"""
        SELECT reason, count(*) FROM (
            SELECT CASE WHEN bool_or(starts_with(e.evidence_value, ?)) THEN '{ROLLED}'
                        WHEN bool_or(e.evidence_value IS NOT NULL) THEN '{SUPERSEDED}'
                        ELSE '{UNEXPLAINED}' END AS reason
            FROM _lane_pairs p
            LEFT JOIN (
                SELECT w.domain, w.evidence_year, w.evidence_value FROM evidence w
                SEMI JOIN _lane_pairs q ON q.domain = w.domain AND q.year = w.evidence_year
                WHERE w.{HIS}
            ) e ON e.domain = p.domain AND e.evidence_year = p.year
            GROUP BY p.domain, p.year
        ) GROUP BY 1 ORDER BY 1
        """,
        [current],
    ).fetchall()
    return reasons, dict(by_pair)


def lane_witnesses(his: held.Held, rolled: dict[str, str], scratch: Path) -> dict[str, str]:
    """`<his file> <line>` for each rolled-up name: the first line of the year file his row
    names whose registrable is the name, by one fixed-string grep of each file."""
    by_file: dict[str, set[str]] = {}
    for name, value in rolled.items():
        by_file.setdefault(value, set()).add(name)
    found: dict[str, str] = {}
    for value, names in sorted(by_file.items()):
        year = re.search(r"(\d{4})\.txt$", value)
        if not year or int(year[1]) not in his.years:
            continue
        scratch.write_text("".join(f"{n}\n" for n in sorted(names)), encoding="utf-8")
        pending = set(names)
        grep = subprocess.Popen(
            ["grep", "-F", "-w", "-f", str(scratch), str(his.year(int(year[1])))],
            stdout=subprocess.PIPE,
            env={**os.environ, "LC_ALL": "C"},
            encoding="utf-8",
            errors="replace",
        )
        try:
            for line in grep.stdout:
                name = to_registrable(line.rstrip("\n"))
                if name in pending:
                    found[name] = f"{value} {line.rstrip()}"
                    pending.discard(name)
                    if not pending:
                        break
        finally:
            grep.kill()
            grep.wait()
            grep.stdout.close()
    return found


def lane_row(
    key: str, lane: Lane, domain="", records=None, labels=("", ""), reason="", witness=""
) -> dict:
    return {
        "lane": key,
        "script": lane.script,
        "domain": domain,
        "weight": str(weight_of(domain)) if domain else "",
        "records_moved": "" if records is None else records,
        "before": labels[0],
        "after": labels[1],
        "reason": reason,
        "witness": witness,
    }


def _lane_settings(conn: duckdb.DuckDBPyConnection, base: Path) -> None:
    (base / "duckdb_tmp").mkdir(parents=True, exist_ok=True)
    for statement in (
        f"SET memory_limit='{LANE_MEMORY}'",
        "SET threads=2",
        f"SET temp_directory='{base / 'duckdb_tmp'}'",
    ):
        conn.execute(statement)


def _fingerprint(path: Path) -> list[int]:
    st = path.stat()
    return [st.st_size, st.st_mtime_ns, len(wal_files(path))]


def explain_lane(key, lane, root, base, records, his, marker, witness) -> tuple[dict, list[dict]]:
    """Diff the two runs' outputs, give every name whose answer moved its reason, and check that
    nothing else moved: an item of a name held answered alike both ways is unexplained, and so
    is a name only `after` attests."""
    calls = [(mode, c) for mode in MODES for c in records[mode]["calls"]]

    def union(fn: str, side: str) -> set:
        return {
            tuple(x) if isinstance(x, list) else x
            for m, c in calls
            if c["fn"] == fn
            for x in c[side]
        }

    lost, gained = union("attested", "legacy_only"), union("attested", "real_only")
    lost_pairs, gained_pairs = (
        union("known_years", "legacy_only"),
        union("known_years", "real_only"),
    )
    entry: dict = {
        "calls": [
            {
                "mode": m,
                "fn": c["fn"],
                "names": c["names"],
                "lost": len(c["legacy_only"]),
                "gained": len(c["real_only"]),
            }
            for m, c in calls
        ]
    }
    files, moved = {}, {}
    if lane.files:
        conn = duckdb.connect()
        try:
            _lane_settings(conn, base)
            files, moved = lane_diff(conn, base)
            if lane.previous:
                entry["previous"] = previous_check(conn, root / lane.previous, base / "before")
        finally:
            conn.close()
    conn = connect_read_only_patiently(root / "data/ark.duckdb")
    try:
        _lane_settings(conn, base)
        reasons, pair_reasons = lane_reasons(
            conn, sorted(lost), sorted(lost_pairs), marker, lane.legacy
        )
    finally:
        conn.close()
    rolled = {name: file for name, (reason, file) in reasons.items() if reason == ROLLED}
    witnesses = lane_witnesses(his, rolled, base / "witness.txt") if witness else {}
    labels = lane.labels if lane.files else ("attested", "not attested")

    def records_of(name: str) -> int | None:
        return max(moved.get(name, (0, 0))) if lane.files else None

    rows, by_reason = [], {}
    for name in sorted(lost):
        reason, file = reasons[name]
        rows.append(
            lane_row(key, lane, name, records_of(name), labels, reason, witnesses.get(name, file))
        )
        tally = by_reason.setdefault(reason, {"names": 0, "records": 0, "ee": Decimal(0)})
        count = records_of(name)
        tally["names"] += 1
        tally["records"] += count or 0
        tally["ee"] += weight_of(name) * (1 if count is None else count)
    for name in sorted(gained):
        rows.append(
            lane_row(key, lane, name, records_of(name), labels[::-1], UNEXPLAINED, "after only")
        )
    for name in sorted(moved.keys() - lost - gained):
        rows.append(
            lane_row(key, lane, name, records_of(name), ("", ""), UNEXPLAINED, "answer unchanged")
        )
    silent = sorted(n for n in lost if n not in moved) if lane.files else []
    entry |= {
        "files": files,
        "lost": len(lost),
        "gained": len(gained),
        "lost_by_reason": {r: t | {"ee": _four(t["ee"])} for r, t in sorted(by_reason.items())},
        "pairs": {
            "lost": len(lost_pairs),
            "gained": len(gained_pairs),
            "lost_by_reason": pair_reasons,
        },
        "unexplained": sum(r["reason"] == UNEXPLAINED for r in rows),
        "pairs_unexplained": pair_reasons.get(UNEXPLAINED, 0) + len(gained_pairs),
        "warnings": {"lost_with_no_moved_item": len(silent), "sample": silent[:20]},
    }
    listed = root / SUPERSEDED_CSV
    if listed.is_file():
        with listed.open(encoding="utf-8", newline="") as fh:
            orphans = {row["domain"] for row in csv.DictReader(fh)}
        entry["superseded_not_in_csv"] = sorted(
            n for n, (reason, _) in reasons.items() if reason == SUPERSEDED and n not in orphans
        )
    return entry, rows


def run_lane(
    key: str, lane: Lane, root: Path, his: held.Held, marker: str, witness: bool
) -> tuple[dict, list[dict]]:
    """Both runs of one lane, then its diff and reasons. Both output folders are deleted; each
    run's log and record stay."""
    base = root / LANE_ROOT / key
    entry: dict = {"script": lane.script, "legacy": lane.legacy}
    try:
        batch, inputs = lane_inputs(lane, root)
    except Absent as gone:
        entry["input_absent"] = str(gone)
        return entry, [lane_row(key, lane, reason="input_absent", witness=str(gone))]
    entry |= {"argv": lane_argv(lane, "{out}", batch), "inputs": inputs, "runs": {}}
    store = root / "data/ark.duckdb"
    was = _fingerprint(store)
    base.mkdir(parents=True, exist_ok=True)
    try:
        records = {}
        for mode in MODES:
            out, record = base / mode, base / f"{mode}.json"
            shutil.rmtree(out, ignore_errors=True)
            record.unlink(missing_ok=True)
            spec = {
                "lane": key,
                "mode": mode,
                "script": str(root / lane.script),
                "argv": lane_argv(lane, str(out), batch),
                "legacy": lane.legacy,
                "out": str(out) if lane.files else None,
                "record": str(record),
                "held_root": str(root / held.HELD_ROOT),
                "baseline": str((root / held.his_dir()).resolve()),
            }
            run = entry["runs"][mode] = run_child(root, spec, base)
            if run["exit"] or not record.is_file():
                entry["failed"] = f"the {mode} run exited {run['exit']}; see {mode}.log"
                return entry, []
            records[mode] = read(record)
        if _fingerprint(store) != was:
            entry["failed"] = "the store changed between the runs"
            return entry, []
        try:
            found, rows = explain_lane(key, lane, root, base, records, his, marker, witness)
        except Exception as exc:  # one lane's diff failing must not lose the lanes after it
            traceback.print_exc()
            entry["failed"] = f"the diff failed: {exc}"
            return entry, []
        return entry | found, rows
    finally:
        for folder in (*MODES, "duckdb_tmp"):
            shutil.rmtree(base / folder, ignore_errors=True)
        (base / "witness.txt").unlink(missing_ok=True)


def _lane_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def lane_deltas(
    root: Path = REPO,
    lanes: dict[str, Lane] | None = None,
    only: list[str] | None = None,
    witness: bool = False,
    marker: str = CURRENT_BASELINE_MARKER,
) -> dict:
    """Run each lane before and after on one store and one input, and give every name whose
    answer moved its reason.

    Reads the store only, and writes under `root`: `LANE_ROOT` (each run's output, deleted once
    diffed), `LANE_CSV` and `LANE_JSON`. A lane not run keeps its rows and entry from its last
    run, so the lanes can run in batches.
    """
    lanes = LANES if lanes is None else lanes
    keys = only or list(lanes)
    if unknown := [k for k in keys if k not in lanes]:
        raise Refused(f"no lane is named {unknown[0]}")
    store = root / "data/ark.duckdb"
    if not store.is_file():
        raise Refused(f"{store} is missing")
    quiet(store)
    his = held.load()
    if his.marker != marker:
        raise Refused(f"the held sets are {his.marker}'s, the store's rows of his {marker}'s")
    rows = _lane_rows(root / LANE_CSV)
    report = read(root / LANE_JSON) if (root / LANE_JSON).is_file() else {"lanes": {}}
    report |= {"his": his.marker, "ran": keys}
    for key in keys:
        entry, lane_rows = run_lane(key, lanes[key], root, his, marker, witness)
        report["lanes"][key] = entry
        rows = [r for r in rows if r["lane"] != key] + lane_rows
        save_lanes(root, rows, report)
    return report


def save_lanes(root: Path, rows: list[dict], report: dict) -> None:
    """Both files, after each lane, so a batch cut short keeps the lanes it finished. The CSV is
    in `LC_ALL=C` order by lane and domain: code points sort as their UTF-8 bytes do."""
    path = root / LANE_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    with part.open("w", encoding="utf-8", newline="") as fh:
        out = csv.DictWriter(fh, LANE_COLUMNS, lineterminator="\n")
        out.writeheader()
        out.writerows(sorted(rows, key=lambda r: (r["lane"], r["domain"], r["reason"])))
    os.replace(part, path)
    every = report["lanes"]
    report |= {
        "unexplained": sum(e.get("unexplained", 0) for e in every.values()),
        "pairs_unexplained": sum(e.get("pairs_unexplained", 0) for e in every.values()),
        "failed": sorted(k for k, e in every.items() if "failed" in e),
    }
    write(root / LANE_JSON, report)


def lane_deltas_main(argv: list[str], root: Path = REPO) -> int:
    ap = argparse.ArgumentParser(
        prog="migrate_store.py lane-deltas", description=lane_deltas.__doc__.split("\n\n")[0]
    )
    ap.add_argument("--only", help="lanes to run, comma separated; the rest keep their last rows")
    ap.add_argument(
        "--witness-lines",
        action="store_true",
        help="find the line of his each rolled-up name comes from, one grep per year file",
    )
    args = ap.parse_args(argv)
    os.chdir(root)
    try:
        report = lane_deltas(
            root, only=args.only.split(",") if args.only else None, witness=args.witness_lines
        )
    except (Refused, held.HeldError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    shown = ("input_absent", "failed", "lost", "lost_by_reason", "unexplained", "pairs_unexplained")
    ran = {k: report["lanes"][k] for k in report["ran"]}
    shown_ran = {k: {f: e[f] for f in shown if f in e} for k, e in ran.items()}
    print(json.dumps(shown_ran, indent=2, default=str))
    bad = [k for k, e in ran.items() if "failed" in e or e.get("unexplained")]
    return 1 if bad or any(e.get("pairs_unexplained") for e in ran.values()) else 0


def lane_run_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="migrate_store.py lane-run")
    ap.add_argument("--lane", required=True)
    ap.add_argument("--mode", choices=MODES, required=True)
    ap.add_argument("--spec", type=Path, required=True)
    args = ap.parse_args(argv)
    spec = read(args.spec)
    if (spec["lane"], spec["mode"]) != (args.lane, args.mode):
        ap.error(f"{args.spec} is the {spec['mode']} run of {spec['lane']}")
    return lane_run(spec)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["deltas"]:
        return deltas_main(argv[1:])
    if argv[:1] == ["lane-deltas"]:
        return lane_deltas_main(argv[1:])
    # one run of one lane in a child process, spawned by lane-deltas
    if argv[:1] == ["lane-run"]:
        return lane_run_main(argv[1:])
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
