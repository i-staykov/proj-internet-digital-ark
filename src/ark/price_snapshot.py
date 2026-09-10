"""The one price a fleet leg may quote, measured against a snapshot instead of the store.

**Why a third pricer, when `price_items.py` and `price_hostnames.py` exist.** Both read
`data/ark.duckdb`, which lives on the laptop and is 52 GB. A fleet runner has neither, so
until now a price leg had no way to answer "is this net-new" and every leg that tried
invented its own arithmetic. That is how a 1,180,003 EE claim reached the register and was
re-priced at about a two-hundredth of it. This prices against a directory the laptop
builds and pushes, `scripts/harness/sync_fleet.sh`, so a leg measures rather than guesses,
and one command's output is the only figure a finding is allowed to carry.

**The snapshot is a set of name lists and a manifest, nothing else.**

    <marker>/{1996..2001}.txt   the reviewer's current baseline, his files
    netnew/{year}*.txt          our last export for that year, not yet in his baseline
    candidates/*.txt            his candidate pool and ours, the second scored track
    manifest.json               {marker, built_at, files: {path: {lines, sha256}}}

Every file the manifest names is hashed before a single item is priced, and a file whose
digest, line count or presence disagrees with the manifest refuses the whole run. A
zero-line file refuses it too: an empty held-set silently makes everything look net-new,
which is the single most flattering way this can be wrong.

**The two rules the funnel applies are the ingest's own, not new ones.**

- *the hostname rule*: a name that IS its registrable is a `domain_year` record, a name
  beneath one is a `hostname_year` record, and a name that reduces to nothing is refused.
  Neither form infers the other: a held parent does not make its child held, and a held
  child does not make the parent held, so membership is tested on the exact name only.
- *the `www.` rule* (ADR-009 and ADR-010, his own words): `www.<registrable>` is a record
  in its own right, and it is NOT folded onto the parent. "The existence of the bare parent
  does not automatically establish the www hostname, nor does the presence of www
  automatically establish the bare hostname", so a `www.` item prices `www.<parent>` and
  nothing else. The share of the figure that arrived in that form is reported rather than
  hidden: a corpus made mostly of `www.` names is a real claim, and a distinct one from a
  claim about the parents, which is why the store carries a check for each direction.

**The corroboration split is not applied, and every result says so** in its `split` field.
This is the whole net-new set, which is `price_items.py`'s "BEFORE the split" line; the
split needs the store's attestation of a name in some other year, and a snapshot carries
year files rather than evidence. So `ee` is an upper bound on what an annual submission of
the same corpus would be credited, and a finding may not quote it as a post-split figure.

Items stream in and are inserted in batches, so a 10M-item file costs the same memory as a
10-item one, and the held sets are loaded restricted to the names actually asked about
rather than in full: his 2001 file alone is 18.5M names. DuckDB runs in memory under
`ARK_DB_MEMORY_LIMIT`, the same knob the store honours.

    uv run ark price-snapshot --snapshot /projects/ark-data --items items.jsonl
    uv run ark price-snapshot --snapshot /projects/ark-data --items names.jsonl.gz \\
        --track candidate
"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import duckdb

from ark.canonical import to_registrable
from ark.db import connect
from ark.delegation import existed_predicate, shipping_filter_for
from ark.english_share import english_weights
from ark.hostnames import YEARS, host_of

MANIFEST_NAME = "manifest.json"
NETNEW_DIR = "netnew"
CANDIDATES_DIR = "candidates"
TRACKS = ("annual", "candidate")
# Printed in every result, because the figure is `price_items.py`'s pre-split number and a
# finding that quoted it as a post-split one would overstate an annual claim.
SPLIT = "none, exact-name membership, pre-corroboration"
# The name files hold one name per line and no delimiter at all, so read_csv is given a
# byte that cannot occur in one. Written as a real control character rather than as the
# escape `\x01`, which reaches DuckDB as four literal characters and only works because
# a delimiter that never matches leaves the line whole.
DELIM = chr(1)
# Items are inserted this many at a time. Large enough that the insert is not the cost of
# the run, small enough that peak memory does not depend on the size of the corpus.
BATCH = 100_000


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


def build_manifest(
    marker: str, files: dict[str, Path], optional: Iterable[str] = ()
) -> tuple[dict, list[str]]:
    """The manifest for a snapshot, and the optional entries left out for being empty.

    A required file that is missing or empty raises: those are the reviewer's year files,
    and pricing against a snapshot without them would report every name as net-new. An
    optional entry may legitimately be empty (a year in which one export family found
    nothing), so it is dropped from the snapshot rather than shipped as a zero-line file.
    """
    optional = set(optional)
    entries: dict[str, dict[str, int | str]] = {}
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
    if not entries:
        raise SnapshotError("a snapshot with no files cannot be priced against")
    manifest = {
        "marker": marker,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
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
    for directory in (manifest["marker"], NETNEW_DIR, CANDIDATES_DIR):
        root = snapshot / directory
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.txt")):
            rel = f"{directory}/{path.name}"
            if rel not in listed:
                raise SnapshotError(f"{rel} is in the snapshot and not in the manifest")


def _opener(path: Path):  # noqa: ANN202 - a text handle of either kind
    return gzip.open(path, "rt", errors="replace") if path.suffix == ".gz" else path.open()


def _year_of(record: dict) -> int | None:
    """The record's own year, or None when it has none inside the window."""
    raw = record.get("year")
    if raw is None:
        return None
    try:
        year = int(raw)
    except (TypeError, ValueError):
        return None
    return year if year in YEARS else None


def _records(items: Path, track: str, counts: Counter[str]) -> Iterator[tuple]:
    """One row per (name, year) the funnel accepts, streamed and never accumulated.

    `host` is the field; `text` is accepted beside it and split on whitespace, which is the
    shape `price_hostnames.py --items` already reads, so an extraction written for one
    pricer does not have to be rewritten for the other.
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
                counts["unparseable"] += 1
                continue
            year = _year_of(record)
            if track == "annual" and year is None:
                counts["undated_or_out_of_window"] += 1
                continue
            # The candidate track claims no year, so one is not carried even when given.
            year = None if track == "candidate" else year
            raw_hosts = []
            if record.get("host"):
                raw_hosts.append(str(record["host"]))
            if record.get("text"):
                raw_hosts.extend(str(record["text"]).split())
            if not raw_hosts:
                counts["no_host"] += 1
                continue
            for raw in raw_hosts:
                host = host_of(raw)
                if host is None:
                    counts["no_host"] += 1
                    continue
                registrable = to_registrable(host)
                if registrable is None:
                    counts["rejected_host"] += 1
                    continue
                if host == registrable:
                    yield registrable, year, None, "registrable", False
                elif host == f"www.{registrable}":
                    counts["www_of_parent"] += 1
                    yield host, year, registrable, "hostname", True
                else:
                    yield host, year, registrable, "hostname", False


def _load_items(conn: duckdb.DuckDBPyConnection, items: Path, track: str) -> Counter[str]:
    conn.execute(
        "CREATE TABLE item (name TEXT, year INTEGER, parent TEXT, kind TEXT, via_www BOOLEAN)"
    )
    counts: Counter[str] = Counter()
    batch: list[tuple] = []
    for row in _records(items, track, counts):
        batch.append(row)
        if len(batch) >= BATCH:
            conn.executemany("INSERT INTO item VALUES (?, ?, ?, ?, ?)", batch)
            batch.clear()
    if batch:
        conn.executemany("INSERT INTO item VALUES (?, ?, ?, ?, ?)", batch)
    # One row per record priced. `kind`, `parent` and `via_www` are properties of the name
    # itself, so the same name cannot arrive with two of them and `any_value` is exact.
    conn.execute(
        """
        CREATE TABLE rec AS
        SELECT name, year, any_value(parent) AS parent, any_value(kind) AS kind,
               any_value(via_www) AS via_www
        FROM item GROUP BY name, year
        """
    )
    return counts


def _quote(path: Path) -> str:
    return str(path).replace("'", "''")


def _load_held(conn: duckdb.DuckDBPyConnection, snapshot: Path, manifest: dict, track: str) -> None:
    """The annual held-set, restricted to the names this run actually asks about.

    Loading his 2001 file in full is 18.5M names; loading the few thousand of them a leg
    asked about is nothing. Both halves are the same namespace, which is why one table
    holds them: his baseline year file and our net-new export for the same year both carry
    registrables and the hostnames beneath them, and a name in either is not ours to
    report again.
    """
    conn.execute("CREATE TABLE held (name TEXT, year INTEGER)")
    listed = set(manifest["files"])
    for year in YEARS:
        files = [f"{manifest['marker']}/{year}.txt"] + sorted(
            rel for rel in listed if rel.startswith(f"{NETNEW_DIR}/{year}") and rel.endswith(".txt")
        )
        for rel in files:
            if rel not in listed:
                continue
            if track == "annual":
                asked = (
                    f"SELECT name FROM rec WHERE year = {year} "
                    f"UNION SELECT parent FROM rec WHERE year = {year} AND parent IS NOT NULL"
                )
            else:
                asked = "SELECT name FROM rec UNION SELECT parent FROM rec WHERE parent IS NOT NULL"
            conn.execute(
                f"""
                INSERT INTO held
                SELECT lower(trim(column0)), {year}
                FROM read_csv('{_quote(snapshot / rel)}', header=false, delim='{DELIM}',
                              columns={{'column0': 'VARCHAR'}})
                WHERE lower(trim(column0)) IN ({asked})
                """
            )


def _load_candidates(conn: duckdb.DuckDBPyConnection, snapshot: Path, manifest: dict) -> None:
    conn.execute("CREATE TABLE held_candidate (name TEXT)")
    for rel in sorted(manifest["files"]):
        if not rel.startswith(f"{CANDIDATES_DIR}/") or not rel.endswith(".txt"):
            continue
        conn.execute(
            f"""
            INSERT INTO held_candidate
            SELECT lower(trim(column0))
            FROM read_csv('{_quote(snapshot / rel)}', header=false, delim='{DELIM}',
                          columns={{'column0': 'VARCHAR'}})
            WHERE lower(trim(column0)) IN (SELECT name FROM rec)
            """
        )


def _tally(rows: list[tuple]) -> dict:
    """Turn the per (year, TLD) counts into the equivalent-English figures.

    Aggregated in SQL and weighted here, so the EE total is exact `Decimal` arithmetic over
    a few hundred groups rather than a float sum over millions of rows. His figures are
    exact to four decimal places and binary floating point does not reproduce them.
    """
    weights = english_weights()
    total = Decimal(0)
    pairs = via_www = hostnames = parent_held = 0
    by_year: dict[int, dict[str, object]] = {}
    by_tld: dict[str, dict[str, object]] = {}
    for year, tld, count, aliases, hosts, held_parents in rows:
        weight = weights.get(tld, Decimal(0)) * count
        total += weight
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
    }


def _grouped(conn: duckdb.DuckDBPyConnection, where: str, held_parent: str) -> list[tuple]:
    return conn.execute(
        f"""
        SELECT r.year, lower(split_part(r.name, '.', -1)) AS tld, count(*),
               sum(CASE WHEN r.via_www THEN 1 ELSE 0 END),
               sum(CASE WHEN r.kind = 'hostname' THEN 1 ELSE 0 END),
               sum(CASE WHEN r.kind = 'hostname' AND {held_parent} THEN 1 ELSE 0 END)
        FROM rec r
        WHERE {where}
        GROUP BY 1, 2
        """
    ).fetchall()


def price(snapshot: Path, items: Path, track: str = "annual") -> dict:
    """Price one items file against one snapshot. Reads only, writes nothing."""
    if track not in TRACKS:
        raise SnapshotError(f"track must be one of {', '.join(TRACKS)}, not {track!r}")
    if not items.is_file():
        raise SnapshotError(f"{items} does not exist")
    manifest, manifest_sha = read_manifest(snapshot)
    verify_snapshot(snapshot, manifest)

    conn = connect(":memory:")
    try:
        counts = _load_items(conn, items, track)
        _load_held(conn, snapshot, manifest, track)
        # An anti-join, not a LEFT JOIN: a name that sits in his baseline and in one of our
        # export families would be counted twice by a join and once by this.
        not_held = "NOT EXISTS (SELECT 1 FROM held h WHERE h.name = r.name AND h.year = r.year)"
        held_parent = "EXISTS (SELECT 1 FROM held h WHERE h.name = r.parent AND h.year = r.year)"
        if track == "annual":
            shipped = shipping_filter_for("r.name", "r.year")
            where = f"{not_held} AND {shipped}"
        else:
            _load_candidates(conn, snapshot, manifest)
            # A candidate must not already sit in an annual file, his or ours, and the year
            # a name is held under does not matter: it is not a candidate any more.
            not_held = "NOT EXISTS (SELECT 1 FROM held h WHERE h.name = r.name)"
            held_parent = "EXISTS (SELECT 1 FROM held h WHERE h.name = r.parent)"
            in_pool = "EXISTS (SELECT 1 FROM held_candidate c WHERE c.name = r.name)"
            shipped = f"r.name NOT LIKE '%.arpa' AND {existed_predicate('r.name')}"
            where = f"{not_held} AND NOT {in_pool} AND {shipped}"
            counts["already_in_candidate_pool"] = conn.execute(
                f"SELECT count(*) FROM rec r WHERE {in_pool}"
            ).fetchone()[0]
        counts["records_priced"] = conn.execute("SELECT count(*) FROM rec").fetchone()[0]
        counts["already_held"] = conn.execute(
            f"SELECT count(*) FROM rec r WHERE NOT ({not_held})"
        ).fetchone()[0]
        counts["not_shippable"] = conn.execute(
            f"SELECT count(*) FROM rec r WHERE NOT ({shipped})"
        ).fetchone()[0]
        priced = _tally(_grouped(conn, where, held_parent))
    finally:
        conn.close()
    return {
        "track": track,
        # **The corroboration split is NOT applied here**, and a reader of a finding has to
        # be told rather than left to assume. `price_items.py` splits its net-new set into a
        # corroborated half (the domain is already attested in some year) and a
        # candidate-pool half, and quotes only the first; this figure is the whole of it,
        # which is that tool's "BEFORE the split" line. On a snapshot the split cannot be
        # computed: it needs the store's attestation, and the snapshot carries year files,
        # not evidence. So a leg's `ee` is an upper bound on what an annual submission of
        # the same corpus would be credited.
        "split": SPLIT,
        **priced,
        "manifest_sha": manifest_sha,
        "snapshot_marker": manifest["marker"],
        "snapshot_built_at": manifest["built_at"],
        "counts": dict(sorted(counts.items())),
    }
