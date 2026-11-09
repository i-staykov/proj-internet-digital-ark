"""Runner lanes: pages lent to GitHub's runners, and their journals banked (issue 585).

IA throttles CDX per address (laws), so a job of `.github/workflows/runner-lanes.yml` walks one
slice from a runner's own address and uploads what it wrote as an artifact named by the slice:
pure scripted requests, no secret on a runner, nothing there knows the VM. `LANES` holds the two
lanes: `slice_*` for the hosted hourly job, `long_*` for `runner-lane-long.yml`, a 6 h job on
the owner's cloud VM (`scripts/fleet/join.sh`), each with its own knob, workflow, lane folder,
walk seconds and stale hours.

`write`, the bank's last step: `docs/registers/runner/<prefix>_<stamp>_<k>.txt` is the next pages
a lane would ask (`cdx_extended_walk.load`, a throwaway lane over `data/raw/cdx_walk/runner/`
ranking as the lanes do, their ask tier in), the runners' slices of both lanes holding at most
`SHARE` of the pages above that tier, then questions (`asks`) once those run short, in
pending.txt's head format; the knob (`cadence` or `long`, a one-line PR) keeps that many cut, the
jobs an hour plus one for the hosted lane, so no job waits for the tick, and none without it, two
for the long lane, a spare on live when a walk ends, since the next cut lags a walk by 1 to 2 h; a
zeroed knob or STOP deletes the slices. A slice's tasks are ceil(walk seconds x rate x `MARGIN`),
at least `PAGES`, the rate the lane's answered rows a second over its last banked log, at most the
walker's one start an `INTERVAL` (a two-row log says nothing faster), so a lane's first slice is
`PAGES` and measures it. The runners are one more client on their own address, the Channel's cap
being per address. A slice goes once its artifact is banked, or after its lane's stale hours (over
the walk, the schedule's gap and the bank's hour) with none, its pages back to the lanes.
`runner/lent.txt` is the union of the slices present and `runner*/done.txt`, reread by the walker
by mtime, so a running lane neither asks a lent page nor one a runner answered. Each pulled log
is judged once: a pause of 15 minutes or more, or under `FLOOR` answered of `FLOOR_REQUESTS` or
more requests, is IA refusing the runners, written with its counts as
`docs/registers/runner/STOP`, every slice deleted; a job finding STOP makes no request, and a PR
lifts it.

`pull`, the tick's first step, touches only `data/`: one artifact listing, a row of another head
repository or branch skipped (a fork's PR run), each new zip unzipped through an allowlist into a
staging folder, its id written to `banked.txt`, then banked: journals under `data/raw/` where the
name is absent, done keys to `runner<index>/done.txt` less the parents whose subpages the job's
pending.txt still owes (a lane re-asks a page the runner cut and did not finish), the log rows
once, under a `# artifact <id> <name>` marker. A staged folder a crash left banks first. Any
failure is one line and exit 0.

`dispatch`, after the bank's push: one run per workflow while its slice is on `live`, none while
STOP or a zeroed knob holds or a run is queued or in progress; the workflow's schedule, which
GitHub delays or drops under load, is the second trigger.

    uv run python scripts/engines/runner_slices.py write|pull|dispatch [--data DIR]
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import NamedTuple

REPO = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("ARK_WALK_DATA", REPO / "data"))
REGISTER = REPO / "docs/registers/runner"
GITHUB = "i-staykov/proj-internet-digital-ark"
PAGES, MARGIN = 300, 1.25
# the runners are one client beside the bank host's three lanes (`cdx_walk_jobs.LANES`): they hold
# at most a fourth of the pages the lanes rank above the ask tier, so lending never empties the
# lanes' page work, which is what pays (laws)
SHARE = 1 / 4
FLOOR, FLOOR_REQUESTS = 0.1, 20
HEAD = "# scripts/engines/runner_slices.py\n"
SLICE = re.compile(r"^(slice|long)_(\d{8}T\d{6}Z)_\d+$")
PAUSE = re.compile(r"^# pause (\d+) s")
ORDER = re.compile(r"^# order .* (\d+) s a start$")
ARTIFACT = re.compile(r"^((?:slice|long)_\d{8}T\d{6}Z_\d+)_r(\d+)$")
STATE = ("cdx_walk/lane0/log.tsv", "cdx_walk/lane0/done.txt", "cdx_walk/lane0/pending.txt")
JOURNAL = re.compile(r"^(cdx_suffix|extended/ia_cdx_hostnames)/walk_[\w.-]+\.jsonl\.gz$")
MEMBER_CAP = 64 << 20


class Lane(NamedTuple):
    knob: str  # docs/registers/runner/<knob>: the slices kept cut
    workflow: str
    index: int  # the job's artifact suffix `_r<index>`, banked as runner<index>
    seconds: int  # the job's WALK_SECONDS
    stale_h: int  # over the walk, the schedule's gap and the bank's hour


LANES = {
    "slice": Lane("cadence", "runner-lanes.yml", 0, 3300, 6),
    "long": Lane("long", "runner-lane-long.yml", 1, 21600, 30),
}


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


walker, jobs = _load("cdx_extended_walk"), _load("cdx_walk_jobs")


def gh(*args: str, timeout: int) -> bytes:
    return subprocess.run(["gh", *args], capture_output=True, timeout=timeout, check=True).stdout


def lines(path: Path) -> list[str]:
    """A slice, lent, done or pending file's lines, its `#` lines and blanks left out."""
    if not path.exists():
        return []
    return [ln for ln in path.read_text().splitlines() if ln.strip() and ln[:1] != "#"]


def keys(path: Path) -> set[str]:
    return {" ".join(ln.split()[:5]) for ln in lines(path)}


def put(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def knob(register: Path, name: str) -> int:
    """The knob's last non-`#` line: the slices kept cut; none without the file."""
    try:
        return int(lines(register / name)[-1])
    except (ValueError, IndexError):
        return 0


def slices(register: Path, prefix: str = "*") -> list[Path]:
    """The register's slice files, one lane's or every lane's."""
    return sorted(f for f in register.glob(f"{prefix}_*.txt") if f.stem.split("_")[0] in LANES)


def blocked(log: list[str]) -> str:
    """Why a job's log says IA refuses the runners, or "" while it does not."""
    requests = answered = long = 0
    for ln in log:
        if m := PAUSE.match(ln):
            long += int(m[1]) >= 900
        r = ln.split("\t")
        if len(r) >= 14 and r[2].isdigit():
            requests += 1
            answered += r[7] in ("200", "HTTP504")
    if long:
        return f"{long} pauses of 15 min or more, {answered} of {requests} requests answered"
    if requests >= FLOOR_REQUESTS and answered < FLOOR * requests:
        return f"{answered} of {requests} requests answered"
    return ""


def judge(runner: Path) -> list[str]:
    """Each log pulled since the last bank, read once and dropped: its reason, if any."""
    why = []
    for f in sorted((runner / "judge").glob("*.tsv")):
        if reason := blocked(f.read_text(errors="replace").splitlines()):
            why.append(f"{f.stem}: {reason}")
        f.unlink()
    return why


def size(log: Path, seconds: int) -> int:
    """A slice for `seconds` of walking at the lane's rate: its answered rows a second over the
    rows after its log's last `# artifact` marker, at most one an `INTERVAL`; `PAGES` before any."""
    rows: list[list[str]] = []
    for ln in log.read_text(errors="replace").splitlines() if log.exists() else []:
        if ln.startswith("# artifact "):
            rows = []
        elif len(r := ln.split("\t")) >= 14 and r[2].isdigit():
            rows.append(r)
    try:
        at = [dt.datetime.strptime(r[0], "%Y%m%dT%H%M%SZ") for r in rows]
        span = (max(at) - min(at)).total_seconds()
    except ValueError:
        return PAGES
    answered = sum(r[7] in ("200", "HTTP504") for r in rows)
    rate = min(answered / span, 1 / walker.INTERVAL) if span else 0
    return max(PAGES, math.ceil(seconds * rate * MARGIN))


def start_cost(walk: Path) -> float:
    """The least seconds a start costs a lane here, its last `# order` line's; the interval when
    none has one: the lane with the most starts ranks the fewest pages above the ask tier."""
    costs = []
    for log in walk.glob("lane[0-9]*/log.tsv"):
        with open(log, "rb") as fh:
            fh.seek(max(0, log.stat().st_size - (1 << 18)))
            tail = fh.read().decode(errors="replace").splitlines()
        costs += [float(m[1]) for ln in tail if (m := ORDER.match(ln))][-1:]
    return min(costs, default=walker.INTERVAL)


def asks(data: Path, tiers: list[str], n: int, out: set[str]) -> list[tuple]:
    """The first `n` questions of `tiers` in turn, each tier's in the pool's file order as the lanes
    ask it, none in `out`: the file read to the first tier's `n`-th, never loaded whole."""
    pool, got = data / "queue/pool_questions.tsv", {t: [] for t in tiers}
    if n > 0 and got and pool.exists():
        with open(pool) as fh:
            for line in fh:
                tier, domain = line.rstrip("\n").split("\t")
                task = (f"ask-{tier}", 1, domain, walker.FIRST, walker.LAST, "ask")
                if task[0] in got and len(got[task[0]]) < n and walker.key_of(task) not in out:
                    got[task[0]].append(task)
                    if len(got[tiers[0]]) == n:
                        break
    return [t for tier in tiers for t in got[tier]][:n]


def cut(data: Path, runner: Path, sizes: list[int]) -> list[list[tuple]]:
    """A slice of each size in turn from the head of the lanes' ranking, the ask tiers in as empty
    markers (the priced ones, no question loaded): both lanes' slices at most `SHARE` of the pages
    above the first tier less the lent, then the priced tiers' questions, none lent or done (a page
    a lane cut is done; its subpages are that lane's own)."""
    a = SimpleNamespace(lane=0, lanes=1, data=data, state_dir=runner, slice=None)
    a.questions, a.max_transient, a.workers = True, 0, jobs.WORKERS
    a.min_interval = start_cost(runner.parent)
    lane = walker.load(a)
    for tier in {u.split(" ")[0] for u in lane.order if u.endswith(" ask")} | set(walker.ASKED):
        lane.pages.setdefault((tier, "ask"), [])
        lane.asked.setdefault((tier, "ask"), 0)
    lane.rerank(force=True)
    tiers = [i for i, u in enumerate(lane.ranked) if u[1] == "ask"]
    above = [t for u in lane.ranked[: tiers[0] if tiers else None] for t in lane.pages[u]]
    free = [t for t in above if walker.key_of(t) not in lane.lent]
    out = len(above) - len(free)  # in a slice present already
    free = free[: max(0, int(len(above) * SHARE) - out)]
    names = [lane.ranked[i][0] for i in tiers]
    free += asks(data, names, sum(sizes) - len(free), lane.done | lane.lent)
    slices, at = [], 0
    for pages in sizes:
        if at >= len(free):
            break
        slices.append(free[at : at + pages])
        at += pages
    return slices


def write(data: Path = DATA, register: Path = REGISTER, now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now(dt.UTC)
    runner = data / "raw/cdx_walk/runner"
    runner.mkdir(parents=True, exist_ok=True)
    stop = register / "STOP"
    if (why := judge(runner)) and not stop.exists():
        put(stop, HEAD + "".join(w + "\n" for w in why))
    off = {p: stop.exists() or not knob(register, lane.knob) for p, lane in LANES.items()}
    banked = runner / "banked.txt"
    taken = {m[1] for ln in lines(banked) if (m := ARTIFACT.match(ln.split("\t")[-1]))}
    gone = 0
    for f in slices(register):
        prefix, m = f.stem.split("_")[0], SLICE.match(f.stem)
        at = dt.datetime.strptime(m[2], "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.UTC) if m else now
        stale = now - at > dt.timedelta(hours=LANES[prefix].stale_h)
        if off[prefix] or not m or f.stem in taken or stale:
            f.unlink()
            gone += 1

    def lend() -> set[str]:
        lent = set().union(*(keys(f) for f in slices(register)))
        lent |= set().union(*(keys(d) for d in runner.parent.glob("runner[0-9]*/done.txt")))
        put(runner / "lent.txt", HEAD + "".join(k + "\n" for k in sorted(lent)))
        return lent

    lend()  # before cutting, so the throwaway lane skips what is out
    plan = []  # (prefix, pages) per slice wanted
    for prefix, lane in LANES.items():
        want = knob(register, lane.knob) - len(slices(register, prefix))
        if want > 0 and not off[prefix]:
            pages = size(runner.parent / f"runner{lane.index}/log.tsv", lane.seconds)
            plan += [(prefix, pages)] * want
    new = []
    for (prefix, _), tasks in zip(plan, cut(data, runner, [p for _, p in plan]), strict=False):
        k = sum(n.startswith(prefix + "_") for n in new)
        name = f"{prefix}_{now:%Y%m%dT%H%M%SZ}_{k}"
        put(register / f"{name}.txt", HEAD + "".join(walker.encode(t, ()) + "\n" for t in tasks))
        new.append(name)
    lent = lend()
    stopped = ", STOP" + (" written" if why else "") if stop.exists() else ""
    return f"runner slices: {len(new)} cut, {gone} gone, {len(lent)} keys lent{stopped}"


def accepted(art: dict) -> bool:
    """An unexpired artifact of this repository's own `live` run, named like a slice."""
    run = art.get("workflow_run") or {}
    own = run.get("head_repository_id") is not None
    own = own and run.get("head_repository_id") == run.get("repository_id")
    own = own and run.get("head_branch") == "live" and not art.get("expired")
    return own and bool(ARTIFACT.match(art.get("name", "")))


def unzip(archive: Path, into: Path) -> int:
    """The allowed members under `into`; how many were dropped."""
    dropped = 0
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            name = info.filename
            if (name in STATE or JOURNAL.match(name)) and info.file_size <= MEMBER_CAP:
                (into / name).parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(into / name, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            else:
                dropped += 1
    return dropped


def bank(stage: Path, data: Path) -> None:
    """A staged artifact into `data/`, then the stage gone; a crash's retry books the log once."""
    _, aid, name = stage.name.split("_", 2)
    lane = data / "raw/cdx_walk" / f"runner{ARTIFACT.match(name)[2]}"
    log, marker = lane / "log.tsv", f"# artifact {aid} {name}"
    if not (log.exists() and marker in log.read_text(errors="replace").splitlines()):
        for folder in ("cdx_suffix", "extended/ia_cdx_hostnames"):
            for src in sorted((stage / folder).glob("walk_*.jsonl.gz")):
                dst = data / "raw" / folder / src.name
                if not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(src, dst)
        state = stage / "cdx_walk/lane0"
        owed = set()
        for ln in lines(state / "pending.txt"):
            try:
                meta = walker.decode(ln)[1]
            except ValueError:
                continue
            if len(meta) > 1:
                owed.add(meta[1])
        lane.mkdir(parents=True, exist_ok=True)
        with open(lane / "done.txt", "a") as fh:
            fh.writelines(k + "\n" for k in sorted(keys(state / "done.txt") - owed))
        rows = (
            (state / "log.tsv").read_text(errors="replace") if (state / "log.tsv").exists() else ""
        )
        put(lane.parent / "runner/judge" / f"{aid}_{name}.tsv", rows)
        with open(log, "a") as fh:
            fh.write(marker + "\n" + rows + ("\n" if rows and not rows.endswith("\n") else ""))
    shutil.rmtree(stage)


def pull(data: Path = DATA) -> str:
    runner = data / "raw/cdx_walk/runner"
    runner.mkdir(parents=True, exist_ok=True)
    banked = runner / "banked.txt"
    ids = {ln.split("\t")[0] for ln in lines(banked)}
    for stage in sorted(runner.glob("pull_*")):
        shutil.rmtree(stage) if stage.suffix == ".tmp" else bank(stage, data)
    listing = json.loads(gh("api", f"repos/{GITHUB}/actions/artifacts?per_page=100", timeout=60))
    n = dropped = 0
    for art in listing.get("artifacts", []):
        aid = str(art.get("id", ""))
        if not (aid and accepted(art)) or aid in ids:
            continue
        stage = runner / f"pull_{aid}_{art['name']}"
        tmp = stage.with_name(stage.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir()
        archive = tmp / "artifact.zip"
        archive.write_bytes(gh("api", f"repos/{GITHUB}/actions/artifacts/{aid}/zip", timeout=300))
        dropped += unzip(archive, tmp)
        archive.unlink()
        os.replace(tmp, stage)
        with open(banked, "a") as fh:
            fh.write(f"{aid}\t{art['name']}\n")
        bank(stage, data)
        n += 1
    return f"runner slices: {n} artifacts banked, {dropped} members dropped"


def dispatch(register: Path = REGISTER) -> str:
    said = []
    for prefix, lane in LANES.items():
        if (register / "STOP").exists() or not knob(register, lane.knob):
            said.append(f"{prefix} off")
        elif not slices(register, prefix):
            said.append(f"{prefix} no slice")
        else:
            args = ("run", "list", "--repo", GITHUB, "--workflow", lane.workflow, "--limit", "5")
            runs = json.loads(gh(*args, "--json", "status", timeout=60))
            if live := sum(r.get("status") != "completed" for r in runs):
                said.append(f"{prefix} {live} live")
            else:
                gh("workflow", "run", lane.workflow, "--repo", GITHUB, "--ref", "live", timeout=60)
                said.append(f"{prefix} asked")
    return "runner dispatch: " + ", ".join(said)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("step", choices=("write", "pull", "dispatch"))
    ap.add_argument("--data", type=Path, default=DATA)
    a = ap.parse_args(argv)
    steps = {"write": lambda: write(a.data), "pull": lambda: pull(a.data), "dispatch": dispatch}
    try:
        print(steps[a.step]())
    except Exception as exc:  # noqa: BLE001  one line in the tick's log, never its exit
        err = (getattr(exc, "stderr", None) or b"").decode(errors="replace").strip().splitlines()
        print(f"runner {a.step}: failed, {type(exc).__name__}: {err[-1] if err else exc}")


if __name__ == "__main__":
    main(sys.argv[1:])
