"""Command-line entry point for the ark pipeline."""

import sys
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger

from ark.db import DEFAULT_DB_PATH, connect, init_db
from ark.ingest import ingest_legacy
from ark.legacy_review import DEFAULT_DROPLIST_PATH, review_legacy
from ark.stats import collect_stats, format_stats
from ark.work_queue import DEFAULT_QUEUE_PATH, connect_queue

app = typer.Typer(
    name="ark",
    help="Collect historical domains (1996-2001) with per-year evidence.",
    no_args_is_help=True,
)

_LOG_FORMAT = "{time:HH:mm:ss} | {level: <7} | {message}"


@app.callback()
def _setup(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging.")] = False,
) -> None:
    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if verbose else "INFO", format=_LOG_FORMAT)


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


@app.command()
def seed() -> None:
    """Load and normalize seed domains into the candidate pool."""
    logger.info("seed: not implemented yet")


@app.command()
def verify() -> None:
    """Check candidate domains for per-year evidence via CDX and WHOIS."""
    logger.info("verify: not implemented yet")


@app.command()
def download() -> None:
    """Download verified pages and extract outbound links."""
    logger.info("download: not implemented yet")


@app.command()
def export() -> None:
    """Write net-new year files and the evidence manifest to output/."""
    logger.info("export: not implemented yet")


@app.command()
def stats() -> None:
    """Print the scoreboard: net-new counts on top of the baseline."""
    conn = connect()
    typer.echo(format_stats(collect_stats(conn)))


def main() -> None:
    app()
