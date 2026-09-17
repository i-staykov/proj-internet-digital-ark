"""The third archive client: `archive.org/wayback/available` as a dating engine (C-88).

A second endpoint is a second budget. Measured 2026-08-30: 1.27 q/s at 0.67% throttled in
the same minutes both CDX collectors ran at 0.308 q/s each and 27.3% throttled. Priced,
1,494 net-new EE/hour over the 4,137,392 com/net/org/uk names held at 2000 and missing
2001, against 600 EE/hour for both CDX collectors together.

Graded against CDX journals already on disk, with no new CDX requests: 204 CDX year-pairs
over 150 domains, 187 recovered, 91.7% recall and 94.3% at 2001, and 40 of 40 CDX-negative
domains came back empty. Two defects make every zero a lower bound and never a false year:
it returns only status-200 captures, and it canonicalises `www.` away.

**That second defect is the whole reason this file is not ten lines.** Spec XIII: a capture
of `www.example.com` does not establish `example.com`. So the answer's OWN url is parsed and
the record is filed under the host the archive actually names, never under the one we asked
for. Ask about `example.com`, get back `www.example.com`, and the row is a hostname row.

    uv run python scripts/engines/wayback_availability.py --deadline <epoch> [--limit N]
"""

from __future__ import annotations

import argparse
import gzip
import json
import queue
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ENDPOINT = "https://archive.org/wayback/available"
UA = "internet-digital-ark/1.0 (research; contact via github.com/i-staykov)"
# The pinned day the measurement used. Mid-year, so a capture either side of it is closest.
PIN = "20010701"
TARGET_YEAR = 2001
WORKERS = 2
BACKOFF_DEFAULT = 30.0


def queue_sql(limit: int) -> str:
    """Held at 2000, missing 2001, com/net/org/uk, richest English weight first."""
    return f"""
        SELECT dy.domain
        FROM domain_year dy
        JOIN domain d ON d.domain = dy.domain
        WHERE dy.assigned_year = 2000
          AND d.tld IN ('com', 'net', 'org', 'uk')
          AND NOT EXISTS (
              SELECT 1 FROM domain_year o
              WHERE o.domain = dy.domain AND o.assigned_year = {TARGET_YEAR}
          )
        ORDER BY d.tld, dy.domain
        LIMIT {int(limit)}
    """


def ask(domain: str) -> tuple[str | None, str | None, float]:
    """One probe. Returns (captured url, 14-digit stamp, seconds to wait before the next).

    A 429 is answered with the archive's own `Retry-After` when it sends one, which is what
    C-77 requires of every client on this host.
    """
    url = f"{ENDPOINT}?{urllib.parse.urlencode({'url': domain, 'timestamp': PIN})}"
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as err:
        if err.code in (429, 503):
            after = err.headers.get("Retry-After") if err.headers else None
            try:
                return None, None, float(after)
            except (TypeError, ValueError):
                return None, None, BACKOFF_DEFAULT
        return None, None, 0.0
    except (urllib.error.URLError, OSError, ValueError):
        return None, None, 0.0
    # **`archived_snapshots.closest.timestamp`, never the last `timestamp` in the document.**
    # The top level echoes the caller's own input back, so reading that makes every probe
    # report a perfect hit.
    closest = (body.get("archived_snapshots") or {}).get("closest") or {}
    if not closest.get("available"):
        return None, None, 0.0
    return closest.get("url"), closest.get("timestamp"), 0.0


def host_of(url: str) -> str | None:
    """The host the archive named, lowercased, port and trailing dot removed."""
    try:
        parsed = urllib.parse.urlsplit(url if "//" in url else f"http://{url}")
    except ValueError:
        return None
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    return host or None


def probe(domain: str) -> dict | None:
    """One answer, filed under the host the ARCHIVE named. None when it dates nothing."""
    url, stamp, wait = ask(domain)
    if wait:
        time.sleep(wait)
        url, stamp, _ = ask(domain)
    if not url or not stamp or len(stamp) < 4 or not stamp[:4].isdigit():
        return None
    if int(stamp[:4]) != TARGET_YEAR:
        return None
    host = host_of(url)
    if host is None:
        return None
    return {"domain": domain, "host": host, "timestamp": stamp, "asked": domain}


def run(domains: list[str], deadline: float, out_dir: Path, host_dir: Path) -> dict[str, int]:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    host_dir.mkdir(parents=True, exist_ok=True)
    totals = {"asked": 0, "exact": 0, "variant": 0, "empty": 0}
    work: queue.Queue[str] = queue.Queue()
    for domain in domains:
        work.put(domain)
    lock = threading.Lock()
    exact = gzip.open(out_dir / f"availability_{stamp}.jsonl.gz", "wt")
    variant = gzip.open(host_dir / f"availability_host_{stamp}.jsonl.gz", "wt")

    def worker() -> None:
        while time.time() < deadline:
            try:
                domain = work.get_nowait()
            except queue.Empty:
                return
            found = probe(domain)
            with lock:
                totals["asked"] += 1
                if found is None:
                    totals["empty"] += 1
                elif found["host"] == domain:
                    # Exact host: the shape `ark ingest cdx_snapshot` already reads.
                    exact.write(
                        json.dumps(
                            {
                                "domain": domain,
                                "status": 200,
                                "years": [TARGET_YEAR],
                                "strategy": "wayback_availability",
                            }
                        )
                        + "\n"
                    )
                    totals["exact"] += 1
                else:
                    # The archive answered about a different host, almost always the `www.`
                    # form. XIII forbids letting that stand for the bare name, so it is
                    # filed as what it is: evidence for that host and for no other.
                    variant.write(
                        json.dumps(
                            {"url": f"http://{found['host']}/", "timestamp": found["timestamp"]}
                        )
                        + "\n"
                    )
                    totals["variant"] += 1

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(WORKERS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    exact.close()
    variant.close()
    return totals


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deadline", type=float, required=True, help="epoch seconds to stop at")
    ap.add_argument("--limit", type=int, default=200_000, help="queue size to take")
    ap.add_argument("--out", type=Path, default=REPO / "data/raw/availability")
    ap.add_argument("--host-out", type=Path, default=REPO / "data/raw/availability_hostgrain")
    ap.add_argument("--queue-file", type=Path, help="one domain per line, instead of the store")
    args = ap.parse_args()

    if args.queue_file:
        domains = [x.strip() for x in args.queue_file.read_text().splitlines() if x.strip()]
    else:
        # Read-only and closed straight away. `ark.db.connect` takes the WRITE lock, and
        # this engine runs for hours beside an ingest loop that needs it every fifteen
        # minutes; the queue is read once at the start and never again.
        import duckdb

        from ark.db import DEFAULT_DB_PATH

        conn = duckdb.connect(str(DEFAULT_DB_PATH), read_only=True)
        try:
            domains = [row[0] for row in conn.execute(queue_sql(args.limit)).fetchall()]
        finally:
            conn.close()
    print(f"queue {len(domains):,} domains, deadline {args.deadline:.0f}")
    totals = run(domains, args.deadline, args.out, args.host_out)
    print(
        f"asked {totals['asked']:,}  exact {totals['exact']:,}  "
        f"variant {totals['variant']:,}  empty {totals['empty']:,}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
