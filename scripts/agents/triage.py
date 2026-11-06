"""The two acts a triage run may take on the VM's units, each behind its guard.

Only a reader (`READERS`) restarts here: the tick and the agent are rails, and restarting the
tick would take the sync lock. A reader restarted twice in a day is a cause no restart fixes,
so a second attempt within 24 h, failed or not, needs an open work item naming the reader
(`--item ID`), which is where the cause gets fixed. A lane reinstalled near a tick races the
tick for the lanes' files, so `just walk install` refuses within 10 minutes of the tick's last
or next trigger, while the sync lock is held, and whenever either time cannot be read. Each
attempt appends one row to `data/logs/triage_acts.tsv` (stamp, act, unit, item, exit).

    python3 scripts/agents/triage.py restart READER [--item ID]
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
# The transient readers `scripts/harness/scheduled_sync.sh` starts.
READERS = ("ark-eot", "ark-har", "ark-clueweb")
TICK_TIMER = "ark-sync.timer"
DAY = dt.timedelta(hours=24)
NEAR_TICK = dt.timedelta(minutes=10)
STAMP = "%Y-%m-%dT%H:%M:%SZ"


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def log(act: str, unit: str, item: str, code: int) -> None:
    ACTS.parent.mkdir(parents=True, exist_ok=True)
    with ACTS.open("a") as f:
        f.write(f"{now().strftime(STAMP)}\t{act}\t{unit}\t{item}\t{code}\n")


def restarted_today(unit: str, at: dt.datetime) -> bool:
    if not ACTS.exists():
        return False
    for line in ACTS.read_text().splitlines():
        row = line.split("\t")
        if len(row) >= 3 and row[1] == "restart" and row[2] == unit:
            try:
                stamp = dt.datetime.strptime(row[0], STAMP).replace(tzinfo=dt.UTC)
            except ValueError:
                return True  # an unreadable row counts against the restart, never for it
            if at - stamp < DAY:
                return True
    return False


def item_names(item_id: str, unit: str) -> bool:
    """An open queue item with this id whose title or evidence names the unit."""
    if not item_id or not QUEUE.exists():
        return False
    for line in QUEUE.read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("id") == item_id and row.get("state") == "open":
            return unit in f"{row.get('title', '')} {row.get('evidence', '')}"
    return False


def tick_times() -> list[dt.datetime]:
    """The tick timer's last and next trigger as UTC; fewer than two means unreadable."""
    show = ["systemctl", "--user", "show", TICK_TIMER]
    props = ["-p", "LastTriggerUSec", "-p", "NextElapseUSecRealtime"]
    # TZ=UTC: `date -d` rejects some zone names systemctl prints, such as CEST.
    env = {**os.environ, "TZ": "UTC"}
    out = subprocess.run(show + props, capture_output=True, text=True, env=env)
    times = []
    for line in out.stdout.splitlines() if out.returncode == 0 else []:
        value = line.partition("=")[2].strip()
        if value:
            date = ["date", "-d", value, "+%s"]
            epoch = subprocess.run(date, capture_output=True, text=True, env=env).stdout.strip()
            if epoch.isdigit():
                times.append(dt.datetime.fromtimestamp(int(epoch), dt.UTC))
    return times


def lock_held() -> bool:
    out = subprocess.run(
        ["bash", "scripts/harness/sync_lock.sh", "holder"], capture_output=True, text=True
    )
    return bool(out.stdout.strip())


def restart(unit: str, item: str) -> int:
    unit = unit.removesuffix(".service")
    if unit not in READERS:
        print(f"refused: only a reader restarts here: {' '.join(READERS)}")
        return 3
    if restarted_today(unit, now()) and not item_names(item, unit):
        print(f"refused: {unit} was restarted within 24 h; queue an item naming it, --item ID")
        return 3
    code = 1 if subprocess.run(["systemctl", "--user", "restart", unit]).returncode else 0
    log("restart", unit, item, code)
    return code


def walk() -> int:
    at = now()
    times = tick_times()
    if len(times) < 2 or any(abs(at - t) < NEAR_TICK for t in times) or lock_held():
        print("refused: the tick is near, unreadable or holds the lock; try the next run")
        return 3
    code = 1 if subprocess.run(["just", "walk", "install"]).returncode else 0
    log("walk", "install", "", code)
    return code


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
