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
# Rows between flushes of both journals and the resume marker. gzip buffers, so an engine
# killed mid-window loses everything it has not flushed: this one ran 95 minutes over a
# 0-byte journal before that was noticed. The window is days long and the archive is slow,
# so flushing every 50 rows costs nothing measurable.
FLUSH_EVERY = 50
QUEUE_FILE = REPO / "data/raw/availability_queue.txt"
STATE_FILE = REPO / "data/raw/availability_queue.done"
# How long to wait for the store's lock when building the queue. The first real run opened a
# read-only connection while the ingest loop held the write lock and sat there silently for
# 2h20m at 0% CPU with an empty journal. A bounded wait that SAYS what it is waiting for is
# the difference between a slow start and a dead engine nobody notices.
QUEUE_LOCK_WAIT_S = 600


QUEUE_TLDS = ("com", "net", "org", "uk")


def _weight_order() -> str:
    """The ORDER BY that puts the richest TLD first, READ from the vendored table.

    Ordering by the TLD NAME truncated the queue to `.com` alone: a 4,000,000 row limit was
    filled by the alphabetically first TLD and `.uk`, the richest of the four, never entered.
    The shares are read rather than spelled here, because a second copy of that table is the
    one thing `test_no_second_copy_of_the_table_exists` exists to stop.
    """
    from ark.english_share import english_weights

    weights = english_weights()
    arms = " ".join(f"WHEN '{t}' THEN {weights.get(t, 0)}" for t in QUEUE_TLDS)
    return f"CASE d.tld {arms} ELSE 0 END DESC"


def queue_sql(limit: int) -> str:
    """Held at 2000, missing 2001, com/net/org/uk, richest English weight first."""
    return f"""
        SELECT dy.domain
        FROM domain_year dy
        JOIN domain d ON d.domain = dy.domain
        WHERE dy.assigned_year = 2000
          AND d.tld IN ({", ".join(repr(t) for t in QUEUE_TLDS)})
          AND NOT EXISTS (
              SELECT 1 FROM domain_year o
              WHERE o.domain = dy.domain AND o.assigned_year = {TARGET_YEAR}
          )
        ORDER BY {_weight_order()}, dy.domain
        LIMIT {int(limit)}
    """


def build_queue(path: Path, limit: int) -> None:
    """Write the queue once, from a read-only connection that is closed straight away."""
    import duckdb

    from ark.db import DEFAULT_DB_PATH

    deadline = time.monotonic() + QUEUE_LOCK_WAIT_S
    while True:
        try:
            conn = duckdb.connect(str(DEFAULT_DB_PATH), read_only=True)
            break
        except duckdb.Error as err:
            if time.monotonic() >= deadline:
                raise SystemExit(
                    f"the store stayed locked for {QUEUE_LOCK_WAIT_S}s: {err}"
                ) from err
            print(f"store locked, waiting 30s to build the queue: {str(err)[:90]}", flush=True)
            time.sleep(30)
    try:
        rows = [row[0] for row in conn.execute(queue_sql(limit)).fetchall()]
    finally:
        conn.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n")
    print(f"queue rebuilt: {len(rows):,} domains -> {path}", flush=True)


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


def probe(domain: str) -> tuple[str, dict | float | None]:
    """("ok", row), ("empty", None), or ("throttled", seconds to wait).

    **A throttle is not an answer and must never be recorded as one.** The first version
    slept once, asked again, and returned None either way, so a sustained 429 marked every
    name in the queue as having no capture and advanced the resume marker past it. Against a
    4,000,000 row queue that silently destroys the queue. The caller puts a throttled name
    back and only then backs off.
    """
    url, stamp, wait = ask(domain)
    if wait:
        return "throttled", wait
    if not url or not stamp or len(stamp) < 4 or not stamp[:4].isdigit():
        return "empty", None
    if int(stamp[:4]) != TARGET_YEAR:
        return "empty", None
    host = host_of(url)
    if host is None:
        return "empty", None
    return "ok", {"domain": domain, "host": host, "timestamp": stamp, "asked": domain}


def run(
    domains: list[str],
    deadline: float,
    out_dir: Path,
    host_dir: Path,
    done_before: int = 0,
) -> dict[str, int]:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    host_dir.mkdir(parents=True, exist_ok=True)
    totals = {"asked": 0, "exact": 0, "variant": 0, "empty": 0, "throttled": 0}
    started_at = done_before
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
            state, payload = probe(domain)
            if state == "throttled":
                # Back on the queue: the name was never answered. The worker waits out the
                # archive's own figure, which is what C-77 requires of every client here.
                work.put(domain)
                with lock:
                    totals["throttled"] += 1
                    if totals["throttled"] % 20 == 0:
                        print(f"throttled {totals['throttled']:,} times so far", flush=True)
                time.sleep(payload if isinstance(payload, float) else BACKOFF_DEFAULT)
                continue
            found = payload
            with lock:
                totals["asked"] += 1
                if totals["asked"] % FLUSH_EVERY == 0:
                    exact.flush()
                    variant.flush()
                    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
                    STATE_FILE.write_text(f"{started_at + totals['asked']}\n")
                    print(
                        f"asked {totals['asked']:,}  exact {totals['exact']:,}  "
                        f"variant {totals['variant']:,}",
                        flush=True,
                    )
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
    ap.add_argument("--queue-file", type=Path, default=QUEUE_FILE, help="one domain per line")
    ap.add_argument("--refresh-queue", action="store_true", help="rebuild the file from the store")
    args = ap.parse_args()

    if args.refresh_queue or not args.queue_file.is_file():
        build_queue(args.queue_file, args.limit)
    domains = [x.strip() for x in args.queue_file.read_text().splitlines() if x.strip()]

    # Where the last run stopped. A 4M queue outlives many windows, and without this every
    # restart re-probes the same head of the file and the tail is never reached.
    done = 0
    if STATE_FILE.is_file():
        try:
            done = int(STATE_FILE.read_text().strip())
        except ValueError:
            done = 0
    domains = domains[done:]
    print(
        f"queue {len(domains):,} left ({done:,} asked before), deadline {args.deadline:.0f}",
        flush=True,
    )
    totals = run(domains, args.deadline, args.out, args.host_out, done_before=done)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(str(done + totals["asked"]) + "\n")
    print(
        f"asked {totals['asked']:,}  exact {totals['exact']:,}  "
        f"variant {totals['variant']:,}  empty {totals['empty']:,}  "
        f"throttled {totals['throttled']:,}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
