"""The one price a fleet leg may quote, measured against a snapshot instead of the store.

A fleet runner has no 52 GB `data/ark.duckdb`, so it prices against a directory the laptop
builds and pushes (`scripts/harness/sync_fleet.sh`).

**The snapshot is name lists, his calculator and a manifest, nothing else.**

    <marker>/{1996..2001}.txt   the reviewer's current baseline, his files
    netnew/{year}*.txt          our last export for that year, and attested_registrables.txt
    candidates/*.txt            his candidate pool and ours, the second scored track
    calculator/                 his equivalent_english_domains.py and the table it loads
    manifest.json               {marker, built_at, claim_sha256, files: {path: {lines, sha256}}}

Every named file is hashed before anything is priced, and a disagreeing digest, line count
or presence refuses the whole run. So does a zero-line file: an empty held-set makes
everything look net-new, the most flattering way this can be wrong.

**Membership is tested on the EXACT name, and neither form infers the other.** A name that
is its registrable is a `domain_year` record, a name beneath one a `hostname_year` record,
a name reducing to nothing is refused, and `www.<registrable>` is never folded onto the
parent. The `www.` share of a figure is reported, not hidden.

**`comm` compares C-sorted files and DuckDB holds only the names left over**, so no held
file is ever loaded. The EE is his calculator's; `split` names the rule its figure used.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TextIO

import duckdb

from ark.canonical import to_registrable
from ark.delegation import existed_predicate, shipping_filter_for
from ark.english_share import english_weights
from ark.evidence_types import REDIRECT_METHOD, WEB_METHODS
from ark.hostnames import _CAPTURE_STATUS, YEARS, host_of

MANIFEST_NAME = "manifest.json"
NETNEW_DIR = "netnew"
CANDIDATES_DIR = "candidates"
CALCULATOR_DIR = "calculator"
# His scorer and the table it loads from beside itself. Both are required: the EE a leg
# quotes is his program's, and it will not run without its model.
CALCULATOR_FILES = ("equivalent_english_domains.py", "q2_tld_top_langs.json")
CALCULATOR = f"{CALCULATOR_DIR}/{CALCULATOR_FILES[0]}"
# `YYYY<TAB>registrable` for every in-window domain-year the store dates beyond his year
# file: with his files, what dates a name read from free text.
ATTESTED = f"{NETNEW_DIR}/attested_registrables.txt"
TRACKS = ("annual", "candidate")
SPLITS = ("auto", "none")
# A name in a delimited field of a self-dating artifact, a listing or a registry record,
# takes no split; nor does a capture by a web method, which is its own corroboration.
NO_SPLIT_CLASSES = frozenset({"artifact_listing", "whois_creation"})
SPLIT_AUTO = (
    "auto: a name read only from free text counts when its registrable is dated that year "
    "in his files or attested_registrables"
)
SPLIT_NONE = "none: every exact-name net-new record counts"
SPLIT_EXEMPT = "none: {head} takes no split"
SPLIT_CANDIDATE = "none: the candidate track claims no year"
# His figures are exact to four decimals, so the two computations of one EE agree to that.
EE_TOLERANCE = Decimal("0.0001")
# sort and comm compare bytes only under the C locale, and his files are sorted that way.
_C_LOCALE = {**os.environ, "LC_ALL": "C"}
# Bytes that make a line other than the name it holds. The attested file's lines are
# `YYYY<TAB>registrable`, so a tab is refused everywhere else.
_NOT_A_NAME = (b"\r", b" ")


class SnapshotError(RuntimeError):
    """The snapshot cannot be priced against, so nothing is measured."""


def file_stats(path: Path) -> tuple[int, str]:
    """(lines, sha256) in one pass, because these files run to hundreds of megabytes.

    A final line with no newline counts, so a hand-edited fixture is not silently one
    name short of what the file holds.
    """
    digest = hashlib.sha256()
    lines = 0
    tail = b""
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
            lines += chunk.count(b"\n")
            tail = chunk[-1:]
    if tail and tail != b"\n":
        lines += 1
    return lines, digest.hexdigest()


def is_sorted(path: Path, tabbed: bool = False) -> bool:
    """Whether `comm` can read the file as it is: lowercase, no CR, space or (unless
    `tabbed`) tab, and C-sorted. BSD comm answers wrongly on unsorted input and exits 0, so
    no file reaches it without this or a sorted copy."""
    dirty = _NOT_A_NAME if tabbed else (*_NOT_A_NAME, b"\t")
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            if chunk.lower() != chunk or any(byte in chunk for byte in dirty):
                return False
    done = subprocess.run(
        ["sort", "-c", str(path)],
        env=_C_LOCALE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return done.returncode == 0


def build_manifest(
    marker: str, files: dict[str, Path], optional: Iterable[str] = (), claim: Iterable[str] = ()
) -> tuple[dict, list[str]]:
    """The manifest for a snapshot, and the optional entries left out for being empty.

    A required file that is missing or empty raises: those are the reviewer's year files,
    and pricing against a snapshot without them would report every name as net-new. An
    optional entry may legitimately be empty (a year in which one export family found
    nothing), so it is dropped from the snapshot rather than shipped as a zero-line file.
    """
    optional = set(optional)
    entries: dict[str, dict[str, int | str | bool]] = {}
    skipped: list[str] = []
    for rel in sorted(files):
        path = files[rel]
        if not path.is_file():
            raise SnapshotError(f"{rel}: {path} does not exist, so the snapshot is incomplete")
        lines, sha256 = file_stats(path)
        if lines == 0:
            if rel in optional:
                skipped.append(rel)
                continue
            raise SnapshotError(f"{rel} has no lines; an empty held-set prices everything as new")
        entries[rel] = {"lines": lines, "sha256": sha256}
        if rel.endswith(".txt"):
            entries[rel]["sorted"] = is_sorted(path, tabbed=rel == ATTESTED)
    if not entries:
        raise SnapshotError("a snapshot with no files cannot be priced against")
    # One digest of the claim as staged: each claim file's path and sha256, in path order.
    # An empty claim file is not staged, so it is not in the digest either.
    digest = hashlib.sha256()
    for rel in sorted(set(claim) & entries.keys()):
        digest.update(f"{rel}\t{entries[rel]['sha256']}\n".encode())
    manifest = {
        "marker": marker,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "claim_sha256": digest.hexdigest(),
        "files": entries,
    }
    return manifest, skipped


def read_manifest(snapshot: Path) -> tuple[dict, str]:
    """The manifest and the sha256 of its own bytes, which is what a finding cites."""
    path = snapshot / MANIFEST_NAME
    if not path.is_file():
        raise SnapshotError(f"{path} does not exist; run sync_fleet.sh to build the snapshot")
    raw = path.read_bytes()
    try:
        manifest = json.loads(raw)
    except ValueError as exc:
        raise SnapshotError(f"{path} is not JSON: {exc}") from exc
    for key in ("marker", "built_at", "files"):
        if key not in manifest:
            raise SnapshotError(f"{path} has no '{key}'")
    if not isinstance(manifest["files"], dict) or not manifest["files"]:
        raise SnapshotError(f"{path} names no files")
    return manifest, hashlib.sha256(raw).hexdigest()


def verify_snapshot(snapshot: Path, manifest: dict) -> None:
    """Refuse a snapshot whose files disagree with its manifest, in either direction.

    Both directions matter. A listed file that changed under the manifest means the price
    would be measured against something other than what the finding cites. An unlisted
    file means a sync was torn halfway, and the unlisted one is the half that would be
    silently ignored.
    """
    claim = manifest.get("claim_sha256")
    if not isinstance(claim, str) or not claim:
        raise SnapshotError(
            "the manifest carries no claim_sha256; rebuild it with snapshot_manifest.py"
        )
    for name in CALCULATOR_FILES:
        if f"{CALCULATOR_DIR}/{name}" not in manifest["files"]:
            raise SnapshotError(
                f"the manifest lists no {CALCULATOR_DIR}/{name}, "
                "so the EE would not be his calculator's"
            )
    for rel, expected in sorted(manifest["files"].items()):
        path = snapshot / rel
        if not path.is_file():
            raise SnapshotError(f"the manifest lists {rel}, which is not in the snapshot")
        lines, sha256 = file_stats(path)
        if lines == 0:
            raise SnapshotError(f"{rel} has no lines; an empty held-set prices everything as new")
        if lines != expected.get("lines") or sha256 != expected.get("sha256"):
            raise SnapshotError(
                f"{rel} does not match the manifest: {lines} lines, sha256 {sha256[:12]}, "
                f"manifest says {expected.get('lines')} lines, "
                f"sha256 {str(expected.get('sha256'))[:12]}"
            )
    listed = set(manifest["files"])
    for directory in (manifest["marker"], NETNEW_DIR, CANDIDATES_DIR, CALCULATOR_DIR):
        root = snapshot / directory
        if not root.is_dir():
            continue
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            rel = path.relative_to(snapshot).as_posix()
            if rel not in listed:
                raise SnapshotError(f"{rel} is in the snapshot and not in the manifest")


def class_head(evidence_class: str | None) -> str:
    """A scout's free-text evidence class by its first word, the way `lead_queue.py` reads it."""
    words = (evidence_class or "").split("(")[0].split()
    return words[0].strip(",:").lower() if words else ""


def takes_no_split(evidence_class: str | None) -> bool:
    """A delimited field of a self-dating artifact, or a capture by a web method."""
    head = class_head(evidence_class)
    return head in NO_SPLIT_CLASSES or head in WEB_METHODS or head == REDIRECT_METHOD


def _opener(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open(encoding="utf-8", errors="replace")


def _year_of(record: dict) -> int | None:
    """The record's `year`, in the window or not, or None when it carries none. A value that
    is not a whole number, a date or a decade, raises ValueError rather than pass as undated."""
    value = record.get("year")
    if isinstance(value, str):
        value = value.strip() or None
        if value is not None and not value.isdigit():
            raise ValueError(value)
    elif value is not None and (isinstance(value, bool) or not isinstance(value, int)):
        raise ValueError(value)
    return None if value is None else int(value)


def _records(items: Path, track: str, counts: Counter[str], out: TextIO) -> None:
    """One `year, name, parent, free` row per name the funnel accepts, streamed to `out`.

    `host` and a capture's `url` are fields. `text` is split on whitespace, the shape
    `price_hostnames.py --items` reads, and a name found only there is free. The year is
    empty on the candidate track, which claims none.
    """
    with _opener(items) as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            counts["items"] += 1
            try:
                record = json.loads(line)
            except ValueError:
                record = None
            if not isinstance(record, dict):
                counts["unparseable"] += 1
                continue
            status = str(record["status"]).strip() if "status" in record else None
            if "url" in record and "host" not in record:
                # A capture row, under the ingest's rule: a status that is not three digits,
                # or a timestamp that is not fourteen, drops the row rather than guessing.
                if status is not None and not _CAPTURE_STATUS.fullmatch(status):
                    counts["bad_status"] += 1
                    continue
                stamp = str(record.get("timestamp", ""))
                if len(stamp) != 14 or not stamp.isdigit():
                    counts["bad_timestamp"] += 1
                    continue
                year, field = int(stamp[:4]), "url"
            else:
                # dated by `year` alone; a status that is no HTTP code ("active") says nothing
                if status is not None and not _CAPTURE_STATUS.fullmatch(status):
                    status = None
                try:
                    year, field = _year_of(record), "host"
                except ValueError:
                    counts["bad_year"] += 1
                    continue
            if year is not None and year not in YEARS:
                counts["out_of_window"] += 1
                continue
            if track == "candidate":
                year = None
            elif year is None:
                counts["undated"] += 1
                continue
            elif status is not None and status[0] in "45":
                # an error capture dates no master year, and is still a candidate
                counts["error_status"] += 1
                continue
            names = [(str(record[field]), 0)] if record.get(field) else []
            if record.get("text"):
                names += [(token, 1) for token in str(record["text"]).split()]
            if not names:
                counts["no_host"] += 1
                continue
            for raw, free in names:
                host = host_of(raw)
                if host is None:
                    counts["no_host"] += 1
                    continue
                registrable = to_registrable(host)
                if registrable is None:
                    counts["rejected_host"] += 1
                    continue
                if host == f"www.{registrable}":
                    counts["www_of_parent"] += 1
                parent = "" if host == registrable else registrable
                out.write(f"{'' if year is None else year}\t{host}\t{parent}\t{free}\n")


def _quote(path: Path) -> str:
    return str(path).replace("'", "''")


def _run(args: list[str], out: Path | None = None) -> None:
    """A C-locale sort or comm, whose failure refuses the price rather than half-reading."""
    with out.open("wb") if out is not None else open(os.devnull, "wb") as handle:
        done = subprocess.run(args, env=_C_LOCALE, stdout=handle, stderr=subprocess.PIPE)
    if done.returncode:
        detail = done.stderr.decode(errors="replace").strip()[-200:]
        raise SnapshotError(f"{args[0]} exited {done.returncode}: {detail}")


def _sort(raw: Path, tmp: Path) -> Path:
    out = raw.with_suffix(".txt")
    _run(["sort", "-u", "-T", str(tmp), "-o", str(out), str(raw)])
    return out


def _union(parts: list[Path], out: Path, tmp: Path) -> Path:
    """The sorted, unique union of sorted files."""
    if parts:
        _run(["sort", "-m", "-u", "-T", str(tmp), "-o", str(out), *map(str, parts)])
    else:
        out.write_bytes(b"")
    return out


def _comm(asked: Path, held: Path, out: Path) -> Path:
    """The asked names that are lines of `held`. comm reads both in step, so a held file of
    any size costs one pass and no memory."""
    _run(["comm", "-12", str(asked), str(held)], out)
    return out


def _read(path: Path, *types: str) -> str:
    """A tab-separated scratch file as a table, `column0` onwards; an empty field is NULL."""
    columns = ", ".join(f"'column{n}': '{kind}'" for n, kind in enumerate(types))
    return (
        f"read_csv('{_quote(path)}', header=false, delim='\t', quote='', escape='', "
        f"auto_detect=false, columns={{{columns}}})"
    )


class _Sorted:
    """Membership in a C-sorted name file, asked in ascending order: a merge join that
    reads the file once and never holds it."""

    def __init__(self, path: Path) -> None:
        self._handle = path.open(encoding="utf-8")
        self._head = self._next()

    def _next(self) -> str | None:
        line = self._handle.readline()
        return line.rstrip("\n") if line else None

    def has(self, name: str) -> bool:
        while self._head is not None and self._head < name:
            self._head = self._next()
        return self._head == name

    def close(self) -> None:
        self._handle.close()


class _Run:
    """One price's scratch directory, and the snapshot files comm reads."""

    def __init__(self, snapshot: Path, manifest: dict, tmp: Path) -> None:
        self.snapshot, self.manifest, self.tmp = snapshot, manifest, tmp
        self._ready: dict[str, Path] = {}

    def his(self, year: int) -> str:
        return f"{self.manifest['marker']}/{year}.txt"

    def ours(self, year: int) -> list[str]:
        """Our export for that year. The attested file dates names; it holds none."""
        return self._listed(f"{NETNEW_DIR}/{year}")

    def pools(self) -> list[str]:
        return self._listed(f"{CANDIDATES_DIR}/")

    def _listed(self, prefix: str) -> list[str]:
        return sorted(
            rel for rel in self.manifest["files"] if rel.startswith(prefix) and rel.endswith(".txt")
        )

    def ready(self, rel: str) -> Path:
        """The file as it is when the manifest found it sorted, else a lowercased, trimmed,
        sorted copy, the way the export reads his lines. His unparsed names are one today."""
        if rel not in self._ready:
            path = self.snapshot / rel
            if self.manifest["files"][rel].get("sorted") is not True:
                raw = self.tmp / f"ready_{len(self._ready)}.raw"
                with path.open("rb") as source, raw.open("wb") as copy:
                    for line in source:
                        if name := line.strip().lower():
                            copy.write(name + b"\n")
                path = _sort(raw, self.tmp)
            self._ready[rel] = path
        return self._ready[rel]

    def hits(self, asked: Path, rels: list[str], tag: str) -> Path:
        """The asked names that are lines of any of `rels`."""
        parts = [
            _comm(asked, self.ready(rel), self.tmp / f"{tag}_{n}.txt")
            for n, rel in enumerate(rels)
            if rel in self.manifest["files"]
        ]
        return _union(parts, self.tmp / f"{tag}.txt", self.tmp)


def _distinct(rows: Path, tmp: Path) -> tuple[dict[str, tuple[Path, Path]], int]:
    """Per year ('' on the candidate track), the records sorted by name and the raw list of
    names and parents to ask about; and how many records there are. A (year, name) given
    twice is one record, free only when every copy came from free text: sorted, a field's
    `0` copy comes first and is the one kept."""
    groups: dict[str, tuple[Path, Path]] = {}
    records = 0
    last = None
    handles: list[TextIO] = []
    try:
        with rows.open(encoding="utf-8") as source:
            for line in source:
                year, name, parent, free = line.rstrip("\n").split("\t")
                if (year, name) == last:
                    continue
                last = (year, name)
                if year not in groups:
                    for handle in handles:
                        handle.close()
                    tag = year or "undated"
                    groups[year] = (tmp / f"rec_{tag}.tsv", tmp / f"asked_{tag}.raw")
                    handles = [path.open("w", encoding="utf-8") for path in groups[year]]
                rec, asked = handles
                rec.write(f"{name}\t{parent}\t{free}\n")
                asked.write(f"{name}\n{parent}\n" if parent else f"{name}\n")
                records += 1
    finally:
        for handle in handles:
            handle.close()
    return groups, records


def _leftovers(
    run: _Run,
    items: Path,
    track: str,
    split: bool,
    counts: Counter[str],
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """Every record held nowhere, into DuckDB as `rec`, flagged when its parent is held in
    its year and, under the split, when its registrable is dated in its year.

    Only these leftovers and the rows about them are ever in memory: each held file is read
    once, by comm, against the sorted names this run asks about.
    """
    tmp = run.tmp
    rows = tmp / "rows.raw"
    with rows.open("w", encoding="utf-8") as out:
        _records(items, track, counts, out)
    groups, records = _distinct(_sort(rows, tmp), tmp)
    counts["records_priced"] = records
    counts["already_held"] = 0
    if track == "candidate":
        counts["already_in_candidate_pool"] = 0
    conn.execute("CREATE TABLE held_parent (name TEXT, year INTEGER)")
    conn.execute("CREATE TABLE dated (name TEXT, year INTEGER)")
    left, wanted = tmp / "left.tsv", tmp / "wanted.raw"
    with left.open("w", encoding="utf-8") as out, wanted.open("w", encoding="utf-8") as want:
        for year, (named, asked_raw) in groups.items():
            tag = year or "undated"
            asked = _sort(asked_raw, tmp)
            his = pool = None
            if track == "annual":
                his = run.hits(asked, [run.his(int(year))], f"his_{tag}")
                ours = run.hits(asked, run.ours(int(year)), f"ours_{tag}")
                held = _union([his, ours], tmp / f"held_{tag}.txt", tmp)
            else:
                # held in any year, his or ours, it is not a candidate any more
                every = [rel for y in YEARS for rel in (run.his(y), *run.ours(y))]
                held = run.hits(asked, every, "held")
                pool = run.hits(asked, run.pools(), "pool")
            parents_raw = tmp / f"parents_{tag}.raw"
            in_held = _Sorted(held)
            in_pool = _Sorted(pool) if pool is not None else None
            try:
                with (
                    named.open(encoding="utf-8") as source,
                    parents_raw.open("w", encoding="utf-8") as parents,
                ):
                    for line in source:
                        name, parent, free = line.rstrip("\n").split("\t")
                        pooled = in_pool is not None and in_pool.has(name)
                        if pooled:
                            counts["already_in_candidate_pool"] += 1
                        if in_held.has(name):
                            counts["already_held"] += 1
                        elif not pooled:
                            out.write(f"{name}\t{year}\t{parent}\t{free}\n")
                            if parent:
                                parents.write(f"{parent}\n")
                            if split and free == "1":
                                want.write(f"{year}\t{parent or name}\n")
            finally:
                in_held.close()
                if in_pool is not None:
                    in_pool.close()
            parents = _sort(parents_raw, tmp)
            value = year or "NULL"
            _insert(conn, "held_parent", _comm(parents, held, tmp / f"hp_{tag}.txt"), value)
            if split and his is not None:
                _insert(conn, "dated", _comm(parents, his, tmp / f"hd_{tag}.txt"), value)
    if split and wanted.stat().st_size:
        if ATTESTED not in run.manifest["files"]:
            raise SnapshotError(
                f"the auto split reads {ATTESTED}, which this snapshot does not list; "
                "rebuild it, or price with --split none"
            )
        hits = _comm(_sort(wanted, tmp), run.ready(ATTESTED), tmp / "attested_hits.txt")
        conn.execute(
            f"INSERT INTO dated SELECT column1, column0 FROM {_read(hits, 'INTEGER', 'VARCHAR')}"
        )
    # Flags joined once here rather than as a subquery in every query after: a correlated
    # EXISTS over the leftovers cost more memory than the leftovers themselves.
    conn.execute(
        f"""
        CREATE TABLE rec AS
        SELECT l.column0 AS name, l.column1 AS year, l.column2 AS parent,
               CASE WHEN l.column2 IS NULL THEN 'registrable' ELSE 'hostname' END AS kind,
               coalesce(l.column0 = 'www.' || l.column2, false) AS via_www,
               l.column3 = 1 AS free,
               h.name IS NOT NULL AS parent_held,
               d.name IS NOT NULL AS dated
        FROM {_read(left, "VARCHAR", "INTEGER", "VARCHAR", "INTEGER")} l
        LEFT JOIN (SELECT DISTINCT name, year FROM held_parent) h
          ON h.name = l.column2 AND h.year IS NOT DISTINCT FROM l.column1
        LEFT JOIN (SELECT DISTINCT name, year FROM dated) d
          ON d.name = coalesce(l.column2, l.column0) AND d.year IS NOT DISTINCT FROM l.column1
        """
    )


def _insert(conn: duckdb.DuckDBPyConnection, table: str, names: Path, year: str) -> None:
    conn.execute(f"INSERT INTO {table} SELECT column0, {year} FROM {_read(names, 'VARCHAR')}")


def _calculate(
    conn: duckdb.DuckDBPyConnection, where: str, run: _Run
) -> dict[int | None, tuple[Decimal, int]]:
    """(EE, valid names) per year from his calculator in the snapshot, one run per year
    because it counts a name once per file, and one for the candidates, whose year is NULL.
    `-B`, so it leaves no bytecode beside it."""
    years = [
        y for (y,) in conn.execute(f"SELECT DISTINCT year FROM rec r WHERE {where}").fetchall()
    ]
    calculated: dict[int | None, tuple[Decimal, int]] = {}
    for year in years:
        tag = "undated" if year is None else str(year)
        listing = run.tmp / f"netnew_{tag}.txt"
        only = "" if year is None else f" AND r.year = {year}"
        conn.execute(
            f"COPY (SELECT r.name FROM rec r WHERE {where}{only}) TO '{_quote(listing)}' "
            "(HEADER false)"
        )
        results = run.tmp / f"calculator_{tag}"
        done = subprocess.run(
            [
                sys.executable,
                "-B",
                str(run.snapshot / CALCULATOR),
                str(listing),
                "--output-dir",
                str(results),
            ],
            capture_output=True,
            text=True,
        )
        if done.returncode:
            raise SnapshotError(
                f"his calculator exited {done.returncode} on {tag}: {done.stderr.strip()[-200:]}"
            )
        summary = json.loads((results / "summary.json").read_text(encoding="utf-8"))
        calculated[year] = (
            Decimal(summary["equivalent_english_domains"]),
            int(summary["unique_valid_domains"]),
        )
    return calculated


def _tally(rows: list[tuple], calculated: dict[int | None, tuple[Decimal, int]]) -> dict:
    """The equivalent-English figures: EE from his calculator, the rest per (year, TLD).

    `english_weights` weighs the same groups in exact `Decimal`, for the TLD and hostname
    breakdowns, and must agree with his calculator to four decimals and on every name, or
    the price is refused: one of the two is not reading the table he scores with.
    """
    weights = english_weights()
    total = host_ee = beneath_ee = Decimal(0)
    pairs = via_www = hostnames = parent_held = beneath = 0
    by_year: dict[int, dict[str, object]] = {}
    by_tld: dict[str, dict[str, object]] = {}
    for year, tld, kind, count, aliases, hosts, held_parents in rows:
        weight = weights.get(tld, Decimal(0)) * count
        total += weight
        if kind == "hostname":
            host_ee += weight
            beneath += count - aliases
            beneath_ee += weights.get(tld, Decimal(0)) * (count - aliases)
        pairs += count
        via_www += aliases
        hostnames += hosts
        parent_held += held_parents
        if year is not None:
            slot = by_year.setdefault(int(year), {"pairs": 0, "ee": Decimal(0)})
            slot["pairs"] += count
            slot["ee"] += weight
        tld_slot = by_tld.setdefault(tld, {"pairs": 0, "ee": Decimal(0)})
        tld_slot["pairs"] += count
        tld_slot["ee"] += weight
    for year, (ee, valid) in calculated.items():
        ours, counted = (
            (total, pairs) if year is None else (by_year[year]["ee"], by_year[year]["pairs"])
        )
        what = "the candidates" if year is None else str(year)
        if valid != counted:
            raise SnapshotError(
                f"his calculator counts {valid} valid names for {what}, this {counted}"
            )
        if abs(ee - ours) >= EE_TOLERANCE:
            raise SnapshotError(f"his calculator says {ee} EE for {what}, english_weights {ours}")
        if year is not None:
            by_year[year]["ee"] = ee
    total = sum((ee for ee, _ in calculated.values()), Decimal(0))
    top = sorted(by_tld.items(), key=lambda kv: (-kv[1]["ee"], kv[0]))[:5]
    return {
        "netnew_pairs": pairs,
        "ee": f"{total:.4f}",
        "by_year": {
            str(y): {"pairs": v["pairs"], "ee": f"{v['ee']:.4f}"}
            for y, v in sorted(by_year.items())
        },
        "by_tld": [{"tld": t, "pairs": v["pairs"], "ee": f"{v['ee']:.4f}"} for t, v in top],
        # What share of the figure is `www.<parent>` rather than a name of its own. A
        # reviewer reading a finding is entitled to see that before crediting it.
        "www_alias_share": round(via_www / pairs, 4) if pairs else 0.0,
        "parent_held_share": round(parent_held / hostnames, 4) if hostnames else 0.0,
        "hostname_records": hostnames,
        # **What of this figure is hostname grain**, which on the candidate track is the
        # part that does not ship. `export.py` builds the candidate pool from registrable
        # domains plus the ISC survey hostnames and nothing else, while the candidate
        # filter here admits any name that is not `.arpa` and not already held. So a
        # hostname-grain source prices here and exports nowhere, and a leg that quotes the
        # headline alone reports EE the claim will never contain: `ddn-hosts-txt` was
        # confirmed at 6,401.3 EE this way on 2026-09-19 and ships 0.
        "ee_hostname": f"{host_ee:.4f}",
        # The unit `price_hostnames.py` quotes as NET-NEW hostname years: names beneath a
        # registrable, never the registrable itself and never `www.<parent>`.
        "netnew_hostname_years": beneath,
        "ee_hostname_years": f"{beneath_ee:.4f}",
    }


def _grouped(conn: duckdb.DuckDBPyConnection, where: str) -> list[tuple]:
    return conn.execute(
        f"""
        SELECT r.year, lower(split_part(r.name, '.', -1)) AS tld, r.kind, count(*),
               sum(CASE WHEN r.via_www THEN 1 ELSE 0 END),
               sum(CASE WHEN r.kind = 'hostname' THEN 1 ELSE 0 END),
               sum(CASE WHEN r.kind = 'hostname' AND r.parent_held THEN 1 ELSE 0 END)
        FROM rec r
        WHERE {where}
        GROUP BY 1, 2, 3
        """
    ).fetchall()


def price(
    snapshot: Path,
    items: Path,
    track: str = "annual",
    split: str = "auto",
    evidence_class: str | None = None,
) -> dict:
    """Price one items file against one snapshot. Reads only, and writes nothing outside a
    temporary directory it removes."""
    if track not in TRACKS:
        raise SnapshotError(f"track must be one of {', '.join(TRACKS)}, not {track!r}")
    if split not in SPLITS:
        raise SnapshotError(f"split must be one of {', '.join(SPLITS)}, not {split!r}")
    if not items.is_file():
        raise SnapshotError(f"{items} does not exist")
    manifest, manifest_sha = read_manifest(snapshot)
    verify_snapshot(snapshot, manifest)
    if track == "candidate":
        rule, applies = SPLIT_CANDIDATE, False
    elif split == "none":
        rule, applies = SPLIT_NONE, False
    elif takes_no_split(evidence_class):
        rule, applies = SPLIT_EXEMPT.format(head=class_head(evidence_class)), False
    else:
        rule, applies = SPLIT_AUTO, True

    with tempfile.TemporaryDirectory(prefix="price_snapshot_") as scratch:
        run = _Run(snapshot, manifest, Path(scratch))
        counts: Counter[str] = Counter()
        # In memory, spilling only into the scratch directory: a price writes nothing else.
        conn = duckdb.connect(":memory:", config={"temp_directory": scratch, "threads": 2})
        try:
            _leftovers(run, items, track, applies, counts, conn)
            if track == "annual":
                shipped = shipping_filter_for("r.name", "r.year")
            else:
                shipped = f"r.name NOT LIKE '%.arpa' AND {existed_predicate('r.name')}"
            where = shipped
            if applies:
                counts["split_dropped"] = conn.execute(
                    f"SELECT count(*) FROM rec r WHERE {where} AND r.free AND NOT r.dated"
                ).fetchone()[0]
                where = f"{where} AND (NOT r.free OR r.dated)"
            # of the names held nowhere, those no shipped file can carry
            counts["not_shippable"] = conn.execute(
                f"SELECT count(*) FROM rec r WHERE NOT ({shipped})"
            ).fetchone()[0]
            priced = _tally(_grouped(conn, where), _calculate(conn, where, run))
        finally:
            conn.close()
    return {
        "track": track,
        # The corroboration rule the figure used, by name, so a finding cannot quote a
        # figure before the split as one after it.
        "split": rule,
        **priced,
        "manifest_sha": manifest_sha,
        "snapshot_marker": manifest["marker"],
        "snapshot_built_at": manifest["built_at"],
        "counts": dict(sorted(counts.items())),
    }
