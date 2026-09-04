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

    uv run python scripts/harness/query_health.py [--write] [--tail N]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "data/logs/query_health.jsonl"
POOL_LOG = REPO / "data/logs/cdx_pool.log"
_STATS = re.compile(r"^cdx: (\{.*\})\s*$")

# Above this share of a batch failing, the batch says nothing about its domains.
FAILURE_RATE_ALARM = 0.25
# The archive throttles before it refuses, so this is the early warning rather than the alarm.
THROTTLES_PER_QUERY_ALARM = 2.0
# Consecutive batches answering nothing at all. Three, because one is noise and two is a bad
# stretch of heavy domains; three in a row is the service and not the queue.
DEAD_RUN_ALARM = 3


def batches(path: Path) -> list[dict]:
    """Every stats line in a collector log, oldest first."""
    if not path.is_file():
        return []
    out: list[dict] = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            match = _STATS.match(line.strip())
            if match is None:
                continue
            try:
                # the collectors print a python dict, not JSON: single quotes
                row = ast.literal_eval(match.group(1))
            except (ValueError, SyntaxError):
                continue
            if isinstance(row, dict) and row.get("queried"):
                out.append(row)
    return out


def health(row: dict) -> dict:
    queried = row.get("queried") or 0
    failed = sum(v for k, v in row.items() if k.startswith("failed_") and isinstance(v, int))
    answered = (row.get("with_capture") or 0) + (row.get("no_capture") or 0)
    throttles = row.get("throttles") or 0
    return {
        "queried": queried,
        "answered": answered,
        "failed": failed,
        "throttles": throttles,
        "failure_rate": round(failed / queried, 4) if queried else None,
        "throttles_per_query": round(throttles / queried, 3) if queried else None,
        "final_delay_ms": row.get("final_delay_ms"),
        "years_found": row.get("years_found") or 0,
    }


def verdicts(rows: list[dict]) -> list[str]:
    """What is worth a human's attention, most recent evidence first."""
    out: list[str] = []
    if not rows:
        return ["no batch has reported yet: nothing to judge, which is not the same as healthy"]
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
    return out or ["healthy on all three signals"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="rewrite the ledger from the logs")
    ap.add_argument("--tail", type=int, default=5, help="batches to print")
    args = ap.parse_args()

    rows = [health(row) for row in batches(POOL_LOG)]
    if args.write:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        print(f"wrote {LEDGER.relative_to(REPO)}: {len(rows):,} batches")

    print(f"\n{len(rows):,} batches in {POOL_LOG.relative_to(REPO)}")
    print(f"{'queried':>9} {'answered':>9} {'failed':>7} {'fail%':>7} {'thr/q':>7} {'delay':>7}")
    for row in rows[-args.tail :]:
        rate = f"{row['failure_rate']:.1%}" if row["failure_rate"] is not None else "n/a"
        print(
            f"{row['queried']:>9,} {row['answered']:>9,} {row['failed']:>7,} {rate:>7} "
            f"{row['throttles_per_query']:>7} {row['final_delay_ms'] or 0:>7}"
        )
    print()
    for line in verdicts(rows):
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
