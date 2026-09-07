"""The failure-state ledger his section XI asks for, derived from what the collectors print.

**Why a reader and not a change to the collectors.** Every batch already emits exactly the fields
XI wants, `queried`, `with_capture`, `no_capture`, `failed_*`, `throttles`, `final_delay_ms`, and
then loses them in a log nobody reads. The collectors also run unattended for days at a time, so a
version of this that needed them restarted would cost more collection than it could ever save.
This parses their logs instead, so it can be written and improved while they are running.

**What it is for.** "Incomplete queries remain scheduled work rather than negative evidence" (his
XI). Without a durable record there is no way to tell an unfinished query family from a dry one,
and during a long run a lane that has started failing looks exactly like a lane with nothing left
to find. Three signals separate them, and each is a measured shape rather than a guess:

- **the failure rate**, `failed_* / queried`. A batch that fails outright is not evidence about
  the domains in it.
- **throttles per query**. The archive asks us to slow down before it refuses, so this rises
  first and is the early warning.
- **a run of batches with no answers at all**, which is the shape of the service having stopped
  rather than of the queue being exhausted.
- **silence**, a lane that has not written for a day. This is the one that decides the sentence
  XI actually cares about, because an unretried query family and a dry one look identical in a
  ledger with no clock in it. The time comes from the log's own last write rather than from the
  batch lines, which print a clock but no date: a reconstructed date would be a guess, and the
  file's mtime is a fact.

**Every collector log, not one.** The first version read `cdx_pool.log` alone, so when that pool
stood down on 2026-09-05 the reader went on judging a lane that had stopped and said nothing about
the two that were still running. A collector that is not watched is the one that fails quietly.

    uv run python scripts/harness/query_health.py [--write] [--tail N]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "data/logs/query_health.jsonl"
LOG_DIR = REPO / "data/logs"
LOG_GLOB = "cdx_*.log"
# **Every batch is logged twice**, once through the logger with a clock and the journal it
# wrote, `21:22:19 | INFO | cdx: {...} -> data/raw/cdx/...`, and once bare. The first version
# anchored on the end of the line, so it matched only the bare copy and every row came back
# without a time. Both forms are read here and the duplicate is dropped below.
# The clock is captured because it is what a human reads back; the date it belongs to is not
# in the line, so nothing here pretends to know it.
_STATS = re.compile(r"^(?:(\d{2}:\d{2}:\d{2})\s*\|[^|]*\|\s*)?cdx: (\{[^}]*\})(?:\s*->.*)?$")

# Above this share of a batch failing, the batch says nothing about its domains.
FAILURE_RATE_ALARM = 0.25
# The archive throttles before it refuses, so this is the early warning rather than the alarm.
THROTTLES_PER_QUERY_ALARM = 2.0
# Consecutive batches answering nothing at all. Three, because one is noise and two is a bad
# stretch of heavy domains; three in a row is the service and not the queue.
DEAD_RUN_ALARM = 3
# A lane silent for longer than this is unretried scheduled work, not an exhausted queue. A day,
# because the collectors run in multi-hour legs and a gap of hours is ordinary between them.
SILENT_HOURS_ALARM = 24.0


def logs(directory: Path | None = None) -> list[Path]:
    """Every collector log, so a lane cannot fail unwatched."""
    return sorted((directory or LOG_DIR).glob(LOG_GLOB))


def batches(path: Path) -> list[dict]:
    """Every stats line in a collector log, oldest first, each carrying its lane and clock."""
    if not path.is_file():
        return []
    lane = path.stem
    out: list[dict] = []
    previous: tuple[str | None, str] = (None, "")
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            match = _STATS.match(line.strip())
            if match is None:
                continue
            clock, payload = match.group(1), match.group(2)
            # A bare line repeating the TIMED line just above it is one batch logged twice.
            # Only that exact shape is collapsed, so two real batches that happen to be
            # identical, which is how a dead lane looks, both survive and DEAD still fires.
            duplicate = clock is None and previous[0] is not None and payload == previous[1]
            previous = (clock, payload)
            if duplicate:
                continue
            try:
                # the collectors print a python dict, not JSON: single quotes
                row = ast.literal_eval(payload)
            except (ValueError, SyntaxError):
                continue
            if isinstance(row, dict) and row.get("queried"):
                out.append({**row, "lane": lane, "clock": clock})
    return out


def silence(path: Path, now: datetime | None = None) -> float | None:
    """Hours since the lane last wrote anything, or None if it never has."""
    if not path.is_file():
        return None
    now = now or datetime.now(UTC)
    last = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return round((now - last).total_seconds() / 3600, 1)


def health(row: dict) -> dict:
    queried = row.get("queried") or 0
    failed = sum(v for k, v in row.items() if k.startswith("failed_") and isinstance(v, int))
    answered = (row.get("with_capture") or 0) + (row.get("no_capture") or 0)
    throttles = row.get("throttles") or 0
    return {
        "lane": row.get("lane"),
        "clock": row.get("clock"),
        "queried": queried,
        "answered": answered,
        "failed": failed,
        "throttles": throttles,
        "failure_rate": round(failed / queried, 4) if queried else None,
        "throttles_per_query": round(throttles / queried, 3) if queried else None,
        "final_delay_ms": row.get("final_delay_ms"),
        "years_found": row.get("years_found") or 0,
    }


def freshest(quiet: dict[str, float | None]) -> tuple[str, float] | None:
    """The lane that wrote most recently, and how long ago.

    **One answer, not one per lane.** The question is whether collection is happening, and
    fifteen retired experiments each announcing their own silence is a surface nobody reads
    (the same law the approvals register carries: forty pending requests must collapse to a
    count). A lane older than the freshest one tells you nothing the freshest does not.
    """
    live = [(lane, hours) for lane, hours in quiet.items() if hours is not None]
    return min(live, key=lambda pair: pair[1]) if live else None


def verdicts(rows: list[dict], quiet: dict[str, float | None] | None = None) -> list[str]:
    """What is worth a human's attention, most recent evidence first."""
    out: list[str] = []
    newest = freshest(quiet or {})
    if newest and newest[1] >= SILENT_HOURS_ALARM:
        lane, hours = newest
        out.append(
            f"SILENT: no collector has written for {hours:,.0f} h ({lane} was the last). "
            "Every queue behind them is unretried scheduled work, not negative evidence"
        )
    if not rows:
        out.append("no batch has reported yet: nothing to judge, which is not the same as healthy")
        return out
    last = rows[-1]
    if (last["failure_rate"] or 0) >= FAILURE_RATE_ALARM:
        out.append(
            f"FAILING: {last['failure_rate']:.0%} of the last batch failed outright "
            f"({last['failed']} of {last['queried']}), so it is not evidence about those domains"
        )
    if (last["throttles_per_query"] or 0) >= THROTTLES_PER_QUERY_ALARM:
        out.append(
            f"THROTTLED: {last['throttles_per_query']} throttles per query, delay now "
            f"{last['final_delay_ms']} ms. The archive slows us before refusing, so this is the "
            "early warning: leave it alone rather than retrying harder"
        )
    dead = 0
    for row in reversed(rows):
        if row["answered"]:
            break
        dead += 1
    if dead >= DEAD_RUN_ALARM:
        out.append(
            f"DEAD: {dead} consecutive batches answered nothing. That is the shape of the "
            "service having stopped, not of the queue being exhausted, so the queue is still "
            "scheduled work and not negative evidence"
        )
    return out or ["healthy on all four signals"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="rewrite the ledger from the logs")
    ap.add_argument("--tail", type=int, default=5, help="batches to print")
    args = ap.parse_args()

    found = logs()
    rows = [health(row) for path in found for row in batches(path)]
    quiet = {path.stem: silence(path) for path in found}
    if args.write:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        print(f"wrote {LEDGER.relative_to(REPO)}: {len(rows):,} batches over {len(found)} lanes")

    ranked = sorted(quiet.items(), key=lambda pair: (pair[1] is None, pair[1]))
    print(f"\n{len(rows):,} batches over {len(found)} collector logs, newest first")
    print(f"{'lane':>22} {'last write':>12} {'batches':>8}")
    for lane, hours in ranked[: args.tail]:
        seen = sum(1 for row in rows if row["lane"] == lane)
        age = "never" if hours is None else f"{hours:,.0f} h ago"
        print(f"{lane:>22} {age:>12} {seen:>8,}")
    if len(ranked) > args.tail:
        print(f"{'':>22} {'':>12} {len(ranked) - args.tail:>8,} older lanes not shown")

    newest = freshest(quiet)
    if newest:
        recent = [row for row in rows if row["lane"] == newest[0]][-args.tail :]
        print(f"\nlast batches of {newest[0]}")
        print(f"{'clock':>9} {'queried':>9} {'ans':>8} {'fail%':>7} {'thr/q':>7}")
        for row in recent:
            rate = f"{row['failure_rate']:.1%}" if row["failure_rate"] is not None else "n/a"
            print(
                f"{row['clock'] or '-':>9} {row['queried']:>9,} "
                f"{row['answered']:>8,} {rate:>7} {row['throttles_per_query']:>7}"
            )
    print()
    for line in verdicts(rows, quiet):
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
