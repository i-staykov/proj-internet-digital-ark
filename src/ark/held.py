"""Held by him is the exact name in his files, tested by `LC_ALL=C comm`.

`prepare` checks each file of his release once and writes `data/held/<marker>/`: a sorted
copy of any file that is not already sorted, unique and lowercase, `all.txt` (his six years)
and `candidates.txt` (his candidate files). His files are never written. `load` hands every
reader the same prepared set, and refuses one his files have moved past.
"""

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import duckdb
from loguru import logger

from ark import baseline as _baseline
from ark.db import DB_MEMORY_LIMIT, DB_TEMP_DIR, DB_THREADS
from ark.evidence_types import CANDIDATE_ONLY_TYPES, HIS_TYPE
from ark.ingest import YEARS

# cwd-relative, like `data/ark.duckdb`: a delivery writes it beside its own store
HELD_ROOT = Path("data/held")
STAMP = "held.json"
ALL = "all.txt"
CANDIDATES = "candidates.txt"
POOL = "candidate_pool.txt"
_C = {**os.environ, "LC_ALL": "C"}
# ours are registrables and hostnames, which `registered_domain_format` and
# `hostname_is_below_its_parent` hold to these bytes
_NOT_OUR_NAME = "[^a-z0-9.-]"
_CANDIDATE_LIST = ", ".join(f"'{t}'" for t in sorted(CANDIDATE_ONLY_TYPES))


class HeldError(RuntimeError):
    """A held set is missing, stale or unsorted, so nothing was compared."""


@dataclass(frozen=True)
class Held:
    """His current release, prepared. `years`, `all` and `candidates` each passed `sort -c -u`
    under LC_ALL=C and hold names as `his_lines` reads them; `candidate_files` are his
    originals, to name in a summary and never to compare against."""

    marker: str
    baseline: Path
    dir: Path
    years: dict[int, Path]
    all: Path
    candidates: Path
    candidate_files: tuple[Path, ...]
    counts: dict[str, int]

    def year(self, year: int) -> Path:
        return self.years[year]


def his_dir() -> Path:
    """Where his current release is, repository or delivery. The seam the tests move."""
    return _baseline.baseline_dir()


# **Every line of a file of his, as every diff reads it.** No dialect sniffing, which refuses a
# file whose line endings are mixed, and no quote, escape or comment character, so no line of
# his is ever parsed away; a carriage return is dropped from the name, and a blank line reads
# as NULL, which matches nothing.
def _read(source: str) -> str:
    return (
        f"read_csv({source}, header=false, delim='\x01', quote='', escape='', auto_detect=false, "
        "strict_mode=false, new_line='\\n', columns={'column0': 'VARCHAR'})"
    )


_NAME = "lower(trim(replace(column0, chr(13), '')))"


def his_lines(source: str = "?") -> str:
    """SQL selecting `name`, one per line of the file `source` names (a `?` or a literal)."""
    return f"SELECT {_NAME} AS name FROM {_read(source)}"


def candidate_files(baseline: Path) -> list[Path]:
    """Every file of his release naming a candidate he holds, in the active pool or outside it.

    **The pool is not all he holds.** His release keeps the ISC survey hostnames as a
    reference collection beside the pool and the names he could not parse in a third file.
    Diffed against the pool alone, the claim hands his own ISC names back to him: 98% of it.
    """
    files = [baseline / POOL, baseline / "candidate_pool_unparsed_format.txt"]
    isc_dir = baseline / "isc_survey_hostnames"
    if baseline.is_dir() and not isc_dir.is_dir():
        logger.warning(f"no ISC collection at {isc_dir}: the candidate claim is not diffed on it")
    files += sorted(isc_dir.glob("*.txt"))
    return [path for path in files if path.is_file()]


def check_sorted(path: Path) -> None:
    """Refuse a file `comm` would misread. macOS `comm` has no `--check-order` and exits 0 on
    unsorted input, so the order is checked here, before any comparison."""
    run = subprocess.run(["sort", "-c", "-u", str(path)], env=_C, capture_output=True)
    if run.returncode != 0:
        raise HeldError(f"{path} is not LC_ALL=C sorted and unique")
    _mark(path)


def lines(path: Path) -> int:
    """Lines in a file, the last one counted with or without its newline."""
    count, last = 0, b"\n"
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            count += chunk.count(b"\n")
            last = chunk[-1:]
    return count + (last != b"\n")


# Paths this process has seen pass `sort -c -u`, keyed by what would change if they were
# rewritten, so a 1.4 GB file of his is checked once per run and not once per comparison
_checked: set[tuple[str, int, int]] = set()


def _key(path: Path) -> tuple[str, int, int]:
    st = path.stat()
    return (str(path.resolve()), st.st_size, st.st_mtime_ns)


def _mark(path: Path) -> None:
    _checked.add(_key(path))


def _ensure_sorted(path: Path) -> None:
    if _key(path) not in _checked:
        check_sorted(path)


def _connect() -> duckdb.DuckDBPyConnection:
    Path(DB_TEMP_DIR).mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect()
    conn.execute(f"SET memory_limit='{DB_MEMORY_LIMIT}'")
    conn.execute(f"SET threads={DB_THREADS}")
    conn.execute(f"SET temp_directory='{DB_TEMP_DIR}'")
    return conn


def _copy_to(conn: duckdb.DuckDBPyConnection, query: str, path: Path) -> None:
    """One name per line, as is: DuckDB quotes a name holding a quote or a comma otherwise."""
    conn.execute(
        f"COPY ({query}) TO '{path}' (HEADER false, QUOTE '', ESCAPE '', DELIMITER '\x01')"
    )


def _is_clean(conn: duckdb.DuckDBPyConnection, path: Path) -> bool:
    """Sorted and unique by byte, and every line already in the form `his_lines` reads.

    BSD `sort -c -u` passes `B.com` before `a.com`, so the form is tested apart, and a blank
    line reads as NULL and fails it. DuckDB also ends a line at a bare carriage return, cuts
    it at the delimiter and drops a leading byte-order mark, none of which `comm` does, so a
    file holding any of them is never clean.
    """
    with path.open("rb") as fh:
        if fh.read(3) == b"\xef\xbb\xbf":
            return False
    if subprocess.run(["grep", "-q", "[\r\x01]", str(path)], env=_C).returncode != 1:
        return False
    run = subprocess.run(["sort", "-c", "-u", str(path)], env=_C, capture_output=True)
    if run.returncode != 0:
        return False
    dirty = conn.execute(
        f"SELECT count(*) FROM {_read('?')} WHERE column0 IS NULL OR column0 <> {_NAME}",
        [str(path)],
    ).fetchone()[0]
    return dirty == 0


def _merge(parts: list[Path], out: Path) -> None:
    part = out.with_name(out.name + ".part")
    try:
        subprocess.run(["sort", "-m", "-u", "-o", str(part), *map(str, parts)], env=_C, check=True)
        check_sorted(part)
        os.replace(part, out)
    finally:
        part.unlink(missing_ok=True)


def _stat(path: Path) -> dict[str, int]:
    st = path.stat()
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns}


def _his_files(baseline: Path) -> list[Path]:
    required = [baseline / f"{year}.txt" for year in YEARS] + [baseline / POOL]
    absent = [str(path) for path in required if not path.is_file()]
    if absent:
        raise HeldError(f"his release is incomplete, missing: {absent}")
    years = [baseline / f"{year}.txt" for year in YEARS]
    return years + candidate_files(baseline)


def prepare(baseline: Path | None = None) -> Held:
    """Check every file of his release and write the held sets under `HELD_ROOT/<marker>/`."""
    baseline = baseline or his_dir()
    files = _his_files(baseline)
    out = HELD_ROOT / baseline.name
    out.mkdir(parents=True, exist_ok=True)
    (out / STAMP).unlink(missing_ok=True)
    conn = _connect()
    stamp: dict = {"marker": baseline.name, "files": {}}
    prepared: dict[Path, Path] = {}
    for path in files:
        rel = path.relative_to(baseline)
        use, copy = path, None
        if not _is_clean(conn, path):
            use = out / rel
            use.parent.mkdir(parents=True, exist_ok=True)
            part = use.with_name(use.name + ".part")
            try:
                _copy_to(
                    conn,
                    f"SELECT DISTINCT name FROM ({his_lines(repr(str(path)))}) "
                    "WHERE coalesce(name, '') <> '' ORDER BY name",
                    part,
                )
                check_sorted(part)
                os.replace(part, use)
            finally:
                part.unlink(missing_ok=True)
            copy = str(rel)
            logger.info(f"{rel}: not sorted, unique and lowercase; a sorted copy is held")
        else:
            (out / rel).unlink(missing_ok=True)
        _mark(use)
        prepared[path] = use
        stamp["files"][str(rel)] = {**_stat(path), "copy": copy}
        if copy:
            stamp["files"][str(rel)]["held"] = _stat(use)
    conn.close()
    year_files = [prepared[baseline / f"{year}.txt"] for year in YEARS]
    _merge(year_files, out / ALL)
    _merge([prepared[p] for p in files[len(YEARS) :]], out / CANDIDATES)
    for name in (ALL, CANDIDATES):
        stamp[name] = _stat(out / name)
    stamp["counts"] = {
        **{str(year): lines(path) for year, path in zip(YEARS, year_files, strict=True)},
        "all": lines(out / ALL),
        "candidates": lines(out / CANDIDATES),
    }
    part = out / f"{STAMP}.part"
    part.write_text(json.dumps(stamp, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(part, out / STAMP)
    return load(baseline)


def load(baseline: Path | None = None) -> Held:
    """The held sets `prepare` wrote for his current release, or `HeldError` if his files have
    changed since, or none were written. Nothing is re-sorted here."""
    baseline = baseline or his_dir()
    out = HELD_ROOT / baseline.name
    fix = "run uv run ark intake"
    try:
        stamp = json.loads((out / STAMP).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HeldError(f"no held sets for {baseline.name} in {out}: {fix}") from None
    try:
        files = _his_files(baseline)
    except HeldError as error:
        raise HeldError(f"{error}: {fix}") from None
    rels = [str(path.relative_to(baseline)) for path in files]
    if sorted(rels) != sorted(stamp["files"]):
        raise HeldError(f"his release lists other files than {out / STAMP} records: {fix}")
    paths: dict[str, Path] = {}
    for rel, path in zip(rels, files, strict=True):
        entry = stamp["files"][rel]
        use = out / entry["copy"] if entry["copy"] else path
        checks = [(path, {k: entry[k] for k in ("size", "mtime_ns")})]
        if entry["copy"]:
            checks.append((use, entry["held"]))
        for checked, recorded in checks:
            if not checked.is_file() or _stat(checked) != recorded:
                raise HeldError(f"{checked} changed since {out / STAMP} was written: {fix}")
        paths[rel] = use
    for name in (ALL, CANDIDATES):
        if not (out / name).is_file() or _stat(out / name) != stamp[name]:
            raise HeldError(f"{out / name} changed since {out / STAMP} was written: {fix}")
    held = Held(
        marker=baseline.name,
        baseline=baseline,
        dir=out,
        years={year: paths[f"{year}.txt"] for year in YEARS},
        all=out / ALL,
        candidates=out / CANDIDATES,
        candidate_files=tuple(files[len(YEARS) :]),
        counts=stamp["counts"],
    )
    for path in [*held.years.values(), held.all, held.candidates]:
        _mark(path)
    return held


def _comm(flag: str, names: Path, against: Path, out: Path) -> int:
    for path in (names, against):
        _ensure_sorted(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_name(out.name + ".part")
    try:
        with part.open("wb") as fh:
            subprocess.run(["comm", flag, str(names), str(against)], stdout=fh, env=_C, check=True)
        os.replace(part, out)
    finally:
        part.unlink(missing_ok=True)
    _mark(out)
    return lines(out)


def minus(names: Path, against: Path, out: Path) -> int:
    """Write the lines of `names` that `against` lacks, by exact name, and count them."""
    return _comm("-23", names, against, out)


def intersect(names: Path, against: Path, out: Path) -> int:
    """Write the lines of `names` that `against` also holds, by exact name, and count them."""
    return _comm("-12", names, against, out)


def dump(conn: duckdb.DuckDBPyConnection, query: str, path: Path) -> int:
    """Write a one-column `query` one name per line, and refuse it unless it is sorted, unique
    and made of the bytes our names are made of: an upper-case, padded or empty name would pass
    `comm` and match nothing of his."""
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    try:
        _copy_to(conn, query, part)
        check_sorted(part)
        found = subprocess.run(["grep", "-q", "-e", _NOT_OUR_NAME, "-e", "^$", str(part)], env=_C)
        if found.returncode != 1:
            raise HeldError(f"{path}: a line is not a lowercase name (grep {found.returncode})")
        os.replace(part, path)
    finally:
        part.unlink(missing_ok=True)
    _mark(path)
    return lines(path)


# **An assignment citing one of HIS evidence rows is re-pointed before it is dropped.** A
# pair he already held was assigned against his marker only because his release was ingested
# first, and many of those we can prove ourselves; dropping them left 32,432,586 of our own
# observations unassigned, which `nothing_earned_is_left_unassigned` correctly reads as a
# domain in the candidate pool holding proof of a year.
#
# **The row it is re-pointed at must be one the assigner would have accepted**, so
# candidate-only types and `www.`-only captures are excluded here, the same two rules
# `no_candidate_leakage` and `a_bare_record_is_not_inferred_from_www` read. A pair with
# nothing left is dropped rather than re-pointed: we cannot prove it, and he can.
OUR_DOMAIN_YEAR_SQL = f"""
        WITH ours AS (
            SELECT domain, evidence_year, min(evidence_id) AS evidence_id
            FROM evidence
            WHERE evidence_type <> '{HIS_TYPE}'
              AND evidence_type NOT IN ({_CANDIDATE_LIST})
              AND evidence_value NOT LIKE 'cdx capture % www.' || domain
            GROUP BY 1, 2
        )
        SELECT dy.* REPLACE (COALESCE(o.evidence_id, dy.evidence_id) AS evidence_id)
        FROM domain_year dy
        JOIN evidence e ON e.evidence_id = dy.evidence_id
        LEFT JOIN ours o ON o.domain = dy.domain AND o.evidence_year = dy.assigned_year
        WHERE e.evidence_type <> '{HIS_TYPE}' OR o.evidence_id IS NOT NULL
    """


def our_domain_year(conn: duckdb.DuckDBPyConnection) -> None:
    """`our_domain_year`, a temp table: the store's assignments with none resting on his rows,
    rebuilt on each call so it never outlives a write. `provenance` ships it as `domain_year`."""
    conn.execute(f"CREATE OR REPLACE TEMP TABLE our_domain_year AS {OUR_DOMAIN_YEAR_SQL}")
