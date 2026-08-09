"""Command-line entry point for the ark pipeline."""

import sys
from collections import Counter
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger
from tqdm import tqdm

from ark.audit import write_audit
from ark.baseline import CURRENT_BASELINE_DIR, CURRENT_BASELINE_MARKER
from ark.bulk import ingest_files
from ark.canonical import to_registrable
from ark.cdx import HOST_TIMEOUT, RateGovernor, http_fetch, lookup_years, lookup_years_per_year
from ark.cdx import answered as cdx_answered
from ark.checks import collect_checks, format_checks
from ark.db import DEFAULT_DB_PATH, connect, init_db
from ark.expand import answered as expand_answered
from ark.expand import expand_page, read_seeds
from ark.export import export_all
from ark.gaps import write_creation_candidates, write_gap_candidates
from ark.ingest import YEARS, ingest_legacy
from ark.journal import journal_path, journal_writer, queried_domains, write_journal_line
from ark.language import (
    JOURNAL_DIR as LANG_JOURNAL_DIR,
)
from ark.language import (
    JOURNAL_PREFIX as LANG_JOURNAL_PREFIX,
)
from ark.language import (
    TARGETS_PATH as LANG_TARGETS_PATH,
)
from ark.language import (
    answered as lang_answered,
)
from ark.language import (
    bytes_fetcher,
    classify_pair,
    format_language_summary,
    ingest_language_journal,
    pair_key,
    read_targets,
    write_lang_targets,
    write_language_summary,
    write_partitioned_annual_files,
)
from ark.legacy_review import DEFAULT_DROPLIST_PATH, review_legacy
from ark.metrics import record_metrics
from ark.provenance import PROVENANCE_DIR, load_provenance
from ark.rdap import (
    JOURNAL_DIR as RDAP_JOURNAL_DIR,
)
from ark.rdap import (
    JOURNAL_PREFIX as RDAP_JOURNAL_PREFIX,
)
from ark.rdap import (
    Router,
    load_registries,
    lookup,
)
from ark.rdap import (
    answered as rdap_answered,
)
from ark.rdap import (
    http_fetch as rdap_http_fetch,
)
from ark.seed import seed_from_file
from ark.seeds import combine_parts, write_source_part
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
# consecutive `ark lang` failures that mean the archive has stopped answering
_LANG_FAILURE_BREAKER = 25
CDX_JOURNAL_DIR = Path("data/raw/cdx")
CDX_JOURNAL_PREFIX = "cdx"
EXPAND_JOURNAL_DIR = Path("data/raw/expand")
EXPAND_JOURNAL_PREFIX = "expand"


@contextmanager
def _abortable_pool(workers: int) -> Iterator[ThreadPoolExecutor]:
    """A worker pool that drops its queued work when the run stops early.

    `with ThreadPoolExecutor(...)` waits for every queued task on the way out.
    These runs submit the whole batch up front, so on Ctrl-C or SIGTERM that
    turns "stop" into "first finish the eleven hundred requests still queued",
    and the process looks like it is ignoring the signal. Cancelling the pending
    futures loses nothing: an unanswered domain was never journalled, so the next
    run simply asks again.
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
        Path, typer.Option(help="Folder holding the provided baseline files.")
    ] = CURRENT_BASELINE_DIR,
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
        Path, typer.Option(help="Folder holding the provided baseline files.")
    ] = CURRENT_BASELINE_DIR,
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
    spec = SOURCES.get(source)
    if spec is None:
        raise typer.BadParameter(f"unknown source '{source}'; known: {', '.join(sorted(SOURCES))}")
    conn = connect()
    init_db(conn)
    queue_conn = connect_queue()
    ingest_files(conn, spec, files, queue_conn=queue_conn, discovered_round=round_)


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

    Deliberately not called `seed`: `ark seed` loads candidate DOMAINS into the
    verification pool, while this writes the HOSTNAME and URL download seeds
    that III.8's registered-domain counting unit necessarily discards.

    Reads the same files through the same parser as `ark ingest`, keeping the raw
    value instead of the canonical one, so a seed cannot disagree with the
    evidence it came from. Re-running a source replaces only its own rows.

    Example: ark seed-pool isc_survey data/raw/isc_survey/*.gz
    """
    spec = SOURCES.get(source)
    if spec is None:
        raise typer.BadParameter(f"unknown source '{source}'; known: {', '.join(sorted(SOURCES))}")
    stats = write_source_part(spec, files)
    combined = combine_parts(connect())
    typer.echo(f"seed-pool {source}: {dict(stats)}\nseed pool: {combined}")


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
    """Fetch archived pages and extract the domains they link to (brief section VII).

    Collection only: writes a per-run journal and never opens the store. Turn it
    into evidence with `ark ingest expansion_links <journal> --round N` for the
    candidate half, and `ark ingest expansion_directory <journal> --round N` for
    pages asserted to be curated directories, whose capture date evidences their
    entries.

    Resumable: a page already answered in a journal in the same folder is skipped.
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
    workers: Annotated[
        int,
        typer.Option(
            "--workers",
            help="Concurrent requests, paced per registry. Measured 2026-08-08 against "
            "Verisign: 8 workers held 25.6 q/s with no refusals at all, so the ceiling "
            "is well above this default.",
        ),
    ] = 8,
    delay: Annotated[
        float,
        typer.Option("--delay", help="Starting seconds between queries to one registry (adapts)."),
    ] = 0.15,
    min_delay: Annotated[
        float,
        typer.Option("--min-delay", help="Floor the per-registry pace may not ease below."),
    ] = 0.01,
    max_delay: Annotated[
        float,
        typer.Option("--max-delay", help="Ceiling on the adaptive per-registry pace."),
    ] = 5.0,
    timeout: Annotated[
        float, typer.Option("--timeout", help="Seconds to wait per request before giving up.")
    ] = 20.0,
    direct: Annotated[
        bool,
        typer.Option(
            "--direct/--redirector",
            help="Query the authoritative registry from the IANA bootstrap file, falling back "
            "to rdap.org per TLD. --redirector forces every query through rdap.org, which is "
            "how journals before 2026-08-08 were collected and is rate-limited far harder.",
        ),
    ] = True,
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

    Queries go straight to the registry that is authoritative for each TLD, and
    each registry is paced by its own adaptive governor, so a refusal from one
    never slows the others. Resumable: any domain already ANSWERED in a journal
    in the same folder is skipped, so an interrupted run is finished by running
    the command again.
    """
    path = out or journal_path(RDAP_JOURNAL_DIR, RDAP_JOURNAL_PREFIX)
    path.parent.mkdir(parents=True, exist_ok=True)
    # only a 200 or a 404 settles a domain: a 429 or a transport failure means the
    # question never landed, and skipping those would drop them from every later run
    already = queried_domains(path.parent, RDAP_JOURNAL_PREFIX, answered=rdap_answered)
    logger.info(f"rdap: {len(already):,} domains already journalled; writing {path}")
    stats: Counter = Counter()

    targets: list[str] = []
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
            already.add(domain)
            targets.append(domain)
            if len(targets) >= limit:
                break

    registries = load_registries() if direct else {}
    router = Router(registries, delay=delay, min_delay=min_delay, max_delay=max_delay)
    stats["registries_known"] = len(registries)
    fetch = rdap_http_fetch(timeout)
    queried = 0
    if targets:
        with journal_writer(path) as journal, _abortable_pool(workers) as pool:
            futures = {
                pool.submit(lookup, domain, fetch, router=router): domain for domain in targets
            }
            for future in tqdm(as_completed(futures), total=len(futures), unit="domain"):
                try:
                    record = future.result()
                except Exception as exc:  # noqa: BLE001 (one bad domain must not end the run)
                    logger.warning(f"{futures[future]}: {exc}")
                    stats["errored"] += 1
                    continue
                write_journal_line(journal, record)
                queried += 1
                if record["creation_year"] is not None:
                    stats["dated"] += 1
                elif rdap_answered(record):
                    stats["not_dated"] += 1
                else:
                    stats[f"failed_{record['status']}"] += 1
                # flush periodically so an interrupted run keeps its work
                if queried % _JOURNAL_FLUSH_EVERY == 0:
                    journal.flush()
    if queried == 0:
        path.unlink(missing_ok=True)
        logger.info("rdap: nothing new to query; no journal written")
    stats["queried"] = queried
    for host, throttles in router.throttles().items():
        stats[f"throttled_{host}"] = throttles
    summary = dict(stats)
    logger.info(f"rdap: {summary} -> {path if queried else 'no journal'}")
    typer.echo(f"rdap: {summary}")
    if queried:
        typer.echo(f"journal: {path}\nnext: uv run ark ingest rdap_snapshot {path}")
        # a domain RDAP cannot date leaves no trace after interpretation, which is
        # right for a pool of already-held domains and wrong for unknown ones,
        # where the undatable ones are meant to be kept as candidates
        if stats.get("not_dated"):
            typer.echo(
                f"note: {stats['not_dated']:,} domains could not be dated; if this list was not "
                f"already held, run `uv run ark seed {candidates}` to keep them as candidates"
            )


@app.command()
def gaps(
    out: Annotated[
        Path, typer.Option("--out", help="Where to write the prioritised domain list.")
    ] = Path("data/raw/cdx/gap_candidates.txt"),
    creation: Annotated[
        bool,
        typer.Option(
            "--creation",
            help="Instead list the population a registry creation date can address: domains "
            "missing an in-window year next to one they hold, most-missing first. Not bounded "
            "to years before the earliest held one, because a creation date resets on "
            "re-registration and can therefore fall after years already held.",
        ),
    ] = False,
    legacy_year_order: Annotated[
        bool,
        typer.Option(
            "--legacy-year-order",
            help="Order by thinnest gap year instead of by expected equivalent-English. The "
            "pre-August-2026 order, kept for reproducing earlier rounds; measured 54% worse "
            "per query under the current metric.",
        ),
    ] = False,
    shards: Annotated[
        int,
        typer.Option(
            "--shards",
            help="Split the list into this many disjoint slices by content hash, so several "
            "machines can collect in parallel without ever querying the same domain twice.",
        ),
    ] = 1,
    shard: Annotated[
        int, typer.Option("--shard", help="Which slice to write, from 0 to --shards minus 1.")
    ] = 0,
) -> None:
    """List held domains worth a per-domain query, best target first.

    By default: domains whose missing year is bracketed by two held years, which
    is the population an archive query addresses. One archive query answers every
    year for a domain, so the output is a domain list. Feed it to `ark cdx`.

    Ordered by expected equivalent-English: the English share of the domain's TLD
    times the number of bracketed years a capture could fill. The hit rate is
    near-uniform over this population, so what separates targets is what an answer
    is worth, not the chance of getting one.
    """
    conn = connect()
    if creation:
        summary = write_creation_candidates(conn, out)
        record_metrics(conn, "gaps", "creation_addressable", summary)
        logger.info(f"gaps (creation): {summary} -> {out}")
        typer.echo(f"gaps (creation): {summary}\nwrote {out}\nnext: uv run ark rdap {out}")
        return
    summary = write_gap_candidates(
        conn, out, legacy_year_order=legacy_year_order, shards=shards, shard=shard
    )
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

    Loads the exported evidence graph into the store and re-runs the
    exporter over it, which regenerates the annual files, the merged masters,
    the candidate list and the manifest. Run `ark check` afterwards to put the
    rebuilt store through the same integrity gate as the original.

    Refuses when the store holds ingested files the export does not, because
    this command DROPS the store's tables before recreating them from Parquet.
    On a finished delivery that is exactly right. During collection it is
    destructive: anything ingested since the last `ark export` is not in the
    Parquet yet and would be discarded without a word. Pass --force if the
    discard is intended.

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
    conn = connect()
    results = collect_checks(conn)
    typer.echo(format_checks(results))
    record_metrics(conn, "check", "integrity", {r["name"]: r["offending"] for r in results})
    if any(not r["ok"] for r in results):
        raise typer.Exit(code=1)


@app.command(name="lang-targets")
def lang_targets(
    out: Annotated[Path, typer.Option("--out", help="Work list to write.")] = LANG_TARGETS_PATH,
) -> None:
    """Write the (domain, year) work list for English-website verification.

    Every net-new pair that has no verdict yet, ordered so the years closest to
    the completeness threshold are classified first.
    """
    conn = connect()
    init_db(conn)
    stats = write_lang_targets(conn, out)
    typer.echo(f"lang-targets: {stats}")
    typer.echo(f"targets: {out}\nnext: uv run ark lang {out} -n 200")


@app.command()
def lang(
    targets: Annotated[
        Path,
        typer.Argument(
            help="Work list: one `domain<TAB>year` per line, from `ark lang-targets`.",
            exists=True,
            readable=True,
        ),
    ],
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="Classify at most this many not-yet-done pairs.")
    ] = 200,
    workers: Annotated[int, typer.Option("--workers", help="Concurrent pairs.")] = 4,
    delay: Annotated[
        float, typer.Option("--delay", help="Starting seconds between requests (adapts).")
    ] = 2.0,
    min_delay: Annotated[
        float,
        typer.Option(
            "--min-delay",
            help="Floor the governor may not ease below. This engine sends up to `samples`+1 "
            "requests per pair, so the floor, not the worker count, is what bounds the load on "
            "web.archive.org. A 0.05 s floor at 4 workers drew a connection refusal in four "
            "minutes on 1 August; 1.5 s holds the run near the ~1,000 requests/hour the CDX "
            "engine sustained for days.",
        ),
    ] = 1.5,
    samples: Annotated[
        int, typer.Option("--samples", help="Captures to classify per (domain, year).")
    ] = 2,
    timeout: Annotated[
        float, typer.Option("--timeout", help="Seconds to wait per request.")
    ] = 45.0,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Journal to write (default data/raw/lang/lang_<UTC>.jsonl.gz)."),
    ] = None,
) -> None:
    """Verify the English-website standard per (domain, year) from archived text.

    Feedback section 6 admits a domain to an annual file only when it belongs to
    an English-language website, or one where English is more than half of the
    reliably classified body text, judged from archived pages for that year
    rather than from the domain spelling or its TLD.

    Collection only: writes a per-run journal and never opens the store, so it
    runs alongside the other engines. Turn journals into verdicts with
    `ark ingest-lang <journal>`. Resumable: a pair already answered in a journal
    in the same folder is skipped.

    Rate note: this hits web.archive.org for one CDX query plus up to `samples`
    page fetches per pair, so it is several times heavier than `ark cdx`. Run the
    two together only at low worker counts.
    """
    path = out or journal_path(LANG_JOURNAL_DIR, LANG_JOURNAL_PREFIX)
    path.parent.mkdir(parents=True, exist_ok=True)
    already = queried_domains(path.parent, LANG_JOURNAL_PREFIX, answered=lang_answered)
    logger.info(f"lang: {len(already):,} pairs already journalled; writing {path}")

    stats: Counter = Counter()
    work: list[tuple[str, int]] = []
    for domain, year in read_targets(
        targets.read_text(encoding="utf-8", errors="replace").splitlines()
    ):
        if pair_key(domain, year) in already:
            stats["skipped_journalled"] += 1
            continue
        work.append((domain, year))
        if len(work) >= limit:
            break

    governor = RateGovernor(delay=delay, min_delay=min_delay, max_delay=15.0)
    cdx_fetch = http_fetch(timeout)
    page_fetch = bytes_fetcher(timeout)
    written = 0
    if work:
        with journal_writer(path) as journal, _abortable_pool(workers) as pool:
            futures = {
                pool.submit(
                    classify_pair,
                    domain,
                    year,
                    cdx_fetch,
                    page_fetch,
                    governor,
                    samples=samples,
                ): (domain, year)
                for domain, year in work
            }
            consecutive_failures = 0
            for future in tqdm(as_completed(futures), total=len(futures), unit="pair"):
                try:
                    record = future.result()
                except Exception as exc:  # noqa: BLE001 (one bad pair must not end the run)
                    logger.warning(f"{futures[future]}: {exc}")
                    stats["errored"] += 1
                    continue
                write_journal_line(journal, record)
                written += 1
                if not lang_answered(record):
                    stats[f"failed_{record['status']}"] += 1
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0
                    stats[record["verdict"]] += 1
                    stats["captures_read"] += len(record.get("evidence_urls") or [])
                if written % _JOURNAL_FLUSH_EVERY == 0:
                    journal.flush()
                # Stop rather than keep dialling a service that has stopped
                # answering. An unbroken run of failures is not bad luck, it is
                # the archive declining the traffic, and continuing turns a
                # temporary refusal into a durable one. Nothing is lost: an
                # unanswered pair was never settled, so the next run asks again.
                if consecutive_failures >= _LANG_FAILURE_BREAKER:
                    stats["circuit_broken"] = 1
                    logger.error(
                        f"lang: {consecutive_failures} consecutive failures; stopping so the "
                        f"archive is not hammered. Journal kept at {path}."
                    )
                    break
    if written == 0:
        path.unlink(missing_ok=True)
        logger.info("lang: nothing new to classify; no journal written")

    stats["classified"] = written
    stats["throttles"] = governor.throttles
    stats["final_delay_ms"] = int(governor.delay * 1000)
    summary = dict(stats)
    logger.info(f"lang: {summary} -> {path if written else 'no journal'}")
    typer.echo(f"lang: {summary}")
    if written:
        typer.echo(f"journal: {path}\nnext: uv run ark ingest-lang {path}")


@app.command(name="ingest-lang")
def ingest_lang(
    journals: Annotated[
        list[Path],
        typer.Argument(help="`ark lang` journals to fold into domain_language.", exists=True),
    ],
) -> None:
    """Fold `ark lang` journals into the domain_language table.

    Language is not evidence, so this writes no evidence rows and touches no
    annual assignment. It records what each website was in each year, which the
    exporter then uses to decide admission.
    """
    conn = connect()
    init_db(conn)
    total: Counter = Counter()
    for path in journals:
        summary = ingest_language_journal(conn, path)
        typer.echo(f"{path.name}: {summary}")
        for key, value in summary.items():
            if isinstance(value, int):
                total[key] += value
    typer.echo(f"ingest-lang: {dict(total)}")


@app.command(name="lang-report")
def lang_report() -> None:
    """Write the English-verified annual files and the section 6.1 language table.

    Two artifacts. `output/netnew_english/` holds the admissible subset, the
    additions the English standard permits. `output/language_summary.csv` is the
    per-year and total mix of English, other, undetermined and not-yet-classified
    records, plus the cross-year unique-domain roll-up, which is the shape
    feedback 6.1 requires every future submission to report.
    """
    conn = connect()
    # No `init_db` here, deliberately. This command only reads the store and
    # writes files, and calling it broke the reviewer's own reproduction path:
    # `ark rebuild` recreates tables with `CREATE TABLE AS SELECT` from Parquet,
    # which carries the data but not the primary keys, so re-running the schema
    # afterwards fails trying to add a foreign key against a `source` table that
    # now has no unique constraint. Found by unpacking the delivery archive and
    # following its README literally, which is the only way this class of bug
    # ever shows up.
    counts = write_partitioned_annual_files(conn)
    rows = write_language_summary(conn)
    typer.echo(format_language_summary(rows))
    typer.echo(f"\nenglish annual files: {counts}")
    record_metrics(conn, "lang-report", "language_summary", counts)


def main() -> None:
    app()
