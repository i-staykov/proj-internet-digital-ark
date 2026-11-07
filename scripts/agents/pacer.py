"""Pace the agent on the subscription's windows, leaving the owner's share.

The owner works on the same account, so the windows are the account's total, whoever spent
it, and the pre-flight's fresh reading decides each run: nothing starts at or over the mode's
`five_hour_stop` percent of the five-hour window (a mode names its own under `modes`, else
`pacing`'s), nor above the seven-day pace line `seven_day_ceiling * min(1, elapsed /
(pace_days * 86400))`, elapsed being the window's age (seven days less the time to its
`resetsAt`); a mode with its own `seven_day_stop` stops flat at that percent of the seven-day
window instead: scout and cdx run flat up to the ceiling while work and triage follow the
pace line, so the scouts keep a reserve when the owner has spent the window. The account's
other half is the owner's whatever the agent does. A window the stream did not report is
unmeasured and does not stop a run. A call the server refused for its limit
(`rate_limit_info.status` `rejected`; `allowed_warning` is a warning) backs the agent off to
that window's reset in `data/logs/agent/.backoff_until`, read before the pre-flight, so a
back-off costs no call. The knobs are `pacing` in `agent/policy.json`.

    python3 scripts/agents/pacer.py check PREFLIGHT.jsonl [--mode M]   0 run, 3 with the reason
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


def knobs(mode: str = "", policy: str = POLICY) -> dict:
    p = json.load(open(policy))
    k = dict(p["pacing"])
    own = p.get("modes", {}).get(mode, {})
    for name in ("five_hour_stop", "seven_day_stop"):
        if own.get(name) is not None:
            k[name] = own[name]
    return k


def stamp(epoch: float) -> str:
    return dt.datetime.fromtimestamp(epoch, dt.UTC).strftime("%Y-%m-%dT%H:%MZ")


def decide(raw: dict, k: dict, now: float, backoff_until: float = 0) -> str | None:
    """The reason not to run now, or None."""
    if now < backoff_until:
        return f"backing off until {stamp(backoff_until)}"
    five = raw.get("five_hour") if isinstance(raw.get("five_hour"), dict) else {}
    used = round((five.get("utilization") or 0) * 100, 1)
    if used >= k["five_hour_stop"]:
        return f"five-hour window at {used:.0f}%, stop at {k['five_hour_stop']}%"
    seven = raw.get("seven_day") if isinstance(raw.get("seven_day"), dict) else {}
    if not seven:
        return None
    used = round((seven.get("utilization") or 0) * 100, 1)
    stop = k.get("seven_day_stop")
    if stop is not None:
        return f"seven-day window at {used:.0f}%, stop at {stop}%" if used >= stop else None
    resets = float(seven.get("resetsAt") or 0)
    elapsed = max(0.0, WEEK - (resets - now)) if resets else WEEK
    target = round(k["seven_day_ceiling"] * min(1.0, elapsed / (k["pace_days"] * 86400)), 1)
    if used > target:
        ceiling = k["seven_day_ceiling"]
        return (
            f"seven-day window at {used:.0f}%, pace line at {target:.1f}% of the {ceiling}% ceiling"
        )
    return None


def refused(path: str) -> float | None:
    """The reset epoch of the window a run was refused on, or None when it was not."""
    for d in agent_ledger.events(path):
        info = d.get("rate_limit_info") if d.get("type") == "rate_limit_event" else None
        if isinstance(info, dict) and info.get("status") == "rejected":
            return float(info.get("resetsAt") or time.time() + 3600)
    return None


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    mode = argv[argv.index("--mode") + 1] if "--mode" in argv else ""
    argv = [a for a in argv if a not in ("--mode", mode)]
    if len(argv) != 2 or argv[0] not in ("check", "backoff"):
        print(__doc__.split("\n\n")[-2], file=sys.stderr)
        return 2
    if argv[0] == "check":
        try:
            until = float(open(BACKOFF).read().strip())
        except (OSError, ValueError):
            until = 0
        why = decide(agent_ledger.windows(argv[1]), knobs(mode), time.time(), until)
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
