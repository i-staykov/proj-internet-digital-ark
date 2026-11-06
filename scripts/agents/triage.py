"""The two acts a triage run may take on the VM's units, each behind its guard.

A unit restarted twice in a day is a cause no restart fixes, so the second restart within 24 h
needs a work item in the queue (`--item ID`), which is where the cause gets fixed. A lane
reinstalled near a tick races the tick for the lanes' files, so `just walk install` refuses
within 10 minutes of the tick's last or next trigger and while the sync lock is held. Each act
appends one row to `data/logs/triage_acts.tsv` (stamp, act, unit, item).

    python3 scripts/agents/triage.py restart UNIT [--item ID]
    python3 scripts/agents/triage.py walk

Exit 0 acted, 3 refused by a guard, 1 the act itself failed. Standard library only;
`ARK_TRIAGE_ACTS` and `ARK_AGENT_QUEUE` move the files, for the tests.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

ACTS = Path(os.environ.get("ARK_TRIAGE_ACTS", "data/logs/triage_acts.tsv"))
QUEUE = Path(os.environ.get("ARK_AGENT_QUEUE", "data/queue/agent_work.jsonl"))
TICK_TIMER = "ark-sync.timer"
DAY = dt.timedelta(hours=24)
NEAR_TICK = dt.timedelta(minutes=10)


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def acts() -> list[list[str]]:
    if not ACTS.exists():
        return []
    return [line.split("\t") for line in ACTS.read_text().splitlines() if line.strip()]


def log(act: str, unit: str, item: str) -> None:
    ACTS.parent.mkdir(parents=True, exist_ok=True)
    with ACTS.open("a") as f:
        f.write(f"{now().strftime('%Y-%m-%dT%H:%M:%SZ')}\t{act}\t{unit}\t{item}\n")


def open_item(item_id: str) -> bool:
    if not QUEUE.exists():
        return False
    for line in QUEUE.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("id") == item_id and row.get("state") == "open":
                return True
    return False


def restarted_today(unit: str, at: dt.datetime) -> bool:
    for row in acts():
        if len(row) >= 3 and row[1] == "restart" and row[2] == unit:
            stamp = dt.datetime.strptime(row[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC)
            if at - stamp < DAY:
                return True
    return False


def tick_times() -> list[dt.datetime]:
    """The tick timer's last and next trigger, from systemd, as UTC."""
    out = subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            TICK_TIMER,
            "-p",
            "LastTriggerUSec",
            "-p",
            "NextElapseUSecRealtime",
        ],
        capture_output=True,
        text=True,
    ).stdout
    times = []
    for line in out.splitlines():
        value = line.partition("=")[2].strip()
        if value and value != "n/a":
            epoch = subprocess.run(
                ["date", "-d", value, "+%s"], capture_output=True, text=True
            ).stdout.strip()
            if epoch.isdigit():
                times.append(dt.datetime.fromtimestamp(int(epoch), dt.UTC))
    return times


def lock_held() -> bool:
    out = subprocess.run(
        ["bash", "scripts/harness/sync_lock.sh", "holder"], capture_output=True, text=True
    )
    return bool(out.stdout.strip())


def restart(unit: str, item: str) -> int:
    if restarted_today(unit, now()) and not open_item(item):
        print(f"refused: {unit} was restarted within 24 h; queue a work item and pass --item ID")
        return 3
    if subprocess.run(["systemctl", "--user", "restart", unit]).returncode:
        return 1
    log("restart", unit, item)
    return 0


def walk() -> int:
    at = now()
    near = [t for t in tick_times() if abs(at - t) < NEAR_TICK]
    if near or lock_held():
        print("refused: within 10 minutes of a tick or the sync lock is held; try next run")
        return 3
    if subprocess.run(["just", "walk", "install"]).returncode:
        return 1
    log("walk", "install", "")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("restart")
    r.add_argument("unit")
    r.add_argument("--item", default="")
    sub.add_parser("walk")
    a = p.parse_args(argv)
    return restart(a.unit, a.item) if a.cmd == "restart" else walk()


if __name__ == "__main__":
    sys.exit(main())
