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
# One source row, two acquisition methods: the NYPW TimeMap parts re-emitted at hostname
# grain are the approved `nypw_timemaps` artifact read one level down, and the method
# column is what lets the shipped contribution table say which artifact a hostname came from.
NYPW_METHOD = "nypw_timemap_hostgrain"
SWEEP_METHOD = "ia_cdx_domain_sweep"


def source_for(path: Path) -> tuple[str, str]:
    """(source name, acquisition method) for one journal, from its filename family."""
    if path.name.startswith("nypw_"):
        return SOURCE_NAME, NYPW_METHOD
    return SOURCE_NAME, SWEEP_METHOD


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
    source_name, method = source_for(path)
    already = conn.execute(
        "SELECT count(*) FROM ingested_file WHERE source_name = ? AND file_name = ?",
        [source_name, path.name],
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
        source_id = ensure_source(conn, source_name, "timestamped")
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
                   ?
            FROM hostage h
            LEFT JOIN hostname_year hy
              ON hy.hostname = h.hostname AND hy.assigned_year = h.year
            WHERE hy.hostname IS NULL
            """,
            [source_id, method],
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
        [source_name, path.name, _sha256(path), stats["hostname_year_rows"]],
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


# The second hostname corpus inside an InterNIC zone file: the nameserver a delegation
# points AT. `parse_internic_zone` reads only the owner of an NS record and discards
# the target on purpose, because at registrable grain the target collapses to its
# operator, which the store already holds (register, 2026-08-29: 14,573 domains,
# 99.28% held at 1997). At hostname grain the same right-hand sides are 90% absent:
# `ns1.`/`ns2.` hosts are exactly what a web crawler never fetches. Same bytes, same
# SOA serial, same `artifact_listing` class Ivo decided master on 2026-08-24.
ZONE_SOURCE_NAME = "internic_zone_hostnames"
ZONE_METHOD = "internic_zone_ns_target"
# The Wayback capture that fixes when each 1997 file existed; the SOA serial inside the
# payload is what dates the records, the capture only says the file was there two days
# later. Files without a recorded capture get no URL, exactly as `internic_zone` rows do.
ZONE_CAPTURE_URLS = {
    "org.zone.gz": "https://web.archive.org/web/19970420113748id_/http://nic.mil/oroot.html/org.zone.gz",
    "edu.zone.gz": "https://web.archive.org/web/19970420112952id_/http://nic.mil/oroot.html/edu.zone.gz",
    "gov.zone.gz": "https://web.archive.org/web/19970420113002id_/http://nic.mil/oroot.html/gov.zone.gz",
}


def zone_ns_targets(path: Path, counts: Counter[str]) -> dict[str, str]:
    """hostname -> parent registrable for every NS target in one zone file.

    Indexed by the `NS` type token rather than by column, because a continuation line
    carries no owner and its first token is the TTL. Targets that are themselves
    registrables belong to `domain_year` and are counted, not kept.
    """
    from ark.sources import _open_text

    parents: dict[str, str] = {}
    with _open_text(path) as fh:
        for line in fh:
            tokens = line.split()
            idx = next((i for i in range(1, min(5, len(tokens))) if tokens[i] == "NS"), None)
            if idx is None or idx + 1 >= len(tokens):
                continue
            counts["ns_records"] += 1
            host = tokens[idx + 1].rstrip(".").lower()
            if host in parents:
                continue
            if not _VALID_HOST.match(host):
                counts["rejected_host"] += 1
                continue
            reg = to_registrable(host)
            if reg is None:
                counts["rejected_host"] += 1
            elif reg == host:
                counts["registrable_row"] += 1
            else:
                parents[host] = reg
    return parents


def ingest_zone_hostnames(
    conn: duckdb.DuckDBPyConnection, path: Path
) -> dict[str, int | str | bool]:
    """One InterNIC zone file's NS targets into hostname_year, idempotently."""
    from ark import approvals
    from ark.sources import _internic_zone_header, _serial_of

    stats: dict[str, int | str | bool] = {"file": path.name, "skipped": False}
    already = conn.execute(
        "SELECT count(*) FROM ingested_file WHERE source_name LIKE ? AND file_name = ?",
        [ZONE_SOURCE_NAME + "%", path.name],
    ).fetchone()[0]
    if already:
        stats["skipped"] = True
        logger.info(f"{path.name}: already ingested, skipping")
        return stats
    header = _internic_zone_header(path)
    if header is None or header[1] not in YEARS:
        stats["out_of_window_file"] = 1
        logger.info(f"{path.name}: no in-window SOA serial, skipping")
        return stats
    apex, year = header
    # One source row per zone year, because the two lanes stand on different terms: the
    # 1997 files are the nic.mil captures Ivo decided on, the 1999 files came off a
    # mirror whose refusal is still unresolved in the register, so they wait for their
    # own Decision line and the 1997 approval cannot be borrowed for them.
    source_name = ZONE_SOURCE_NAME if year == 1997 else f"{ZONE_SOURCE_NAME}_{year}"
    approvals.check(source_name, "artifact_listing")
    zone = apex.lower() or "root"
    serial = _serial_of(path)
    counts: Counter[str] = Counter()
    parents = zone_ns_targets(path, counts)
    rows = [(host, parents[host], year) for host in sorted(parents)]
    stats.update(counts)
    stats["hostname_year_candidates"] = len(rows)
    if rows:
        source_id = ensure_source(conn, source_name, "timestamped")
        prefix = f"internic {zone} zone serial {serial} NS "
        conn.execute(
            "CREATE TEMP TABLE IF NOT EXISTS zonehost (hostname TEXT, parent TEXT, year INTEGER)"
        )
        conn.execute("DELETE FROM zonehost")
        conn.executemany("INSERT INTO zonehost VALUES (?, ?, ?)", rows)
        conn.execute(
            r"""
            INSERT OR IGNORE INTO domain (domain, tld, discovered_source)
            SELECT DISTINCT parent, regexp_replace(parent, '^[^.]+\.', ''), ?
            FROM zonehost
            """,
            [source_id],
        )
        before = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]
        conn.execute(
            """
            INSERT INTO evidence (domain, source_id, evidence_year, evidence_type,
                                  evidence_value, evidence_url, acquisition_method)
            SELECT z.parent, ?, z.year, 'artifact_listing', ? || z.hostname, ?, ?
            FROM zonehost z
            LEFT JOIN hostname_year hy
              ON hy.hostname = z.hostname AND hy.assigned_year = z.year
            WHERE hy.hostname IS NULL
            """,
            [source_id, prefix, ZONE_CAPTURE_URLS.get(path.name), ZONE_METHOD],
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO hostname_year
                (hostname, parent_domain, assigned_year, evidence_id)
            SELECT z.hostname, z.parent, z.year, e.evidence_id
            FROM zonehost z
            JOIN evidence e
              ON e.domain = z.parent AND e.evidence_year = z.year
             AND e.evidence_value = ? || z.hostname
            """,
            [prefix],
        )
        after = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]
        stats["hostname_year_rows"] = after - before
        # The registry serving `ns1.foo.com` for a delegation is also its statement
        # that foo.com existed that day, the same class at registrable grain, so the
        # parent earns its year from the same row (the check `nothing_earned_is_left_
        # unassigned` requires it). Almost all are already held; the rest are the 63
        # pairs the 2026-08-29 registrable-grain measurement found and closed on yield.
        dy_before = conn.execute("SELECT count(*) FROM domain_year").fetchone()[0]
        conn.execute(
            """
            INSERT OR IGNORE INTO domain_year (domain, assigned_year, evidence_id)
            SELECT e.domain, e.evidence_year, min(e.evidence_id)
            FROM evidence e
            JOIN zonehost z ON e.domain = z.parent AND e.evidence_year = z.year
             AND e.evidence_value = ? || z.hostname
            GROUP BY e.domain, e.evidence_year
            """,
            [prefix],
        )
        dy_after = conn.execute("SELECT count(*) FROM domain_year").fetchone()[0]
        stats["parent_year_rows"] = dy_after - dy_before
        conn.execute("DELETE FROM zonehost")
    else:
        stats["hostname_year_rows"] = 0
    conn.execute(
        "INSERT INTO ingested_file (source_name, file_name, sha256, record_rows) "
        "VALUES (?, ?, ?, ?)",
        [source_name, path.name, _sha256(path), stats["hostname_year_rows"]],
    )
    logger.info(str(stats))
    return stats
