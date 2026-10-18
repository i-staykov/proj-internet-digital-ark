"""Keep the extended walk running with nobody at the keyboard: `just walk install|status|remove`.

`ARK_HOSTS` in local.env lists the collector hosts, `target:lane` each, the target an ssh alias,
`login@host`, or `local` for this machine, whose lane walks straight into `data/` here. On each,
cron starts its lane at boot and every 10 minutes under `flock`, a remote one from a shallow
clone of `live`, with `--lanes` their count and the lanes 0 to n-1, so the queue splits by hash
the same way everywhere. `install` first seeds a remote lane's state (done set, page counts,
request log) from `data/` here, so a lane that once ran elsewhere walks on rather than over.
The tick pulls each remote lane's journals home and re-ranks the queue (`just sync`, step 7).
The laptop runs no lane (AGENTS.md, Channel).
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
    found = [(t.rpartition(":")[0], int(t.rpartition(":")[2])) for t in out]
    # The walk shards pages by hash modulo the lane count, so a gap orphans its share.
    if sorted(lane for _, lane in found) != list(range(len(found))):
        raise SystemExit("ARK_HOSTS lanes must be 0 to n-1, each once: a gap is never walked")
    return found


SSH = ["ssh", "-o", "ConnectTimeout=15", "-o", "BatchMode=yes"]


def run(target: str, cmd: str) -> str:
    argv = ["bash", "-c", cmd] if target == "local" else [*SSH, target, cmd]
    p = subprocess.run(argv, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return (p.stdout + p.stderr).strip()


def cron(lane: int, lanes: int, code: str, data: str) -> str:
    return (
        f"cd {code} && flock -n {data}/lane.lock /usr/bin/python3 "
        f"scripts/engines/cdx_extended_walk.py --lane {lane} --lanes {lanes} "
        f"--data {data} --workers 3 --max-local 1 --connect-timeout 4 "
        f"--max-transient 30 >> {data}/logs/lane{lane}.log 2>&1"
    )


def install() -> None:
    lanes = len(hosts())
    for target, lane in hosts():
        code, data = WALK, "$HOME/ark-walk-data"
        if target == "local":
            code, data = str(CODE), str(DATA)
        else:
            state = f"ark-walk-data/raw/cdx_walk/lane{lane}/"
            if run(target, f"mkdir -p {state} ark-walk-data/queue && echo ok") != "ok":
                print(f"lane {lane}: its host did not answer, nothing installed")
                continue
            rsync = ["rsync", "-a", "--ignore-existing", "--timeout=120", "-e", " ".join(SSH)]
            seed = [DATA / "raw/cdx_walk" / f"lane{lane}" / f for f in STATE]
            if seed := [str(f) for f in seed if f.is_file()]:
                subprocess.run([*rsync, *seed, f"{target}:{state}"])
            queue = [str(DATA / "queue" / f) for f in ("cdx_order.json", "cdx_walked.txt")]
            subprocess.run([*rsync, *queue, f"{target}:ark-walk-data/queue/"])
            run(target, (
                f"[ -d {WALK}/.git ] || git clone -q --depth 1 -b live {URL} {WALK}; "
                f"git -C {WALK} pull -q --ff-only"
            ))  # fmt: skip
        line = shlex.quote(cron(lane, lanes, code, data))
        print(f"lane {lane}:", run(target, (
            f"mkdir -p {data}/logs; (crontab -l 2>/dev/null | grep -v '{TAG}'; "
            f"echo @reboot {line} '{TAG}'; echo '*/10 * * * *' {line} '{TAG}') | crontab -; "
            f"git -C {code} log --oneline -1"
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
