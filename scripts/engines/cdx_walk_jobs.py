"""Keep the extended walk running with nobody at the keyboard: `just walk install|status|remove`.

`ARK_HOSTS` in local.env lists the collector hosts, `target:lane` each, the target an ssh alias
or `login@host`. On each, cron starts its lane at boot and every 10 minutes under `flock`, from
a shallow clone of `live`, with `--lanes` one past the highest lane, so the queue splits by hash
the same way everywhere. `install` first seeds a lane's state (done set, page counts, request
log) from `data/` here, so a lane that once ran elsewhere walks on rather than over. The tick
pulls each lane's journals home and re-ranks the queue (`just sync`, step 7). The laptop runs
no lane (AGENTS.md, Channel).
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parents[2]
DATA = CODE / "data"
URL = "https://github.com/i-staykov/proj-internet-digital-ark"
TAG = "# ark-walk"
PY = "^/usr/bin/python3 .*cdx_extended_walk[.]py"  # the walker, not its shell or flock
WALK = "$HOME/ark-walk"
STATE = ("done.txt", "pages.json", "pending.txt", "log.tsv")


def hosts() -> list[tuple[str, int]]:
    env = ["bash", "-c", ". ./local.env; echo $ARK_HOSTS"]
    out = subprocess.run(env, cwd=CODE, capture_output=True, text=True).stdout.split()
    if not out:
        raise SystemExit("set ARK_HOSTS in local.env, target:lane each")
    return [(t.rpartition(":")[0], int(t.rpartition(":")[2])) for t in out]


def run(target: str, cmd: str) -> str:
    ssh = ["ssh", "-o", "ConnectTimeout=15", "-o", "BatchMode=yes", target, cmd]
    p = subprocess.run(ssh, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return (p.stdout + p.stderr).strip()


def cron(lane: int, lanes: int) -> str:
    return (
        f"cd {WALK} && flock -n $HOME/ark-walk-data/lane.lock /usr/bin/python3 "
        f"scripts/engines/cdx_extended_walk.py --lane {lane} --lanes {lanes} "
        "--data $HOME/ark-walk-data --workers 3 --max-local 1 --connect-timeout 4 "
        f"--max-transient 30 >> $HOME/ark-walk-data/lane{lane}.log 2>&1"
    )


def install() -> None:
    lanes = max(lane for _, lane in hosts()) + 1
    for target, lane in hosts():
        state = f"ark-walk-data/raw/cdx_walk/lane{lane}/"
        run(target, f"mkdir -p {state} ark-walk-data/queue")
        rsync = ["rsync", "-a", "--ignore-existing", "--timeout=120"]
        seed = [DATA / "raw/cdx_walk" / f"lane{lane}" / f for f in STATE]
        if seed := [str(f) for f in seed if f.is_file()]:
            subprocess.run([*rsync, *seed, f"{target}:{state}"], check=True)
        queue = [str(DATA / "queue" / f) for f in ("cdx_order.json", "cdx_walked.txt")]
        subprocess.run([*rsync, *queue, f"{target}:ark-walk-data/queue/"], check=True)
        line = shlex.quote(cron(lane, lanes))
        print(f"lane {lane}:", run(target, (
            f"[ -d {WALK}/.git ] || git clone -q --depth 1 -b live {URL} {WALK}; "
            f"git -C {WALK} pull -q --ff-only; "
            f"(crontab -l 2>/dev/null | grep -v '{TAG}'; echo @reboot {line} '{TAG}'; "
            f"echo '*/10 * * * *' {line} '{TAG}') | crontab -; git -C {WALK} log --oneline -1"
        )))  # fmt: skip


def status() -> None:
    for target, lane in hosts():
        log = DATA / f"raw/cdx_walk/lane{lane}/log.tsv"
        rows = log.read_text().splitlines() if log.exists() else ["no requests yet"]
        print(f"lane {lane}: walkers {run(target, f'pgrep -fc {PY!r}') or '?'} | {rows[-1]}")


def remove() -> None:
    for target, lane in hosts():
        cmd = f"crontab -l | grep -v '{TAG}' | crontab -; pkill -f '{PY}'"
        print(f"lane {lane}:", run(target, cmd))


if __name__ == "__main__":
    git = ["git", "-C", str(CODE), "rev-parse", "--git-dir", "--git-common-dir"]
    gitdir, common = subprocess.run(git, capture_output=True, text=True).stdout.split()
    if Path(CODE, gitdir).resolve() != Path(CODE, common).resolve():
        raise SystemExit("run `just walk` from the main checkout, whose data/ the bank reads")
    {"install": install, "status": status, "remove": remove}[(sys.argv[1:] or ["status"])[0]]()
