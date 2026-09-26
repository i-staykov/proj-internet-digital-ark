"""Command-line entry point for the ark pipeline."""

import json
import sys
from collections import Counter
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from typing import Annotated

import duckdb
import typer
from loguru import logger
from tqdm import tqdm

from ark import approvals
from ark.audit import write_audit
from ark.baseline import CURRENT_BASELINE_MARKER, baseline_dir
from ark.bulk import ingest_files
from ark.canonical import to_registrable
from ark.cdx import HOST_TIMEOUT, RateGovernor, http_fetch, lookup_years, lookup_years_per_year
from ark.cdx import answered as cdx_answered
from ark.checks import AUDIT_PATH, collect_checks, format_checks
from ark.db import DEFAULT_DB_PATH, connect, connect_patiently, connect_read_only_patiently, init_db
from ark.expand import answered as expand_answered
from ark.expand import expand_page, read_seeds
from ark.export import export_all
from ark.ingest import YEARS, ingest_legacy
from ark.journal import journal_path, journal_writer, queried_domains, write_journal_line
from ark.legacy_review import DEFAULT_DROPLIST_PATH, review_legacy
from ark.metrics import record_metrics
from ark.price_snapshot import SnapshotError
from ark.price_snapshot import price as price_against_snapshot
from ark.provenance import PROVENANCE_DIR, load_provenance
from ark.seed import seed_from_file
from ark.seed_pool import combine_parts, write_source_part
from ark.sources import SOURCES
from ark.stats import collect_stats, format_stats
from ark.work_queue import DEFAULT_QUEUE_PATH, connect_queue

# Resolved once at import. Which layout we are in, repository or unpacked
# delivery, cannot change while the process runs.
BASELINE_DIR = baseline_dir()

app = typer.Typer(
    name="ark",
    help="Collect historical domains (1996-2001) with per-year evidence.",
    no_args_is_help=True,
)

_LOG_FORMAT = "{time:HH:mm:ss} | {level: <7} | {message}"
_LOG_FILE = "data/logs/ark_{time:YYYY-MM-DD}.log"
# flush the RDAP journal this often, so a killed run keeps nearly all its work
_JOURNAL_FLUSH_EVERY = 25
CDX_JOURNAL_DIR = Path("data/raw/cdx")
CDX_JOURNAL_PREFIX = "cdx"
EXPAND_JOURNAL_DIR = Path("data/raw/expand")
EXPAND_JOURNAL_PREFIX = "expand"


@contextmanager
def _abortable_pool(workers: int) -> Iterator[ThreadPoolExecutor]:
    """A worker pool that drops its queued work when the run stops early.

    These runs submit the whole batch up front, and a plain `with ThreadPoolExecutor`
    waits for every queued task on the way out, so Ctrl-C looks ignored. Cancelling
    pending futures loses nothing: an unanswered domain was never journalled.
    """
    pool = ThreadPoolExecutor(workers)
    try:
        yield pool
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


@app.callback()
def _setup(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging.")] = False,
) -> None:
    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if verbose else "INFO", format=_LOG_FORMAT)
    # every run leaves a permanent execution log; the delivery requires them
    logger.add(_LOG_FILE, level="DEBUG", format="{time} | {level: <7} | {message}")


@app.command()
def init() -> None:
    """Create the databases and apply their schemas."""
    conn = connect()
    init_db(conn)
    logger.info(f"provenance store ready at {DEFAULT_DB_PATH}")
    connect_queue()
    logger.info(f"work queue ready at {DEFAULT_QUEUE_PATH}")


@app.command(name="ingest-legacy")
def ingest_legacy_cmd(
    legacy_dir: Annotated[
        Path,
        typer.Option(
            help="Folder holding the provided baseline files. Defaults to wherever the "
            "current release actually is: the repository path, or `baseline/<marker>/` "
            "in an unpacked delivery, where the repository path does not exist."
        ),
    ] = BASELINE_DIR,
    marker_prefix: Annotated[
        str,
        typer.Option(
            "--marker-prefix",
            help="Namespace for this baseline's evidence markers, e.g. 'merged260727'. Required "
            "when loading a later release: the marker is the file name alone, so a second "
            "1996.txt would otherwise be skipped as already ingested. Defaults to the current "
            "release; pass the pair explicitly to load an older one.",
        ),
    ] = CURRENT_BASELINE_MARKER,
) -> None:
    """Load the baseline year files and merge stats into the store."""
    conn = connect()
    init_db(conn)
    all_stats = ingest_legacy(conn, legacy_dir, marker_prefix=marker_prefix)
    ingested = [s for s in all_stats if not s["skipped"]]
    total_rows = sum(s.get("year_rows", 0) for s in ingested)
    total_rejected = sum(s.get("rejected", 0) for s in ingested)
    logger.info(
        f"done: {len(ingested)} files ingested, {len(all_stats) - len(ingested)} skipped, "
        f"{total_rows} year rows added, {total_rejected} lines rejected"
    )


@app.command(name="legacy-review")
def legacy_review_cmd(
    legacy_dir: Annotated[
        Path,
        typer.Option(
            help="Folder holding the provided baseline files. Defaults to wherever the "
            "current release actually is: the repository path, or `baseline/<marker>/` "
            "in an unpacked delivery, where the repository path does not exist."
        ),
    ] = BASELINE_DIR,
) -> None:
    """Write the grouped droplist of baseline lines the pipeline excludes."""
    counts = review_legacy(legacy_dir)
    logger.info(f"see {DEFAULT_DROPLIST_PATH} ({sum(counts.values())} distinct entries)")


# Banking a finished journal is top of ADR-001's ordering, so this is the job that waits
# rather than the one that yields. Generous, because `ark seed` has been measured holding
# the lock for 33 minutes and a banking pass that gives up leaves collected work on disk.
INGEST_LOCK_PATIENCE_S = 2400


@app.command(name="ingest")
def ingest_cmd(
    source: Annotated[
        str, typer.Argument(help=f"Bulk source key: one of {', '.join(sorted(SOURCES))}.")
    ],
    files: Annotated[
        list[Path],
        typer.Argument(help="Source files to ingest (gzip ok).", exists=True, readable=True),
    ],
    round_: Annotated[
        int,
        typer.Option(
            "--round",
            help="Discovery round to stamp on newly seen domains. Round 0 is a directly "
            "ingested source; a re-discovery round should carry its own number so the "
            "expansion cycle is traceable.",
        ),
    ] = 0,
) -> None:
    """Ingest bulk source files through the shared audited loader.

    Idempotent per file: a file already in the ledger is skipped whole.
    Example: ark ingest early_web data/raw/early_web/*.cdx.gz
    """
    from ark.hostnames import FLEETREAD_SOURCE

    spec = SOURCES.get(source)
    if spec is None and FLEETREAD_SOURCE.match(source):
        _ingest_fleet_read(source, files)
        return
    if spec is None:
        raise typer.BadParameter(f"unknown source '{source}'; known: {', '.join(sorted(SOURCES))}")
    # Checked before the store is opened, so an unapproved ingest does not even take
    # the write lock. `ingest_files` checks again, because it is the gate every
    # caller passes through and this one is only the fast, polite failure.
    try:
        approvals.check(spec.source_name, spec.evidence_type)
    except approvals.NotApproved as exc:
        typer.echo(f"refusing to ingest: {exc}", err=True)
        raise typer.Exit(code=2) from None
    # Top of ADR-001's ordering: banking a collector's finished journal is work already
    # paid for, so this is the job that waits and everything below it yields to it.
    conn = connect_patiently(patience_s=INGEST_LOCK_PATIENCE_S)
    init_db(conn)
    queue_conn = connect_queue()
    ingest_files(conn, spec, files, queue_conn=queue_conn, discovered_round=round_)


def _ingest_fleet_read(source: str, files: list[Path]) -> None:
    """A fleet read banks both halves under its own source: its journal parts through the
    hostname ingest, its registrables through the `cdx_snapshot` parser. A file that is not
    this read's, a refused part or a failed file exits non-zero, so the bank stops there."""
    from ark.hostnames import fleet_read_spec, ingest_hostname_journal

    try:
        specs = [fleet_read_spec(source, path) for path in files]
        approvals.check(source, "cdx_timestamp")
    except (ValueError, approvals.NotApproved) as exc:
        typer.echo(f"refusing to ingest: {exc}", err=True)
        raise typer.Exit(code=2) from None
    conn = connect_patiently(patience_s=INGEST_LOCK_PATIENCE_S)
    init_db(conn)
    for path, spec in zip(files, specs, strict=True):
        if spec is None:
            failed = bool(ingest_hostname_journal(conn, path).get("refused"))
        else:
            failed = bool(ingest_files(conn, spec, [path]).get("files_failed"))
        if failed:
            typer.echo(f"{source}: {path.name} did not ingest", err=True)
            raise typer.Exit(code=1)


@app.command(name="ingest-hostnames")
def ingest_hostnames_cmd(
    paths: Annotated[
        list[Path],
        typer.Argument(
            help="Raw capture journals ({url, timestamp} lines) or directories of them.",
            exists=True,
            readable=True,
        ),
    ],
) -> None:
    """Fill hostname_year from raw CDX capture journals (second output unit).

    Class cdx_timestamp. A hostname that is its own registrable is refused here,
    because it belongs to domain_year. Idempotent per file.
    Example: ark ingest-hostnames data/raw/cdx_suffix/
    """
    from ark.hostnames import ingest_hostname_dir

    conn = connect_patiently(patience_s=INGEST_LOCK_PATIENCE_S)
    init_db(conn)
    for path in paths:
        ingest_hostname_dir(conn, path)


@app.command(name="retract-status")
def retract_status_cmd(
    audit: Annotated[
        Path,
        typer.Option(help="The status audit's error captures, `status_errors.tsv.gz`."),
    ] = Path("data/audit/status_errors.tsv.gz"),
    write: Annotated[
        bool, typer.Option("--write", help="Repoint and retract; without it, count only.")
    ] = False,
) -> None:
    """Take every master record off the 4xx and 5xx captures `status_audit.py` lists.

    A host-year with a 2xx or 3xx in the audited raw moves to a new evidence row at the
    earliest one; the rest keep a row that now carries its error status, so they fail XIII
    and export as candidates. `--write` then reads the other web families' journals again
    for the host-years left on an error capture, so a year another family holds comes back.
    """
    from ark.hostnames import AUDITED_FAMILIES, retract_error_captures

    for path in (audit, audit.with_name("status_repoint.tsv.gz")):
        if not path.is_file():
            raise typer.BadParameter(f"no {path}; run scripts/round/status_audit.py")
    conn = connect_patiently(patience_s=INGEST_LOCK_PATIENCE_S)
    init_db(conn)
    stats = retract_error_captures(conn, audit, write=write)

    def total(prefix: str) -> int:
        return sum(n for k, n in stats.items() if k.startswith(prefix))

    for scope, prefix in (("shipped", "shipped_"), ("store", "")):
        count = {
            (grain, action): total(f"{prefix}{grain}_hit_{action}_")
            for grain in ("hy", "dy")
            for action in ("retract", "repoint", "retracted")
        }
        retract = count["hy", "retract"] + count["dy", "retract"]
        repoint = count["hy", "repoint"] + count["dy", "repoint"]
        by_family = ", ".join(
            f"{total(f'{prefix}hy_hit_retract_{f}') + total(f'{prefix}dy_hit_retract_{f}')} {f}"
            for f in AUDITED_FAMILIES
        )
        typer.echo(
            f"{scope}: {retract + repoint:,} records on a 4xx or 5xx capture "
            f"({count['hy', 'retract'] + count['hy', 'repoint']:,} hostname years, "
            f"{count['dy', 'retract'] + count['dy', 'repoint']:,} domain years): "
            f"{retract:,} to retract ({by_family}), {repoint:,} to repoint; "
            f"{count['hy', 'retracted'] + count['dy', 'retracted']:,} already retracted"
        )
    if write:
        typer.echo(
            f"written; {stats['parent_years_moved_to_another_row']:,} parent years moved to "
            f"another row, {stats['restored_by_another_web_family']:,} host-years restored by "
            f"another web family, {stats['left_on_an_error_capture']:,} left as candidates"
        )


@app.command(name="ingest-zone-hostnames")
def ingest_zone_hostnames_cmd(
    paths: Annotated[
        list[Path],
        typer.Argument(help="InterNIC zone files (`*.zone.gz`).", exists=True, readable=True),
    ],
) -> None:
    """Fill hostname_year with the nameserver TARGETS of an InterNIC zone file.

    `ark ingest internic_zone` records the delegated names; this records the hosts
    they point at, which a web crawl never fetches. Dated by the zone's own SOA
    serial, class artifact_listing, idempotent per file.
    Example: ark ingest-zone-hostnames data/raw/internic_zones/org.zone.gz
    """
    from ark.hostnames import ingest_zone_hostnames

    conn = connect_patiently(patience_s=INGEST_LOCK_PATIENCE_S)
    init_db(conn)
    for path in paths:
        stats = ingest_zone_hostnames(conn, path)
        typer.echo(str(stats))


@app.command(name="ingest-blocklist-hostnames")
def ingest_blocklist_hostnames_cmd(
    paths: Annotated[
        list[Path],
        typer.Argument(
            help="Flattened `squidguard-*` list files, or the chastity orig tarball.",
            exists=True,
            readable=True,
        ),
    ],
) -> None:
    """Fill hostname_year with the sub-registrable hosts two banked blocklists name.

    `ark ingest squidguard_2001_blacklist` and `chastity_dated` collapse every listed
    host to its registrable; this keeps the host. Dated by the same stamps, squidGuard's
    compile header and chastity's tar member header, so it reads the tarball.
    Idempotent per file.
    """
    from ark.hostnames import ingest_blocklist_hostnames

    conn = connect_patiently(patience_s=INGEST_LOCK_PATIENCE_S)
    init_db(conn)
    totals: Counter = Counter()
    for path in paths:
        for key, value in ingest_blocklist_hostnames(conn, path).items():
            if isinstance(value, int) and not isinstance(value, bool):
                totals[key] += value
    typer.echo(str(dict(totals)))


@app.command(name="ingest-ripe-nserver-hostnames")
def ingest_ripe_nserver_hostnames_cmd(
    paths: Annotated[
        list[Path],
        typer.Argument(
            help="FUNET's `ripe.db.gz` (1999 snapshot) and `split/ripe.db.domain.gz` (2004).",
            exists=True,
            readable=True,
        ),
    ],
) -> None:
    """Fill hostname_year with the nameservers RIPE `domain:` objects point at.

    `ark ingest ripe_dbase_1999` and `ripe_dbase_split_2004` record the delegated
    names; this records the `*ns:` / `nserver:` hosts they name, dated by the same
    stamps (the snapshot's header, the object's latest `changed:` line). Class
    artifact_listing, under the RIPE NCC permission. Idempotent per file.
    """
    from ark.hostnames import ingest_ripe_nserver_hostnames

    conn = connect_patiently(patience_s=INGEST_LOCK_PATIENCE_S)
    init_db(conn)
    for path in paths:
        typer.echo(str(ingest_ripe_nserver_hostnames(conn, path)))


@app.command(name="ingest-isc-hostnames")
def ingest_isc_hostnames_cmd(
    paths: Annotated[
        list[Path],
        typer.Argument(
            help="ISC survey per-TLD host files (`data/raw/isc_survey/wb_nw_*_<tld>.gz`).",
            exists=True,
            readable=True,
        ),
    ],
) -> None:
    """Fill hostname_year with the hosts the ISC Internet Domain Survey lists.

    `ark ingest isc_survey` collapses every `IP hostname` line to its registrable;
    this keeps the host itself, dated by the same `YYMM` survey code, class
    artifact_listing. `.domains` files are skipped by name. Idempotent per file.
    Example: ark ingest-isc-hostnames data/raw/isc_survey/wb_nw_*.gz
    """
    from ark.hostnames import ingest_isc_hostnames

    conn = connect_patiently(patience_s=INGEST_LOCK_PATIENCE_S)
    init_db(conn)
    for path in paths:
        typer.echo(str(ingest_isc_hostnames(conn, path)))


@app.command(name="ingest-usenet-hostnames")
def ingest_usenet_hostnames_cmd(
    paths: Annotated[
        list[Path],
        typer.Argument(
            help="`{item, year, text}` shards, or directories of them "
            "(`data/raw/usenet_*_items/`).",
            exists=True,
            readable=True,
        ),
    ],
) -> None:
    """Fill hostname_year with the hosts typed as body URLs in dated Usenet posts.

    Class link_source. The host authority of an explicit `http://`, `https://` or
    `ftp://` URL in the post BODY only: a `Path`, `Xref`, `NNTP-Posting-Host`,
    `Message-ID`, `From` or `Organization` host is a news relay or a mailbox, never a
    host that served a page. Idempotent per shard, keyed by pool and shard name.
    Example: ark ingest-usenet-hostnames data/raw/usenet_comp_items
    """
    from ark.hostnames import ingest_usenet_item_dir

    conn = connect_patiently(patience_s=INGEST_LOCK_PATIENCE_S)
    init_db(conn)
    for path in paths:
        typer.echo(str(ingest_usenet_item_dir(conn, path)))


@app.command(name="ingest-maillist-hostnames")
def ingest_maillist_hostnames_cmd(
    paths: Annotated[
        list[Path],
        typer.Argument(
            help="`{item, year, text}` shards from build_maillist_pool.py, or directories "
            "of them (`data/raw/maillists_items/`).",
            exists=True,
            readable=True,
        ),
    ],
) -> None:
    """Fill hostname_year with the hosts typed as body URLs in dated mailing-list messages.

    Class link_source, the Usenet lane's evidence shape read from pipermail month files.
    The item pointer is `<host>/<list>__<YYYY-Month>.txt#<n>`, message n of a file the
    archive host still serves by name. Idempotent per shard.
    Example: ark ingest-maillist-hostnames data/raw/maillists_items
    """
    from ark.hostnames import MAILLIST_FAMILY, ingest_usenet_item_dir

    conn = connect_patiently(patience_s=INGEST_LOCK_PATIENCE_S)
    init_db(conn)
    for path in paths:
        typer.echo(str(ingest_usenet_item_dir(conn, path, family=MAILLIST_FAMILY)))


@app.command(name="ingest-enron-hostnames")
def ingest_enron_hostnames_cmd(
    paths: Annotated[
        list[Path],
        typer.Argument(
            help="`{item, year, text}` shards from build_enron_pool.py, or directories "
            "of them (`data/raw/enron_items/`).",
            exists=True,
            readable=True,
        ),
    ],
) -> None:
    """Fill hostname_year with the hosts typed as body URLs in dated Enron messages.

    Class link_source, the third member of the body-URL family, from the CMU release of
    the Enron mailbox. The item pointer is the message's own path inside the tarball,
    `maildir/<custodian>/<folder>/<n>.`. Idempotent per shard.
    Example: ark ingest-enron-hostnames data/raw/enron_items
    """
    from ark.hostnames import ENRON_FAMILY, ingest_usenet_item_dir

    conn = connect_patiently(patience_s=INGEST_LOCK_PATIENCE_S)
    init_db(conn)
    for path in paths:
        typer.echo(str(ingest_usenet_item_dir(conn, path, family=ENRON_FAMILY)))


@app.command(name="ingest-apache-header-hostnames")
def ingest_apache_header_hostnames_cmd(
    paths: Annotated[
        list[Path],
        typer.Argument(
            help="`{item, year, text}` shards from build_apache_header_pool.py, or "
            "directories of them (`data/raw/apache_header_items/`).",
            exists=True,
            readable=True,
        ),
    ],
) -> None:
    """Fill hostname_year with the relay hosts of dated Apache list messages.

    C-83, class link_source, for the `Received: ... by <host>` clause ALONE: the receiving
    MTA writes its own name there, so the field is machine-written and takes no
    corroboration split. The `from` clause is a sender-chosen HELO name and is not read,
    nor is the parenthesised reverse-DNS: neither was approved. The item pointer is
    `<list domain>/<list>__<YYYY-MM>#<n>`, message n of that list-month's mbox export.
    Idempotent per shard.
    Example: ark ingest-apache-header-hostnames data/raw/apache_header_items
    """
    from ark.hostnames import APACHE_FAMILY, ingest_usenet_item_dir

    conn = connect_patiently(patience_s=INGEST_LOCK_PATIENCE_S)
    init_db(conn)
    for path in paths:
        typer.echo(str(ingest_usenet_item_dir(conn, path, family=APACHE_FAMILY)))


@app.command(name="ingest-ietf-header-hostnames")
def ingest_ietf_header_hostnames_cmd(
    paths: Annotated[
        list[Path],
        typer.Argument(
            help="`{item, year, text}` shards from collect_ietf_mail_archive.py, or "
            "directories of them (`data/raw/ietf_header_items/`).",
            exists=True,
            readable=True,
        ),
    ],
) -> None:
    """Fill hostname_year with the relay hosts of dated IETF list messages.

    C-83's class at a second host, not a new class: the same `Received: ... by <host>`
    clause, read by the Apache lane's parser, with `from` and the parenthesised
    reverse-DNS skipped here too. The item pointer is `www.ietf.org/<tree>/<list>/<file>#<n>`,
    and the file name is carried whole because the archive spells early months `1996-03`
    and later ones `1999-05.mail`. Idempotent per shard.
    Example: ark ingest-ietf-header-hostnames data/raw/ietf_header_items
    """
    from ark.hostnames import IETF_FAMILY, ingest_usenet_item_dir

    conn = connect_patiently(patience_s=INGEST_LOCK_PATIENCE_S)
    init_db(conn)
    for path in paths:
        typer.echo(str(ingest_usenet_item_dir(conn, path, family=IETF_FAMILY)))


@app.command(name="ingest-usenet-header-hostnames")
def ingest_usenet_header_hostnames_cmd(
    paths: Annotated[
        list[Path],
        typer.Argument(
            help="`{item, year, text}` shards from build_usenet_header_pool.py, or "
            "directories of them.",
            exists=True,
            readable=True,
        ),
    ],
) -> None:
    """Fill hostname_year with the server-written header hosts of dated Usenet posts.

    Three fields, all written by a news server about a transaction it completed: the
    trailing hostname of `X-Trace:`, the `NNTP-Posting-Host:` the accepting server
    logged, and the final `Path:` hop. The `Message-ID` host is client-written and is
    not read. Idempotent per shard.
    Example: ark ingest-usenet-header-hostnames data/raw/usenet_header_items
    """
    from ark.hostnames import USENET_HEADER_FAMILY, ingest_usenet_item_dir

    conn = connect_patiently(patience_s=INGEST_LOCK_PATIENCE_S)
    init_db(conn)
    for path in paths:
        typer.echo(str(ingest_usenet_item_dir(conn, path, family=USENET_HEADER_FAMILY)))


@app.command(name="seed-pool")
def seed_pool(
    source: Annotated[
        str,
        typer.Argument(help=f"Bulk source key: one of {', '.join(sorted(SOURCES))}."),
    ],
    files: Annotated[
        list[Path],
        typer.Argument(help="The same source files that were ingested.", readable=True),
    ],
) -> None:
    """Extract a source's raw hostnames and URLs into the auxiliary seed pool.

    Deliberately not `ark seed`, which loads candidate DOMAINS: this writes the HOSTNAME
    and URL download seeds kept by registrable-grain parsers, and they do not replace the
    evidence-backed annual hostname records brief IV.8 requires. Same files, same parser
    as `ark ingest`, keeping the raw value instead of the canonical one, so a seed cannot
    disagree with the evidence it came from. Re-running a source replaces only its rows.

    Example: ark seed-pool isc_survey data/raw/isc_survey/*.gz
    """
    spec = SOURCES.get(source)
    if spec is None:
        raise typer.BadParameter(f"unknown source '{source}'; known: {', '.join(sorted(SOURCES))}")
    stats = write_source_part(spec, files)
    combined = combine_parts(connect())
    typer.echo(f"seed-pool {source}: {dict(stats)}\nseed pool: {combined}")


# Deliberately short: long enough to ride out the gap between two files inside one ingest
# pass, no longer. A generous wait does not make the seed polite, it makes it QUEUE, so it
# wins the lock the moment the ingest finishes and then holds it for its own long run.
# ADR-001 is explicit that seeding yields, because a candidate claims nothing until
# something dates it.
SEED_LOCK_PATIENCE_S = 20


@app.command()
def seed(
    seed_file: Annotated[
        Path,
        typer.Argument(help="File with one host or URL per line.", exists=True, readable=True),
    ],
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-n", help="Read at most this many non-blank lines."),
    ] = None,
) -> None:
    """Load seed domains into the candidate pool and queue unknown ones.

    Example: ark seed legacy-data/deduplicated_urls_2001-2002.txt --limit 5000

    Yields to a writer rather than crashing against one: ADR-001 puts banking a
    collector's journal above seeding. It waits only long enough to ride out a gap
    inside one ingest pass, then says it yielded. Safe to re-run: inserts autocommit
    and are `INSERT OR IGNORE`.
    """
    try:
        conn = connect_patiently(patience_s=SEED_LOCK_PATIENCE_S)
    except duckdb.IOException as exc:
        if "Conflicting lock" not in str(exc):
            raise
        raise SystemExit(
            f"the store was still being written after {SEED_LOCK_PATIENCE_S}s, so this seed "
            f"yielded and wrote nothing.\n"
            f"Per ADR-001 banking a finished journal outranks seeding, so waiting is correct "
            f"and this is not an error.\n"
            f"Re-run when the ingest loop is idle: a re-run is additive, since inserts "
            f"autocommit and the insert ignores duplicates."
        ) from None
    queue_conn = connect_queue()
    seed_from_file(conn, queue_conn, seed_file, limit)


@app.command()
def download(
    seeds: Annotated[
        Path,
        typer.Argument(
            help="Seed file: one page URL per line, optionally TAB 'directory' to assert "
            "the page is a curated catalogue.",
            exists=True,
            readable=True,
        ),
    ],
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="Fetch at most this many not-yet-done pages.")
    ] = 100,
    workers: Annotated[int, typer.Option("--workers", help="Concurrent fetches.")] = 4,
    delay: Annotated[
        float, typer.Option("--delay", help="Starting seconds between requests.")
    ] = 0.3,
    captures: Annotated[
        int,
        typer.Option(
            "--captures", help="In-window captures to fetch per page (each is its own year)."
        ),
    ] = 2,
    out: Annotated[
        Path | None,
        typer.Option(
            "--out", help="Journal to write (default data/raw/expand/expand_<UTC>.jsonl.gz)."
        ),
    ] = None,
) -> None:
    """Fetch archived pages and extract links for the brief's source-expansion loop.

    Collection only: writes a per-run journal and never opens the store. Bank it with
    `ark ingest expansion_links <journal> --round N` for the candidate half, or
    `expansion_directory` for pages asserted to be curated directories, whose capture
    date evidences their entries. Resumable: a page already answered is skipped.
    """
    path = out or journal_path(EXPAND_JOURNAL_DIR, EXPAND_JOURNAL_PREFIX)
    path.parent.mkdir(parents=True, exist_ok=True)
    done = queried_domains(path.parent, EXPAND_JOURNAL_PREFIX, answered=expand_answered)
    seed_list = [
        (url, curated)
        for url, curated in read_seeds(
            seeds.read_text(encoding="utf-8", errors="replace").splitlines()
        )
        if url not in done
    ][:limit]

    first, last = min(YEARS), max(YEARS)
    governor = RateGovernor(delay=delay, max_delay=5.0)
    fetch = http_fetch(70.0)
    stats: Counter = Counter({"seeds": len(seed_list), "skipped_done": len(done)})
    written = 0
    if seed_list:
        with journal_writer(path) as journal, _abortable_pool(workers) as pool:
            futures = {
                pool.submit(
                    expand_page,
                    url,
                    first,
                    last,
                    fetch,
                    governor,
                    curated=curated,
                    per_page_captures=captures,
                ): url
                for url, curated in seed_list
            }
            for future in tqdm(as_completed(futures), total=len(futures), unit="page"):
                try:
                    records = future.result()
                except Exception as exc:  # noqa: BLE001 (one bad page must not end the run)
                    logger.warning(f"{futures[future]}: {exc}")
                    stats["errored"] += 1
                    continue
                for record in records:
                    # the journal keys on the page URL, so a record needs it even
                    # when the fetch failed and there is nothing else to say
                    record["domain"] = record["page_url"]
                    write_journal_line(journal, record)
                    written += 1
                    stats["captures" if record["status"] == 200 else "failed"] += 1
                    stats["domains_found"] += len(record.get("domains") or [])
                if written % _JOURNAL_FLUSH_EVERY == 0:
                    journal.flush()
    if written == 0:
        path.unlink(missing_ok=True)
        logger.info("download: nothing new to fetch; no journal written")
    summary = dict(stats)
    logger.info(f"download: {summary} -> {path if written else 'no journal'}")
    typer.echo(f"download: {summary}")
    if written:
        typer.echo(
            f"journal: {path}\n"
            f"next: uv run ark ingest expansion_links {path} --round 1\n"
            f"      uv run ark ingest expansion_directory {path} --round 1"
        )


@app.command()
def export(
    provenance: Annotated[
        bool,
        typer.Option(
            "--provenance/--no-provenance",
            help="Also write the provenance graph. Needed to ship a round or to `ark rebuild`.",
        ),
    ] = False,
    claim: Annotated[
        bool,
        typer.Option(
            "--claim",
            help="Write only the claim and its stamp, as the bank does. Packaging refuses it.",
        ),
    ] = False,
) -> None:
    """Write net-new year files, candidates, manifest, merged masters and the stamp; `--claim`
    writes only the claim files ROUND.md reads and the stamp.

    Patient, because it is the first step of shipping a round: DuckDB blocks a write
    connection against any other process holding the file, even a reader, and this
    project always has readers.

    **The provenance graph is off unless asked for**: it is 229 of the command's 444
    seconds and 2,319 MB, and only `package_delivery.sh` and `just rebuild` read it.
    """
    if claim and provenance:
        raise typer.BadParameter("--claim writes no provenance graph: pass one of the two")
    conn = connect_patiently()
    export_all(conn, with_provenance=provenance, claim_only=claim)


@app.command(name="price-snapshot")
def price_snapshot_cmd(
    snapshot: Annotated[
        Path,
        typer.Option(help="Snapshot directory: manifest.json, the marker, netnew, candidates."),
    ],
    items: Annotated[
        Path, typer.Option(help="JSONL(.gz) of {host, year, text?}, one item per line.")
    ],
    track: Annotated[
        str, typer.Option(help="`annual` for (name, year) records, `candidate` for undated names.")
    ] = "annual",
) -> None:
    """Price items against a pushed snapshot and print one JSON object.

    The only price a fleet leg may quote. Reads no store, writes nothing, and refuses a
    snapshot whose files disagree with its manifest, so the figure is reproducible from
    the marker and `built_at` it carries.
    """
    try:
        priced = price_against_snapshot(snapshot, items, track)
    except SnapshotError as exc:
        logger.error(str(exc))
        raise typer.Exit(2) from exc
    # stdout is the JSON and nothing else: a leg copies fields out of it.
    typer.echo(json.dumps(priced, indent=2))


@app.command()
def audit(
    legacy_dir: Annotated[
        Path, typer.Option(help="Folder holding the provided baseline files.")
    ] = Path("legacy-data"),
) -> None:
    """Write the normalization/salvage audit CSV over the baseline files."""
    write_audit(legacy_dir)


@app.command()
def stats() -> None:
    """Print the scoreboard: net-new counts on top of the baseline."""
    # Waits out the ingest loop rather than raising a lock traceback: this records a
    # metrics row, so it needs the write lock even though it only reports.
    conn = connect_patiently()
    scoreboard = collect_stats(conn)
    typer.echo(format_stats(scoreboard))
    # the exact reported figures leave a timestamped audit trail
    record_metrics(conn, "stats", "scoreboard", scoreboard)


@app.command()
def cdx(
    candidates: Annotated[
        Path,
        typer.Argument(help="File with one domain or URL per line.", exists=True, readable=True),
    ],
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="Query at most this many not-yet-queried domains.")
    ] = 1000,
    workers: Annotated[
        int, typer.Option("--workers", help="Concurrent requests; the governor paces them.")
    ] = 8,
    delay: Annotated[
        float, typer.Option("--delay", help="Starting seconds between requests (adapts).")
    ] = 0.25,
    max_delay: Annotated[
        float,
        typer.Option(
            "--max-delay",
            help="Ceiling on the adaptive pace. Keep low at high concurrency: pacing is a "
            "safety valve, and a high ceiling turns one throttle burst into a stalled run.",
        ),
    ] = 5.0,
    min_delay: Annotated[
        float,
        typer.Option(
            "--min-delay",
            help="Floor the governor may not ease below. The default is the historic pace that "
            "sustained roughly 1,000 domains/hour for days. Raise it when another engine is "
            "already querying web.archive.org, since the floor, not the worker count, is what "
            "bounds the combined load.",
        ),
    ] = 0.05,
    timeout: Annotated[
        float,
        typer.Option("--timeout", help="Seconds to wait per request before giving up."),
    ] = 70.0,
    host_timeout: Annotated[
        float,
        typer.Option(
            "--host-timeout",
            help="Seconds to allow the cheap per-host query before giving up on it "
            "and asking the root pages instead. Short on purpose: that tier answers "
            "at a p90 of 6.2s, so anything slower is a domain it cannot serve, and "
            "waiting the full timeout for that verdict is paid on every such domain.",
        ),
    ] = HOST_TIMEOUT,
    wildcard_first: Annotated[
        bool,
        typer.Option(
            "--wildcard-first",
            help="Ask the `*.domain` scan before the cheap per-host query, which is "
            "the old order. The default asks the host first because it measured a "
            "median 2.07s against roughly 33s for the scan, with the same years "
            "returned every time both answered. Use this to reproduce older runs.",
        ),
    ] = False,
    per_year: Annotated[
        bool,
        typer.Option(
            "--per-year",
            help="Ask one cheap query per year instead of one per domain. Slower overall, "
            "but succeeds on heavily archived domains the default strategy cannot finish. "
            "Use it as a second sweep: unanswered domains are picked up automatically.",
        ),
    ] = False,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Journal to write (default data/raw/cdx/cdx_<UTC>.jsonl.gz)."),
    ] = None,
) -> None:
    """Ask the IA CDX index which in-window years hold a capture, per domain.

    Collection only: writes a per-run journal and never opens the store, so it
    runs for hours alongside other work. Turn journals into evidence with
    `ark ingest cdx_snapshot <journal>`.

    One collapsed query covers all six years. Requests are paced by an adaptive
    governor that eases up while the service is healthy and backs off hard on
    429/503/504, honouring Retry-After, per brief section VII. Resumable: any
    domain already recorded in a journal in the same folder is skipped.
    """
    path = out or journal_path(CDX_JOURNAL_DIR, CDX_JOURNAL_PREFIX)
    path.parent.mkdir(parents=True, exist_ok=True)
    already = queried_domains(path.parent, CDX_JOURNAL_PREFIX, answered=cdx_answered)
    logger.info(f"cdx: {len(already):,} domains already journalled; writing {path}")

    targets: list[str] = []
    stats: Counter = Counter()
    with candidates.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            raw = line.strip()
            if not raw:
                continue
            domain = to_registrable(raw)
            if domain is None:
                stats["rejected"] += 1
                continue
            if domain in already:
                stats["skipped_journalled"] += 1
                continue
            targets.append(domain)
            if len(targets) >= limit:
                break

    first, last = min(YEARS), max(YEARS)
    governor = RateGovernor(delay=delay, min_delay=min_delay, max_delay=max_delay)
    written = 0
    if targets:
        with journal_writer(path) as journal, _abortable_pool(workers) as pool:
            strategy: Callable[..., dict] = (
                lookup_years_per_year
                if per_year
                else partial(
                    lookup_years,
                    host_first=not wildcard_first,
                    host_fetch=http_fetch(host_timeout),
                )
            )
            fetch = http_fetch(timeout)
            futures = {
                pool.submit(strategy, d, first, last, fetch, governor=governor): d for d in targets
            }
            for future in tqdm(as_completed(futures), total=len(futures), unit="domain"):
                try:
                    record = future.result()
                except Exception as exc:  # noqa: BLE001 (one bad domain must not end the run)
                    logger.warning(f"{futures[future]}: {exc}")
                    stats["errored"] += 1
                    continue
                write_journal_line(journal, record)
                written += 1
                if not cdx_answered(record):
                    stats[f"failed_{record['status']}"] += 1
                elif record["years"]:
                    stats["with_capture"] += 1
                    stats["years_found"] += len(record["years"])
                else:
                    stats["no_capture"] += 1
                if written % _JOURNAL_FLUSH_EVERY == 0:
                    journal.flush()
    if written == 0:
        path.unlink(missing_ok=True)
        logger.info("cdx: nothing new to query; no journal written")

    stats["queried"] = written
    stats["throttles"] = governor.throttles
    stats["final_delay_ms"] = int(governor.delay * 1000)
    summary = dict(stats)
    logger.info(f"cdx: {summary} -> {path if written else 'no journal'}")
    typer.echo(f"cdx: {summary}")
    if written:
        typer.echo(f"journal: {path}\nnext: uv run ark ingest cdx_snapshot {path}")
        # interpretation keeps only years the archive returned, so a domain it could
        # not date leaves no trace. That is right for a pool drawn from domains
        # already held, and wrong for a pool of unknown ones, where the undatable
        # ones are meant to be kept as candidates.
        undated = stats.get("no_capture", 0) + stats.get("failed_0", 0)
        if undated:
            typer.echo(
                f"note: {undated:,} domains got no in-window capture; if this list was not "
                f"already held, run `uv run ark seed {candidates}` to keep them as candidates"
            )


@app.command()
def rebuild(
    provenance_dir: Annotated[
        Path,
        typer.Argument(help="Folder holding the provenance Parquet files."),
    ] = PROVENANCE_DIR,
    force: Annotated[
        bool,
        typer.Option("--force", help="Rebuild even when the store is ahead of the export."),
    ] = False,
) -> None:
    """Rebuild the result from a provenance export, with no source data.

    Loads the exported evidence graph into the store and re-runs the exporter, which
    regenerates the annual files, the merged masters, the candidate list and the
    manifest. Run `ark check` afterwards.

    DROPS the store's tables before recreating them from Parquet, so it refuses when the
    store holds ingested files the export does not: during collection anything banked
    since the last `ark export` would be discarded silently. --force if that is intended.

    Example: ark rebuild ../provenance
    """
    conn = connect()
    ledger_query = "SELECT count(*) FROM ingested_file"
    try:
        in_store = conn.execute(ledger_query).fetchone()[0]
    except Exception:  # noqa: BLE001 - an empty store has no ledger yet, which is fine
        in_store = 0
    parquet = provenance_dir / "ingested_file.parquet"
    in_export = 0
    if parquet.exists():
        in_export = conn.execute(
            f"SELECT count(*) FROM read_parquet('{parquet}')"  # noqa: S608
        ).fetchone()[0]
    if in_store > in_export and not force:
        raise typer.BadParameter(
            f"refusing to rebuild: the store holds {in_store:,} ingested files and "
            f"{provenance_dir} holds {in_export:,}. Rebuilding drops the store's tables, so "
            f"the {in_store - in_export:,} newer ingests would be discarded. Run `ark export` "
            f"first, or pass --force if that is what you want."
        )

    load_provenance(conn, provenance_dir)
    stats = export_all(conn)
    typer.echo(f"rebuilt from {provenance_dir}: {stats}\nnext: uv run ark check")


@app.command()
def check() -> None:
    """Run integrity checks over the store; exit non-zero if any fails."""
    # Read-only and patient: the gate writes nothing, and a lock traceback out of it reads
    # as a broken invariant when the store is merely busy. Closed before returning, since a
    # read-write open in the same process fails while this connection lives.
    conn = connect_read_only_patiently()
    try:
        results = collect_checks(conn, audit=AUDIT_PATH)
    finally:
        conn.close()
    typer.echo(format_checks(results))
    if any(not r["ok"] for r in results):
        raise typer.Exit(code=1)


def main() -> None:
    app()
