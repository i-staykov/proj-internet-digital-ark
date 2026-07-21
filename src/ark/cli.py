"""Command-line entry point for the ark pipeline."""

import sys
from typing import Annotated

import typer
from loguru import logger

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


def main() -> None:
    app()
