"""Stage A: rebuild the store without his superseded rows and our duplicate rows, then swap.

    caffeinate -i uv run python scripts/round/migrate_store.py stage-a --rehearse 1
    caffeinate -i uv run python scripts/round/migrate_store.py stage-a --run
    caffeinate -i uv run python scripts/round/migrate_store.py stage-a --swap
    caffeinate -i uv run python scripts/round/migrate_store.py stage-a --rollback

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
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import resource
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

import duckdb  # noqa: E402

from ark.baseline import CURRENT_BASELINE_MARKER, baseline_dir  # noqa: E402
from ark.checks import collect_checks, format_checks  # noqa: E402
from ark.db import connect_read_only_patiently, init_db  # noqa: E402
from ark.evidence_types import ALL_TYPES  # noqa: E402
from ark.export import export_all  # noqa: E402
from ark.ingest import BATCH_ROWS, YEARS  # noqa: E402
from ark.metrics import _TABLE as METRICS_TABLE  # noqa: E402
from ark.provenance import SHIPPED  # noqa: E402
from ark.stats import BASELINE_TYPE  # noqa: E402

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
COMPARED = ("netnew", "exports", "reports/year_growth.csv", "candidate_unverified.txt")
MASKED = ("evidence_rows", "domains_touched", "evidence_type")

HIS = f"evidence_type = '{BASELINE_TYPE}'"
OURS = f"evidence_type <> '{BASELINE_TYPE}'"
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
        masters_dir=out / "exports",
        report_dir=out / "reports",
        provenance_dir=out / "provenance",
        baseline=stage.baseline,
    )
    return collect_checks(conn, out / "netnew")


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
        found = sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]
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
    held = read(stage.record("preflight"))["sha256"]
    results["old_file_unchanged"] = {"ok": sha256(stage.store) == held}
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
    held = preflight(live)
    sample = make_sample(live, stage, pct)
    write(stage.work / "live_preflight.json", held)
    write(stage.work / "sample_store.json", sample | {"seconds": round(time.monotonic() - started)})
    report = stage_a_run(stage, isolate)
    report |= {"mode": f"rehearse {pct}", "rollback_restored": False}
    if report["swap_ready"]:
        steps, ok = run(stage, isolate, ("swap", "rollback"))
        report["steps"] += steps
        report["rollback_restored"] = ok and read(stage.record("rollback"))["rollback_restored"]
    report["live_store_unchanged"] = sha256(live.store) == held["sha256"]
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


def main(argv: list[str] | None = None) -> int:
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
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    shown = {k: v for k, v in report.items() if k not in ("census", "build")}
    print(json.dumps(shown, indent=2, default=str))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
