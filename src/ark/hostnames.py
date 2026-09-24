"""Hostname records: the second output unit.

Both registrable domains and valid hostnames are annual database records; registrables stay
prioritised as query seeds and every distinct evidence-backed hostname beneath them is
retained. This module fills `hostname_year` from raw CDX capture journals, one JSON object
per capture row (`{"url": ..., "timestamp": ...}`), the shape
`scripts/engines/cdx_suffix_sweep.py` writes.

The evidence wall is the registrable unit's, unchanged:

- what dates one item is the row's own 14-digit capture timestamp (`cdx_timestamp`),
  quoted in the evidence row;
- every `hostname_year` row foreign-keys one `evidence` row;
- the hostname must reduce to its parent registrable through the same `to_registrable`
  funnel, and a hostname that IS its own registrable is refused here, because that record
  belongs to `domain_year`;
- **the observation must show the host IN USE**, a capture of a URL on it or a URL listing
  naming it. A DNS listing (a reverse walk, an `nserver:`, an NS target) proves a machine
  answered, not a site, so those lanes date the parent registrable and write no hostname
  year. C-83 admits one non-web observation by name, the `Received: ... by <host>` clause
  of a dated message. Spec XIII narrows what such a record may ENTER an annual file with:
  only exact-host year-specific web evidence, the rest being candidates;
- **`www.<parent>` is its own record** (ADR-009/ADR-010) and neither form establishes the
  other, so a `www.` capture dates that host and NOT the bare parent.

The registrable half of the same journal is `cdx_suffix_convert.py`'s job: captures whose host
IS the registrable, collapsed into per-domain year sets for the `cdx_snapshot` ingest.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import duckdb
from loguru import logger

from ark.canonical import to_registrable
from ark.ingest import ensure_source

SOURCE_NAME = "ia_cdx_hostnames"
# One source row, two acquisition methods: the NYPW TimeMap parts re-emitted at hostname
# grain are the approved `nypw_timemaps` artifact read one level down, and the method
# column is what lets the shipped contribution table say which artifact a hostname came from.
NYPW_METHOD = "nypw_timemap_hostgrain"
SWEEP_METHOD = "ia_cdx_domain_sweep"
# Two bulk CDX artifacts re-emitted the same way, each under its own source row because the
# approval, the lineage note and the contribution table name them separately: IA's Early Web
# index (banked at registrable grain as `early_web_cdx`) and the USFEDGOV-EXTRACT-2001
# merged ZipNum index.
EARLY_WEB_SOURCE = "early_web_cdx_hostnames"
EARLY_WEB_METHOD = "early_web_hostgrain"
USFEDGOV_SOURCE = "usfedgov_extract_hostnames"
USFEDGOV_METHOD = "usfedgov_extract_hostgrain"
# Arquivo.pt's donated IA index, read at hostname grain on Ivo's ruling (C-81). Its OWN source
# row, not the IA sweep's: it is a different archive with its own terms, which require the
# citation "[fonte: Arquivo.pt, dd/mm/aaaa]", so a row of it must not read as an IA capture.
ARQUIVO_SOURCE = "arquivo_ia_hostnames"
ARQUIVO_METHOD = "arquivo_ia_cdxj_hostgrain"
# The IA's `Poland_pl-ccTLD_2001-12-31` extraction, item-level CDX. Same class and artifact
# shape as USFEDGOV-EXTRACT, its own source row because it is its own collection with its
# own terms: the ARCs beside these indexes are `private: true` and are never fetched, and
# the collection is flagged `access-restricted-item` while every index file is served
# without login.
POLAND_SOURCE = "poland_pl_extract_hostnames"
POLAND_METHOD = "poland_pl_extract_hostgrain"
# The Internet Archive's per-item aggregate CDX beside the DARTMOUTH-NBER-RESEARCH-2017 ARCs:
# a bulk IA CDX file, read at hostname grain for the items whose stamps fall in the window
# (found 2026-09-21 by the fleet at 5,107 EE on a tenth of one item). Its own source row
# because it is its own collection; the method is the allowlist's bulk-CDX name, since a row
# is an IA capture with the URL and stamp retained, which is XIII's reference pattern.
DARTMOUTH_ARCS_SOURCE = "dartmouth_arcs_cdx_hostnames"
DARTMOUTH_ARCS_METHOD = "bulk_cdx_file"

# The public CDX of one IA storage node, item `host_cdx_ia600702`, the same class read the same
# way (2026-09-21). Its own source row because it is a different collection.
HOSTCDX_SOURCE = "ia_node_host_cdx_hostnames"
HOSTCDX_METHOD = DARTMOUTH_ARCS_METHOD


# The gap engine's own journals, re-emitted at hostname grain. Same source row as the suffix
# sweep, because both are IA CDX responses, and its own method so the contribution table can
# say which query shape found a host.
GAP_METHOD = "ia_cdx_gap_hostgrain"
# The availability engine's rows about another host than the one asked, almost always the
# `www.` form: the same IA capture index through `wayback/available`, named as such.
AVAILABILITY_METHOD = "wayback_availability"


def source_for(path: Path) -> tuple[str, str]:
    """(source name, acquisition method) for one journal, from its filename family."""
    if path.name.startswith("cdx_gap_"):
        return SOURCE_NAME, GAP_METHOD
    if path.name.startswith("availability_host_"):
        return SOURCE_NAME, AVAILABILITY_METHOD
    if path.name.startswith("nypw_"):
        return SOURCE_NAME, NYPW_METHOD
    if path.name.startswith("early_web_"):
        return EARLY_WEB_SOURCE, EARLY_WEB_METHOD
    if path.name.startswith("usfedgov_"):
        return USFEDGOV_SOURCE, USFEDGOV_METHOD
    if path.name.startswith("arquivo_"):
        return ARQUIVO_SOURCE, ARQUIVO_METHOD
    if path.name.startswith("poland_pl_"):
        return POLAND_SOURCE, POLAND_METHOD
    if path.name.startswith("dartmouth_arcs_"):
        return DARTMOUTH_ARCS_SOURCE, DARTMOUTH_ARCS_METHOD
    if path.name.startswith("hostcdx_"):
        return HOSTCDX_SOURCE, HOSTCDX_METHOD
    return SOURCE_NAME, SWEEP_METHOD


# The lanes whose observation shows the host IN USE in the year. Only these write
# hostname_year; a lane missing here still runs and still dates the parent registrable
# from the same row, so nothing is lost if the reviewer later rules DNS listings count.
# Every member but the last is a web-serving observation, which is what the set held
# until C-83. The name is kept because `ark check`, two round scripts and a test read it.
WEB_FACING_HOST_SOURCES = frozenset(
    {
        SOURCE_NAME,
        EARLY_WEB_SOURCE,
        USFEDGOV_SOURCE,
        ARQUIVO_SOURCE,
        POLAND_SOURCE,
        DARTMOUTH_ARCS_SOURCE,
        HOSTCDX_SOURCE,
        "squidguard_2001_hostnames",
        "chastity_list_hostnames",
        # `USENET_SOURCE`, spelled out because it is defined with its own ingest further down.
        # A person typing `http://host/` in a post is naming a host that served them a page.
        "usenet_body_url_hostnames",
        # The same shape in a dated mailing-list message (`MAILLIST_FAMILY`, 2026-09-04).
        "maillist_body_url_hostnames",
        # And in a dated message of the released Enron mailbox (`ENRON_FAMILY`, 2026-09-04).
        "enron_body_url_hostnames",
        # The one non-web observation in this set (`APACHE_FAMILY`, C-83). A
        # `Received: ... by <host>` clause is written by the MTA at that host, about itself,
        # in a message the ASF's own archive dated independently. It proves the host was in
        # use rather than that it served a page, the reading his section IV.1 allows.
        "apache_list_header_hostnames",
        # The same clause in the IETF mail archive (`IETF_FAMILY`, C-83 at a second host).
        "ietf_list_header_hostnames",
        # And the news-server twin (`USENET_HEADER_FAMILY`). An `X-Trace`,
        # `NNTP-Posting-Host` or final `Path` hop is written by the server that accepted the
        # article, about itself or the machine it came from, in a transaction it completed.
        # Same reading as C-83, different protocol.
        "usenet_header_fqdn_hostnames",
    }
)
# `www.<parent>` is a record here, per ADR-009 and his section XI ("a valid base hostname and
# distinct valid subdomain hostnames may each be annual records when each has year-specific
# evidence"). The shape is native to his own corpus: 1,450,310 of his names begin `www.`,
# 1,221,065 with the bare name in the SAME year file, 114,875 of those from nobody but him.


def writes_hostname_years(source_name: str) -> bool:
    """Whether a lane's observation is web-facing and so may write hostname records."""
    return source_name in WEB_FACING_HOST_SOURCES


# His structural rule, verbatim: "A valid annual hostname must have dot-separated labels, use
# letters, digits, and interior hyphens only, and end in an alphabetic TLD label."
#
# The era's archives carry underscore NT-server names; those are refused here and by the
# exact-host registrable converter, so such a capture dates nothing.
#
# **The final `\.[a-z]+` is the alphabetic TLD label.** `to_registrable` also consults the
# public suffix list, so this catches nothing today, but "no violations today" and "cannot
# violate" are different properties and only the second survives a new source.
_VALID_HOST = re.compile(
    r"^(?=.{1,253}$)"
    r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*\.[a-z]{2,63}$"
)
YEARS = range(1996, 2002)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def host_of(url: str) -> str | None:
    """The hostname of a capture URL, lowercased, port and trailing dot stripped."""
    rest = url.split("://", 1)[-1]
    host = rest.split("/", 1)[0].split(":", 1)[0].strip().lower().rstrip(".")
    if not host or not _VALID_HOST.match(host):
        return None
    return host


def ingest_hostname_journal(
    conn: duckdb.DuckDBPyConnection, path: Path, ledger: set[tuple[str, str, str]] | None = None
) -> dict[str, int | str | bool]:
    """One journal of raw capture rows into hostname_year, idempotently."""
    from ark import approvals

    stats: dict[str, int | str | bool] = {"file": path.name, "skipped": False}
    source_name, method = source_for(path)
    # **Skip on the CONTENT, not on the name**, because `cdx_suffix_sweep.py` appends to its
    # journal under the journal's FINAL name, one batch per index page, for hours. A name-only
    # ledger marks a live journal done at whatever length it happened to have, and every row
    # written afterwards is never read. The `.part`-then-rename convention does not cover an
    # append-style collector; this does, for every lane at once.
    digest = _sha256(path)
    # **One query for the whole directory, not one per file.** The check itself is cheap;
    # asking the store 24,664 times is not, and at ~60ms of round trip each that was 24
    # minutes of a 25 minute run. `ingest_hostname_dir` reads the ledger once and passes
    # it; a caller with no ledger still asks, so a single-file ingest is unchanged.
    if ledger is not None:
        already = (source_name, path.name, digest) in ledger
    else:
        already = bool(
            conn.execute(
                "SELECT count(*) FROM ingested_file "
                "WHERE source_name = ? AND file_name = ? AND sha256 = ?",
                [source_name, path.name, digest],
            ).fetchone()[0]
        )
    if already:
        stats["skipped"] = True
        # debug, not info: in a directory of 24,664 journals this line alone wrote 24,664
        # rows to the log every run, and it says nothing a reader wants.
        logger.debug(f"{path.name}: already ingested, skipping")
        return stats
    # The same gate every other master-eligible ingest passes: a journal family with no
    # `Decision: master` line behind its source row is refused before anything is read.
    approvals.check(source_name, "cdx_timestamp")

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
                host = host_of(str(row.get("url", "")))
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
        # A capture under the domain evidences the parent registrable in that year too, in
        # the same cdx_timestamp class: one row per (parent, year).
        #
        # **Except `www.` in front of the parent** (ADR-010, his words): "the existence of
        # the bare parent does not automatically establish the www hostname, nor does the
        # presence of www automatically establish the bare hostname". Letting it through
        # ships one observation as two records, in `additions/` and in `hostnames/`. Any
        # OTHER subdomain still dates the parent, so the exclusion names that one shape.
        dy_before = conn.execute("SELECT count(*) FROM domain_year").fetchone()[0]
        conn.execute(
            """
            INSERT OR IGNORE INTO domain_year (domain, assigned_year, evidence_id)
            SELECT e.domain, e.evidence_year, min(e.evidence_id)
            FROM evidence e
            JOIN hostage h ON e.domain = h.parent AND e.evidence_year = h.year
             AND e.evidence_value = 'cdx capture ' || h.ts || ' ' || h.hostname
            WHERE h.hostname <> 'www.' || h.parent
            GROUP BY e.domain, e.evidence_year
            """,
        )
        dy_after = conn.execute("SELECT count(*) FROM domain_year").fetchone()[0]
        stats["parent_year_rows"] = dy_after - dy_before
        conn.execute("DELETE FROM hostage")
    else:
        stats["hostname_year_rows"] = 0

    # `ingested_file` is keyed on (source_name, file_name), so a grown journal UPDATES its
    # row to the new digest rather than adding one. `record_rows` accumulates, because the
    # journal really did yield rows on both passes and the total is what the ledger is for.
    conn.execute(
        "INSERT INTO ingested_file (source_name, file_name, sha256, record_rows) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT (source_name, file_name) DO UPDATE SET sha256 = excluded.sha256, "
        "record_rows = ingested_file.record_rows + excluded.record_rows",
        [source_name, path.name, digest, stats["hostname_year_rows"]],
    )
    logger.info(str(stats))
    return stats


def ingest_hostname_dir(
    conn: duckdb.DuckDBPyConnection, root: Path, pattern: str = "*.jsonl.gz"
) -> dict[str, int]:
    totals: Counter[str] = Counter()
    files = sorted(root.glob(pattern)) if root.is_dir() else [root]
    # The whole ledger, once. It is one row per file ever ingested, so it costs a few MB
    # of memory and saves one round trip per file in the directory.
    ledger = {
        (str(s), str(f), str(h))
        for s, f, h in conn.execute(
            "SELECT source_name, file_name, sha256 FROM ingested_file"
        ).fetchall()
    }
    logger.info(f"ledger: {len(ledger):,} files already ingested, read in one query")
    for i, path in enumerate(files, 1):
        stats = ingest_hostname_journal(conn, path, ledger=ledger)
        for key, value in stats.items():
            if isinstance(value, int) and not isinstance(value, bool):
                totals[key] += value
            elif key == "skipped" and value:
                totals["files_skipped"] += 1
        if not stats.get("skipped") or i % 2000 == 0 or i == len(files):
            logger.info(f"[{i}/{len(files)}] {path.name} done")
    totals["files_seen"] = len(files)
    logger.info(f"hostnames: {dict(totals)}")
    return dict(totals)


# The second hostname corpus inside an InterNIC zone file: the nameserver a delegation
# points AT. `parse_internic_zone` discards the target on purpose, because at registrable
# grain it collapses to its operator, which the store holds (14,573 domains, 99.28% held at
# 1997). At hostname grain the same right-hand sides are 90% absent: `ns1.`/`ns2.` hosts are
# what a web crawler never fetches. Same bytes, same SOA serial, same `artifact_listing`.
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
        if writes_hostname_years(source_name):
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


# The third hostname corpus: the sub-registrable hosts inside two blocklists already banked
# at registrable grain, squidGuard 1.2.0's robot-compiled 2001-12 lists (10,376.9 EE) and
# chastity-list 0.5's hand-kept 2001-12 edition (14,229.0 EE). The lists name the offending
# HOST and `members.tripod.com/x` collapses to `tripod.com`, throwing away a hostname the
# crawl rarely fetched: 7,653 (hostname, 2001) records and 3,410.4 EE absent from both the
# store and the reviewer's own 2001 file. Same bytes, same stamps, same classes.
SQUIDGUARD_HOST_SOURCE = "squidguard_2001_hostnames"
SQUIDGUARD_HOST_URL = (
    "http://archive.debian.org/debian/pool/main/s/squidguard/squidguard_1.2.0.orig.tar.gz"
)
CHASTITY_HOST_SOURCE = "chastity_list_hostnames"
CHASTITY_HOST_URL = (
    "https://archive.debian.org/debian/pool/main/c/chastity-list/chastity-list_0.5.orig.tar.gz"
)
# chastity's stamp is the tar member header, so the lane reads the tarball itself and
# takes each member's own mtime; an unpacked copy has lost that header to the extraction.
_CHASTITY_MEMBER = re.compile(
    r"^[^/]+/db/([a-z0-9-]+)/(domains|urls)(?:\.(\d{4})(\d{2})(\d{2})\.diff)?$"
)
_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
# The free-webmail providers list, hand-kept in both families and never dated.
_SKIPPED_CATEGORY = "mail"


def _list_hosts(text: str, is_diff: bool, counts: Counter[str]) -> dict[str, str]:
    """hostname -> parent registrable for the hosts one blocklist file names.

    The same reading `parse_squidguard_blacklist` applies at registrable grain: `#`
    comments skipped, a diff's `+` lines kept and its `-` removals dropped, a URL's path
    stripped. IP addresses and bare registrables are counted and not kept.
    """
    parents: dict[str, str] = {}
    for line in text.splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if is_diff:
            if not entry.startswith("+"):
                counts["diff_removal_or_context"] += 1
                continue
            entry = entry[1:].strip()
        host = entry.split("/", 1)[0].split(":", 1)[0].lower().rstrip(".")
        if not host or _IPV4.match(host):
            counts["ip_or_empty"] += 1
            continue
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


def _squidguard_members(path: Path, counts: Counter[str]) -> list[tuple[str, int, dict[str, str]]]:
    """[(evidence prefix, year, hosts)] for one flattened squidGuard list file."""
    from ark.sources import _SG_FILE, _SG_STAMP

    match = _SG_FILE.match(path.name)
    if match is None:
        counts["not_a_blacklist_file"] += 1
        return []
    category, kind = match.group(1), match.group(2)
    if category == _SKIPPED_CATEGORY:
        counts["mail_list_skipped"] += 1
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    is_diff = match.group(3) is not None
    if is_diff:
        year, stamp = int(match.group(3)), "".join(match.groups()[2:])
    else:
        found = _SG_STAMP.search(text)
        if found is None:
            counts["no_compile_stamp"] += 1
            return []
        year, stamp = int(found.group(1)), "".join(found.groups())
    if year not in YEARS:
        counts["out_of_window_edition"] += 1
        return []
    return [(f"squidguard:{category}/{kind}@{stamp}", year, _list_hosts(text, is_diff, counts))]


def _chastity_members(path: Path, counts: Counter[str]) -> list[tuple[str, int, dict[str, str]]]:
    """[(evidence prefix, year, hosts)] per list member of the chastity orig tarball."""
    import tarfile
    from datetime import UTC, datetime

    out: list[tuple[str, int, dict[str, str]]] = []
    with tarfile.open(path, "r:gz") as tar:
        for member in tar:
            match = _CHASTITY_MEMBER.match(member.name)
            if match is None or not member.isfile():
                continue
            category, kind = match.group(1), match.group(2)
            if category == _SKIPPED_CATEGORY:
                counts["mail_list_skipped"] += 1
                continue
            stamped = datetime.fromtimestamp(member.mtime, tz=UTC)
            if stamped.year not in YEARS:
                counts["out_of_window_member"] += 1
                continue
            fh = tar.extractfile(member)
            if fh is None:
                continue
            text = fh.read().decode("utf-8", errors="replace")
            is_diff = match.group(3) is not None
            prefix = f"chastity-list:{stamped:%Y%m%d} {category}/{kind}"
            out.append((prefix, stamped.year, _list_hosts(text, is_diff, counts)))
    return out


def ingest_blocklist_hostnames(
    conn: duckdb.DuckDBPyConnection, path: Path
) -> dict[str, int | str | bool]:
    """One blocklist file's sub-registrable hosts into hostname_year, idempotently.

    A `squidguard-*` file is the robot's own output, `artifact_listing`, no split. The
    chastity orig tarball is hand-kept, `dated_directory`, and takes the corroboration
    split exactly as `split_chastity.py` states it: a host counts only when its parent
    registrable already carries an assigned year; the rest is counted as parked.
    """
    from ark import approvals

    stats: dict[str, int | str | bool] = {"file": path.name, "skipped": False}
    counts: Counter[str] = Counter()
    if path.name.startswith("squidguard-"):
        source_name, etype, method, url = (
            SQUIDGUARD_HOST_SOURCE,
            "artifact_listing",
            "robot_compiled_blocklist",
            SQUIDGUARD_HOST_URL,
        )
        members = _squidguard_members(path, counts)
        split = False
    elif path.name.startswith("chastity-list") and path.name.endswith(".tar.gz"):
        source_name, etype, method, url = (
            CHASTITY_HOST_SOURCE,
            "dated_directory",
            "dated_blocklist_release",
            CHASTITY_HOST_URL,
        )
        members = _chastity_members(path, counts)
        split = True
    else:
        stats["not_a_blacklist_file"] = 1
        return stats
    already = conn.execute(
        "SELECT count(*) FROM ingested_file WHERE source_name = ? AND file_name = ?",
        [source_name, path.name],
    ).fetchone()[0]
    if already:
        stats["skipped"] = True
        logger.info(f"{path.name}: already ingested, skipping")
        return stats
    approvals.check(source_name, etype)

    rows: list[tuple[str, str, int, str]] = []
    seen: set[tuple[str, int]] = set()
    for prefix, year, parents in members:
        for host, parent in sorted(parents.items()):
            if (host, year) not in seen:
                seen.add((host, year))
                rows.append((host, parent, year, f"{prefix} host {host}"))
    stats.update(counts)
    stats["hostname_year_candidates"] = len(rows)
    stats["hostname_year_rows"] = 0
    if rows:
        source_id = ensure_source(conn, source_name, "timestamped")
        conn.execute(
            "CREATE TEMP TABLE IF NOT EXISTS listhost "
            "(hostname TEXT, parent TEXT, year INTEGER, value TEXT)"
        )
        conn.execute("DELETE FROM listhost")
        conn.executemany("INSERT INTO listhost VALUES (?, ?, ?, ?)", rows)
        if split:
            parked = conn.execute(
                "SELECT count(*) FROM listhost l WHERE NOT EXISTS "
                "(SELECT 1 FROM domain_year d WHERE d.domain = l.parent)"
            ).fetchone()[0]
            stats["split_parked"] = parked
            conn.execute(
                "DELETE FROM listhost WHERE parent NOT IN (SELECT domain FROM domain_year)"
            )
        conn.execute(
            r"""
            INSERT OR IGNORE INTO domain (domain, tld, discovered_source)
            SELECT DISTINCT parent, regexp_replace(parent, '^[^.]+\.', ''), ?
            FROM listhost
            """,
            [source_id],
        )
        before = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]
        conn.execute(
            """
            INSERT INTO evidence (domain, source_id, evidence_year, evidence_type,
                                  evidence_value, evidence_url, acquisition_method)
            SELECT l.parent, ?, l.year, ?, l.value, ?, ?
            FROM listhost l
            LEFT JOIN hostname_year hy
              ON hy.hostname = l.hostname AND hy.assigned_year = l.year
            WHERE hy.hostname IS NULL
            """,
            [source_id, etype, url, method],
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO hostname_year
                (hostname, parent_domain, assigned_year, evidence_id)
            SELECT l.hostname, l.parent, l.year, e.evidence_id
            FROM listhost l
            JOIN evidence e
              ON e.domain = l.parent AND e.evidence_year = l.year
             AND e.evidence_value = l.value
            """,
        )
        after = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]
        stats["hostname_year_rows"] = after - before
        # The list naming `x.foo.com` as live is the same claim about foo.com in that
        # year, so the parent earns its year from the same row, as the check
        # `nothing_earned_is_left_unassigned` requires. Nearly all are already held.
        dy_before = conn.execute("SELECT count(*) FROM domain_year").fetchone()[0]
        conn.execute(
            """
            INSERT OR IGNORE INTO domain_year (domain, assigned_year, evidence_id)
            SELECT e.domain, e.evidence_year, min(e.evidence_id)
            FROM evidence e
            JOIN listhost l ON e.domain = l.parent AND e.evidence_year = l.year
             AND e.evidence_value = l.value
            GROUP BY e.domain, e.evidence_year
            """,
        )
        dy_after = conn.execute("SELECT count(*) FROM domain_year").fetchone()[0]
        stats["parent_year_rows"] = dy_after - dy_before
        conn.execute("DELETE FROM listhost")
    conn.execute(
        "INSERT INTO ingested_file (source_name, file_name, sha256, record_rows) "
        "VALUES (?, ?, ?, ?)",
        [source_name, path.name, _sha256(path), stats["hostname_year_rows"]],
    )
    logger.info(str(stats))
    return stats


# The nameservers a RIPE `domain:` object points AT. Worth nothing at registrable grain and
# 93% absent at hostname grain: 38,189 (hostname, 1999) records from the 1999 snapshot plus
# 11,895 from the 2004 split edition dated by their latest `changed:` line, about 11,400 EE.
#
# **The RIPE NCC permission constrains the code**, as it does `parse_ripe_dbase_1999`: read
# only `*ns:` / `nserver:` values, the object key and the trailing date of `changed:`; never
# `*de`, `*ac`, `*tc`, `*zc`, `*ch` or the address half of `changed:`.
RIPE_NS_SOURCE = "ripe_nserver_hostnames"
RIPE_NS_SNAPSHOT_METHOD = "ripe_snapshot_nserver"
RIPE_NS_CHANGED_METHOD = "ripe_changed_nserver"
RIPE_NS_URLS = {
    "ripe.db.gz": "https://ftp.funet.fi/pub/netinfo/RIPE/dbase/ripe.db.gz",
    "ripe.db.domain.gz": "https://ftp.funet.fi/pub/netinfo/RIPE/dbase/split/ripe.db.domain.gz",
}


def _ns_host(token: str, counts: Counter[str]) -> tuple[str, str] | None:
    """(hostname, parent) for one nameserver token, or None with the reason counted."""
    host = token.strip().lower().rstrip(".")
    if not host or _IPV4.match(host):
        counts["glue_or_empty"] += 1
        return None
    if not _VALID_HOST.match(host):
        counts["rejected_host"] += 1
        return None
    reg = to_registrable(host)
    if reg is None:
        counts["rejected_host"] += 1
        return None
    if reg == host:
        counts["registrable_row"] += 1
        return None
    return host, reg


def ripe_snapshot_nservers(path: Path, counts: Counter[str]) -> list[tuple[str, str, int, str]]:
    """[(hostname, parent, 1999, value)] for every `*ns:` value in the 1999 snapshot.

    The year is the file's own generation stamp on line 2, read the way the banked
    parser reads it and refused if absent or out of window. Reverse-zone objects are
    kept: their nameservers are hosts the registry stated on the same day.
    """
    from ark.sources import _RIPE_STAMP, _open_text

    year: int | None = None
    stamp_text = ""
    hosts: dict[str, tuple[str, str]] = {}
    with _open_text(path) as fh:
        for number, line in enumerate(fh, 1):
            if year is None:
                stamp = _RIPE_STAMP.match(line.rstrip("\n"))
                if stamp is not None:
                    two = int(stamp.group(1))
                    year = (1900 + two) if two >= 90 else (2000 + two)
                    if year not in YEARS:
                        counts["stamp_out_of_window"] += 1
                        return []
                    stamp_text = "".join(stamp.groups())
                    continue
                if number > 40:
                    counts["no_header_stamp"] += 1
                    return []
                continue
            if not line.startswith("*ns:"):
                continue
            counts["ns_lines"] += 1
            for token in line[4:].split():
                found = _ns_host(token, counts)
                if found is not None and found[0] not in hosts:
                    hosts[found[0]] = (found[1], f"ripe_dbase:19{stamp_text} ns {found[0]}")
    if year is None:
        counts["no_header_stamp"] += 1
        return []
    return [(host, parent, year, value) for host, (parent, value) in sorted(hosts.items())]


def ripe_changed_nservers(path: Path, counts: Counter[str]) -> list[tuple[str, str, int, str]]:
    """[(hostname, parent, year, value)] for the `nserver:` set of each `domain:` object.

    An object whose LATEST `changed:` line falls in year Y is the registry stating that
    its nserver set stood as written in Y, and rule 6 keeps the record to that year. An
    object last changed outside the window contributes nothing.
    """
    from ark.sources import _RIPE_CHANGED_LONG, _open_text

    out: dict[tuple[str, int], tuple[str, str]] = {}
    nservers: list[str] = []
    latest: str | None = None
    in_object = False

    def flush() -> None:
        if not in_object or latest is None:
            return
        year = int(latest[:4])
        if year not in YEARS:
            counts["object_out_of_window"] += 1
            return
        counts["objects_in_window"] += 1
        for token in nservers:
            found = _ns_host(token, counts)
            if found is not None and (found[0], year) not in out:
                out[(found[0], year)] = (found[1], f"ripe_changed:{latest} nserver {found[0]}")

    with _open_text(path) as fh:
        for line in fh:
            if line.startswith("domain:"):
                flush()
                in_object, nservers, latest = True, [], None
                counts["domain_objects"] += 1
            elif not in_object:
                continue
            elif line.startswith("nserver:"):
                counts["ns_lines"] += 1
                tokens = line[8:].split()
                if tokens:
                    nservers.append(tokens[0])
            else:
                found = _RIPE_CHANGED_LONG.match(line.rstrip("\n"))
                if found is not None and (latest is None or found.group(1) > latest):
                    latest = found.group(1)
    flush()
    return [(host, parent, year, value) for (host, year), (parent, value) in sorted(out.items())]


def ingest_ripe_nserver_hostnames(
    conn: duckdb.DuckDBPyConnection, path: Path
) -> dict[str, int | str | bool]:
    """One RIPE database file's nameserver hosts into hostname_year, idempotently."""
    from ark import approvals

    stats: dict[str, int | str | bool] = {"file": path.name, "skipped": False}
    if path.name not in RIPE_NS_URLS:
        stats["not_a_ripe_file"] = 1
        return stats
    already = conn.execute(
        "SELECT count(*) FROM ingested_file WHERE source_name = ? AND file_name = ?",
        [RIPE_NS_SOURCE, path.name],
    ).fetchone()[0]
    if already:
        stats["skipped"] = True
        logger.info(f"{path.name}: already ingested, skipping")
        return stats
    approvals.check(RIPE_NS_SOURCE, "artifact_listing")
    counts: Counter[str] = Counter()
    if path.name == "ripe.db.gz":
        method, rows = RIPE_NS_SNAPSHOT_METHOD, ripe_snapshot_nservers(path, counts)
    else:
        method, rows = RIPE_NS_CHANGED_METHOD, ripe_changed_nservers(path, counts)
    stats.update(counts)
    stats["hostname_year_candidates"] = len(rows)
    stats["hostname_year_rows"] = 0
    if rows:
        source_id = ensure_source(conn, RIPE_NS_SOURCE, "timestamped")
        conn.execute(
            "CREATE TEMP TABLE IF NOT EXISTS ripehost "
            "(hostname TEXT, parent TEXT, year INTEGER, value TEXT)"
        )
        conn.execute("DELETE FROM ripehost")
        conn.executemany("INSERT INTO ripehost VALUES (?, ?, ?, ?)", rows)
        conn.execute(
            r"""
            INSERT OR IGNORE INTO domain (domain, tld, discovered_source)
            SELECT DISTINCT parent, regexp_replace(parent, '^[^.]+\.', ''), ?
            FROM ripehost
            """,
            [source_id],
        )
        before = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]
        conn.execute(
            """
            INSERT INTO evidence (domain, source_id, evidence_year, evidence_type,
                                  evidence_value, evidence_url, acquisition_method)
            SELECT r.parent, ?, r.year, 'artifact_listing', r.value, ?, ?
            FROM ripehost r
            LEFT JOIN hostname_year hy
              ON hy.hostname = r.hostname AND hy.assigned_year = r.year
            WHERE hy.hostname IS NULL
            """,
            [source_id, RIPE_NS_URLS[path.name], method],
        )
        if writes_hostname_years(RIPE_NS_SOURCE):
            conn.execute(
                """
                INSERT OR IGNORE INTO hostname_year
                    (hostname, parent_domain, assigned_year, evidence_id)
                SELECT r.hostname, r.parent, r.year, e.evidence_id
                FROM ripehost r
                JOIN evidence e
                  ON e.domain = r.parent AND e.evidence_year = r.year
                 AND e.evidence_value = r.value
                """,
            )
        after = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]
        stats["hostname_year_rows"] = after - before
        # The registry naming `ns.foo.net` as serving a delegation that day is the same
        # statement about foo.net, so the parent earns its year from the same row, as
        # the check `nothing_earned_is_left_unassigned` requires. 98% are already held.
        dy_before = conn.execute("SELECT count(*) FROM domain_year").fetchone()[0]
        conn.execute(
            """
            INSERT OR IGNORE INTO domain_year (domain, assigned_year, evidence_id)
            SELECT e.domain, e.evidence_year, min(e.evidence_id)
            FROM evidence e
            JOIN ripehost r ON e.domain = r.parent AND e.evidence_year = r.year
             AND e.evidence_value = r.value
            GROUP BY e.domain, e.evidence_year
            """,
        )
        dy_after = conn.execute("SELECT count(*) FROM domain_year").fetchone()[0]
        stats["parent_year_rows"] = dy_after - dy_before
        conn.execute("DELETE FROM ripehost")
    conn.execute(
        "INSERT INTO ingested_file (source_name, file_name, sha256, record_rows) "
        "VALUES (?, ?, ?, ?)",
        [RIPE_NS_SOURCE, path.name, _sha256(path), stats["hostname_year_rows"]],
    )
    logger.info(str(stats))
    return stats


# The fifth hostname corpus: the per-TLD host lists of the Network Wizards / ISC Internet
# Domain Survey, banked at registrable grain as `isc_survey` (14,956 EE, the best 1996-1997
# source here) and complete at that grain. Every line is `IP hostname`, the PTR walk's
# record of a host that answered in DNS during the survey month, and the registrable
# collapse threw away 98% of the rows: a census of five 9607 files found 100% of parents
# held at 1996 and 98.2% of the hosts absent from both the store and the reviewer's own
# 1996 file. Same bytes, same `YYMM` stamp, same `artifact_listing`. The `.domains` lists
# hold registrables only and belong to `isc_survey`.
ISC_SOURCE_NAME = "isc_survey_hostnames"
ISC_METHOD = "isc_survey_host_list"
_ISC_HOST_FILE = re.compile(r"^wb_nw_(9\d{3})_([a-z0-9-]+)\.gz$")


def isc_survey_hosts(path: Path, counts: Counter[str]) -> dict[str, str]:
    """hostname -> parent registrable for every host one survey file lists.

    The last whitespace token is the host, as `parse_isc_survey` reads it. Underscore
    NT names and other non-RFC-1123 shapes are refused, exactly as the journal ingest
    refuses them; a host that IS its own registrable is `isc_survey`'s row, not ours.
    """
    from ark.sources import _open_text

    parents: dict[str, str] = {}
    with _open_text(path) as fh:
        for line in fh:
            tokens = line.split()
            if not tokens:
                continue
            counts["lines"] += 1
            host = tokens[-1].rstrip(".").lower()
            if host in parents:
                counts["duplicate_line"] += 1
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


def ingest_isc_hostnames(
    conn: duckdb.DuckDBPyConnection, path: Path
) -> dict[str, int | str | bool]:
    """One ISC survey host file's sub-registrable hosts into hostname_year, idempotently."""
    from ark import approvals
    from ark.sources import _isc_survey_date

    stats: dict[str, int | str | bool] = {"file": path.name, "skipped": False}
    match = _ISC_HOST_FILE.match(path.name)
    if match is None:
        stats["not_a_host_file"] = 1
        logger.info(f"{path.name}: not a per-TLD host file, skipping")
        return stats
    already = conn.execute(
        "SELECT count(*) FROM ingested_file WHERE source_name = ? AND file_name = ?",
        [ISC_SOURCE_NAME, path.name],
    ).fetchone()[0]
    if already:
        stats["skipped"] = True
        logger.info(f"{path.name}: already ingested, skipping")
        return stats
    dated = _isc_survey_date(path.name)
    if dated is None or dated[0] not in YEARS:
        stats["out_of_window_file"] = 1
        logger.info(f"{path.name}: survey month outside the window, skipping")
        return stats
    year, survey = dated
    approvals.check(ISC_SOURCE_NAME, "artifact_listing")
    code, tld = match.group(1), match.group(2)
    # The artifact's own published address; the bytes on disk are its Wayback copy and
    # `scripts/sources/directories/fetch_nw_host_files.py` records how they were taken.
    artifact_url = f"http://nw.com/zone/{code}.hosts/{tld}.gz"
    counts: Counter[str] = Counter()
    parents = isc_survey_hosts(path, counts)
    prefix = f"isc survey {survey} host "
    rows = [(host, parents[host], year, prefix + host) for host in sorted(parents)]
    stats.update(counts)
    stats["hostname_year_candidates"] = len(rows)
    if rows:
        source_id = ensure_source(conn, ISC_SOURCE_NAME, "timestamped")
        conn.execute(
            "CREATE TEMP TABLE IF NOT EXISTS ischost "
            "(hostname TEXT, parent TEXT, year INTEGER, value TEXT)"
        )
        conn.execute("DELETE FROM ischost")
        # A survey file runs to 1.3 million hosts, so the rows go in as one relation
        # rather than one prepared statement each.
        conn.register("ischost_rows", _as_arrow(rows))
        conn.execute("INSERT INTO ischost SELECT * FROM ischost_rows")
        conn.unregister("ischost_rows")
        conn.execute(
            r"""
            INSERT OR IGNORE INTO domain (domain, tld, discovered_source)
            SELECT DISTINCT parent, regexp_replace(parent, '^[^.]+\.', ''), ?
            FROM ischost
            """,
            [source_id],
        )
        before = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]
        conn.execute(
            """
            INSERT INTO evidence (domain, source_id, evidence_year, evidence_type,
                                  evidence_value, evidence_url, acquisition_method)
            SELECT i.parent, ?, i.year, 'artifact_listing', i.value, ?, ?
            FROM ischost i
            LEFT JOIN hostname_year hy
              ON hy.hostname = i.hostname AND hy.assigned_year = i.year
            WHERE hy.hostname IS NULL
            """,
            [source_id, artifact_url, ISC_METHOD],
        )
        if writes_hostname_years(ISC_SOURCE_NAME):
            conn.execute(
                """
                INSERT OR IGNORE INTO hostname_year
                    (hostname, parent_domain, assigned_year, evidence_id)
                SELECT i.hostname, i.parent, i.year, e.evidence_id
                FROM ischost i
                JOIN evidence e
                  ON e.domain = i.parent AND e.evidence_year = i.year
                 AND e.evidence_value = i.value
                """,
            )
        after = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]
        stats["hostname_year_rows"] = after - before
        # The survey answering for `pc50.foo.co.uk` that month is the same observation
        # of foo.co.uk, so the parent earns its year from the same row, as the check
        # `nothing_earned_is_left_unassigned` requires. Every parent is already held
        # at registrable grain by construction: `isc_survey` read these same lines.
        dy_before = conn.execute("SELECT count(*) FROM domain_year").fetchone()[0]
        conn.execute(
            """
            INSERT OR IGNORE INTO domain_year (domain, assigned_year, evidence_id)
            SELECT e.domain, e.evidence_year, min(e.evidence_id)
            FROM evidence e
            JOIN ischost i ON e.domain = i.parent AND e.evidence_year = i.year
             AND e.evidence_value = i.value
            GROUP BY e.domain, e.evidence_year
            """,
        )
        dy_after = conn.execute("SELECT count(*) FROM domain_year").fetchone()[0]
        stats["parent_year_rows"] = dy_after - dy_before
        conn.execute("DELETE FROM ischost")
    else:
        stats["hostname_year_rows"] = 0
    conn.execute(
        "INSERT INTO ingested_file (source_name, file_name, sha256, record_rows) "
        "VALUES (?, ?, ?, ?)",
        [ISC_SOURCE_NAME, path.name, _sha256(path), stats["hostname_year_rows"]],
    )
    logger.info(str(stats))
    return stats


def _as_arrow(rows: list[tuple[str, str, int, str]]):  # noqa: ANN202 - pyarrow.Table
    import pyarrow as pa

    return pa.table(
        {
            "hostname": [r[0] for r in rows],
            "parent": [r[1] for r in rows],
            "year": pa.array([r[2] for r in rows], type=pa.int32()),
            "value": [r[3] for r in rows],
        }
    )


# A host somebody typed as an explicit `http://`, `https://` or `ftp://` URL in the BODY of a
# dated Usenet post, `link_source`.
#
# **A typed URL is not a crawler artifact**: a bulk CDX index re-read at hostname grain is
# 99.5% to 100.0% the crawler's own `www.` alias on all three corpora tested, while typed
# URLs keep three quarters of the figure.
#
# **What dates one item** is the post's machine-written `Date:` header, read at extraction
# and verified against raw bytes. The evidence row quotes the post: `<group>.mbox.zip#<n>`,
# the archive archive.org serves by name from `data/raw/usenet_catalog.json`.
#
# **The discount is measured, not assumed**: a sample puts the fiction rate at 6.25% (Wilson
# 95% CI 2.7% to 13.8%) and the register quotes the lane net of it. A mechanical word list
# finds only 0.52%, which is why the rate is sampled and not screened.
USENET_SOURCE = "usenet_body_url_hostnames"
USENET_METHOD = "usenet_body_url"
_USENET_ITEM = re.compile(r"^(?P<group>[a-z0-9][a-z0-9.+_-]*)\.mbox\.zip#\d+$")


def _usenet_url(item: str) -> str:
    hierarchy = item.split(".", 1)[0]
    return f"https://archive.org/download/usenet-{hierarchy}/{item.split('#')[0]}"


# The mailing-list twin: the pipermail month files `collect_mailing_lists.py` fetched, read
# at hostname grain from their body URLs by `build_maillist_pool.py`. The item is
# `<host>/<file>#<n>`, message n of a month file the archive host still serves by name;
# gnome serves it gzipped and python plain, so the URL is built per host, not by pattern.
MAILLIST_SOURCE = "maillist_body_url_hostnames"
MAILLIST_METHOD = "maillist_body_url"
_MAILLIST_ITEM = re.compile(
    r"^(?P<host>gnome|python)/(?P<list>[a-z0-9][a-z0-9._+-]*)__"
    r"(?P<month>(?:199[6-9]|200[01])-[A-Z][a-z]+)\.txt#\d+$"
)
_MAILLIST_ARCHIVE = {
    "gnome": "https://mail.gnome.org/archives/{list}/{month}.txt.gz",
    "python": "https://mail.python.org/pipermail/{list}/{month}.txt",
}


def _maillist_url(item: str) -> str:
    m = _MAILLIST_ITEM.match(item)
    assert m is not None  # the caller matched it already
    return _MAILLIST_ARCHIVE[m["host"]].format(list=m["list"], month=m["month"])


@dataclass(frozen=True)
class ItemFamily:
    """One `{item, year, text}` lane: its source row, item pointer and archive URL."""

    source: str
    method: str
    noun: str  # leads the evidence value, before the year: `usenet post 1999 <item> <host>`
    item_re: re.Pattern[str]
    url_of: Callable[[str], str]


USENET_FAMILY = ItemFamily(USENET_SOURCE, USENET_METHOD, "usenet post", _USENET_ITEM, _usenet_url)
MAILLIST_FAMILY = ItemFamily(
    MAILLIST_SOURCE, MAILLIST_METHOD, "list message", _MAILLIST_ITEM, _maillist_url
)

# The third member of the body-URL family: the CMU release of the Enron mailbox, one message
# per tar member, read at hostname grain by `build_enron_pool.py`. The item is the member's
# own path in the tarball, `maildir/<custodian>/<folder>/<n>.`, and every item resolves to
# the one artifact CMU still serves. `collect_enron.py` banked the same messages at
# registrable grain.
ENRON_SOURCE = "enron_body_url_hostnames"
ENRON_METHOD = "enron_body_url"
ENRON_ARCHIVE = "https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz"
_ENRON_ITEM = re.compile(r"^maildir/[^\s#/]+/[^\s#]+$")


def _enron_url(item: str) -> str:
    return ENRON_ARCHIVE


ENRON_FAMILY = ItemFamily(ENRON_SOURCE, ENRON_METHOD, "enron message", _ENRON_ITEM, _enron_url)

# The fourth member, and the first that is NOT a body URL: the `Received: ... by <host>`
# clause of a dated message in the Ponymail archive at `lists.apache.org`, C-83, for the `by`
# clause alone. `build_apache_header_pool.py` writes the shards and carries the parsing traps.
#
# The item is `<list domain>/<list>__<YYYY-MM>#<n>`, message n of one list-month's mbox
# export, still served by name from the API. `mbox.lua` accepts only `d=YYYY-MM`, a year
# range answering 200 with a 13-message stub, so the month is part of the pointer.
APACHE_SOURCE = "apache_list_header_hostnames"
APACHE_METHOD = "apache_list_received_by"
_APACHE_ITEM = re.compile(
    r"^(?P<domain>[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,})/"
    r"(?P<list>[a-z0-9][a-z0-9._+-]*)__"
    r"(?P<month>(?:199[6-9]|200[01])-(?:0[1-9]|1[0-2]))#\d+$"
)


def _apache_url(item: str) -> str:
    m = _APACHE_ITEM.match(item)
    assert m is not None  # the caller matched it already
    return (
        "https://lists.apache.org/api/mbox.lua"
        f"?list={m['list']}&domain={m['domain']}&d={m['month']}"
    )


APACHE_FAMILY = ItemFamily(APACHE_SOURCE, APACHE_METHOD, "list header", _APACHE_ITEM, _apache_url)

# The fifth member, C-83's class at a SECOND host rather than a new class: the same
# `Received: ... by <host>` clause in the IETF mail archive, read by
# `scripts/sources/mail_corpora/collect_ietf_mail_archive.py`, which imports the Apache
# lane's parser so the two figures are comparable.
#
# The item is the month file's own path, `www.ietf.org/<tree>/<list>/<file>#<n>`, the file
# name carried whole rather than derived from the month: this archive spells `1996-03` in
# the early years and `1999-05.mail` from 1998 on, so a guessed suffix 404s on half of it.
IETF_SOURCE = "ietf_list_header_hostnames"
IETF_METHOD = "ietf_list_received_by"
_IETF_ITEM = re.compile(
    r"^www\.ietf\.org/(?P<tree>ietf-mail-archive|concluded-wg-ietf-mail-archive)/"
    r"(?P<list>[A-Za-z0-9][A-Za-z0-9._+-]*)/"
    r"(?P<file>(?:199[6-9]|200[01])-(?:0[1-9]|1[0-2])(?:\.mail)?)#\d+$"
)


def _ietf_url(item: str) -> str:
    m = _IETF_ITEM.match(item)
    assert m is not None  # the caller matched it already
    return f"https://www.ietf.org/ietf-ftp/{m['tree']}/{m['list']}/{m['file']}"


IETF_FAMILY = ItemFamily(IETF_SOURCE, IETF_METHOD, "list header", _IETF_ITEM, _ietf_url)

# The sixth member: the server-written header fields of a dated Usenet post.
#
# **Three fields, all written by a news server about a transaction it completed**, the
# reading C-83 settled for a `Received: ... by` clause: the trailing hostname of `X-Trace:`,
# the `NNTP-Posting-Host:` the accepting server logged, and the final `Path:` hop, the site
# that injected the article. `Message-ID` is NOT read: Turnpike and Demon clients stamp it
# from a configured nodename, so it is client-written and needs its own ruling.
# `build_usenet_header_pool.py` writes the shards and carries the parsing traps.
#
# The item is `<group>.mbox.zip#<n>`, the same pointer shape and archive as the body-URL
# lane, so `_USENET_ITEM` and `_usenet_url` are reused.
USENET_HEADER_SOURCE = "usenet_header_fqdn_hostnames"
USENET_HEADER_METHOD = "usenet_server_written_header"
USENET_HEADER_FAMILY = ItemFamily(
    USENET_HEADER_SOURCE, USENET_HEADER_METHOD, "usenet header", _USENET_ITEM, _usenet_url
)


def usenet_item_rows(
    path: Path, counts: Counter[str], family: ItemFamily = USENET_FAMILY
) -> list[tuple[str, str, int, str, str]]:
    """(hostname, parent, year, evidence value, archive URL) for one `{item, year, text}` shard.

    One row per (host, year), keeping the lowest-sorting item that names it, so re-reading
    the same shard produces the same evidence and the join below cannot fan out.
    """
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
                year = row.get("year")
                if not isinstance(year, int) or year not in YEARS:
                    counts["out_of_window"] += 1
                    continue
                item = str(row.get("item", ""))
                if not family.item_re.match(item):
                    counts["bad_item"] += 1
                    continue
                for token in str(row.get("text", "")).split():
                    host = token.strip().lower().rstrip(".")
                    if not _VALID_HOST.match(host):
                        counts["rejected_host"] += 1
                        continue
                    key = (host, year)
                    if key not in seen or item < seen[key]:
                        seen[key] = item
    except (EOFError, OSError):
        # a shard cut mid-write; what was read is real and the tail returns next sweep
        counts["truncated_tail"] += 1

    parents: dict[str, str] = {}
    for host in {h for h, _ in seen}:
        reg = to_registrable(host)
        if reg is None:
            counts["rejected_host"] += 1
        elif reg == host:
            counts["registrable_row"] += 1  # belongs to domain_year, not here
        else:
            parents[host] = reg

    rows: list[tuple[str, str, int, str, str]] = []
    for (host, year), item in sorted(seen.items()):
        if host not in parents:
            continue
        rows.append(
            (
                host,
                parents[host],
                year,
                # The year comes FIRST, before the item. `evidence_year_matches_its_value`
                # reads the first four-digit run in the value, and a Usenet item is full of
                # them: a post index (`#1997`), group names like `alt.2600`. Item-first
                # fails on 3,933,601 rows, every one a false positive.
                f"{family.noun} {year} {item} {host}",
                family.url_of(item),
            )
        )
    return rows


def _as_arrow_usenet(rows: list[tuple[str, str, int, str, str]]):  # noqa: ANN202 - pyarrow.Table
    import pyarrow as pa

    return pa.table(
        {
            "hostname": [r[0] for r in rows],
            "parent": [r[1] for r in rows],
            "year": pa.array([r[2] for r in rows], type=pa.int32()),
            "value": [r[3] for r in rows],
            "url": [r[4] for r in rows],
        }
    )


def ingest_usenet_item_journal(
    conn: duckdb.DuckDBPyConnection, path: Path, family: ItemFamily = USENET_FAMILY
) -> dict[str, int | str | bool]:
    """One `{item, year, text}` shard into hostname_year, idempotently.

    The idempotence key carries the pool, because every pool names its shards
    `shard_000.jsonl.gz` and a bare filename would mark twelve of the thirteen as done.
    """
    from ark import approvals

    stats: dict[str, int | str | bool] = {"file": path.name, "skipped": False}
    file_key = f"{path.parent.name}/{path.name}"
    digest = _sha256(path)
    # **The key is the name AND the digest, because one lane's shard GROWS.** Most pools
    # write a shard once, but the IETF collector appends every month of a list to that
    # list's one shard, so a name key would mark it done at its first length and skip every
    # later month silently. Re-reading a grown shard costs one pass and its existing rows
    # land on `INSERT OR IGNORE`.
    previous = conn.execute(
        "SELECT sha256, record_rows FROM ingested_file WHERE source_name = ? AND file_name = ?",
        [family.source, file_key],
    ).fetchone()
    if previous is not None and previous[0] == digest:
        stats["skipped"] = True
        logger.info(f"{file_key}: already ingested, skipping")
        return stats
    approvals.check(family.source, "link_source")

    counts: Counter[str] = Counter()
    rows = usenet_item_rows(path, counts, family)
    stats.update(counts)
    stats["hostname_year_candidates"] = len(rows)
    if rows:
        source_id = ensure_source(conn, family.source, "timestamped")
        conn.execute(
            "CREATE TEMP TABLE IF NOT EXISTS usenethost "
            "(hostname TEXT, parent TEXT, year INTEGER, value TEXT, url TEXT)"
        )
        conn.execute("DELETE FROM usenethost")
        # A shard runs to millions of item lines, so the rows go in as one relation
        conn.register("usenethost_rows", _as_arrow_usenet(rows))
        conn.execute("INSERT INTO usenethost SELECT * FROM usenethost_rows")
        conn.unregister("usenethost_rows")
        conn.execute(
            r"""
            INSERT OR IGNORE INTO domain (domain, tld, discovered_source)
            SELECT DISTINCT parent, regexp_replace(parent, '^[^.]+\.', ''), ?
            FROM usenethost
            """,
            [source_id],
        )
        before = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]
        conn.execute(
            """
            INSERT INTO evidence (domain, source_id, evidence_year, evidence_type,
                                  evidence_value, evidence_url, acquisition_method)
            SELECT u.parent, ?, u.year, 'link_source', u.value, u.url, ?
            FROM usenethost u
            LEFT JOIN hostname_year hy
              ON hy.hostname = u.hostname AND hy.assigned_year = u.year
            WHERE hy.hostname IS NULL
            """,
            [source_id, family.method],
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO hostname_year
                (hostname, parent_domain, assigned_year, evidence_id)
            SELECT u.hostname, u.parent, u.year, e.evidence_id
            FROM usenethost u
            JOIN evidence e
              ON e.domain = u.parent AND e.evidence_year = u.year
             AND e.evidence_value = u.value
            """,
        )
        after = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]
        stats["hostname_year_rows"] = after - before
        # The post that names `pages.foo.com` names foo.com in the same breath, so the
        # parent earns its year from the same observation, as
        # `nothing_earned_is_left_unassigned` requires of every master-eligible row.
        dy_before = conn.execute("SELECT count(*) FROM domain_year").fetchone()[0]
        conn.execute(
            """
            INSERT OR IGNORE INTO domain_year (domain, assigned_year, evidence_id)
            SELECT e.domain, e.evidence_year, min(e.evidence_id)
            FROM evidence e
            JOIN usenethost u ON e.domain = u.parent AND e.evidence_year = u.year
             AND e.evidence_value = u.value
            GROUP BY e.domain, e.evidence_year
            """,
        )
        dy_after = conn.execute("SELECT count(*) FROM domain_year").fetchone()[0]
        stats["parent_year_rows"] = dy_after - dy_before
        conn.execute("DELETE FROM usenethost")
    else:
        stats["hostname_year_rows"] = 0

    # One row per file, carrying what it has contributed across every reading of it, because
    # `ingested_file` is keyed on (source_name, file_name) and a grown shard has to replace
    # its own row rather than collide with it.
    banked = (previous[1] if previous else 0) + int(stats["hostname_year_rows"])
    conn.execute(
        "INSERT OR REPLACE INTO ingested_file "
        "(source_name, file_name, sha256, record_rows) VALUES (?, ?, ?, ?)",
        [family.source, file_key, digest, banked],
    )
    logger.info(str(stats))
    return stats


def ingest_usenet_item_dir(
    conn: duckdb.DuckDBPyConnection,
    root: Path,
    pattern: str | None = None,
    family: ItemFamily = USENET_FAMILY,
) -> dict[str, int]:
    """Every `{item, year, text}` shard under `root`, or `root` itself when it is a file.

    **Both `.jsonl.gz` and plain `.jsonl` are read** unless the caller names a pattern,
    because `collect_ietf_mail_archive.py` appends an uncompressed shard per list directory
    and a gz-only glob reports success over `files_seen: 0`. `usenet_item_rows` picks its
    opener off the suffix.
    """
    totals: Counter[str] = Counter()
    if root.is_dir():
        patterns = [pattern] if pattern else ["*.jsonl.gz", "*.jsonl"]
        files = sorted({p for pat in patterns for p in root.glob(pat)})
    else:
        files = [root]
    for i, path in enumerate(files, 1):
        stats = ingest_usenet_item_journal(conn, path, family)
        for key, value in stats.items():
            if isinstance(value, int) and not isinstance(value, bool):
                totals[key] += value
            elif key == "skipped" and value:
                totals["files_skipped"] += 1
        logger.info(f"[{i}/{len(files)}] {path.name} done")
    totals["files_seen"] = len(files)
    logger.info(f"usenet hostnames: {dict(totals)}")
    return dict(totals)
