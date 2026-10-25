"""Keep the extended walk running with nobody at the keyboard: `just walk install|status|remove`.

`ARK_HOSTS` in local.env lists the collector hosts, `target:lane` each, the target an ssh alias,
`login@host`, or `local` for this machine, whose lane walks straight into `data/` here. On each,
cron starts its lane at boot and every 10 minutes under `flock`, a remote one from a shallow
clone of `live`, with `--lanes` their count and the lanes 0 to n-1, so the queue splits by hash
the same way everywhere. `install` first seeds every lane's state (done set, page counts,
request log) from `data/` here, a missing done set built from its log (`done`), so a lane walks
on from what any lane answered.
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


def setting(name: str) -> str:
    env = ["bash", "-c", f". ./local.env; echo ${name}"]
    return subprocess.run(env, cwd=CODE, capture_output=True, text=True).stdout.strip()


def hosts() -> list[tuple[str, int]]:
    out = setting("ARK_HOSTS").split()
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
    done()
    lanes = len(hosts())
    for target, lane in hosts():
        code, data = WALK, "$HOME/ark-walk-data"
        if target == "local":
            code, data = str(CODE), str(DATA)
        elif target == setting("ARK_VM"):
            print(f"lane {lane}: the VM installs its own lane, `just vm install`")
            continue
        else:
            state = "ark-walk-data/raw/cdx_walk/"
            if run(target, f"mkdir -p {state}lane{lane} ark-walk-data/queue && echo ok") != "ok":
                print(f"lane {lane}: its host did not answer, nothing installed")
                continue
            rsync = ["rsync", "-a", "--ignore-existing", "--timeout=120", "-e", " ".join(SSH)]
            if seed := [str(d) for d in sorted((DATA / "raw/cdx_walk").glob("lane*"))]:
                subprocess.run([*rsync, *seed, f"{target}:{state}"])  # every lane's done set
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
    {"install": install, "done": done, "status": status, "remove": remove}[
        (sys.argv[1:] or ["status"])[0]
    ]()
