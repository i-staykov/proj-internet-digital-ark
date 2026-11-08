"""Prove the unattended path: exit 0 only when every part the tick leans on is as it should be.

Run at the end of every tick (`scheduled_sync.sh`) and by hand (`just check unattended`). One
line per check, `ok` or `FAIL`, then the verdict; exit 1 on any FAIL.

- timer: `ark-sync.timer` is active.
- walk: the crontab holds six `# ark-walk` lines, each `cd` here and running the walker, and
  `data/logs/.walk_code` names HEAD's walker blobs, so the lanes run HEAD's code.
- lock: the sync lock is free or its holder's pid is alive.
- hold: each unit or flag the hold file names is off (the timer not enabled unless the label
  holds it, the flag file present).
- login: `gh auth status` succeeds.
- space: free space clears the bank's floor plus its write budget (`ark.disk.space`).
- lanes: a lane under no pause flag runs, or wrote its log within cron's restart period. Its
  `# exit ... pending=0` row is no proof of an empty queue (a stopped lane writes it too), and
  cron restarts a finished lane, which writes that row again, every period.
- readers, only where `local.env` ARK_HOSTS runs here: a reader (`READERS`) with parts under
  three strikes left and no hold is an active unit, unless the tick has yet to start it (no
  log, its script changed in the last two hours) or its log's last line says it waits until a
  later UTC stamp or was held within the hour; with none left it reads `finished`, and
  `check_unattended.py left <unit>` prints the count, which the tick reads before starting the
  unit.
"""

from __future__ import annotations

import calendar
import importlib.util
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ark.disk import space  # noqa: E402

TIMER = "ark-sync.timer"
WALKERS = ("scripts/engines/cdx_walk_jobs.py", "scripts/engines/cdx_extended_walk.py")
WALKER = "scripts/engines/cdx_extended_walk.py"
LANES = 3
# cron starts a stopped lane every 10 minutes; one more for the start itself
RESTART_S = 11 * 60
STATE = Path(os.environ.get("ARK_STATE_DIR", Path.home() / "ark/state"))
READERS = {  # the tick's transient units, their readers and logs (scheduled_sync.sh)
    "ark-eot": ("scripts/sources/eot/eot_cdxj.py", "eot_cdxj"),
    "ark-har": ("scripts/sources/httparchive/har_year.py", "har"),
    "ark-clueweb": ("scripts/sources/crawl_lists/clueweb.py", "clueweb"),
    "ark-header": ("scripts/sources/usenet/run_usenet_header_items.py", "usenet_header"),
}
START_S = 2 * 3600
WAITS = re.compile(r"waits until (\d{8}T\d{6}Z)")


def run(*cmd: str) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)
    return p.returncode, p.stdout.strip()


def hold_names() -> list[str] | None:
    hold = STATE / "hold"
    return hold.read_text().splitlines()[2:] if hold.exists() else None


def timer() -> tuple[bool, str]:
    _, state = run("systemctl", "--user", "is-active", TIMER)
    return state == "active", f"{TIMER} {state or 'unknown'}"


def walk() -> tuple[bool, str]:
    _, tab = run("crontab", "-l")
    lines = [ln for ln in tab.splitlines() if ln.rstrip().endswith("# ark-walk")]
    ours = [ln for ln in lines if f"cd {ROOT} " in ln and WALKER in ln]
    _, head = run("git", "rev-parse", *(f"HEAD:{w}" for w in WALKERS))
    code = ROOT / "data/logs/.walk_code"
    fresh = code.exists() and code.read_text().split() == head.split()
    ok = len(lines) == len(ours) == 2 * LANES and fresh
    return ok, f"{len(ours)} of {len(lines)} ark-walk lines here, want 6; walk code " + (
        "at HEAD" if fresh else "not HEAD's"
    )


def lock() -> tuple[bool, str]:
    path = Path(os.environ.get("ARK_SYNC_LOCK", ROOT / "data/logs/.sync.lock"))
    if not path.exists():
        return True, "free"
    rc, pid = run("bash", "scripts/harness/sync_lock.sh", "holder")
    return rc == 0, f"held by {pid}" if rc == 0 else "held by a dead pid"


def hold() -> tuple[bool, str]:
    names = hold_names()
    if names is None:
        return True, "no hold"
    by_label = (STATE / "hold").read_text().startswith("label\n")
    bad = []
    for name in names:
        if (
            name == TIMER
            and not by_label
            and run("systemctl", "--user", "is-enabled", TIMER)[1] == "enabled"
        ):
            bad.append(f"{TIMER} still enabled")
        elif name == "pause-platform" and not (STATE / name).exists():
            bad.append("pause-platform flag missing")
    return not bad, "; ".join(bad) or f"holds {' '.join(names) or 'nothing named'}"


def login() -> tuple[bool, str]:
    rc, _ = run("gh", "auth", "status")
    return rc == 0, "gh login alive" if rc == 0 else "gh login dead"


def disk() -> tuple[bool, str]:
    rc, lines = space(root=ROOT)
    return rc == 0, lines[0] if rc == 0 else "; ".join(lines)


def lane(n: int) -> tuple[bool, str]:
    if (STATE / "pause-platform").exists():
        return True, "paused"
    if run("pgrep", "-f", f"cdx_extended_walk[.]py --lane {n} ")[0] == 0:
        return True, "running"
    log = ROOT / f"data/raw/cdx_walk/lane{n}/log.tsv"
    if not log.exists():
        return False, "stopped, never ran"
    idle = time.time() - log.stat().st_mtime
    return idle < RESTART_S, f"last wrote {idle / 60:.0f} min ago"


def module(path: str):
    spec = importlib.util.spec_from_file_location(Path(path).stem, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def left(unit: str) -> int:
    """Parts under three strikes the unit's reader has not read, from its own files alone."""
    return module(READERS[unit][0]).left()


def reader(unit: str) -> tuple[bool, str]:
    if not (parts := left(unit)):
        return True, "finished"
    state = run("systemctl", "--user", "is-active", unit)[1] or "unknown"
    held = hold_names() is not None
    why = f"{state}, {parts} parts left" + (", held" if held else "")
    log = ROOT / f"data/logs/{READERS[unit][1]}.log"
    if state == "active" or held:
        return True, why
    if not log.exists():  # the tick starts a reader within the hour its code arrived
        new = time.time() - (ROOT / READERS[unit][0]).stat().st_mtime < START_S
        return new, f"not started yet, {parts} parts left"
    with open(log, "rb") as fh:
        fh.seek(max(0, log.stat().st_size - 4096))
        last = (fh.read().decode(errors="replace").strip().splitlines() or [""])[-1]
    now = time.time()
    if (m := WAITS.search(last)) and calendar.timegm(time.strptime(m[1], "%Y%m%dT%H%M%SZ")) > now:
        return True, f"{state}, {parts} parts left, {m[0]}"
    if last.endswith("held") and now - log.stat().st_mtime < 3600:
        return True, f"{state}, {parts} parts left, held within the hour"
    return False, why


def readers() -> list[tuple[str, bool, str]]:
    env = ROOT / "local.env"
    if "local:" not in (env.read_text() if env.exists() else ""):
        return [("readers", True, "not run here")]
    return [(unit, *reader(unit)) for unit in READERS]


def main(argv: list[str]) -> int:
    if argv[:1] == ["left"]:
        print(left(argv[1]))
        return 0
    checks = [
        ("timer", *timer()),
        ("walk", *walk()),
        ("lock", *lock()),
        ("hold", *hold()),
        ("login", *login()),
        ("space", *disk()),
        *((f"lane{n}", *lane(n)) for n in range(LANES)),
        *readers(),
    ]
    failed = [name for name, ok, _ in checks if not ok]
    for name, ok, why in checks:
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {why}")
    print(f"unattended: {'FAIL ' + ' '.join(failed) if failed else 'ok'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
