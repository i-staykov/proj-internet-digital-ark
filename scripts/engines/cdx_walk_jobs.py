"""Keep the extended walk running with nobody at the keyboard: `just walk install|status|remove`.

launchd keeps laptop lanes 0 and 1 alive (`RunAtLoad`, `KeepAlive`, restarted at most every
10 minutes) under `caffeinate -i -s`, since idle sleep stops a lane with no error; cron starts
VPS lane 2 at boot and every 10 minutes under `flock`, from a shallow clone of `live`. The tick
pulls the VPS lane's journals home and re-ranks the queue (`just sync`, step 8).
"""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parents[2]
DATA = CODE / "data"
AGENTS = Path.home() / "Library/LaunchAgents"
URL = "https://github.com/i-staykov/proj-internet-digital-ark"
TAG = "# ark-walk"
PY = "^/usr/bin/python3 .*cdx_extended_walk[.]py"  # the VPS walker, not its shell or flock
WALK = "$HOME/ark-walk"
CRON = (
    f"cd {WALK} && flock -n $HOME/ark-walk-data/lane.lock /usr/bin/python3 "
    "scripts/engines/cdx_extended_walk.py --lane 2 --lanes 3 --data $HOME/ark-walk-data "
    "--workers 3 --max-local 1 --connect-timeout 4 --max-transient 30 "
    ">> $HOME/ark-walk-data/lane2.log 2>&1"
)


def launchctl(*args: str) -> int:
    return subprocess.run(["launchctl", *args], capture_output=True).returncode


def vps(cmd: str) -> str:
    env = ["bash", "-c", ". ./local.env; echo $ARK_VPS"]
    host = subprocess.run(env, cwd=CODE, capture_output=True, text=True).stdout.strip()
    ssh = ["ssh", "-o", "ConnectTimeout=15", "-o", "BatchMode=yes", host, cmd]
    p = subprocess.run(ssh, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return (p.stdout + p.stderr).strip()


def install() -> None:
    domain = f"gui/{os.getuid()}"
    for lane in (0, 1):
        label, log = f"com.ark.walk.lane{lane}", str(DATA / f"logs/com.ark.walk.lane{lane}.log")
        walk = str(CODE / "scripts/engines/cdx_extended_walk.py")
        args = ["/usr/bin/caffeinate", "-i", "-s", str(CODE / ".venv/bin/python"), walk]
        args += ["--lane", str(lane), "--lanes", "3", "--workers", "2"]
        job = {"Label": label, "ProgramArguments": args, "RunAtLoad": True, "KeepAlive": True,
               "ThrottleInterval": 600, "WorkingDirectory": str(CODE), "StandardOutPath": log,
               "StandardErrorPath": log}  # fmt: skip
        (AGENTS / f"{label}.plist").write_bytes(plistlib.dumps(job))
        launchctl("bootout", f"{domain}/{label}")
        launchctl("enable", f"{domain}/{label}")
        if launchctl("bootstrap", domain, str(AGENTS / f"{label}.plist")):
            subprocess.run(["sleep", "5"])  # a lane still stopping from the bootout
            launchctl("bootstrap", domain, str(AGENTS / f"{label}.plist"))
        print(f"loaded {label}")
    print("VPS:", vps(
        f"[ -d {WALK}/.git ] || git clone -q --depth 1 -b live {URL} {WALK}; "
        f"git -C {WALK} pull -q --ff-only; mkdir -p $HOME/ark-walk-data/queue; "
        f"(crontab -l 2>/dev/null | grep -v '{TAG}'; echo '@reboot {CRON} {TAG}'; "
        f"echo '*/10 * * * * {CRON} {TAG}') | crontab -; git -C {WALK} log --oneline -1"
    ))  # fmt: skip


def status() -> None:
    listed = subprocess.run(["launchctl", "list"], capture_output=True, text=True).stdout
    for lane in (0, 1, 2):
        job = [ln for ln in listed.splitlines() if ln.endswith(f"com.ark.walk.lane{lane}")]
        log = DATA / f"raw/cdx_walk/lane{lane}/log.tsv"
        rows = log.read_text().splitlines() if log.exists() else ["no requests yet"]
        print(f"lane {lane}: {job[0] if job else '-'} | {rows[-1]}")
    print("VPS walkers:", vps(f"pgrep -fc '{PY}'"))


def remove() -> None:
    for lane in (0, 1):
        launchctl("bootout", f"gui/{os.getuid()}/com.ark.walk.lane{lane}")
        (AGENTS / f"com.ark.walk.lane{lane}.plist").unlink(missing_ok=True)
    print("VPS:", vps(f"crontab -l | grep -v '{TAG}' | crontab -; pkill -f '{PY}'"))


if __name__ == "__main__":
    git = ["git", "-C", str(CODE), "rev-parse", "--git-dir", "--git-common-dir"]
    gitdir, common = subprocess.run(git, capture_output=True, text=True).stdout.split()
    if Path(CODE, gitdir).resolve() != Path(CODE, common).resolve():
        raise SystemExit("run `just walk` from the main checkout, whose data/ the bank reads")
    {"install": install, "status": status, "remove": remove}[(sys.argv[1:] or ["status"])[0]]()
