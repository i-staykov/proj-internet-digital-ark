"""Keep the extended walk running with nobody at the keyboard: `just walk install|status|remove`.

The bank host walks: the machine whose `ARK_HOSTS` in local.env has a `local` entry runs `LANES`
lanes, the Channel's clients, each `WORKERS` requests at once. Cron starts each at boot and every
10 minutes under its own `flock`, with `--lanes` their count, so the queue splits by hash. The
tick reinstalls the cron and stops the walkers when this file or the walker changed, and cron
restarts them on the new code (`scripts/harness/scheduled_sync.sh`). `install` first gives every
lane folder a done set (`done`), since each lane skips what any lane answered. The laptop runs no
lane (AGENTS.md, Channel).
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parents[2]
DATA = CODE / "data"
TAG = "# ark-walk"
PY = "^/usr/bin/python3 .*cdx_extended_walk[.]py"  # the walker, not its shell or flock
LANES, WORKERS = 3, 3  # the Channel's three clients here, requests at once in each


def here() -> bool:
    """Whether this machine walks: a `local` entry in its ARK_HOSTS."""
    env = ["bash", "-c", ". ./local.env; echo $ARK_HOSTS"]
    hosts = subprocess.run(env, cwd=CODE, capture_output=True, text=True).stdout.split()
    return any(h.rpartition(":")[0] == "local" for h in hosts)


def sh(cmd: str) -> str:
    p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
    return (p.stdout + p.stderr).strip()


def cron(lane: int) -> str:
    return (
        f"cd {CODE} && flock -n {DATA}/lane{lane}.lock /usr/bin/python3 "
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
    {"install": install, "done": done, "status": status, "remove": remove}[
        (sys.argv[1:] or ["status"])[0]
    ]()
