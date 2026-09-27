"""Stage B rebuilds the store with only our rows, from the provenance Parquet, with no evidence
index and no foreign key, then swaps; `deltas` and `lane-deltas` explain what an export and a
lane changed by its reason.

    caffeinate -i uv run python scripts/round/migrate_store.py stage-b --rehearse 10
    caffeinate -i uv run python scripts/round/migrate_store.py stage-b --run
    caffeinate -i uv run python scripts/round/migrate_store.py stage-b --swap
    caffeinate -i uv run python scripts/round/migrate_store.py stage-b --rollback
    uv run python scripts/round/migrate_store.py deltas BEFORE AFTER [--store DB] [--out CSV]
    uv run python scripts/round/migrate_store.py lane-deltas [--only K1,K2] [--witness-lines]

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

`deltas` diffs two `output/netnew` folders, and the `candidate_unverified.txt` beside each, by
`LC_ALL=C comm`, and classes each changed line from the store, read-only, and his held sets. It
writes `data/migrate/stage_b/deltas.csv`, prices each reason with his calculator into
`deltas.json` beside it, and exits 0 only when no line is unexplained.

`lane-deltas` runs each lane in `LANES` twice on one store and one input: `before` answers
`held.attested` and `held.known_years` by table membership, `after` as held does on a store
that still holds his rows. It gives every name whose answer moved its reason from the store in
`data/migrate/stage_b/lane_deltas.csv`, writes `lane_deltas.json` beside it, and exits 0 only
when every lane whose input is on disk ran and nothing is unexplained.
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
from dataclasses import dataclass, fields, replace
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
from ark.checks import AUDIT_PATH, collect_checks, format_checks  # noqa: E402
from ark.db import connect_read_only_patiently, init_db  # noqa: E402
from ark.english_share import weight_of  # noqa: E402
from ark.evidence_types import (  # noqa: E402
    ALL_TYPES,
    CANDIDATE_ONLY_TYPES,
    exact_host_sql,
    qualifies_sql,
    web_evidence_exists,
    web_evidence_sql,
)
from ark.export import ATTESTED_NAME, CANDIDATES_PATH, STAMP_NAME, export_all  # noqa: E402
from ark.ingest import YEARS  # noqa: E402
from ark.metrics import _TABLE as METRICS_TABLE  # noqa: E402
from ark.provenance import SHIPPED, load_provenance, write_provenance  # noqa: E402

GIB = 1024**3
# His rows in a store that still holds them: their evidence type and their source. Only this
# file names them, to read a store stage B has not rebuilt; the store it builds holds none.
HIS_TYPE, HIS_SOURCE = "prior_reused", "prior_task"
HIS = f"evidence_type = '{HIS_TYPE}'"
OURS = f"evidence_type <> '{HIS_TYPE}'"
_CANDIDATE_LIST = ", ".join(f"'{t}'" for t in sorted(CANDIDATE_ONLY_TYPES))
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
def _our_domain_year_sql(names: str | None = None) -> str:
    only = f"AND domain IN (SELECT name FROM {names})" if names else ""
    keep = f"AND dy.domain IN (SELECT name FROM {names})" if names else ""
    return f"""
        WITH q AS (
            SELECT domain, evidence_year, min(evidence_id) AS evidence_id
            FROM evidence w
            WHERE evidence_type <> '{HIS_TYPE}' AND evidence_type NOT IN ({_CANDIDATE_LIST})
              AND {qualifies_sql("w", "w.domain")} {only}
            GROUP BY 1, 2
        ), ours AS (
            SELECT domain, evidence_year, min(evidence_id) AS evidence_id
            FROM evidence
            WHERE evidence_type <> '{HIS_TYPE}' AND evidence_type NOT IN ({_CANDIDATE_LIST})
              AND evidence_value NOT LIKE 'cdx capture % www.' || domain {only}
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
        WHERE (e.evidence_type <> '{HIS_TYPE}' OR o.evidence_id IS NOT NULL) {keep}
    """


OUR_DOMAIN_YEAR_SQL = _our_domain_year_sql()


def our_domain_year(conn: duckdb.DuckDBPyConnection, names: str, table: str) -> None:
    """`table`, a temp table of our assignments to the domains in `names` (a table with a `name`
    column), on a store that still holds his rows."""
    conn.execute(f"CREATE OR REPLACE TEMP TABLE {table} AS {_our_domain_year_sql(names)}")


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
            # `before/`, `deltas.csv` and `lane_deltas.csv` beside it are the diffs' own
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


def sql_list(values: list[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


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
        WHERE w.{OURS} AND w.evidence_type NOT IN ({_CANDIDATE_LIST}) {sample}
    """)
    # of those pairs, the ones a capture in the new file dates already; a restored row joins
    # none of them. Read over the pairs of those rows alone, not the whole table.
    conn.execute(f"""
        CREATE TEMP TABLE captured AS SELECT DISTINCT w.domain, w.evidence_year
        FROM main.evidence w
        SEMI JOIN (SELECT domain, evidence_year FROM gone r
                   WHERE {qualifies_sql("r", "r.domain")}) g
          ON g.domain = w.domain AND g.evidence_year = w.evidence_year
        WHERE w.evidence_type NOT IN ({_CANDIDATE_LIST}) AND {qualifies_sql("w", "w.domain")}
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


# `deltas`. His rows are named here as stage B names them: that one of them no longer holds a
# pair is often why its line moved.
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
# the rows of ours `our_domain_year` may cite
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
        f"{_CAND} AND c.change = 'added' AND f.his_named AND f.we_know AND f.claim_year IS NULL "
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
    our_domain_year(conn, "_cand", "_cand_ody")
    conn.execute(f"""
        CREATE OR REPLACE TEMP TABLE _cf AS
        SELECT n.name, i.name IS NOT NULL AS in_his, m.file AS moved_file, k.year AS claim_year,
               wb.domain IS NOT NULL AS web_before, hb.hostname IS NOT NULL AS host_web_before,
               hn.hostname IS NOT NULL AS host_now, hr.domain IS NOT NULL AS his_named,
               od.domain IS NOT NULL AS ody_named, wk.domain IS NOT NULL AS we_know
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
        LEFT JOIN (SELECT d.domain FROM domain d
                   WHERE d.domain IN (SELECT name FROM _cand)
                     AND (d.discovered_source IS DISTINCT FROM
                            (SELECT source_id FROM source WHERE name = '{HIS_SOURCE}')
                          OR EXISTS (SELECT 1 FROM evidence e
                                     WHERE e.domain = d.domain AND e.{OURS}))
                  ) wk ON wk.domain = n.name
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
                     AND (c.change = 'removed' OR strpos(c.row, ' | ' || r.q_value || ' | ') > 0)
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


PRICED_MARK = ".deltas"


def _price(conn, calculator: Path, priced_dir: Path, work: Path) -> list[dict]:
    """His calculator over each (reason, change, family, year) list, one file per year: it
    counts a name once per file, and a pair is the unit of an annual file."""
    if priced_dir.exists() and not (priced_dir / PRICED_MARK).is_file():
        raise Refused(f"{priced_dir} exists and was not written by deltas: move it first")
    shutil.rmtree(priced_dir, ignore_errors=True)
    priced_dir.mkdir(parents=True)
    (priced_dir / PRICED_MARK).write_text("his calculator's inputs, written by deltas\n")
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
    if out.suffix != ".csv":
        raise Refused(f"{out} must end in .csv: its calculator lists go in the folder beside it")
    for side in (before, after):
        if not side.is_dir():
            raise Refused(f"{side} is not an export folder")
    if not superseded.is_file():
        raise Refused(f"{superseded} is missing; stage A wrote it")
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
# a name the old test did not know that his files hold as an exact line: the new rule gains it
HIS_EXACT = "his_exact_name"
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


def our_pairs(conn: duckdb.DuckDBPyConnection, names: list[str]) -> set[tuple[str, int]]:
    """The pairs of `our_domain_year` among `names`."""
    _as_table(conn, "_our_names", _names_table(names))
    try:
        our_domain_year(conn, "_our_names", "_our_pairs")
        return set(conn.execute("SELECT domain, assigned_year FROM _our_pairs").fetchall())
    finally:
        conn.execute("DROP TABLE IF EXISTS _our_pairs")
        conn.execute("DROP TABLE IF EXISTS _our_names")


def real_attested(conn, names: list[str], his: held.Held | None) -> set[str]:
    """What `held.attested` answers on a store that still holds his rows: a pair of ours, or
    an exact line of his `all.txt`."""
    if not names:
        return set()
    his = his or held.load()
    return {d for d, _ in our_pairs(conn, names)} | held.names_in(names, his.all)


def real_known(conn, names: list[str], his: held.Held | None) -> set[tuple[str, int]]:
    """What `held.known_years` answers on a store that still holds his rows: a pair of ours,
    or an exact line of his file for that year."""
    if not names:
        return set()
    his = his or held.load()
    pairs = our_pairs(conn, names)
    for year in YEARS:
        pairs |= {(n, year) for n in held.names_in(names, his.year(year))}
    return pairs


def lane_run(spec: dict) -> int:
    """One run of one lane, alone in this process. Every call of `held.attested` and
    `held.known_years` is answered both ways and both answers are recorded; `before` returns
    table membership of the names asked, `after` held's answer on a store that still holds his
    rows. The script then runs as `python <script> <argv>` runs it."""
    baseline = Path(spec["baseline"])
    held.HELD_ROOT = Path(spec["held_root"])
    held.his_dir = lambda: baseline
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
    his_exact = held.names_in(gained, his.all) if gained else set()
    gained_tally = {"names": 0, "records": 0, "ee": Decimal(0)}
    for name in sorted(gained):
        exact = name in his_exact
        reason, why = (HIS_EXACT, "his all.txt") if exact else (UNEXPLAINED, "after only")
        rows.append(lane_row(key, lane, name, records_of(name), labels[::-1], reason, why))
        if reason == HIS_EXACT:
            count = records_of(name)
            gained_tally["names"] += 1
            gained_tally["records"] += count or 0
            gained_tally["ee"] += weight_of(name) * (1 if count is None else count)
    exact_pairs = {
        (name, year)
        for year in YEARS
        for name in held.names_in({n for n, y in gained_pairs if y == year}, his.year(year))
    }
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
        "gained_by_reason": {HIS_EXACT: gained_tally | {"ee": _four(gained_tally["ee"])}},
        "pairs": {
            "lost": len(lost_pairs),
            "gained": len(gained_pairs),
            "lost_by_reason": pair_reasons,
            "gained_his_exact": len(exact_pairs),
        },
        "unexplained": sum(r["reason"] == UNEXPLAINED for r in rows),
        "pairs_unexplained": pair_reasons.get(UNEXPLAINED, 0) + len(gained_pairs - exact_pairs),
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
