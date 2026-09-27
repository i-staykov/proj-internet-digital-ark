"""Stage B rebuilds the store with only our rows, from the provenance Parquet, with no evidence
index and no foreign key, then swaps.

    caffeinate -i uv run python scripts/round/migrate_store.py stage-b --rehearse 10
    caffeinate -i uv run python scripts/round/migrate_store.py stage-b --run
    caffeinate -i uv run python scripts/round/migrate_store.py stage-b --swap
    caffeinate -i uv run python scripts/round/migrate_store.py stage-b --rollback

`--run` reads the store only, through views that hide his rows: `evidence` holds our rows, each
with the file it was read from and its place in it where the ledger or the URL says; each
`domain_year` row cites its best row of ours, or goes when only his rows date it; `domain`
holds the names we know. It exports those views, writes them as the provenance Parquet, loads
that into `data/ark.stage_b.duckdb` and exports the new file, which must match byte for byte.
It then restores from `data/ark.duckdb.pre-stage-a.bak` each exact capture of ours stage A
dropped where the new file holds no capture for that pair, re-points the pair's record to it
and exports again: every line that adds must be a pair the restore dated. All of it lands in
`data/migrate/stage_b/run/`, with `report.json`. `--swap` moves the store to
`data/ark.duckdb.pre-stage-b.bak` and the new file into its place, only when the report says
`swap_ready`; `--rollback` moves both back and checks the store's sha256. `--rehearse PCT`
runs every step, a swap and a rollback included, on the `hash(domain) % 100 < PCT` sample under
`data/migrate/stage_b/rehearse/`, and never writes the live store.

"""

from __future__ import annotations

import argparse
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
from dataclasses import dataclass, fields, replace
from datetime import UTC, date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

import duckdb  # noqa: E402

from ark import held  # noqa: E402
from ark.baseline import CURRENT_BASELINE_MARKER, baseline_dir  # noqa: E402
from ark.checks import AUDIT_PATH, collect_checks, format_checks  # noqa: E402
from ark.db import init_db  # noqa: E402
from ark.evidence_types import (  # noqa: E402
    ALL_TYPES,
    CANDIDATE_ONLY_SQL,
    qualifies_sql,
)
from ark.export import STAMP_NAME, export_all  # noqa: E402
from ark.ingest import YEARS  # noqa: E402
from ark.metrics import _TABLE as METRICS_TABLE  # noqa: E402
from ark.provenance import SHIPPED, load_provenance, write_provenance  # noqa: E402

GIB = 1024**3
# His rows in a store that still holds them: their evidence type and their source. Only this
# file names them, to read a store stage B has not rebuilt; the store it builds holds none.
HIS_TYPE, HIS_SOURCE = "prior_reused", "prior_task"
HIS = f"evidence_type = '{HIS_TYPE}'"
OURS = f"evidence_type <> '{HIS_TYPE}'"
# The build holds no evidence index, so 8GB is its limit; the views, the exports and the
# restore join tables of 60M to 140M rows and run at 16GB.
PLAN_MEMORY = EXPORT_MEMORY = RESTORE_MEMORY = "16GB"
BUILD_MEMORY = "8GB"
# Our rows the stage-A store holds, from the issue: the new file is held to 1% of it.
PROJECTED_EVIDENCE = 74_600_000
PROJECTED = {"minutes": [20, 45], "memory_gb": 8, "store_gb": [5, 10]}
# Every table a stage-A store holds, in the order its foreign keys need; stage B builds all but
# his merge statistics, which nothing reads.
OLD_TABLES = (
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
TABLES = OLD_TABLES[:-1]
LOCATED = ("source_file", "record_location")
# What the two exports must match byte for byte.
COMPARED = (
    "netnew",
    "reports/year_growth.csv",
    "reports/source_contribution.csv",
    "candidate_unverified.txt",
)
# A URL that names one capture by its 14-digit stamp, and so the row's place in the archive.
CAPTURE_URL = r"^https?://[^/]+/(web|wayback)/[0-9]{14}/"
# How long after its evidence a lane wrote its ledger row: lanes autocommit each statement.
MAX_LEDGER_LAG = "30 minutes"
# Lanes whose ledger row counts hostname records they never write, so its `record_rows` is 0
# whatever the file held; every other ledger row with 0 rows added no evidence.
UNCOUNTED_LEDGER = (
    "source_name LIKE 'internic_zone_hostnames%' "
    "OR source_name IN ('ripe_nserver_hostnames', 'isc_survey_hostnames')"
)
# Evidence ids per INSERT when a rehearsal copies a sample: the copy keeps the store's evidence
# key, and DuckDB holds a statement's index work until it commits.
SAMPLE_IDS = 20_000_000


# **Our assignments: none rests on one of his rows, and each cites its best row.** A pair his
# release was loaded against keeps a row of ours when we hold one the assigner would accept
# (no candidate-only type, no `www.`-only capture), and is dropped otherwise: we cannot prove
# it, and he can. A pair citing a row that is not a capture of exactly its domain moves to the
# lowest row of ours that is, when there is one. So a pair cites its own row when that row
# qualifies, else the lowest one that does, and this query over its own output gives it back:
# stage B builds `domain_year` from it, and the store's readers then read `domain_year` alone.
OUR_DOMAIN_YEAR_SQL = f"""
    WITH q AS (
        SELECT domain, evidence_year, min(evidence_id) AS evidence_id
        FROM evidence w
        WHERE evidence_type <> '{HIS_TYPE}' AND evidence_type NOT IN ({CANDIDATE_ONLY_SQL})
          AND {qualifies_sql("w", "w.domain")}
        GROUP BY 1, 2
    ), ours AS (
        SELECT domain, evidence_year, min(evidence_id) AS evidence_id
        FROM evidence
        WHERE evidence_type <> '{HIS_TYPE}' AND evidence_type NOT IN ({CANDIDATE_ONLY_SQL})
          AND evidence_value NOT LIKE 'cdx capture % www.' || domain
        GROUP BY 1, 2
    )
    SELECT dy.* REPLACE (CASE
        WHEN e.evidence_type <> '{HIS_TYPE}'
             AND (q.evidence_id IS NULL OR {qualifies_sql("e", "dy.domain")})
          THEN dy.evidence_id
        WHEN q.evidence_id IS NOT NULL THEN q.evidence_id
        ELSE o.evidence_id END AS evidence_id)
    FROM domain_year dy
    JOIN evidence e ON e.evidence_id = dy.evidence_id
    LEFT JOIN q ON q.domain = dy.domain AND q.evidence_year = dy.assigned_year
    LEFT JOIN ours o ON o.domain = dy.domain AND o.evidence_year = dy.assigned_year
    WHERE (e.evidence_type <> '{HIS_TYPE}' OR o.evidence_id IS NOT NULL)
"""


class Refused(Exception):
    """A precondition failed, so the step wrote nothing."""


@dataclass(frozen=True)
class Stage:
    store: Path  # the file being replaced, opened read-only until the swap
    new: Path
    bak: Path
    pre_a: Path  # the store before stage A, read-only: the rows the restore brings back
    work: Path
    baseline: Path  # his release, which every export diffs against
    temp: Path
    audit: Path  # the status audit `ark check` reads
    live_out: Path  # the last full export, compared for information only
    marker: str = CURRENT_BASELINE_MARKER
    live: bool = False  # held to the hold, the audit and PROJECTED_EVIDENCE
    floor_gib: int = 50
    footprint_gib: int = 30
    command: str = "stage-b"  # how a step's child process is run

    @classmethod
    def at(cls, root: Path) -> Stage:
        data = root / "data"
        return cls(
            store=data / "ark.duckdb",
            new=data / "ark.stage_b.duckdb",
            bak=data / "ark.duckdb.pre-stage-b.bak",
            pre_a=data / "ark.duckdb.pre-stage-a.bak",
            work=data / "migrate/stage_b/run",
            baseline=(root / baseline_dir()).resolve(),
            temp=data / "duckdb_tmp",
            audit=root / AUDIT_PATH,
            live_out=root / "output/netnew",
            live=True,
        )

    def sample(self) -> Stage:
        work = self.work.parent / "rehearse"
        return replace(
            self,
            store=work / "ark.duckdb",
            new=work / "ark.stage_b.duckdb",
            bak=work / "ark.duckdb.pre-stage-b.bak",
            work=work,
            live=False,
            floor_gib=0,
        )

    def record(self, name: str) -> Path:
        return self.work / f"{name}.json"

    def save(self) -> dict:
        return {k: str(v) if isinstance(v, Path) else v for k, v in vars(self).items()}

    @classmethod
    def load(cls, saved: dict) -> Stage:
        paths = {f.name for f in fields(cls) if f.type == "Path"}
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


def hold_on() -> bool:
    """The hold file exists, so no scheduled job or bank writes the store."""
    done = subprocess.run(["bash", str(REPO / "scripts/harness/hold.sh"), "holds"], check=False)
    return done.returncode == 0


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


def tables_of(conn: duckdb.DuckDBPyConnection, catalog: str) -> set[str]:
    rows = conn.execute("SELECT table_name FROM duckdb_tables() WHERE database_name = ?", [catalog])
    return {r[0] for r in rows.fetchall()}


def columns(conn: duckdb.DuckDBPyConnection, catalog: str, table: str) -> list[str]:
    rows = conn.execute(
        "SELECT column_name FROM duckdb_columns() WHERE database_name = ? AND table_name = ? "
        "ORDER BY column_index",
        [catalog, table],
    )
    return [r[0] for r in rows.fetchall()]


def constraints(conn: duckdb.DuckDBPyConnection, catalog: str) -> list[tuple[str, str]]:
    """(table, constraint type) of each key a catalog's tables carry; NOT NULL and CHECK are
    not keys."""
    return conn.execute(
        "SELECT table_name, constraint_type FROM duckdb_constraints() WHERE database_name = ? "
        "AND constraint_type IN ('PRIMARY KEY', 'UNIQUE', 'FOREIGN KEY') ORDER BY ALL",
        [catalog],
    ).fetchall()


def attach_old(conn: duckdb.DuckDBPyConnection, stage: Stage) -> None:
    conn.execute(f"ATTACH '{stage.store}' AS old (READ_ONLY)")


def preflight(stage: Stage) -> dict:
    quiet(stage.store, stage.pre_a)
    if stage.bak.exists():
        raise Refused(f"{stage.bak.name} exists: the store was swapped, so roll back first")
    if stage.live and not hold_on():
        raise Refused("the hold is off, so a job could write the store: just hold on")
    if stage.marker != CURRENT_BASELINE_MARKER:
        raise Refused(f"the current release is {CURRENT_BASELINE_MARKER}, not {stage.marker}")
    his = held.load(stage.baseline)
    if his.marker != stage.marker:
        raise Refused(f"the held sets are {his.marker}'s, not {stage.marker}'s")
    if not stage.pre_a.is_file():
        raise Refused(f"{stage.pre_a} is missing, and the restore reads what stage A dropped")
    if stage.live and not stage.audit.is_file():
        raise Refused(f"no status audit at {stage.audit}, so ark check would skip its check")
    conn = duckdb.connect()
    try:
        settings(conn, stage, PLAN_MEMORY)
        attach_old(conn, stage)
        found = tables_of(conn, "old")
        if unknown := found - set(OLD_TABLES):
            raise Refused(f"the store holds tables stage B does not build: {sorted(unknown)}")
        if missing := set(TABLES) - found:
            raise Refused(f"the store lacks {sorted(missing)}")
        if ("evidence", "PRIMARY KEY") not in constraints(conn, "old"):
            raise Refused("the store's evidence has no key: stage B has built it already")
        his_rows = one(conn, f"SELECT count(*) FROM old.main.evidence WHERE {HIS}")
    finally:
        conn.close()
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
    pre = stage.pre_a.stat()
    return {
        "store": str(stage.store),
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "inode": st.st_ino,
        "sha256": sha256(stage.store),
        "free_gib": round(free / GIB, 1),
        "need_gib": round(need / GIB, 1),
        "his_rows": his_rows,
        "pre_a": {"path": str(stage.pre_a), "size": pre.st_size, "mtime_ns": pre.st_mtime_ns},
    }


def next_ids(conn: duckdb.DuckDBPyConnection, catalog: str) -> dict[str, int]:
    """The first id no row of a closed store ever had, deleted rows included: past the highest
    id held, and at or past the id its sequence would issue next. DuckDB writes a sequence it
    has used with that next id as its start, and reads it back as both its start and its last
    value; one never used keeps its start, which stage A set past every id the store before it
    held."""
    issued = {
        name: (start, last or 0)
        for name, start, last in conn.execute(
            "SELECT sequence_name, start_value, last_value FROM duckdb_sequences() "
            "WHERE database_name = ?",
            [catalog],
        ).fetchall()
    }
    top = {
        "evidence_seq": one(conn, f"SELECT coalesce(max(evidence_id), 0) FROM {catalog}.evidence"),
        "source_seq": one(conn, f"SELECT coalesce(max(source_id), 0) FROM {catalog}.source"),
    }
    out = {}
    for name, held_top in top.items():
        start, last = issued.get(name, (1, 0))
        out[name] = max(held_top + 1, start, last)
    return out


def not_null(conn: duckdb.DuckDBPyConnection, catalog: str) -> set[tuple[str, str]]:
    return set(
        conn.execute(
            "SELECT table_name, unnest(constraint_column_names) FROM duckdb_constraints() "
            "WHERE database_name = ? AND constraint_type = 'NOT NULL'",
            [catalog],
        ).fetchall()
    )


def tightened(conn: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Each column the new schema holds NOT NULL and the old store does not, with the NULLs
    it holds: the load would refuse them an hour in, so the plan refuses them first."""
    scratch = duckdb.connect()
    try:
        init_db(scratch)
        new = not_null(scratch, "memory")
    finally:
        scratch.close()
    out = {}
    for table, column in sorted(new - not_null(conn, "old")):
        if table in TABLES and column in columns(conn, "old", table):
            nulls = f'SELECT count(*) FROM old.main.{table} WHERE "{column}" IS NULL'
            out[f"{table}.{column}"] = one(conn, nulls)
    return out


def plan(stage: Stage) -> dict:
    db = stage.work / "plan.duckdb"
    remove(db)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db))
    try:
        settings(conn, stage, PLAN_MEMORY)
        attach_old(conn, stage)
        conn.execute(f"ATTACH '{stage.pre_a}' AS pre (READ_ONLY)")
        return _plan(conn)
    finally:
        conn.close()


def _plan(conn: duckdb.DuckDBPyConnection) -> dict:
    types = dict(
        conn.execute(
            "SELECT evidence_type, count(*) FROM old.main.evidence GROUP BY 1 ORDER BY 1"
        ).fetchall()
    )
    if unknown := set(types) - set(ALL_TYPES) - {HIS_TYPE}:
        raise Refused(f"evidence types the schema refuses: {sorted(unknown)}")
    loose = tightened(conn)
    if nulls := {k: n for k, n in loose.items() if n}:
        raise Refused(f"NULLs in columns the new schema holds NOT NULL: {nulls}")
    # each assignment re-pointed as the store's readers read it before stage B
    conn.execute("USE old")
    conn.execute(f"""
        CREATE TABLE plan.main.dy_new AS SELECT * FROM ({OUR_DOMAIN_YEAR_SQL})
        ORDER BY domain, assigned_year
    """)
    conn.execute("USE plan")
    # the names we know, by the rule the Parquet ships them by, over our rows alone
    conn.execute(f"CREATE TEMP VIEW evidence AS SELECT * FROM old.main.evidence WHERE {OURS}")
    conn.execute("CREATE TEMP VIEW domain AS SELECT * FROM old.main.domain")
    conn.execute("CREATE TEMP VIEW source AS SELECT * FROM old.main.source")
    conn.execute(
        f"CREATE TABLE plan.main.domain_new AS SELECT * FROM ({SHIPPED['domain']}) ORDER BY domain"
    )
    for view in ("evidence", "domain", "source"):
        conn.execute(f"DROP VIEW {view}")

    # **`source_file` comes from the ledger row each evidence batch was written with.** Bulk
    # writes a file's rows and its ledger row in one transaction, so both carry one timestamp;
    # a hostname lane autocommits, so its ledger row follows its rows. A batch takes a file
    # only when each is the other's nearest, the file after the batch and the batch before the
    # file, within MAX_LEDGER_LAG, so a batch whose own ledger row is gone never takes the next
    # file's. The batches before stage A count too: a batch it dropped whole would otherwise
    # leave its file to the batch before it.
    conn.execute(f"""
        CREATE TABLE batch AS
        SELECT source_id, ingested_at FROM old.main.evidence WHERE {OURS}
        UNION SELECT source_id, ingested_at FROM pre.main.evidence WHERE {OURS}
    """)
    conn.execute(f"""
        CREATE TABLE ledger AS
        SELECT s.source_id, f.source_name, f.file_name, f.ingested_at
        FROM old.main.ingested_file f JOIN old.main.source s ON s.name = f.source_name
        WHERE f.record_rows > 0 OR {UNCOUNTED_LEDGER}
    """)
    conn.execute(f"""
        CREATE TABLE located AS
        WITH fwd AS (
            SELECT b.source_id, b.ingested_at AS batch_at, l.ingested_at AS ledger_at, l.file_name
            FROM batch b ASOF JOIN ledger l
              ON l.source_id = b.source_id AND l.ingested_at >= b.ingested_at),
        back AS (
            SELECT l.source_id, l.ingested_at AS ledger_at, b.ingested_at AS batch_at
            FROM ledger l ASOF JOIN batch b
              ON b.source_id = l.source_id AND b.ingested_at <= l.ingested_at),
        single AS (SELECT source_id, ingested_at FROM ledger GROUP BY 1, 2 HAVING count(*) = 1)
        SELECT f.source_id, f.batch_at AS ingested_at, f.file_name, f.ledger_at - f.batch_at AS lag
        FROM fwd f
        JOIN back k
          ON k.source_id = f.source_id AND k.ledger_at = f.ledger_at AND k.batch_at = f.batch_at
        JOIN single u ON u.source_id = f.source_id AND u.ingested_at = f.ledger_at
        WHERE f.ledger_at - f.batch_at <= INTERVAL '{MAX_LEDGER_LAG}'
        ORDER BY 1, 2
    """)

    counts = {
        "his_rows": f"SELECT count(*) FROM old.main.evidence WHERE {HIS}",
        "ours_rows": f"SELECT count(*) FROM old.main.evidence WHERE {OURS}",
        "domain_year_before": "SELECT count(*) FROM old.main.domain_year",
        "domain_year_after": "SELECT count(*) FROM dy_new",
        "domain_before": "SELECT count(*) FROM old.main.domain",
        "domain_after": "SELECT count(*) FROM domain_new",
        "domain_language_before": "SELECT count(*) FROM old.main.domain_language",
        "domain_language_after": (
            "SELECT count(*) FROM old.main.domain_language l "
            "SEMI JOIN domain_new d ON d.domain = l.domain"
        ),
        "batches": "SELECT count(*) FROM batch",
        "batches_located": "SELECT count(*) FROM located",
        "located_max_lag_s": "SELECT coalesce(max(epoch(lag)), 0) FROM located",
        "located_twice": (
            "SELECT count(*) - count(DISTINCT (source_id, ingested_at)) FROM located"
        ),
        "seed_only_domains_kept": (
            f"SELECT count(*) FROM domain_new d ANTI JOIN "
            f"(SELECT domain FROM old.main.evidence WHERE {OURS}) e ON e.domain = d.domain"
        ),
        "hostname_year_orphans": (
            "SELECT count(*) FROM old.main.hostname_year h "
            "ANTI JOIN domain_new d ON d.domain = h.parent_domain"
        ),
        "domain_year_orphans": (
            "SELECT count(*) FROM dy_new y ANTI JOIN domain_new d ON d.domain = y.domain"
        ),
        "domain_year_cites_his": (
            f"SELECT count(*) FROM dy_new y ANTI JOIN "
            f"(SELECT evidence_id FROM old.main.evidence WHERE {OURS}) e "
            "ON e.evidence_id = y.evidence_id"
        ),
    }
    out: dict = {"tables": sorted(tables_of(conn, "old")), "types": types, "tightened": loose}
    out |= {name: one(conn, sql) for name, sql in counts.items()}
    moved = conn.execute(f"""
        SELECT count(*) FILTER (WHERE n.evidence_id <> o.evidence_id),
               count(*) FILTER (WHERE n.evidence_id <> o.evidence_id AND e.{HIS})
        FROM dy_new n
        JOIN old.main.domain_year o ON o.domain = n.domain AND o.assigned_year = n.assigned_year
        JOIN old.main.evidence e ON e.evidence_id = o.evidence_id
    """).fetchone()
    out |= {
        "domain_year_repointed": moved[0],
        "domain_year_repointed_from_his": moved[1],
        "domain_year_dropped": out["domain_year_before"] - out["domain_year_after"],
        "his_only_domains_dropped": out["domain_before"] - out["domain_after"],
        "domain_language_dropped": out["domain_language_before"] - out["domain_language_after"],
        "prior_merge_stats_rows": (
            one(conn, "SELECT count(*) FROM old.main.prior_merge_stats")
            if "prior_merge_stats" in out["tables"]
            else 0
        ),
        "next_ids": next_ids(conn, "old"),
    }
    # checked here, before the build, so a miss costs minutes rather than an hour
    for name in ("hostname_year_orphans", "domain_year_orphans", "domain_year_cites_his"):
        if out[name]:
            raise Refused(f"{name}: {out[name]:,}; the new store would break its walls")
    if out["located_twice"]:
        raise Refused(f"{out['located_twice']} batches matched two files")
    return out


def catalog(conn: duckdb.DuckDBPyConnection, stage: Stage, planned: dict) -> None:
    """Views named as the store's tables, over the old store read-only and the plan, as the
    store stage B builds holds them: our rows, each with its file and its place in it, each
    pair citing its best row of ours, the names we know. Every export and the Parquet read
    these. The sequences start where the new file's will, for `ark check`."""
    attach_old(conn, stage)
    conn.execute(f"ATTACH '{stage.work / 'plan.duckdb'}' AS plan (READ_ONLY)")
    have = columns(conn, "old", "evidence")
    kept = ", ".join(f"e.{c}" for c in have if c not in LOCATED)
    # a store `ark init` migrated carries both columns, NULL but for the rows written since
    migrated = set(LOCATED) <= set(have)
    capture = f"CASE WHEN regexp_matches(e.evidence_url, '{CAPTURE_URL}') THEN e.evidence_url END"
    source_file = "coalesce(e.source_file, l.file_name)" if migrated else "l.file_name"
    record_location = f"coalesce(e.record_location, {capture})" if migrated else capture
    views = {
        "source": "SELECT * FROM old.main.source",
        "domain": "SELECT * FROM plan.main.domain_new",
        "evidence": f"""
            SELECT {kept}, {source_file} AS source_file, {record_location} AS record_location
            FROM old.main.evidence e
            LEFT JOIN plan.main.located l
              ON l.source_id = e.source_id AND l.ingested_at = e.ingested_at
            WHERE e.{OURS}""",
        "domain_year": "SELECT * FROM plan.main.dy_new",
        "hostname_year": "SELECT * FROM old.main.hostname_year",
        "domain_language": (
            "SELECT l.* FROM old.main.domain_language l "
            "SEMI JOIN plan.main.domain_new d ON d.domain = l.domain"
        ),
        "ingested_file": "SELECT * FROM old.main.ingested_file",
        "run_metrics": "SELECT * FROM old.main.run_metrics",
    }
    for name, sql in views.items():
        conn.execute(f"CREATE VIEW memory.main.{name} AS {sql}")
    for name, start in planned["next_ids"].items():
        conn.execute(f"CREATE SEQUENCE memory.main.{name} START WITH {int(start)}")


def export_into(conn: duckdb.DuckDBPyConnection, out: Path, stage: Stage) -> list[dict]:
    """What `ark export` writes, every destination under `out`, then `ark check` on those
    files, the status audit's check included."""
    shutil.rmtree(out, ignore_errors=True)
    export_all(
        conn,
        netnew_dir=out / "netnew",
        candidates_path=out / "candidate_unverified.txt",
        report_dir=out / "reports",
        provenance_dir=out / "provenance",
        baseline=stage.baseline,
    )
    return collect_checks(conn, out / "netnew", audit=stage.audit, baseline=stage.baseline)


def over_views(stage: Stage, task) -> dict:
    conn = duckdb.connect()
    try:
        settings(conn, stage, EXPORT_MEMORY)
        catalog(conn, stage, read(stage.record("plan")))
        return task(conn)
    finally:
        conn.close()


def reference(stage: Stage) -> dict:
    before = stage.work / "before"
    return over_views(stage, lambda conn: {"checks": export_into(conn, before, stage)})


def provenance(stage: Stage) -> dict:
    out = stage.work / "provenance"
    shutil.rmtree(out, ignore_errors=True)
    return over_views(stage, lambda conn: write_provenance(conn, out))


def load(stage: Stage) -> dict:
    planned = read(stage.record("plan"))
    remove(stage.new)
    conn = duckdb.connect(str(stage.new))
    try:
        settings(conn, stage, BUILD_MEMORY)
        counts = load_provenance(conn, stage.work / "provenance", starts=planned["next_ids"])
        # our run log, which is not provenance
        conn.execute(METRICS_TABLE)
        attach_old(conn, stage)
        conn.execute("INSERT INTO run_metrics BY NAME SELECT * FROM old.main.run_metrics")
        conn.execute("DETACH old")
        counts["run_metrics"] = one(conn, "SELECT count(*) FROM run_metrics")
        conn.execute("CHECKPOINT")
    finally:
        conn.close()
    if wal := wal_files(stage.new):
        raise Refused(f"{wal[0].name} was left behind")
    return {"counts": counts, "size": stage.new.stat().st_size}


def digest(conn: duckdb.DuckDBPyConnection, relation: str, cols: list[str]) -> list:
    quoted = ", ".join(f'"{c}"' for c in cols)
    return list(
        conn.execute(
            f"SELECT count(*), coalesce(sum(hash({quoted})::HUGEINT), 0) FROM {relation}"
        ).fetchone()
    )


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


def differing(was: dict[str, str], now: dict[str, str]) -> list[str]:
    return sorted(
        k for k in was.keys() | now.keys() if was.get(k) != now.get(k) or was.get(k) == "missing"
    )


def failed_checks(results: list[dict]) -> list[str]:
    """A check that failed, or read no export: both exports are written just before."""
    return [r["name"] for r in results if not r["ok"] or "no exported" in r.get("skipped", "")]


def live_output(before: Path, live: Path) -> dict:
    """For information: the files of the before export against the last full export."""
    if not live.is_dir():
        return {"ok": True, "informational": True, "absent": str(live)}
    same, differ = 0, []
    for path in sorted(p for p in before.iterdir() if p.is_file() and p.name != STAMP_NAME):
        theirs = live / path.name
        if theirs.is_file() and sha256(theirs) == sha256(path):
            same += 1
        else:
            differ.append(path.name)
    return {"ok": True, "informational": True, "same": same, "differ": differ}


def verify(stage: Stage) -> dict:
    planned, before = read(stage.record("plan")), read(stage.record("reference"))
    conn = duckdb.connect()
    try:
        settings(conn, stage, EXPORT_MEMORY)
        catalog(conn, stage, planned)
        conn.execute(f"ATTACH '{stage.new}' AS fresh (READ_ONLY)")
        results = _verify(conn, stage, planned, before)
    finally:
        conn.close()
    recorded = read(stage.record("preflight"))["sha256"]
    results["old_file_unchanged"] = {"ok": sha256(stage.store) == recorded}
    results["live_output"] = live_output(stage.work / "before" / "netnew", stage.live_out)
    return {
        "checks": results,
        "swap_ready": all(r["ok"] for r in results.values() if not r.get("informational")),
        "new_sha256": sha256(stage.new),
        "new_size": stage.new.stat().st_size,
    }


def _verify(conn: duckdb.DuckDBPyConnection, stage: Stage, planned: dict, before: dict) -> dict:
    out: dict[str, dict] = {}

    def check(name: str, ok: bool, **detail) -> None:
        out[name] = {"ok": bool(ok), **detail}

    found = tables_of(conn, "fresh")
    check("tables", found == set(TABLES), fresh=sorted(found))
    # every table is what the views hold, `source_file` and `record_location` included, which
    # proves the Parquet, the load and the backfill together
    for table in TABLES:
        if table in found:
            cols = columns(conn, "fresh", table)
            a = digest(conn, f"fresh.main.{table}", cols)
            b = digest(conn, f"memory.main.{table}", cols)
            check(f"{table}_is_the_plan", a == b, rows=a[0], planned=b[0])
    rows = one(conn, "SELECT count(*) FROM fresh.main.evidence")
    # held to the issue's figure on the live store; a sample or a test to its own plan
    projected = PROJECTED_EVIDENCE if stage.live else planned["ours_rows"]
    check(
        "evidence_rows",
        rows == planned["ours_rows"] and abs(rows / max(projected, 1) - 1) <= 0.01,
        rows=rows,
        planned=planned["ours_rows"],
        vs_projection_pct=round((rows / max(projected, 1) - 1) * 100, 2),
    )
    his_rows = one(conn, f"SELECT count(*) FROM fresh.main.evidence WHERE {HIS}")
    check("no_his_rows", his_rows == 0, rows=his_rows)
    his_only = one(
        conn,
        f"""
        SELECT count(*) FROM fresh.main.domain d
        WHERE d.discovered_source IS NOT DISTINCT FROM
              (SELECT source_id FROM fresh.main.source WHERE name = '{HIS_SOURCE}')
          AND d.domain NOT IN (SELECT domain FROM fresh.main.evidence)
        """,
    )
    check("no_his_only_domains", his_only == 0, domains=his_only)
    # duckdb_indexes() never lists a key's index, so the keys are read from the constraints
    keys = constraints(conn, "fresh")
    indexes = one(
        conn,
        "SELECT count(*) FROM duckdb_indexes() "
        "WHERE database_name = 'fresh' AND table_name = 'evidence'",
    )
    on_evidence = [k for t, k in keys if t == "evidence"]
    check("no_evidence_index", not indexes and not on_evidence, indexes=indexes, keys=on_evidence)
    foreign = [t for t, k in keys if k == "FOREIGN KEY"]
    check("no_foreign_key", not foreign, tables=foreign)
    keyed = {t for t, k in keys if k == "PRIMARY KEY"}
    check(
        "primary_keys_kept",
        keyed == set(TABLES) - {"evidence", "run_metrics"} and ("source", "UNIQUE") in keys,
        primary_keys=sorted(keyed),
    )
    starts = dict(
        conn.execute(
            "SELECT sequence_name, start_value FROM duckdb_sequences() "
            "WHERE database_name = 'fresh'"
        ).fetchall()
    )
    starts = {name: starts.get(name) for name in planned["next_ids"]}
    check("sequences_past_the_old_ids", starts == planned["next_ids"], starts=starts)
    dangling = one(
        conn,
        """
        SELECT (SELECT count(*) FROM fresh.main.domain_year d
                ANTI JOIN fresh.main.evidence e ON e.evidence_id = d.evidence_id)
             + (SELECT count(*) FROM fresh.main.hostname_year h
                ANTI JOIN fresh.main.evidence e ON e.evidence_id = h.evidence_id)
        """,
    )
    check("no_dangling_id", dangling == 0, dangling=dangling)
    # compared in SQL: a TIMESTAMPTZ fetched into Python needs pytz
    span = "SELECT source_id, min(ingested_at), max(ingested_at) FROM {} GROUP BY 1"
    was, now = span.format(f"old.main.evidence WHERE {OURS}"), span.format("fresh.main.evidence")
    moved = [
        r[0]
        for r in conn.execute(
            f"SELECT DISTINCT source_id FROM (({was} EXCEPT {now}) UNION ALL ({now} EXCEPT {was})) "
            "ORDER BY 1"
        ).fetchall()
    ]
    check("ingested_at_kept", not moved, differ=moved)
    by_source = conn.execute("""
        SELECT s.name, count(*), count(*) FILTER (WHERE e.source_file IS NULL),
               count(*) FILTER (WHERE e.record_location IS NULL)
        FROM fresh.main.evidence e JOIN fresh.main.source s ON s.source_id = e.source_id
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    check(
        "nulls",
        True,
        source_file_null=sum(r[2] for r in by_source),
        record_location_null=sum(r[3] for r in by_source),
        by_source={
            name: {"rows": n, "source_file_null": sf, "record_location_null": rl}
            for name, n, sf, rl in by_source
        },
    )

    conn.execute("USE fresh")
    after = export_into(conn, stage.work / "after", stage)
    failed = failed_checks(after)
    check(
        "integrity_checks",
        not failed and after == before["checks"],
        failed=failed,
        report=format_checks(after),
    )
    old_files, new_files = files_under(stage.work / "before"), files_under(stage.work / "after")
    differ = differing(old_files, new_files)
    check("exports_byte_identical", not differ, files=len(old_files), differ=differ)
    return out


# `restore`: what the export may change by the restore alone. A pair it dates adds its line to
# the year's file and its manifest row, and leaves the candidate pool; the tallies follow.
ANNUAL = re.compile(r"netnew/(\d{4})\.txt")
POOL = "netnew/candidate_additions.txt"
MANIFEST = "netnew/evidence_manifest.csv"
TALLIES = (
    "netnew/candidate_additions_summary.json",
    "reports/year_growth.csv",
    "reports/source_contribution.csv",
)


def restore(stage: Stage) -> dict:
    """Bring back each exact capture of ours stage A dropped where the new file holds no capture
    for its pair, with its id, `ingested_at` and every value it had; re-point the pair's record
    from a row that is no capture to the lowest one restored; export again. Only lines of the
    pairs it dated may change."""
    if not read(stage.record("verify"))["swap_ready"]:
        raise Refused("the verification failed, so nothing is restored")
    conn = duckdb.connect(str(stage.new))
    try:
        settings(conn, stage, RESTORE_MEMORY)
        conn.execute(f"ATTACH '{stage.pre_a}' AS pre (READ_ONLY)")
        attach_old(conn, stage)
        conn.execute(f"ATTACH '{stage.work / 'plan.duckdb'}' AS plan (READ_ONLY)")
        done = _restore(conn, stage)
        for name in ("pre", "old", "plan"):
            conn.execute(f"DETACH {name}")
        conn.execute("CHECKPOINT")
    finally:
        conn.close()
    if wal := wal_files(stage.new):
        raise Refused(f"{wal[0].name} was left behind")
    conn = duckdb.connect()
    try:
        settings(conn, stage, EXPORT_MEMORY)
        conn.execute(f"ATTACH '{stage.new}' AS fresh (READ_ONLY)")
        conn.execute("USE fresh")
        results = export_into(conn, stage.work / "restored", stage)
        conn.execute(
            "CREATE TEMP TABLE dated_pair AS SELECT domain, assigned_year AS year "
            "FROM read_csv(?, header=true, columns={'domain': 'VARCHAR', 'assigned_year': "
            "'INTEGER'})",
            [str(stage.work / "restored_pairs.csv")],
        )
        changes = restore_changes(conn, stage.work / "after", stage.work / "restored")
    finally:
        conn.close()
    failed = failed_checks(results)
    done |= {
        "integrity_checks": {"failed": failed, "report": format_checks(results)},
        "changes": changes,
        "added_by_year": changes["added_by_year"],
        "new_sha256": sha256(stage.new),
        "new_size": stage.new.stat().st_size,
    }
    done["ok"] = not failed and not changes["unexplained"] and not done["skipped_unknown_domain"]
    return done


def _restore(conn: duckdb.DuckDBPyConnection, stage: Stage) -> dict:
    # the rows of ours stage A dropped, about a tenth of the file before it, of a type the
    # assigner accepts; a rehearsal's sample holds only some names, so it reads theirs
    sample = "" if stage.live else "AND w.domain IN (SELECT domain FROM main.domain)"
    cols = ", ".join(f"w.{c}" for c in columns(conn, "pre", "evidence") if c not in LOCATED)
    conn.execute(f"""
        CREATE TEMP TABLE gone AS
        SELECT {cols} FROM pre.main.evidence w
        ANTI JOIN old.main.evidence o ON o.evidence_id = w.evidence_id
        WHERE w.{OURS} AND w.evidence_type NOT IN ({CANDIDATE_ONLY_SQL}) {sample}
    """)
    # of those pairs, the ones a capture in the new file dates already; a restored row joins
    # none of them. Read over the pairs of those rows alone, not the whole table.
    conn.execute(f"""
        CREATE TEMP TABLE captured AS SELECT DISTINCT w.domain, w.evidence_year
        FROM main.evidence w
        SEMI JOIN (SELECT domain, evidence_year FROM gone r
                   WHERE {qualifies_sql("r", "r.domain")}) g
          ON g.domain = w.domain AND g.evidence_year = w.evidence_year
        WHERE w.evidence_type NOT IN ({CANDIDATE_ONLY_SQL}) AND {qualifies_sql("w", "w.domain")}
    """)
    conn.execute(f"""
        CREATE TEMP TABLE dropped AS
        SELECT r.* FROM gone r
        ANTI JOIN captured c ON c.domain = r.domain AND c.evidence_year = r.evidence_year
        WHERE {qualifies_sql("r", "r.domain")}
    """)
    # a row of a name the new file lacks has nowhere to go; on the live store none may be left
    unknown = one(
        conn, "SELECT count(*) FROM dropped r ANTI JOIN main.domain d ON d.domain = r.domain"
    )
    conn.execute(f"""
        INSERT INTO main.evidence BY NAME
        SELECT r.*, l.file_name AS source_file,
               CASE WHEN regexp_matches(r.evidence_url, '{CAPTURE_URL}')
                    THEN r.evidence_url END AS record_location
        FROM dropped r
        LEFT JOIN plan.main.located l
          ON l.source_id = r.source_id AND l.ingested_at = r.ingested_at
        WHERE r.domain IN (SELECT domain FROM main.domain)
        ORDER BY r.evidence_id
    """)
    conn.execute(f"""
        CREATE TEMP TABLE repoint AS
        SELECT dy.domain, dy.assigned_year, dy.evidence_id AS was, r.evidence_id AS now
        FROM main.domain_year dy
        JOIN (SELECT domain, evidence_year, min(evidence_id) AS evidence_id FROM dropped
              WHERE domain IN (SELECT domain FROM main.domain) GROUP BY 1, 2) r
          ON r.domain = dy.domain AND r.evidence_year = dy.assigned_year
        JOIN main.evidence e ON e.evidence_id = dy.evidence_id
        WHERE NOT {qualifies_sql("e", "dy.domain")}
    """)
    conn.execute("""
        UPDATE main.domain_year SET evidence_id = r.now FROM repoint r
        WHERE r.domain = domain_year.domain AND r.assigned_year = domain_year.assigned_year
    """)
    conn.execute(
        f"COPY (SELECT domain, assigned_year FROM repoint ORDER BY ALL) "
        f"TO '{stage.work / 'restored_pairs.csv'}' (HEADER true)"
    )
    kept = "FROM dropped r WHERE r.domain IN (SELECT domain FROM main.domain)"
    return {
        "dropped_by_stage_a": one(conn, "SELECT count(*) FROM gone"),
        "rows": one(conn, f"SELECT count(*) {kept}"),
        "pairs": one(conn, f"SELECT count(*) FROM (SELECT DISTINCT domain, evidence_year {kept})"),
        "repointed": one(conn, "SELECT count(*) FROM repoint"),
        "pairs_without_record": one(
            conn,
            f"""SELECT count(*) FROM (SELECT DISTINCT r.domain, r.evidence_year {kept}) p
                ANTI JOIN main.domain_year dy
                  ON dy.domain = p.domain AND dy.assigned_year = p.evidence_year""",
        ),
        "by_method": dict(
            conn.execute(
                f"SELECT r.acquisition_method, count(*) {kept} GROUP BY 1 ORDER BY 1"
            ).fetchall()
        ),
        "skipped_unknown_domain": unknown,
        "evidence_rows": one(conn, "SELECT count(*) FROM main.evidence"),
    }


def restore_changes(conn: duckdb.DuckDBPyConnection, was: Path, now: Path) -> dict:
    """Every file the restore changed, by lines added and removed, and the lines no pair of
    `dated_pair` explains. A year's file and the manifest may only gain those pairs, the pool
    may only lose their names, and the tallies follow; any other change is unexplained."""
    files: dict[str, dict] = {}
    by_year = dict.fromkeys(YEARS, 0)
    scratch = Path(tempfile.mkdtemp(prefix=".restore-", dir=now.parent))
    try:
        for rel in differing(files_under(was), files_under(now)):
            a, b = was / rel, now / rel
            annual = ANNUAL.fullmatch(rel)
            if not (a.is_file() and b.is_file()):
                files[rel] = {"unexplained": 1, "why": "missing on one side"}
            elif annual or rel == POOL:
                added = held.minus(b, a, scratch / "added.txt")
                removed = held.minus(a, b, scratch / "removed.txt")
                # a year's file gains its pairs, the pool loses their names in any year
                moved, wrong = ("added", removed) if annual else ("removed", added)
                year = f"AND p.year = {int(annual[1])}" if annual else ""
                held.read_names(conn, "_moved", scratch / f"{moved}.txt")
                stray = one(
                    conn,
                    "SELECT count(*) FROM _moved m WHERE NOT EXISTS "
                    f"(SELECT 1 FROM dated_pair p WHERE p.domain = m.name {year})",
                )
                files[rel] = {"added": added, "removed": removed, "unexplained": stray + wrong}
                if annual:
                    by_year[int(annual[1])] = added
            elif rel == MANIFEST:
                for name, path in (("_was", a), ("_now", b)):
                    conn.execute(
                        f"CREATE OR REPLACE TEMP TABLE {name} AS "
                        "SELECT * FROM read_csv(?, header=true, all_varchar=true)",
                        [str(path)],
                    )
                added, removed, stray = conn.execute("""
                    WITH plus AS (FROM _now EXCEPT ALL FROM _was),
                         minus AS (FROM _was EXCEPT ALL FROM _now)
                    SELECT (SELECT count(*) FROM plus), (SELECT count(*) FROM minus),
                           (SELECT count(*) FROM plus m WHERE NOT EXISTS (
                               SELECT 1 FROM dated_pair p WHERE p.domain = m.domain
                                 AND p.year = TRY_CAST(m.assigned_year AS INTEGER)))
                """).fetchone()
                files[rel] = {"added": added, "removed": removed, "unexplained": stray + removed}
            elif rel in TALLIES:
                files[rel] = {"tally": True, "unexplained": 0}
            else:
                files[rel] = {"unexplained": 1, "why": "changed"}
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return {
        "files": files,
        "added_by_year": by_year,
        "unexplained": sum(f["unexplained"] for f in files.values()),
    }


def swap(stage: Stage) -> dict:
    report = read(stage.record("report"))
    if not report.get("swap_ready"):
        raise Refused(f"{stage.record('report')} does not say swap_ready")
    quiet(stage.store, stage.new)
    if stage.bak.exists():
        raise Refused(f"{stage.bak.name} already exists")
    if sha256(stage.store) != read(stage.record("preflight"))["sha256"]:
        raise Refused("the store changed after the preflight")
    if sha256(stage.new) != report["new_sha256"]:
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
    "plan": plan,
    "reference": reference,
    "provenance": provenance,
    "load": load,
    "verify": verify,
    "restore": restore,
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
                stage.command,
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


RUN = ("preflight", "plan", "reference", "provenance", "load", "verify", "restore")
# the records `report.json` carries whole; the preflight and the reference checks stay beside it
REPORTED = ("plan", "provenance", "load", "verify", "restore")
SCRATCH = ("before", "after", "restored", "provenance")


def clear(stage: Stage) -> None:
    """What an earlier attempt left, so a rerun starts clean and its free space counts right."""
    if stage.bak.exists():
        raise Refused(f"{stage.bak.name} exists: the store was swapped, so roll back first")
    for path in (stage.new, stage.work / "plan.duckdb"):
        remove(path)
    (stage.work / "restored_pairs.csv").unlink(missing_ok=True)
    for name in (*RUN, "report", "swap", "rollback"):
        stage.record(name).unlink(missing_ok=True)
    for folder in SCRATCH:
        shutil.rmtree(stage.work / folder, ignore_errors=True)


def figures(report: dict) -> dict:
    """The block to post: time, memory and size against the issue's projection, and each figure
    the issue's box names."""
    steps = report["steps"]
    seconds = {s["step"]: s["seconds"] for s in steps}
    checks = report.get("verify", {}).get("checks", {})
    restored = report.get("restore", {})
    size = restored.get("new_size") or report.get("load", {}).get("size")
    nulls = checks.get("nulls", {})
    return {
        "minutes_total": round(sum(seconds.values()) / 60, 1),
        "minutes_build": round((seconds.get("provenance", 0) + seconds.get("load", 0)) / 60, 1),
        "peak_rss_gb": round(max(s["peak_rss_bytes"] for s in steps) / 1e9, 2),
        "steps_failed": [s["step"] for s in steps if s["exit"]],
        "checks_failed": sorted(
            k for k, v in checks.items() if not v["ok"] and not v.get("informational")
        ),
        "store_bytes": size,
        "store_gb": round(size / 1e9, 2) if size else None,
        "evidence_rows": checks.get("evidence_rows", {}).get("rows"),
        "evidence_vs_projection_pct": checks.get("evidence_rows", {}).get("vs_projection_pct"),
        "prior_reused_rows": checks.get("no_his_rows", {}).get("rows"),
        "evidence_indexes": checks.get("no_evidence_index", {}).get("indexes"),
        "evidence_keys": checks.get("no_evidence_index", {}).get("keys"),
        "foreign_keys": checks.get("no_foreign_key", {}).get("tables"),
        "netnew_identical": checks.get("exports_byte_identical", {}).get("ok"),
        "files_compared": checks.get("exports_byte_identical", {}).get("files"),
        "source_file_null": nulls.get("source_file_null"),
        "record_location_null": nulls.get("record_location_null"),
        "nulls_by_source": nulls.get("by_source"),
        "restored_rows": restored.get("rows"),
        "evidence_rows_restored": restored.get("evidence_rows"),
        "restored_pairs_repointed": restored.get("repointed"),
        "restored_lines_by_year": restored.get("added_by_year"),
        "projected": PROJECTED,
    }


def stage_b_run(stage: Stage, isolate: bool = False) -> dict:
    clear(stage)
    steps, ok = run(stage, isolate, RUN[:-1])
    # the restore changes the new file only once it has proved identical to the old one
    if ok and read(stage.record("verify"))["swap_ready"]:
        more, ok = run(stage, isolate, RUN[-1:])
        steps += more
    report = {"mode": "run", "steps": steps, "swap_ready": False}
    report |= {n: read(stage.record(n)) for n in REPORTED if stage.record(n).exists()}
    if ok and "restore" in report:
        report["swap_ready"] = report["verify"]["swap_ready"] and report["restore"]["ok"]
        report["new_sha256"] = report["restore"]["new_sha256"]
    report["figures"] = figures(report)
    return write(stage.record("report"), report)


def make_sample(live: Stage, stage: Stage, pct: int) -> dict:
    """A copy of the live store holding only the `hash(domain) % 100 < pct` sample, with the
    live store's own tables, keys and sequences, so the rehearsal runs every step and its swap
    on a file of the same shape."""
    shutil.rmtree(stage.work, ignore_errors=True)
    stage.work.mkdir(parents=True)
    started = time.monotonic()
    conn = duckdb.connect(str(stage.store))
    try:
        settings(conn, live, PLAN_MEMORY)
        attach_old(conn, live)
        for (sql,) in conn.execute(
            "SELECT sql FROM duckdb_sequences() WHERE database_name = 'old'"
        ).fetchall():
            conn.execute(sql)
        ddl = dict(
            conn.execute(
                "SELECT table_name, sql FROM duckdb_tables() WHERE database_name = 'old'"
            ).fetchall()
        )
        sampled = f"hash(domain) % 100 < {int(pct)}"
        where = {
            "domain": sampled,
            "evidence": sampled,
            "domain_year": sampled,
            "domain_language": sampled,
            "hostname_year": f"hash(parent_domain) % 100 < {int(pct)}",
        }
        top = one(conn, "SELECT coalesce(max(evidence_id), 0) FROM old.main.evidence")
        for table in (t for t in OLD_TABLES if t in ddl):
            conn.execute(ddl[table])
            select = f"SELECT * FROM old.main.{table} WHERE {where.get(table, 'true')}"
            if table == "evidence":
                for lo in range(0, top + 1, SAMPLE_IDS):
                    conn.execute(
                        f"INSERT INTO evidence {select} AND evidence_id >= ? AND evidence_id < ? "
                        "ORDER BY evidence_id",
                        [lo, lo + SAMPLE_IDS],
                    )
            else:
                conn.execute(f"INSERT INTO {table} {select}")
            conn.execute("CHECKPOINT")
    finally:
        conn.close()
    return {
        "pct": pct,
        "size": stage.store.stat().st_size,
        "seconds": round(time.monotonic() - started, 1),
    }


def stage_b_rehearse(live: Stage, pct: int, isolate: bool = False) -> dict:
    stage = live.sample()
    pre = preflight(live)
    sample = make_sample(live, stage, pct)
    write(stage.work / "live_preflight.json", pre)
    write(stage.work / "sample_store.json", sample)
    report = stage_b_run(stage, isolate)
    report |= {"mode": f"rehearse {pct}", "sample": sample, "rollback_restored": False}
    if report["swap_ready"]:
        steps, ok = run(stage, isolate, ("swap", "rollback"))
        report["steps"] += steps
        report["rollback_restored"] = ok and read(stage.record("rollback"))["rollback_restored"]
    report["live_store_unchanged"] = sha256(live.store) == pre["sha256"]
    # the steps and the file scale with the store; the peak is measured, not scaled
    scale = 100 / pct
    measured = report["figures"]
    report["projection"] = {
        "minutes_total": round(measured["minutes_total"] * scale, 1),
        "minutes_build": round(measured["minutes_build"] * scale, 1),
        "store_gb": round((measured["store_gb"] or 0) * scale, 2),
        "peak_rss_gb_measured": measured["peak_rss_gb"],
        "projected": PROJECTED,
    }
    for path in (stage.store, stage.new, stage.bak, stage.work / "plan.duckdb"):
        remove(path)
    shutil.rmtree(stage.work / "provenance", ignore_errors=True)
    return write(stage.record("report"), report)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=["stage-b"])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--rehearse", type=int, metavar="PCT", help="rehearse on a sample")
    mode.add_argument("--run", action="store_true", help="build, verify, restore; no swap")
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
            report = stage_b_rehearse(live, args.rehearse, isolate=True)
            ok = report["swap_ready"] and report["rollback_restored"]
            ok = ok and report["live_store_unchanged"]
        elif args.run:
            report = stage_b_run(live, isolate=True)
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
    shown = {k: v for k, v in report.items() if k not in REPORTED}
    print(json.dumps(shown, indent=2, default=str))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
