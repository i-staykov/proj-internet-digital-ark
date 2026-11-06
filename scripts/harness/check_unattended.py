"""Prove the unattended path: exit 0 only when every part the tick leans on is as it should be.

Run at the end of every tick (`scheduled_sync.sh`) and by hand (`just check unattended`). One
line per check, `ok` or `FAIL`, then the verdict; exit 1 on any FAIL.

- timer: `ark-sync.timer` is active.
- walk: the crontab holds six `# ark-walk` lines, each `cd` here and running the walker, and
  `data/logs/.walk_code` names HEAD's walker blobs, so the lanes run HEAD's code.
- lock: the sync lock is free or its holder's pid is alive.
- hold: each unit or flag the hold file names is off (the timer not enabled, the flag file
  present).
- login: `gh auth status` succeeds.
- space: free space clears the bank's floor plus its write budget (`ark.db.space`).
- lanes: a lane with work left and no pause flag runs, or ran within cron's restart period; its
  last `# exit ... pending=0` row means its queue is empty.
- readers, only where `local.env` ARK_HOSTS runs here: End of Term and ClueWeb09 with parts left
  and no hold are active units. The HTTP Archive reader's queue needs archive.org's search, and
  the header lane has no unit yet, so both are reported, never judged.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ark.db import space  # noqa: E402

TIMER = "ark-sync.timer"
WALKERS = ("scripts/engines/cdx_walk_jobs.py", "scripts/engines/cdx_extended_walk.py")
WALKER = "scripts/engines/cdx_extended_walk.py"
LANES = 3
# cron starts a stopped lane every 10 minutes; one more for the start itself
RESTART_S = 11 * 60
STATE = Path(os.environ.get("ARK_STATE_DIR", Path.home() / "ark/state"))


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
    bad = []
    for name in names:
        if name == TIMER and run("systemctl", "--user", "is-enabled", TIMER)[1] == "enabled":
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


def last_row(path: Path) -> str:
    with path.open("rb") as f:
        f.seek(max(0, path.stat().st_size - 4096))
        rows = f.read().decode(errors="replace").splitlines()
    return rows[-1] if rows else ""


def lane(n: int) -> tuple[bool, str]:
    if (STATE / "pause-platform").exists():
        return True, "paused"
    if run("pgrep", "-f", f"cdx_extended_walk[.]py --lane {n} ")[0] == 0:
        return True, "running"
    log = ROOT / f"data/raw/cdx_walk/lane{n}/log.tsv"
    if not log.exists():
        return False, "stopped, never ran"
    if last_row(log).startswith("# exit") and last_row(log).endswith("pending=0"):
        return True, "queue empty"
    idle = time.time() - log.stat().st_mtime
    return idle < RESTART_S, f"stopped {idle / 60:.0f} min with work left"


def module(path: str):
    spec = importlib.util.spec_from_file_location(Path(path).stem, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def reader(unit: str, left: int) -> tuple[bool, str]:
    state = run("systemctl", "--user", "is-active", unit)[1] or "unknown"
    held = hold_names() is not None
    ok = state == "active" or not left or held
    return ok, f"{state}, {left} parts left" + (", held" if held else "")


def readers() -> list[tuple[str, bool, str]]:
    env = ROOT / "local.env"
    if "local:" not in (env.read_text() if env.exists() else ""):
        return [("readers", True, "not run here")]
    eot = module("scripts/sources/eot/eot_cdxj.py")
    eot_left = [
        p for p in eot.PARTS if not (eot.OUT / f"eot_{p}.jsonl.gz").exists() and eot.failures(p) < 3
    ]
    clueweb = module("scripts/sources/crawl_lists/clueweb.py")
    har = run("systemctl", "--user", "is-active", "ark-har")[1] or "unknown"
    return [
        ("ark-eot", *reader("ark-eot", len(eot_left))),
        ("ark-clueweb", *reader("ark-clueweb", len(clueweb.todo()))),
        ("ark-har", True, f"{har}, queue needs archive.org's search, not judged"),
    ]


def main() -> int:
    checks = [
        ("timer", *timer()),
        ("walk", *walk()),
        ("lock", *lock()),
        ("hold", *hold()),
        ("login", *login()),
        ("space", *disk()),
        *((f"lane{n}", *lane(n)) for n in range(LANES)),
        *readers(),
        ("header lane", True, "no unit yet, not judged"),
    ]
    failed = [name for name, ok, _ in checks if not ok]
    for name, ok, why in checks:
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {why}")
    print(f"unattended: {'FAIL ' + ' '.join(failed) if failed else 'ok'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
