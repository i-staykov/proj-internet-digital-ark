"""Pace the agent on the subscription's windows, leaving the owner's share.

The owner works on the same account, so the pre-flight's fresh reading decides each run:
nothing starts at or over `five_hour_stop` percent of the five-hour window, nor over the
seven-day pace line `seven_day_ceiling * min(1, elapsed / (pace_days * 86400))`, elapsed
being the window's age (seven days less the time to its `resetsAt`); the rest of the week is
the owner's. A window the stream did not report is unmeasured and does not stop a run. A
run the server refused for its limit (`rate_limit_info.status` not `allowed`, or a result
naming the limit) backs the agent off to that window's reset, once, in
`data/logs/agent/.backoff_until`; no retry before it. The knobs are `pacing` in
`agent/policy.json`.

    python3 scripts/agents/pacer.py check PREFLIGHT.jsonl   exit 0 run, 3 with the reason
    python3 scripts/agents/pacer.py backoff RUN.jsonl       the back-off, when the run was refused

Standard library only, beside `agent_ledger.py`, whose stream readers it shares.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_ledger  # noqa: E402

POLICY = "agent/policy.json"
BACKOFF = os.environ.get("ARK_AGENT_LOG_DIR", "data/logs/agent") + "/.backoff_until"
WEEK = 7 * 86400
DEFAULTS = {"five_hour_stop": 40, "seven_day_ceiling": 50, "pace_days": 7}


def knobs(policy: str = POLICY) -> dict:
    try:
        return DEFAULTS | json.load(open(policy)).get("pacing", {})
    except (OSError, ValueError):
        return dict(DEFAULTS)


def stamp(epoch: float) -> str:
    return dt.datetime.fromtimestamp(epoch, dt.UTC).strftime("%Y-%m-%dT%H:%MZ")


def decide(raw: dict, k: dict, now: float, backoff_until: float = 0) -> str | None:
    """The reason not to run now, or None."""
    if now < backoff_until:
        return f"backing off until {stamp(backoff_until)}"
    five = raw.get("five_hour") if isinstance(raw.get("five_hour"), dict) else {}
    used = (five.get("utilization") or 0) * 100
    if used >= k["five_hour_stop"]:
        return f"five-hour window at {used:.0f}%, stop at {k['five_hour_stop']}%"
    seven = raw.get("seven_day") if isinstance(raw.get("seven_day"), dict) else {}
    if not seven:
        return None
    used = (seven.get("utilization") or 0) * 100
    resets = float(seven.get("resetsAt") or 0)
    elapsed = max(0.0, WEEK - (resets - now)) if resets else WEEK
    target = k["seven_day_ceiling"] * min(1.0, elapsed / (k["pace_days"] * 86400))
    if used >= target:
        ceiling = k["seven_day_ceiling"]
        return (
            f"seven-day window at {used:.0f}%, pace line at {target:.1f}% of the {ceiling}% ceiling"
        )
    return None


def refused(path: str) -> float | None:
    """The reset epoch of the window a run was refused on, or None when it was not."""
    for d in agent_ledger.events(path):
        info = d.get("rate_limit_info") if d.get("type") == "rate_limit_event" else None
        if isinstance(info, dict) and info.get("status") not in (None, "allowed"):
            return float(info.get("resetsAt") or time.time() + 3600)
    res = agent_ledger.result(path)
    text = str(res.get("result") or res.get("error") or "")
    if res.get("is_error") and "limit" in text.lower():
        return time.time() + 3600
    return None


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] not in ("check", "backoff"):
        print(__doc__.split("\n\n")[-2], file=sys.stderr)
        return 2
    if argv[0] == "check":
        try:
            until = float(open(BACKOFF).read().strip())
        except (OSError, ValueError):
            until = 0
        why = decide(agent_ledger.windows(argv[1]), knobs(), time.time(), until)
        if why:
            print(why)
            return 3
        return 0
    at = refused(argv[1])
    if at is None:
        return 0
    os.makedirs(os.path.dirname(BACKOFF), exist_ok=True)
    open(BACKOFF, "w").write(f"{at:.0f}\n")
    print(f"refused for the limit; backing off until {stamp(at)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
