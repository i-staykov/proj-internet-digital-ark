"""The hold, the one sync lock and the launchd job: what stops the hourly loop and keeps one
writer in the store. launchctl, gh, ssh, rsync, uv and a nested `just` are one logging shim
acting on files under tmp. Each recipe is rendered once as `just --dry-run` shows it, with no
`just`, which CI lacks, and bash runs it as just would, so no run writes a new executable for
macOS to scan."""

import os
import plistlib
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ["leg.yaml", "read.yaml", "improver.yaml"]
NAMES = ["com.ark.sync", "pause-platform", *WORKFLOWS]
JUST = shutil.which("just")
UID = os.getuid()
ME = str(os.getpid())  # a live pid to hold the lock with
STAMP = "2026-01-01T00:00:00Z"
FLAG = f"human\n{STAMP}\n"
# What `hold on` leaves: the file, the flag here and on the VPS, the job and workflows disabled.
HELD = {
    "state/hold": FLAG + "".join(f"{n}\n" for n in NAMES),
    "state/pause-platform": FLAG,
    "shim/vps/ark/state/pause-platform": FLAG,
    "shim/launchd/disabled/com.ark.sync": "",
    **{f"shim/workflows/{wf}": "disabled_manually\n" for wf in WORKFLOWS},
}
RECIPES = {"sync": ["sync"], "bank": ["bank"], "install": ["schedule", "install"]}
SCRIPTS = ("hold.sh", "scheduled_sync.sh", "sync_lock.sh")
REFUSED = f"a sync is already running as pid {ME}"
UV = r"uv (.+) lock=(\S*) held=(\S*)"

SHIM = r"""#!/bin/bash
name=${0##*/}
S=$SHIM_STATE
{ read -r lock < "$ARK_SYNC_LOCK/pid"; } 2>/dev/null
[ "$name" = uv ] && set -- "$@" "lock=${lock:-}" "held=${ARK_LOCK_HELD:-}"
echo "$name $*" >> "$SHIM_LOG"
case $name in
launchctl)
    L=$S/launchd
    case $1 in
    disable) : > "$L/disabled/${2##*/}" ;;
    enable) rm -f "$L/disabled/${2##*/}" ;;
    bootout) [ -e "$L/loaded/${2##*/}" ] || exit 3; rm -f "$L/loaded/${2##*/}" ;;
    bootstrap) l=${3##*/}; l=${l%.plist}; [ -e "$L/disabled/$l" ] && exit 5; : > "$L/loaded/$l" ;;
    print-disabled) for f in "$L"/disabled/*; do echo "\"${f##*/}\" => disabled"; done ;;
    list) for f in "$L"/loaded/*; do [ -e "$f" ] && printf -- '-\t0\t%s\n' "${f##*/}"; done ;;
    esac ;;
gh)
    [ -e "$S/offline" ] && exit 1
    case "$1 $2" in
    "api "*) f=$S/workflows/${2##*/}; if [ -e "$f" ]; then echo "$(<"$f")"; else echo active; fi ;;
    "workflow disable") echo disabled_manually > "$S/workflows/$3" ;;
    "workflow enable") echo active > "$S/workflows/$3" ;;
    esac ;;
ssh)
    # The command runs as the VPS would run it: its own home, its own ARK_STATE_DIR.
    [ -e "$S/offline" ] && exit 255
    for cmd; do :; done; unset ARK_STATE_DIR; HOME=$S/vps; eval "$cmd" ;;
uv)
    # Something arrived only when the test says so, for the first check. The slot check fails.
    case "$*" in *"bank_trigger.py check lock="*)
        rm "$S/arrived" 2>/dev/null || { echo "bank: nothing arrived"; exit 1; } ;;
    *--slots-only*) exit 1 ;; esac ;;
just) [ "$1" = bank ] && exec bash "$RECIPES/bank"; exit 99 ;;
esac
"""


def recipe(root: Path, name: str) -> str:
    """A shebang recipe as `just --dry-run` shows it: the body dedented, each `{{x}}` filled
    from the defaults, a variadic's empty."""
    text = (root / "justfile").read_text()
    params, body = re.search(rf"^{name}\b(.*):\n((?:(?:    .*)?\n)+)", text, re.M).groups()
    given = dict(re.findall(r'(\w+)(?:="([^"]*)")?', params))
    given["justfile_directory()"] = str(root)
    body = re.sub(r"^    ", "", body.rstrip("\n") + "\n", flags=re.M)
    return re.sub(r"\{\{(.+?)\}\}", lambda m: given[m[1].strip()], body)


class Box:
    def __init__(self, tmp: Path):
        self.tmp, self.repo, self.state = tmp, tmp / "repo", tmp / "state"
        self.shim, self.log, self.lock = tmp / "shim", tmp / "calls.log", tmp / "sync.lock"
        self.agents = tmp / "home/Library/LaunchAgents"
        self.quiet = {"cwd": self.repo, "capture_output": True, "text": True}
        for rel in ("justfile", *(f"scripts/harness/{n}" for n in SCRIPTS)):
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / rel, self.repo / rel)
        (bin_dir := tmp / "bin").mkdir()
        (bin_dir / "shim").write_text(SHIM)
        (bin_dir / "shim").chmod(0o755)
        for name in ("launchctl", "gh", "ssh", "rsync", "uv", "just"):
            (bin_dir / name).symlink_to("shim")
        (recipes := tmp / "recipes").mkdir()
        for name, argv in RECIPES.items():
            text = recipe(self.repo, argv[0])
            if JUST:  # the reading is just's own wherever just is installed
                args = [JUST, "--justfile", str(self.repo / "justfile"), "--dry-run", *argv]
                assert subprocess.run(args, **self.quiet).stderr == text, name
            (recipes / name).write_text(text)
        paths = {"ARK_STATE_DIR": self.state, "ARK_SYNC_LOCK": self.lock, "RECIPES": recipes}
        paths |= {"HOME": tmp / "home", "SHIM_LOG": self.log, "SHIM_STATE": self.shim}
        self.base = {k: str(v) for k, v in paths.items()}
        self.base |= {"PATH": f"{bin_dir}:/usr/bin:/bin", "ARK_VPS": "vps.test"}

    def reset(self) -> None:
        for path in (self.state, self.shim, self.lock, self.agents, self.repo / "data"):
            shutil.rmtree(path, ignore_errors=True)
        self.log.unlink(missing_ok=True)
        for sub in ("launchd/disabled", "launchd/loaded", "workflows"):
            (self.shim / sub).mkdir(parents=True)
        (self.shim / "launchd/loaded/com.ark.sync").touch()
        self.agents.mkdir(parents=True)
        (self.agents / "com.ark.sync.plist").write_text("<plist/>\n")

    def run(self, argv: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
        # A timeout, so a recipe that walks past the hold fails rather than hangs.
        return subprocess.run(argv, env=self.base | (env or {}), timeout=60, **self.quiet)

    def hold(self, *args: str) -> subprocess.CompletedProcess:
        return self.run(["bash", "scripts/harness/hold.sh", *args])

    def recipes(self, *runs: tuple[str, dict]) -> list[subprocess.CompletedProcess]:
        """Recipes run side by side: each run here reads the hold and the lock, none writes."""
        with ThreadPoolExecutor() as pool:
            return list(pool.map(lambda r: self.run(["bash", f"../recipes/{r[0]}"], r[1]), runs))

    def lines(self, prefix: str) -> list[str]:
        text = self.log.read_text() if self.log.exists() else ""
        return [ln for ln in text.splitlines() if ln.startswith(prefix)]

    def uv(self) -> list[tuple[str, str, str]]:
        """Each uv call as (command, the lock's pid then, ARK_LOCK_HELD)."""
        return [re.fullmatch(UV, ln).groups() for ln in self.lines("uv ")]

    def launchd(self) -> list[str]:
        verbs = ("disable", "enable", "bootout", "bootstrap")
        return [ln for ln in self.lines("launchctl ") if ln.split()[1] in verbs]

    def files(self) -> dict[str, str]:
        """Every file here, on the VPS, in launchd and on GitHub, its stamps as STAMP."""
        paths = [p for root in (self.state, self.shim) for p in root.rglob("*") if p.is_file()]
        stamp = re.compile(r"\d{4}-\d\d-\d\dT[\d:]{8}Z")
        return {p.relative_to(self.tmp).as_posix(): stamp.sub(STAMP, p.read_text()) for p in paths}

    def write(self, files: dict[str, str]) -> None:
        for rel, text in files.items():
            (self.tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.tmp / rel).write_text(text)
        if "shim/launchd/disabled/com.ark.sync" in files:
            (self.shim / "launchd/loaded/com.ark.sync").unlink()

    def take(self, pid: str) -> None:
        self.lock.mkdir()
        (self.lock / "pid").write_text(pid + "\n")


@pytest.fixture(scope="module")
def shared(tmp_path_factory) -> Box:
    return Box(tmp_path_factory.mktemp("hold"))


@pytest.fixture
def box(shared) -> Box:
    shared.reset()
    return shared


def test_on_disables_before_bootout_writes_the_flag_here_and_on_the_vps_and_status_reads_it(box):
    out = box.hold("on")
    assert out.returncode == 0, out.stdout + out.stderr
    assert box.files() == HELD
    calls = [" ".join(call.split()[:2]) for call in box.launchd()]
    assert calls.index("launchctl disable") < calls.index("launchctl bootout")
    assert box.lines("ssh -o ConnectTimeout=15 -o BatchMode=yes vps.test ")
    for wf in WORKFLOWS:
        assert box.lines(f"gh workflow disable {wf} --repo i-staykov/ark-fleet"), wf
    status = box.hold("status")
    assert (status.returncode, status.stdout.splitlines()) == (0, [f"HELD      {n}" for n in NAMES])
    # Status reads the machine, not the file, and names what the file lists but it does not know.
    (box.shim / "launchd/disabled/com.ark.sync").rename(box.shim / "launchd/loaded/com.ark.sync")
    (box.shim / "vps/ark/state/pause-platform").unlink()
    (box.shim / "workflows/leg.yaml").write_text("active\n")
    with (box.state / "hold").open("a") as hold:
        hold.write("com.ark.cycle\n")
    status = box.hold("status")
    assert status.returncode == 1
    assert status.stdout.splitlines() == [
        "NOT HELD  com.ark.sync: not disabled, loaded",
        "NOT HELD  pause-platform: no flag on the VPS",
        "NOT HELD  leg.yaml: active",
        "HELD      read.yaml",
        "HELD      improver.yaml",
        "NOT HELD  com.ark.cycle: not a hold name; 'just hold off com.ark.cycle' drops it",
    ]


def test_off_enables_before_bootstrap_lifts_one_name_or_all_and_drops_one_it_does_not_know(box):
    box.write(HELD | {"state/hold": HELD["state/hold"] + "pause\n", "state/pause": "human\n"})
    # The header's `human` is not a name, and a name neither known nor listed is refused.
    for name in ("com.ark.other", "human"):
        assert box.hold("off", name).returncode == 2, name
    # A listed name it does not know, as status says to run it, only drops its line.
    unknown = box.hold("off", "pause")
    assert unknown.returncode == 0 and "pause: not a hold name, dropped" in unknown.stdout
    assert box.launchd() == []
    one = box.hold("off", "com.ark.sync")
    assert one.returncode == 0, one.stdout
    assert box.launchd() == [
        f"launchctl enable gui/{UID}/com.ark.sync",
        f"launchctl bootstrap gui/{UID} {box.agents / 'com.ark.sync.plist'}",
    ]
    assert (box.state / "hold").read_text().splitlines()[2:] == NAMES[1:]
    out = box.hold("off")
    assert out.returncode == 0, out.stdout + out.stderr
    active = {f"shim/workflows/{wf}": "active\n" for wf in WORKFLOWS}
    loaded = {"shim/launchd/loaded/com.ark.sync": ""}
    assert box.files() == loaded | active | {"state/pause": "human\n"}


def test_the_sync_the_bank_and_the_install_obey_the_hold(box):
    """A recipe past the hold stops at the lock, held here by a live pid; a dry run's hand run
    passes and says so, any other bypass value is held, and nothing is lifted."""
    box.write({"state/hold": HELD["state/hold"]})
    box.take(ME)
    before = box.files()
    d, other = {"ARK_HOLD_BYPASS": "dry-run"}, {"ARK_HOLD_BYPASS": "yes"}
    runs = [("sync", {}), ("bank", {}), ("sync", other), ("bank", other), ("install", {})]
    *held, install, dry_sync, dry_bank = box.recipes(*runs, ("sync", d), ("bank", d))
    assert [(r.returncode, r.stdout) for r in held] == [(0, "held\n")] * 4
    assert install.returncode != 0 and "just hold off" in install.stderr
    for passed in (dry_sync, dry_bank):
        assert passed.stdout.splitlines()[0] == "hold bypassed: dry-run"
        assert REFUSED in passed.stdout
    assert box.files() == before and box.lines("") == []
    # With the job lifted and the rest still held, the sync and the bank pass and an
    # install, which would lift the rest, is still refused.
    box.write({"state/hold": FLAG + "".join(f"{n}\n" for n in NAMES[1:])})
    sync, bank, install = box.recipes(("sync", {}), ("bank", {}), ("install", {}))
    assert REFUSED in sync.stdout and REFUSED in bank.stdout
    assert install.returncode != 0 and "just hold off" in install.stderr


def test_a_live_lock_names_its_holder_and_a_dead_runs_lock_is_taken_over(box):
    def lock(*args: str) -> subprocess.CompletedProcess:
        return box.run(["bash", "scripts/harness/sync_lock.sh", *args])

    assert lock("take", ME).returncode == 0
    assert (lock("holder").returncode, lock("holder").stdout) == (0, f"{ME}\n")
    second = lock("take", "99999")
    assert second.returncode == 3 and f"pid {ME}" in second.stdout
    assert "Nothing was changed" in second.stdout
    assert lock("drop").returncode == 0 and not box.lock.exists()
    assert lock("holder").returncode == 1
    # drop runs in EXIT traps under `set -e`, where a failing drop fails the recipe.
    assert (lock("drop").returncode, lock("unlock").returncode) == (0, 2), "free drop, bad word"
    # A killed sync leaves the directory behind; holding the lane shut is worse.
    box.take("999999")
    taken = lock("take", ME)
    assert taken.returncode == 0 and "took over a lock left by pid 999999" in taken.stdout
    assert (box.lock / "pid").read_text() == f"{ME}\n"


def test_the_bank_takes_the_lock_unless_its_caller_holds_it(box):
    """The tick hands its lock to the bank as ARK_LOCK_HELD, trusted only while the lock
    agrees; any other bank, and a second sync, is refused and names the holder."""
    box.take(ME)
    runs = [("bank", {}), ("bank", {"ARK_LOCK_HELD": "1"}), ("sync", {})]
    *refused, called = box.recipes(*runs, ("bank", {"ARK_LOCK_HELD": ME}))
    for run in refused:
        assert run.returncode == 0 and REFUSED in run.stdout, run.stdout
    assert called.stdout.strip() == "bank: nothing arrived", called.stdout + called.stderr
    check = "run python scripts/harness/bank_trigger.py check"
    assert box.uv() == [(check, ME, ME)] and (box.lock / "pid").read_text() == f"{ME}\n"
    # The tick: its lock before any step, its bank under it, a failed slot check not fatal,
    # no store opened, the lock dropped.
    shutil.rmtree(box.lock)
    (box.shim / "arrived").touch()
    tick = box.run(["bash", "../recipes/sync"])
    assert tick.returncode == 0, tick.stdout + tick.stderr
    steps = box.uv()[1:]
    pid = steps[0][1]
    assert pid not in ("", ME) and {lock for _, lock, _ in steps} == {pid}, steps
    assert (check, pid, pid) in steps
    slots = "run python scripts/harness/discover_cycle.py --slots-only --fleet "
    assert [cmd for cmd, _, _ in steps if cmd.startswith(slots)], steps
    assert "uv run ark " not in (box.tmp / "recipes/sync").read_text()
    assert not box.lock.exists()
    # By hand, the bank takes the lock under its own pid and drops it when done.
    box.log.unlink()
    hand = box.run(["bash", "../recipes/bank"])
    assert hand.stdout.strip() == "bank: nothing arrived", hand.stdout + hand.stderr
    ((lock, held),) = {(lock, held) for _, lock, held in box.uv()}
    assert lock not in ("", ME) and held == "" and not box.lock.exists()


def test_the_launchd_template_names_a_script_that_exists_and_a_path_that_finds_the_tools():
    """A moved script exits 127 while `launchctl list` looks normal; so does a bare PATH, and
    its stderr log is where either shows. The template is the one the install renders."""
    job = re.search(r"^JOB=(\S+)$", recipe(ROOT, "schedule"), re.M)[1]
    text = (ROOT / f"scripts/harness/{job}.plist.template").read_text()
    assert str(ROOT) not in text and "ARK_ROOT" in text and "ARK_HOME" in text
    plist = plistlib.loads(text.replace("ARK_ROOT", str(ROOT)).replace("ARK_HOME", "/h").encode())
    assert plist["Label"] == job
    shell, script = plist["ProgramArguments"]
    assert shell == "/bin/bash" and Path(script).is_file(), script
    assert plist["WorkingDirectory"] == str(ROOT)
    assert plist["StandardErrorPath"].startswith(str(ROOT / "data/logs"))
    env = plist["EnvironmentVariables"]
    assert {"/opt/homebrew/bin", "/h/.local/bin"} <= set(env["PATH"].split(":"))
    assert env["HOME"] == "/h"


def test_an_unreachable_vps_and_gh_leave_the_local_hold_whole(box):
    (box.shim / "offline").touch()
    out = box.hold("on")
    assert out.returncode == 0, out.stdout + out.stderr
    # The VPS, and each workflow gh could not be asked about.
    assert out.stdout.count("unconfirmed") == 1 + len(WORKFLOWS)
    local = {k: v for k, v in HELD.items() if k.startswith(("state/", "shim/launchd/"))}
    assert box.files() == local | {"shim/offline": ""}
    status = box.hold("status")
    assert status.returncode == 1
    assert "NOT HELD  pause-platform: the VPS did not answer" in status.stdout.splitlines()
    assert "HELD      com.ark.sync" in status.stdout.splitlines()
    # With no plist, as after `just schedule remove`, the lift only enables the job.
    (box.agents / "com.ark.sync.plist").unlink()
    lift = box.hold("off", "com.ark.sync")
    assert "com.ark.sync: enabled, no plist to load" in lift.stdout
    assert box.launchd()[-1:] == [f"launchctl enable gui/{UID}/com.ark.sync"]
