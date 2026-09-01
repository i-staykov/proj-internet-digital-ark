"""Hostname records: the second output unit, accepted by the reviewer on 2026-09-01.

His reply (verbatim in `private/personal-context.md`): both registrable domains and
valid hostnames are annual database records, registrables stay prioritized as query
seeds, and every distinct evidence-backed hostname beneath them is retained. So this
module fills `hostname_year` from raw CDX capture journals, one JSON object per
capture row (`{"url": ..., "timestamp": ...}`), the exact shape
`scripts/engines/cdx_suffix_sweep.py` has written since 2026-08-21.

The evidence wall is the one the registrable unit uses, unchanged:

- what dates one item is the row's own 14-digit capture timestamp (`cdx_timestamp`,
  master-eligible, approved), quoted in the evidence row;
- every `hostname_year` row foreign-keys one `evidence` row;
- the hostname must reduce to its parent registrable through the same
  `to_registrable` funnel every registrable passed, and a hostname that IS its own
  registrable is refused here, because that record belongs to `domain_year`.

The registrable half of the same journal is NOT this module's job:
`cdx_suffix_convert.py` already collapses capture rows into per-domain year sets for
the approved `cdx_snapshot` ingest, and both halves can be run over one journal.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
from collections import Counter
from pathlib import Path

import duckdb

from ark.canonical import to_registrable
from ark.ingest import ensure_source

logger = logging.getLogger(__name__)

SOURCE_NAME = "ia_cdx_hostnames"
# The reviewer accepts "valid hostnames": RFC 1123 letters, digits and hyphens only.
# The era's archives carry underscore NT-server names; those are refused here and the
# capture still evidences the parent registrable through the registrable path.
_VALID_HOST = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
YEARS = range(1996, 2002)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _host_of(url: str) -> str | None:
    """The hostname of a capture URL, lowercased, port and trailing dot stripped."""
    rest = url.split("://", 1)[-1]
    host = rest.split("/", 1)[0].split(":", 1)[0].strip().lower().rstrip(".")
    if not host or not _VALID_HOST.match(host):
        return None
    return host


def ingest_hostname_journal(
    conn: duckdb.DuckDBPyConnection, path: Path
) -> dict[str, int | str | bool]:
    """One journal of raw capture rows into hostname_year, idempotently."""
    stats: dict[str, int | str | bool] = {"file": path.name, "skipped": False}
    already = conn.execute(
        "SELECT count(*) FROM ingested_file WHERE source_name = ? AND file_name = ?",
        [SOURCE_NAME, path.name],
    ).fetchone()[0]
    if already:
        stats["skipped"] = True
        logger.info(f"{path.name}: already ingested, skipping")
        return stats

    counts: Counter[str] = Counter()
    # first seen capture per (host, year); the earliest stamp is the quoted evidence
    seen: dict[tuple[str, int], str] = {}
    opener = gzip.open if path.suffix == ".gz" else open
    try:
        with opener(path, "rt", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                counts["lines"] += 1
                try:
                    row = json.loads(line)
                except ValueError:
                    counts["unparseable"] += 1
                    continue
                ts = str(row.get("timestamp", ""))
                if len(ts) != 14 or not ts.isdigit():
                    counts["bad_timestamp"] += 1
                    continue
                year = int(ts[:4])
                if year not in YEARS:
                    counts["out_of_window"] += 1
                    continue
                host = _host_of(str(row.get("url", "")))
                if host is None:
                    counts["no_host"] += 1
                    continue
                key = (host, year)
                if key not in seen or ts < seen[key]:
                    seen[key] = ts
    except (EOFError, OSError):
        # a journal cut mid-write; what was read is real, the tail returns next sweep
        counts["truncated_tail"] += 1

    # the registrable funnel, once per distinct host
    parents: dict[str, str] = {}
    for host in {h for h, _ in seen}:
        reg = to_registrable(host)
        if reg is None:
            counts["rejected_host"] += 1
        elif reg == host:
            counts["registrable_row"] += 1  # belongs to domain_year, not here
        else:
            parents[host] = reg

    rows = [
        (host, parents[host], year, ts)
        for (host, year), ts in sorted(seen.items())
        if host in parents
    ]
    stats.update(counts)
    stats["hostname_year_candidates"] = len(rows)
    if rows:
        source_id = ensure_source(conn, SOURCE_NAME, "timestamped")
        conn.execute(
            "CREATE TEMP TABLE IF NOT EXISTS hostage "
            "(hostname TEXT, parent TEXT, year INTEGER, ts TEXT)"
        )
        conn.execute("DELETE FROM hostage")
        conn.executemany("INSERT INTO hostage VALUES (?, ?, ?, ?)", rows)
        conn.execute(
            r"""
            INSERT OR IGNORE INTO domain (domain, tld, discovered_source)
            SELECT DISTINCT parent, regexp_replace(parent, '^[^.]+\.', ''), ?
            FROM hostage
            """,
            [source_id],
        )
        before = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]
        conn.execute(
            """
            INSERT INTO evidence (domain, source_id, evidence_year, evidence_type,
                                  evidence_value, evidence_url, acquisition_method)
            SELECT h.parent, ?, h.year, 'cdx_timestamp',
                   'cdx capture ' || h.ts || ' ' || h.hostname,
                   'https://web.archive.org/web/' || h.ts || '/http://' || h.hostname || '/',
                   'ia_cdx_domain_sweep'
            FROM hostage h
            LEFT JOIN hostname_year hy
              ON hy.hostname = h.hostname AND hy.assigned_year = h.year
            WHERE hy.hostname IS NULL
            """,
            [source_id],
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO hostname_year
                (hostname, parent_domain, assigned_year, evidence_id)
            SELECT h.hostname, h.parent, h.year, e.evidence_id
            FROM hostage h
            JOIN evidence e
              ON e.domain = h.parent AND e.evidence_year = h.year
             AND e.evidence_value = 'cdx capture ' || h.ts || ' ' || h.hostname
            """,
        )
        after = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]
        stats["hostname_year_rows"] = after - before
        # A capture under the domain evidences the parent registrable in that year
        # too, in the same cdx_timestamp class: assign it, one row per (parent, year),
        # so the parent earns its year from the same observation.
        dy_before = conn.execute("SELECT count(*) FROM domain_year").fetchone()[0]
        conn.execute(
            """
            INSERT OR IGNORE INTO domain_year (domain, assigned_year, evidence_id)
            SELECT e.domain, e.evidence_year, min(e.evidence_id)
            FROM evidence e
            JOIN hostage h ON e.domain = h.parent AND e.evidence_year = h.year
             AND e.evidence_value = 'cdx capture ' || h.ts || ' ' || h.hostname
            GROUP BY e.domain, e.evidence_year
            """,
        )
        dy_after = conn.execute("SELECT count(*) FROM domain_year").fetchone()[0]
        stats["parent_year_rows"] = dy_after - dy_before
        conn.execute("DELETE FROM hostage")
    else:
        stats["hostname_year_rows"] = 0

    conn.execute(
        "INSERT INTO ingested_file (source_name, file_name, sha256, record_rows) "
        "VALUES (?, ?, ?, ?)",
        [SOURCE_NAME, path.name, _sha256(path), stats["hostname_year_rows"]],
    )
    logger.info(str(stats))
    return stats


def ingest_hostname_dir(
    conn: duckdb.DuckDBPyConnection, root: Path, pattern: str = "*.jsonl.gz"
) -> dict[str, int]:
    totals: Counter[str] = Counter()
    files = sorted(root.glob(pattern)) if root.is_dir() else [root]
    for i, path in enumerate(files, 1):
        stats = ingest_hostname_journal(conn, path)
        for key, value in stats.items():
            if isinstance(value, int) and not isinstance(value, bool):
                totals[key] += value
            elif key == "skipped" and value:
                totals["files_skipped"] += 1
        logger.info(f"[{i}/{len(files)}] {path.name} done")
    totals["files_seen"] = len(files)
    logger.info(f"hostnames: {dict(totals)}")
    return dict(totals)
