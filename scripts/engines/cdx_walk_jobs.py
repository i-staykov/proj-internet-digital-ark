"""Keep the extended walk running with nobody at the keyboard: `just walk install|status|remove`.

The bank host walks: the machine whose `ARK_HOSTS` in local.env has a `local` entry runs `LANES`
lanes, the Channel's clients less the runners' (`lanes`: while `docs/registers/runner/cadence`
is set and no STOP holds, `runner_slices.py`, and `GRACE_S` past the register's last change,
since a job that read live before STOP, or before `cadence` fell, walks into the next hour), each
`WORKERS` requests at once. Cron starts each at boot and every 10 minutes under its own `flock`,
with `--lanes` their count, so the queue splits by hash; a dropped lane's pending goes to the lane
its number folds onto, under that flock (the walker's `adopt`). The tick reinstalls the cron and
stops the walkers once `code` (HEAD's blobs of `WALK`, this file and the walker, and the lane
count) changed since the install, and cron restarts them (`scripts/harness/scheduled_sync.sh`);
the bank cuts the runners a slice only while the install is `current`. `install` first gives
every lane folder a done set (`done`), since each lane skips what any lane answered. The laptop
runs no lane (AGENTS.md, Channel).
"""

from __future__ import annotations

import shlex
import subprocess
import sys
import time
from pathlib import Path

CODE = Path(__file__).resolve().parents[2]
DATA = CODE / "data"
TAG = "# ark-walk"
PY = "^/usr/bin/python3 .*cdx_extended_walk[.]py"  # the walker, not its shell or flock
RUNNER = CODE / "docs/registers/runner"  # the runners' cadence and STOP (runner_slices.py)
WALK = ("scripts/engines/cdx_walk_jobs.py", "scripts/engines/cdx_extended_walk.py")
GRACE_S = 90 * 60  # a job starts at :17 and is killed by :14 the next hour, GitHub's delay on top
FLOOR_ENV = ("ARK_FREE_SPACE_GIB", "ARK_WRITE_BUDGET_GIB")  # src/ark/disk.py


def code() -> str:
    """HEAD's blobs of `WALK` and the lane count, what the tick keeps in `data/logs/.walk_code`."""
    blobs = sh(f"git -C {CODE} ls-tree HEAD {' '.join(WALK)}")
    return f"{blobs}\n{lanes()}"


def current() -> bool:
    """Whether the walk installed is `code`'s."""
    try:
        return (DATA / "logs/.walk_code").read_text().split() == code().split()
    except OSError:
        return False


def runners() -> bool:
    """Whether the runners are a client: `cadence` keeps slices cut and no STOP holds."""
    try:
        on = int((RUNNER / "cadence").read_text().split()[-1]) > 0
    except (OSError, ValueError, IndexError):
        on = False
    return on and not (RUNNER / "STOP").exists()


def lanes() -> int:
    """The Channel's three clients here, less the runners' while they are one, and for `GRACE_S`
    after the register last changed, since a job that read live before may still walk."""
    files = (RUNNER, RUNNER / "cadence", RUNNER / "STOP")
    changed = max((p.stat().st_mtime for p in files if p.exists()), default=0.0)
    return 3 - (runners() or time.time() - changed < GRACE_S)


LANES, WORKERS = lanes(), 3  # lanes here, requests at once in each


def local_env(name: str) -> str:
    """One name's value in local.env, which assigns without export."""
    env = ["bash", "-c", f". ./local.env 2>/dev/null; echo ${name}"]
    return subprocess.run(env, cwd=CODE, capture_output=True, text=True).stdout.strip()


def here() -> bool:
    """Whether this machine walks: a `local` entry in its ARK_HOSTS."""
    return any(h.rpartition(":")[0] == "local" for h in local_env("ARK_HOSTS").split())


def sh(cmd: str) -> str:
    p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
    return (p.stdout + p.stderr).strip()


def cron(lane: int) -> str:
    # cron inherits no local.env: the bank's floor travels in the line
    floor = "".join(f"{k}={v} " for k in FLOOR_ENV if (v := local_env(k)))
    return (
        f"cd {CODE} && {floor}flock -n {DATA}/lane{lane}.lock /usr/bin/python3 "
        f"scripts/engines/cdx_extended_walk.py --lane {lane} --lanes {LANES} "
        f"--data {DATA} --workers {WORKERS} --max-local {LANES} --connect-timeout 4 "
        f"--max-transient 30 >> {DATA}/logs/lane{lane}.log 2>&1"
    )


def sub(key: str, k: int) -> str:
    """Subpage k of a page's done key: ten times finer, the same years."""
    sfx, size, page, years = key.split(" ", 3)
    return f"{sfx} {int(size) // 10} {int(page) * 10 + k} {years}"


def done() -> None:
    """Give each lane folder with a log but no done set one, booked as the walker books, or less:
    a complete 200, a subpage's 400 or its fourth 504 in a row; a cut 200 or a 1,000-block 504
    only once the subpages it owes are booked, so a page is at worst asked again."""
    for lane in sorted((DATA / "raw/cdx_walk").glob("lane*")):
        if (lane / "done.txt").exists() or not (lane / "log.tsv").exists():
            continue
        booked, owing, rows, streak = set(), {}, {}, {}
        for row in (f.split("\t") for f in (lane / "log.tsv").read_text().splitlines()):
            if len(row) < 14 or not row[2].isdigit():  # a `#` note or a torn line
                continue
            key, size, status = " ".join(row[1:6]), int(row[2]), row[7]
            streak[key] = streak.get(key, 0) + 1 if status == "HTTP504" else 0
            rows[key] = rows.get(key, 0) + (int(row[11]) if status == "200" else 0)
            whole = status == "200" and row[8] == "1"
            if whole or size < 1000 and (status == "HTTP400" or streak[key] >= 4):
                booked.add(key)
            elif status == "200" and int(row[11]) > 0 or status == "HTTP504" and size >= 1000:
                owing[key] = status
        for key, status in sorted(owing.items(), key=lambda o: int(o[0].split()[1])):
            # the finest first; probes 0 and 5, all ten once one has rows
            probes = [sub(key, 0), sub(key, 5)]
            wanted = probes if status != "200" and not any(rows.get(p) for p in probes) else None
            if all(k in booked for k in wanted or [sub(key, k) for k in range(10)]):
                booked.add(key)
        (lane / "done.txt").write_text("".join(k + "\n" for k in sorted(booked)))
        print(f"{lane.name}: {len(booked)} answered pages from its log")


def install() -> None:
    if not here():
        print("no lane here: the bank host walks, `just vm install`")
        return
    done()
    lines = "".join(
        f"echo {w} {shlex.quote(cron(lane))} '{TAG}'; "
        for lane in range(LANES)
        for w in ("@reboot", "'*/10 * * * *'")
    )
    sh(f"mkdir -p {DATA}/logs; (crontab -l 2>/dev/null | grep -v '{TAG}'; {lines}) | crontab -")
    if sh(f"crontab -l | grep -c -- '--lanes {LANES} .*{TAG}'") != str(2 * LANES):
        raise SystemExit("walk install: the crontab did not take; the tick stops no walker")
    print(f"{LANES} lanes of {WORKERS} workers:", sh(f"git -C {CODE} log --oneline -1"))


def status() -> None:
    print("walkers:", sh(f"pgrep -fc {PY!r}") or "0")
    for lane in range(LANES):
        log = DATA / f"raw/cdx_walk/lane{lane}/log.tsv"
        print(f"lane {lane}:", log.read_text().splitlines()[-1] if log.exists() else "no requests")


def remove() -> None:
    print(sh(f"crontab -l | grep -v '{TAG}' | crontab -; pkill -f '{PY}'"))


if __name__ == "__main__":
    git = ["git", "-C", str(CODE), "rev-parse", "--git-dir", "--git-common-dir"]
    gitdir, common = subprocess.run(git, capture_output=True, text=True).stdout.split()
    if Path(CODE, gitdir).resolve() != Path(CODE, common).resolve():
        raise SystemExit("run `just walk` from the main checkout, whose data/ the bank reads")
    what = (sys.argv[1:] or ["status"])[0]
    if what == "code":
        print(code())
    else:
        {"install": install, "done": done, "status": status, "remove": remove}[what]()
