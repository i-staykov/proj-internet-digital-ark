"""Command-line entry point for the ark pipeline."""

import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger
from tqdm import tqdm

from ark.audit import write_audit
from ark.bulk import ingest_files
from ark.canonical import to_registrable
from ark.cdx import RateGovernor, http_fetch, lookup_years, lookup_years_per_year
from ark.cdx import answered as cdx_answered
from ark.checks import collect_checks, format_checks
from ark.db import DEFAULT_DB_PATH, connect, init_db
from ark.export import export_all
from ark.gaps import write_gap_candidates
from ark.ingest import YEARS, ingest_legacy
from ark.journal import journal_path, open_journal_for_write, queried_domains, write_journal_line
from ark.legacy_review import DEFAULT_DROPLIST_PATH, review_legacy
from ark.metrics import record_metrics
from ark.rdap import (
    JOURNAL_DIR as RDAP_JOURNAL_DIR,
)
from ark.rdap import (
    JOURNAL_PREFIX as RDAP_JOURNAL_PREFIX,
)
from ark.rdap import (
    lookup,
)
from ark.seed import seed_from_file
from ark.sources import SOURCES
from ark.stats import collect_stats, format_stats
from ark.verify import verify_batch
from ark.work_queue import DEFAULT_QUEUE_PATH, connect_queue

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
        Path, typer.Option(help="Folder holding the provided baseline files.")
    ] = Path("legacy-data"),
) -> None:
    """Load the baseline year files and merge stats into the store."""
    conn = connect()
    init_db(conn)
    all_stats = ingest_legacy(conn, legacy_dir)
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
        Path, typer.Option(help="Folder holding the provided baseline files.")
    ] = Path("legacy-data"),
) -> None:
    """Write the grouped droplist of baseline lines the pipeline excludes."""
    counts = review_legacy(legacy_dir)
    logger.info(f"see {DEFAULT_DROPLIST_PATH} ({sum(counts.values())} distinct entries)")


@app.command(name="ingest")
def ingest_cmd(
    source: Annotated[
        str, typer.Argument(help=f"Bulk source key: one of {', '.join(sorted(SOURCES))}.")
    ],
    files: Annotated[
        list[Path],
        typer.Argument(help="Source files to ingest (gzip ok).", exists=True, readable=True),
    ],
) -> None:
    """Ingest bulk source files through the shared audited loader.

    Idempotent per file: a file already in the ledger is skipped whole.
    Example: ark ingest early_web data/raw/early_web/*.cdx.gz
    """
    spec = SOURCES.get(source)
    if spec is None:
        raise typer.BadParameter(f"unknown source '{source}'; known: {', '.join(sorted(SOURCES))}")
    conn = connect()
    init_db(conn)
    queue_conn = connect_queue()
    ingest_files(conn, spec, files, queue_conn=queue_conn)


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
    """
    conn = connect()
    queue_conn = connect_queue()
    seed_from_file(conn, queue_conn, seed_file, limit)


@app.command()
def verify(
    batch_size: Annotated[
        int, typer.Option("--batch-size", "-b", help="Domains to verify in this run.")
    ] = 25,
) -> None:
    """Check queued candidates for per-year evidence via the IA CDX index."""
    conn = connect()
    queue_conn = connect_queue()
    verify_batch(conn, queue_conn, batch_size)


@app.command()
def download() -> None:
    """Download verified pages and extract outbound links."""
    logger.info("download: not implemented yet")


@app.command()
def export() -> None:
    """Write net-new year files, candidates, manifest, and merged masters."""
    conn = connect()
    export_all(conn)


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
    conn = connect()
    scoreboard = collect_stats(conn)
    typer.echo(format_stats(scoreboard))
    # the exact reported figures leave a timestamped audit trail
    record_metrics(conn, "stats", "scoreboard", scoreboard)


@app.command()
def rdap(
    candidates: Annotated[
        Path,
        typer.Argument(
            help="File with one candidate domain or URL per line.", exists=True, readable=True
        ),
    ],
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="Query at most this many not-yet-queried domains.")
    ] = 1000,
    delay: Annotated[
        float, typer.Option("--delay", help="Seconds to pause between RDAP queries (politeness).")
    ] = 0.15,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Journal to write (default data/raw/rdap/rdap_<UTC>.jsonl.gz)."),
    ] = None,
) -> None:
    """Query RDAP for candidate domains and write a per-run journal file.

    Collection only: writes no evidence and never opens the store, so it runs
    alongside other stages. Turn a journal into evidence with
    `ark ingest rdap_snapshot <journal>`, which hashes it into the file ledger
    like any other source. Keeping whole responses means a later change of
    evidence standard is a re-parse, not a migration.

    Resumable: any domain already recorded in a journal in the same folder is
    skipped, so an interrupted run is finished by running the command again.
    """
    path = out or journal_path(RDAP_JOURNAL_DIR, RDAP_JOURNAL_PREFIX)
    path.parent.mkdir(parents=True, exist_ok=True)
    already = queried_domains(path.parent, RDAP_JOURNAL_PREFIX)
    logger.info(f"rdap: {len(already):,} domains already journalled; writing {path}")
    stats: Counter = Counter()
    queried = 0
    with open_journal_for_write(path) as journal:
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
                if queried >= limit:
                    break
                already.add(domain)
                queried += 1
                record = lookup(domain)
                write_journal_line(journal, record)
                stats["dated" if record["creation_year"] is not None else "not_dated"] += 1
                # flush periodically so an interrupted run keeps its work
                if queried % _JOURNAL_FLUSH_EVERY == 0:
                    journal.flush()
                if delay:
                    time.sleep(delay)
    if queried == 0:
        path.unlink(missing_ok=True)
        logger.info("rdap: nothing new to query; no journal written")
    stats["queried"] = queried
    summary = dict(stats)
    logger.info(f"rdap: {summary} -> {path if queried else 'no journal'}")
    typer.echo(f"rdap: {summary}")
    if queried:
        typer.echo(f"journal: {path}\nnext: uv run ark ingest rdap_snapshot {path}")


@app.command()
def gaps(
    out: Annotated[
        Path, typer.Option("--out", help="Where to write the prioritised domain list.")
    ] = Path("data/raw/cdx/gap_candidates.txt"),
) -> None:
    """List held domains whose missing year is bracketed by two held years.

    One archive query answers every year for a domain, so the output is a
    domain list, ordered thinnest gap year first. Feed it to `ark cdx`.
    """
    conn = connect()
    summary = write_gap_candidates(conn, out)
    record_metrics(conn, "gaps", "sandwich", summary)
    logger.info(f"gaps: {summary} -> {out}")
    typer.echo(f"gaps: {summary}\nwrote {out}\nnext: uv run ark cdx {out}")


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
    timeout: Annotated[
        float,
        typer.Option("--timeout", help="Seconds to wait per request before giving up."),
    ] = 70.0,
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
    429/503/504, honouring Retry-After, per brief section VI. Resumable: any
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
    governor = RateGovernor(delay=delay, max_delay=max_delay)
    written = 0
    if targets:
        with open_journal_for_write(path) as journal, ThreadPoolExecutor(workers) as pool:
            strategy = lookup_years_per_year if per_year else lookup_years
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


@app.command()
def check() -> None:
    """Run integrity checks over the store; exit non-zero if any fails."""
    conn = connect()
    results = collect_checks(conn)
    typer.echo(format_checks(results))
    record_metrics(conn, "check", "integrity", {r["name"]: r["offending"] for r in results})
    if any(not r["ok"] for r in results):
        raise typer.Exit(code=1)


def main() -> None:
    app()
