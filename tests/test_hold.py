"""`just hold`: every laptop job, both pause flags and the fleet workflows off until lifted.

launchctl, gh and ssh are shims that act on files under tmp, so the order of every call and
what each leaves behind can be read back: disable before bootout, enable before bootstrap,
both flags here and on the VPS, and the refusals the hold file drives.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JOBS = ["com.ark.sync", "com.ark.collectors", "com.ark.cycle", "com.ark.digest"]
FLAGS = ["pause", "pause-platform"]
NAMES = [*JOBS, *FLAGS, "wave.yaml", "improver.yaml"]
PLISTS = ["com.ark.sync", "com.ark.collectors"]
JUST = shutil.which("just")
UID = os.getuid()

SHIMS = {
    "launchctl": r"""
S="$SHIM_STATE/launchd"; mkdir -p "$S/disabled" "$S/loaded"
case "$1" in
disable) touch "$S/disabled/${2##*/}" ;;
enable) rm -f "$S/disabled/${2##*/}" ;;
bootout) [ -e "$S/loaded/${2##*/}" ] || exit 3; rm -f "$S/loaded/${2##*/}" ;;
bootstrap) l=$(basename "$3" .plist); [ -e "$S/disabled/$l" ] && exit 5; touch "$S/loaded/$l" ;;
print-disabled)
    echo "disabled services = {"
    for f in "$S"/disabled/*; do [ -e "$f" ] && printf '\t"%s" => disabled\n' "${f##*/}"; done
    echo "}" ;;
list)
    printf 'PID\tStatus\tLabel\n'
    for f in "$S"/loaded/*; do [ -e "$f" ] && printf -- '-\t0\t%s\n' "${f##*/}"; done ;;
esac
""",
    "gh": r"""
[ -e "$SHIM_STATE/offline" ] && exit 1
W="$SHIM_STATE/workflows"; mkdir -p "$W"
case "$1 $2" in
"api "*) cat "$W/${2##*/}" 2>/dev/null || echo active ;;
"workflow disable") echo disabled_manually > "$W/$3" ;;
"workflow enable") echo active > "$W/$3" ;;
esac
""",
    # The command runs as the VPS would run it: its own home, its own ARK_STATE_DIR.
    "ssh": r"""
[ -e "$SHIM_STATE/offline" ] && exit 255
for cmd; do :; done
env -u ARK_STATE_DIR HOME="$SHIM_STATE/vps" sh -c "$cmd"
""",
}


class Box:
    def __init__(self, tmp: Path):
        self.repo = tmp / "repo"
        self.state = tmp / "state"
        self.shim = tmp / "shim"
        self.vps_state = self.shim / "vps" / "ark" / "state"
        self.log = tmp / "calls.log"
        self.agents = tmp / "home" / "Library" / "LaunchAgents"
        harness = self.repo / "scripts" / "harness"
        harness.mkdir(parents=True)
        for name in ("hold.sh", "collectors.sh", "scheduled_sync.sh"):
            shutil.copy(ROOT / "scripts" / "harness" / name, harness / name)
        shutil.copy(ROOT / "justfile", self.repo / "justfile")
        # The sync and the bank stop at the lock, so reaching it is passing the hold.
        (harness / "sync_lock.sh").write_text('echo "reached the lock"; exit 3\n')
        self.agents.mkdir(parents=True)
        (self.shim / "launchd" / "loaded").mkdir(parents=True)
        for job in PLISTS:
            (self.agents / f"{job}.plist").write_text("<plist/>\n")
            (self.shim / "launchd" / "loaded" / job).touch()
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        for name, body in SHIMS.items():
            shim = bin_dir / name
            shim.write_text(f'#!/bin/bash\necho "{name} $*" >> "$SHIM_LOG"\n{body}')
            shim.chmod(0o755)
        path = [str(bin_dir), *([str(Path(JUST).parent)] if JUST else []), "/usr/bin", "/bin"]
        self.env = {
            "PATH": ":".join(path),
            "HOME": str(tmp / "home"),
            "ARK_STATE_DIR": str(self.state),
            "ARK_VPS": "vps.test",
            "SHIM_LOG": str(self.log),
            "SHIM_STATE": str(self.shim),
        }

    def run(self, *argv: str) -> subprocess.CompletedProcess:
        # A timeout, so a supervisor that walks past the hold fails rather than hangs.
        return subprocess.run(
            argv, cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=60
        )

    def hold(self, *args: str) -> subprocess.CompletedProcess:
        return self.run("bash", str(self.repo / "scripts/harness/hold.sh"), *args)

    def just(self, *args: str) -> subprocess.CompletedProcess:
        return self.run(JUST, "--justfile", str(self.repo / "justfile"), *args)

    def launchd_calls(self) -> list[str]:
        """The state-changing launchctl calls, in order."""
        verbs = ("disable", "enable", "bootout", "bootstrap")
        lines = self.log.read_text().splitlines() if self.log.exists() else []
        return [ln for ln in lines if ln.startswith("launchctl ") and ln.split()[1] in verbs]

    def hold_names(self) -> list[str]:
        return (self.state / "hold").read_text().splitlines()[2:]

    def workflow(self, name: str) -> str:
        path = self.shim / "workflows" / name
        return path.read_text().strip() if path.exists() else "active"


@pytest.fixture
def box(tmp_path) -> Box:
    return Box(tmp_path)


def test_on_disables_before_bootout_and_writes_both_flags_here_and_on_the_vps(box):
    out = box.hold("on")
    assert out.returncode == 0, out.stdout + out.stderr
    calls = box.launchd_calls()
    for job in JOBS:
        disable = calls.index(f"launchctl disable gui/{UID}/{job}")
        assert disable < calls.index(f"launchctl bootout gui/{UID}/{job}"), job
    for home in (box.state, box.vps_state):
        for flag in FLAGS:
            assert (home / flag).read_text().splitlines()[0] == "human", home / flag
    hold = (box.state / "hold").read_text().splitlines()
    assert hold[0] == "human" and hold[2:] == NAMES
    log = box.log.read_text()
    assert "ssh -o ConnectTimeout=15 -o BatchMode=yes vps.test " in log
    for wf in ("wave.yaml", "improver.yaml"):
        assert f"gh workflow disable {wf} --repo i-staykov/ark-fleet" in log
        assert box.workflow(wf) == "disabled_manually"
    status = box.hold("status")
    assert status.returncode == 0, status.stdout
    assert status.stdout.splitlines() == [f"HELD      {name}" for name in NAMES]
    # Status reads the machine, not the file.
    (box.shim / "launchd" / "disabled" / "com.ark.cycle").unlink()
    (box.shim / "launchd" / "loaded" / "com.ark.digest").touch()
    (box.vps_state / "pause-platform").unlink()
    (box.shim / "workflows" / "wave.yaml").write_text("active\n")
    status = box.hold("status")
    assert status.returncode == 1
    for line in (
        "NOT HELD  com.ark.cycle: not disabled",
        "NOT HELD  com.ark.digest: loaded",
        "NOT HELD  pause-platform: no flag on the VPS",
        "NOT HELD  wave.yaml: active",
        "HELD      improver.yaml",
    ):
        assert line in status.stdout.splitlines(), line


def test_off_one_job_lifts_only_that_job(box):
    box.hold("on")
    before = len(box.launchd_calls())
    assert box.hold("off", "com.ark.sync").returncode == 0
    assert box.launchd_calls()[before:] == [
        f"launchctl enable gui/{UID}/com.ark.sync",
        f"launchctl bootstrap gui/{UID} {box.agents / 'com.ark.sync.plist'}",
    ]
    assert box.hold_names() == [n for n in NAMES if n != "com.ark.sync"]
    assert box.hold("holds", "com.ark.sync").returncode == 1
    collectors = box.run("bash", str(box.repo / "scripts/harness/collectors.sh"), "run")
    assert (collectors.returncode, collectors.stdout.strip()) == (0, "held")


@pytest.mark.skipif(JUST is None, reason="just not on PATH")
def test_the_sync_the_bank_and_the_install_obey_the_hold(box):
    box.hold("on")
    before = len(box.launchd_calls())
    for recipe in ("sync", "bank"):
        done = box.just(recipe)
        assert (done.returncode, done.stdout.strip()) == (0, "held"), recipe
    install = box.just("schedule", "install")
    assert install.returncode != 0 and "just hold off" in install.stderr
    assert box.launchd_calls()[before:] == []
    box.hold("off", "com.ark.sync")
    before = len(box.launchd_calls())
    for recipe in ("sync", "bank"):
        assert "reached the lock" in box.just(recipe).stdout, recipe
    install = box.just("schedule", "install")
    assert install.returncode != 0 and "just hold off" in install.stderr
    assert box.launchd_calls()[before:] == []


def test_bare_off_enables_before_bootstrap_and_removes_everything(box):
    box.hold("on")
    before = len(box.launchd_calls())
    out = box.hold("off")
    assert out.returncode == 0, out.stdout + out.stderr
    calls = box.launchd_calls()[before:]
    for job in JOBS:
        enable = calls.index(f"launchctl enable gui/{UID}/{job}")
        bootstrap = f"launchctl bootstrap gui/{UID} {box.agents / f'{job}.plist'}"
        if job in PLISTS:
            assert enable < calls.index(bootstrap), job
        else:
            assert bootstrap not in calls, job
    assert not (box.state / "hold").exists()
    for home in (box.state, box.vps_state):
        assert not any((home / flag).exists() for flag in FLAGS), home
    assert box.workflow("wave.yaml") == box.workflow("improver.yaml") == "active"


def test_an_unreachable_vps_and_gh_leave_the_local_hold_whole(box):
    (box.shim / "offline").touch()
    out = box.hold("on")
    assert out.returncode == 0, out.stdout + out.stderr
    assert out.stdout.count("unconfirmed") == 3
    assert all((box.state / flag).is_file() for flag in FLAGS)
    assert not list((box.shim / "launchd" / "loaded").iterdir())
    status = box.hold("status")
    assert status.returncode == 1
    assert "NOT HELD  pause: the VPS did not answer" in status.stdout
    assert "HELD      com.ark.sync" in status.stdout
