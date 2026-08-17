"""Verify queued candidates against the Internet Archive CDX index.

For each claimed domain this asks, year by year, whether the archive holds a
capture inside that calendar year. One in-year capture is item-level proof;
its timestamp becomes the evidence and the (domain, year) pair is assigned.
The fetcher is injectable so tests never touch the network.
"""

import sqlite3
from collections.abc import Callable

import duckdb
from loguru import logger

from ark.db import assign_year, ensure_source, record_evidence
from ark.ingest import YEARS
from ark.metrics import record_metrics
from ark.seed import CDX_TASK
from ark.work_queue import claim, mark_done, mark_failed, reset_in_flight

# a capture found for (domain, year): timestamp and archived URL, or None
Fetcher = Callable[[str, int], tuple[str, str] | None]

SOURCE_NAME = "ia_cdx"
RETRY_AFTER_S = 600


def _cdx_fetcher() -> Fetcher:
    import cdx_toolkit

    cdx = cdx_toolkit.CDXFetcher(source="ia")

    def fetch(domain: str, year: int) -> tuple[str, str] | None:
        # *.domain matches the domain and all subdomains; a capture of
        # shop.foo.com proves foo.com existed. one in-year capture suffices
        for obj in cdx.iter(
            f"*.{domain}", from_ts=str(year), to=str(year), limit=1, filter=["status:200"]
        ):
            return obj["timestamp"], obj["url"]
        return None

    return fetch


def verify_batch(
    conn: duckdb.DuckDBPyConnection,
    queue_conn: sqlite3.Connection,
    batch_size: int = 25,
    fetcher: Fetcher | None = None,
) -> dict[str, int]:
    """Claim up to batch_size queued domains and verify them year by year."""
    if fetcher is None:
        fetcher = _cdx_fetcher()
    # return crash leftovers to pending before claiming new work
    reset_in_flight(queue_conn)
    source_id = ensure_source(conn, SOURCE_NAME, "timestamped")
    stats = {"claimed": 0, "with_evidence": 0, "years_assigned": 0, "failed": 0}
    domains = claim(queue_conn, CDX_TASK, batch_size)
    stats["claimed"] = len(domains)
    for domain in domains:
        try:
            found_years = 0
            for year in YEARS:
                capture = fetcher(domain, year)
                if capture is None:
                    continue
                timestamp, original_url = capture
                evidence_id = record_evidence(
                    conn,
                    domain,
                    source_id,
                    year,
                    "cdx_timestamp",
                    timestamp,
                    url=f"https://web.archive.org/web/{timestamp}/{original_url}",
                    acquisition_method="ia_cdx_year_query",
                )
                if assign_year(conn, evidence_id):
                    found_years += 1
        except Exception as exc:
            stats["failed"] += 1
            logger.warning(f"{domain}: fetch failed ({exc}); will retry")
            mark_failed(queue_conn, CDX_TASK, domain, retry_after_s=RETRY_AFTER_S)
            continue
        mark_done(queue_conn, CDX_TASK, domain)
        if found_years:
            stats["with_evidence"] += 1
            stats["years_assigned"] += found_years
        logger.info(f"{domain}: {found_years} year(s) evidenced")
    logger.info(f"verify batch: {stats}")
    record_metrics(conn, "verify", SOURCE_NAME, stats)
    return stats
