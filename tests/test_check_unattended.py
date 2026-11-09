"""The tick end to end in a temp clone: its exit is the sync's, else `just check unattended`'s.

gh, ssh, the network, systemd, cron and uv are stubbed; the tick, the `sync` recipe's opening, the
hold, the lock and the check run as they are. Without a `just` binary (CI) a shim runs the named
recipe's shebang body from the justfile.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import script

ROOT = Path(__file__).resolve().parents[1]
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@invalid", "-c", "init.defaultBranch=live"]

JUST_SHIM = r"""
import re, subprocess, sys
recipe, *args = sys.argv[1:]
lines = open("justfile").read().splitlines()
start = next(i for i, ln in enumerate(lines) if re.match(rf"{recipe}( |:)", ln))
params = re.findall(r'(\w+)="([^"]*)"', lines[start])
values = {k: (args[n] if n < len(args) else v) for n, (k, v) in enumerate(params)}
star = re.search(r"\*(\w+)", lines[start])
if star:
    values[star[1]] = " ".join(args[len(params) :])
body = []
for ln in lines[start + 1 :]:
    if ln and not ln.startswith("    "):
        break
    body.append(re.sub(r"\{\{(\w+)\}\}", lambda m: values[m[1]], ln[4:]))
sys.exit(subprocess.run(["bash", "-c", "\n".join(body)]).returncode)
"""


def stub(bin_dir: Path, name: str, body: str) -> None:
    f = bin_dir / name
    f.write_text(f"#!/usr/bin/env bash\n{body}\n")
    f.chmod(0o755)


@pytest.fixture
def clone(tmp_path):
    """A copy of the working tree as a fresh repo on `live`, its origin a local bare repo."""
    repo = tmp_path.resolve() / "ark"
    # A git hook exports GIT_DIR, a worktree's gitdir: `git init` under it re-inits the shared
    # clone as bare. No git variable reaches the temp clone.
    clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    files = subprocess.run(
        ["git", "ls-files", "-z", "-co", "--exclude-standard"],
        cwd=ROOT,
        env=clean,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")
    for rel in filter(None, files):
        if (ROOT / rel).is_file():
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, repo / rel)
    subprocess.run([*GIT, "init", "-q"], cwd=repo, env=clean, check=True)
    subprocess.run([*GIT, "add", "-A"], cwd=repo, env=clean, check=True)
    subprocess.run([*GIT, "commit", "-qm", "t"], cwd=repo, env=clean, check=True)
    subprocess.run(
        [*GIT, "clone", "-q", "--bare", str(repo), str(tmp_path / "origin.git")],
        env=clean,
        check=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", str(tmp_path / "origin.git")], cwd=repo, env=clean
    )
    subprocess.run(["git", "fetch", "-q", "origin"], cwd=repo, env=clean, check=True)
    code = subprocess.run(
        [sys.executable, "scripts/engines/cdx_walk_jobs.py", "code"],
        cwd=repo,
        env=clean,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    (repo / "data/logs").mkdir(parents=True, exist_ok=True)
    (repo / "data/logs/.walk_code").write_text(code)
    (repo / "data/logs/.sync.lock").mkdir()
    (repo / "data/logs/.sync.lock/pid").write_text(f"{os.getpid()}\n")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    cron = f"cd {repo} && /usr/bin/python3 scripts/engines/cdx_extended_walk.py # ark-walk"
    # gh answers the hold label's listing with ARK_TEST_HOLD_LABEL and names every workflow active
    stub(
        bin_dir,
        "gh",
        'echo "gh $*" >> "$ARK_TEST_CALLS"; case "$*" in'
        ' *"--label hold "*) echo "${ARK_TEST_HOLD_LABEL:-}" ;; *workflows/*) echo active ;;'
        ' esac; exit "${ARK_TEST_GH_RC:-0}"',
    )
    for name in ("ssh", "rsync", "curl", "wget"):
        stub(bin_dir, name, f'echo "{name} $*" >> "$ARK_TEST_CALLS"; exit 1')
    stub(bin_dir, "pkill", "exit 0")
    stub(bin_dir, "pgrep", 'case "$*" in *Runner.Worker*|*dpkg*) exit 1 ;; esac')
    stub(bin_dir, "loginctl", "exit 0")
    for name in ("systemd-run", "sudo"):
        stub(bin_dir, name, f'echo "{name} $*" >> "$ARK_TEST_CALLS"')
    stub(
        bin_dir,
        "systemctl",
        'echo "systemctl $*" >> "$ARK_TEST_CALLS";'
        ' case "$*" in *is-enabled*) echo enabled ;; *bank-force*) exit 3 ;;'
        ' *apt-daily*) echo inactive; echo "${ARK_TEST_APT:-inactive}"; exit 3 ;;'
        " *) echo active ;; esac",
    )
    stub(bin_dir, "crontab", f"for i in 1 2 3 4 5 6; do echo '{cron}'; done")
    stub(
        bin_dir,
        "uv",
        f'[ "$1" = run ] && shift; [ "$1" = python ] && shift; exec {sys.executable} "$@"',
    )
    if not shutil.which("just"):
        (tmp_path / "just.py").write_text(JUST_SHIM)
        stub(bin_dir, "just", f'exec {sys.executable} {tmp_path}/just.py "$@"')
    env = {
        **clean,
        "PATH": f"{bin_dir}:{clean['PATH']}",
        "HOME": str(tmp_path),
        "ARK_STATE_DIR": str(tmp_path / "state"),
        "ARK_FREE_SPACE_GIB": "0.001",
        "ARK_WRITE_BUDGET_GIB": "0.001",
        "ARK_TEST_CALLS": str(tmp_path / "calls"),
        "ARK_REBOOT_FLAG": str(tmp_path / "reboot-required"),
        "ARK_UPTIME": str(tmp_path / "uptime"),
    }
    (tmp_path / "uptime").write_text("864000.00 1.00\n")  # up ten days
    for key in ("ARK_HOSTS", "ARK_SYNC_LOCK", "ARK_LOCK_HELD", "ARK_HOLD_BYPASS"):
        env.pop(key, None)
    return repo, env


def tick(repo: Path, env: dict) -> tuple[int, str]:
    p = subprocess.run(
        ["bash", str(repo / "scripts/harness/scheduled_sync.sh")],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    log = (repo / "data/logs/scheduled_sync.log").read_text().splitlines()
    return p.returncode, log[-1]


def test_green_tick_exits_zero(clone):
    repo, env = clone
    rc, last = tick(repo, env)
    assert (rc, last.split()[2:]) == (0, ["sync=0", "check=0"]), last
    assert "unattended: ok" in (repo / "data/logs/scheduled_sync.log").read_text()


def test_dead_login_fails_the_check_and_the_tick(clone):
    repo, env = clone
    rc, last = tick(repo, {**env, "ARK_TEST_GH_RC": "1"})
    assert (rc, last.split()[2:]) == (1, ["sync=0", "check=1"]), last
    assert "FAIL login" in (repo / "data/logs/scheduled_sync.log").read_text()


def test_a_failed_sync_is_the_ticks_status(clone):
    repo, env = clone
    (repo / "data/logs/.sync.lock/pid").unlink()
    (repo / "data/logs/.sync.lock").rmdir()
    subprocess.run(["git", "checkout", "-q", "-b", "main"], cwd=repo, env=env, check=True)
    rc, last = tick(repo, env)
    assert rc != 0 and last.split()[2:] == [f"sync={rc}", "check=0"], last


def test_the_hold_label_holds_through_the_tick_and_its_removal_lifts(clone):
    repo, env = clone
    state, calls = Path(env["ARK_STATE_DIR"]), Path(env["ARK_TEST_CALLS"])
    rc, last = tick(repo, {**env, "ARK_TEST_HOLD_LABEL": "7"})
    assert (rc, last.split()[2:]) == (0, ["sync=0", "check=0"]), last
    assert (state / "hold").read_text().startswith("label\n") and (
        state / "pause-platform"
    ).exists()
    assert "disable --now ark-sync.timer" not in calls.read_text()
    assert "\nheld\n" in (repo / "data/logs/scheduled_sync.log").read_text()  # this sync too
    calls.unlink()
    rc, last = tick(repo, env)
    assert (rc, last.split()[2:]) == (0, ["sync=0", "check=0"]), last
    assert "bank: forced" in (repo / "data/logs/scheduled_sync.log").read_text()
    assert not (state / "hold").exists() and not (state / "pause-platform").exists()
    assert "systemd-run --user --unit ark-bank-force" in calls.read_text()


@pytest.mark.parametrize("busy", ["", "a sync", "an apt run", "up under an hour"])
def test_a_pending_reboot_waits_only_on_what_it_would_cut(clone, tmp_path, busy):
    """A tick that banked (its `just sync` stamps the bank) reboots unless the fixture's lock is
    this boot's live sync, apt runs or the boot is under an hour old; that lock from an earlier
    boot is stale."""
    repo, env = clone
    Path(env["ARK_REBOOT_FLAG"]).write_text("*** System restart required ***\n")
    if busy != "a sync":
        (repo / "data/logs/.sync.lock/boot").write_text("an earlier boot")
    if busy == "up under an hour":
        Path(env["ARK_UPTIME"]).write_text("600.00 1.00\n")
    (tmp_path / "bin2").mkdir()
    just = shutil.which("just", path=env["PATH"])
    banks = '[ "$1" = sync ] && { touch data/logs/bank_stamp.json; echo bank: banked; exit 0; }'
    stub(tmp_path / "bin2", "just", f'{banks}; exec {just} "$@"')
    env = {**env, "PATH": f"{tmp_path / 'bin2'}:{env['PATH']}"}
    tick(repo, {**env, "ARK_TEST_APT": "activating"} if busy == "an apt run" else env)
    log = (repo / "data/logs/scheduled_sync.log").read_text()
    assert "\tbanked\t" in (repo / "data/logs/ticks.tsv").read_text(), log
    assert (f"reboot pending, not now: {busy}\n" in log) == bool(busy), log
    assert ("sudo -n /usr/sbin/reboot" in Path(env["ARK_TEST_CALLS"]).read_text()) == (not busy)


def test_a_finished_reader_reads_finished_and_is_not_started(clone, tmp_path, monkeypatch):
    check = script("harness/check_unattended.py")
    monkeypatch.setattr(check, "ROOT", tmp_path)
    monkeypatch.setattr(check, "STATE", tmp_path / "state")
    (tmp_path / "local.env").write_text("ARK_HOSTS=local:2\n")
    monkeypatch.setattr(check, "run", lambda *cmd: (0, "inactive"))
    left = {"ark-eot": 0, "ark-har": 3, "ark-clueweb": 2, "ark-fineweb": 0, "ark-header": 5}
    monkeypatch.setattr(check, "left", left.get)
    stalls = {}
    monkeypatch.setattr(check, "stalled", lambda unit: stalls.get(unit, ""))
    # har stopped mid-item, clueweb new and not started yet, the header lane inside its back-off
    logs = tmp_path / "data/logs"
    logs.mkdir(parents=True)
    clueweb = tmp_path / "scripts/sources/crawl_lists/clueweb.py"
    clueweb.parent.mkdir(parents=True)
    clueweb.write_text("")
    (logs / "har.log").write_text("har httparchive_2010: read\n")
    (logs / "usenet_header.log").write_text("header: 429 in x, waits until 29991231T000000Z\n")
    assert check.readers() == [
        ("ark-eot", True, "finished"),
        ("ark-har", False, "inactive, 3 parts left"),
        ("ark-clueweb", True, "not started yet, 2 parts left"),
        ("ark-fineweb", True, "finished"),
        ("ark-header", True, "inactive, 5 parts left, waits until 29991231T000000Z"),
    ]
    (logs / "usenet_header.log").write_text("header: 429 in x, waits until 20001231T000000Z\n")
    (logs / "har.log").write_text("har: held\n")
    os.utime(clueweb, (0, 0))  # its code arrived long ago, and the tick never started it
    assert [ok for _u, ok, _w in check.readers()] == [True, True, False, True, False]
    stalls["ark-header"] = "stalled at a"  # a day without progress fails even an active unit
    monkeypatch.setattr(check, "run", lambda *cmd: (0, "active"))
    assert check.reader("ark-header") == (False, "active, 5 parts left, stalled at a")
    # the tick: eot and har with every part read, clueweb and fineweb with parts left, the header
    # lane with its list and every top screened, one under the floor and one run out
    repo, env = clone
    (repo / "local.env").write_text("ARK_HOSTS=local:2\n")
    eot = repo / "data/raw/extended/eot_cdxj"
    eot.mkdir(parents=True)
    for part in script("sources/eot/eot_cdxj.py").PARTS:
        (eot / f"eot_{part}.jsonl.gz").write_bytes(b"")
    har = repo / "data/raw/extended/httparchive_har"
    har.mkdir(parents=True)
    (har / ".har_items.json").write_text('[["httparchive_2010", 2010]]')
    (har / ".har_httparchive_2010.zips.json").write_text("{}")
    header = repo / "data/queue/usenet_header"
    header.mkdir(parents=True)
    (header / "seen.json").write_text("[]")
    (header / "tops.txt").write_text("cheap\nrich\n")
    screens = ("cheap", 30_000_000, 9, 1, 1, 1, 8.0), ("rich", 30_000_000, 9, 1, 1, 1, 90.0)
    (header / "screen.tsv").write_text("".join("\t".join(map(str, r)) + "\n" for r in screens))
    (header / "log.tsv").write_text("ran\trich\n")
    rc, last = tick(repo, env)
    started = [ln for ln in (tmp_path / "calls").read_text().splitlines() if "systemd-run" in ln]
    units = [ln.split()[3] for ln in started]
    assert rc == 0 and units == ["ark-clueweb", "ark-fineweb"], (last, started)
    log = (repo / "data/logs/scheduled_sync.log").read_text()
    assert "ok   ark-eot: finished" in log and "ok   ark-har: finished" in log, log
    assert "ok   ark-header: finished" in log, log


def diverge(repo: Path, env: dict, subject: str, clash: bool = False) -> str:
    """`live` moved by a PR that edits a register page, then this clone's own commit to that
    page on the old tip, on the PR's line when `clash`; lock freed. Returns HEAD."""
    page = repo / "docs/registers/questions.md"
    base = page.read_text()

    def commit(text: str, message: str) -> None:
        page.write_text(text)
        subprocess.run([*GIT, "commit", "-qam", message], cwd=repo, env=env, check=True)

    commit("theirs\n" + base, "a merged PR")
    subprocess.run([*GIT, "push", "-q", "origin", "HEAD:live"], cwd=repo, env=env, check=True)
    subprocess.run([*GIT, "reset", "-q", "--hard", "HEAD~1"], cwd=repo, env=env, check=True)
    commit(("ours\n" + base) if clash else (base + "ours\n"), subject)
    for key, value in (("user.name", "t"), ("user.email", "t@invalid")):
        subprocess.run(["git", "config", key, value], cwd=repo, env=env, check=True)
    (repo / "data/logs/.sync.lock/pid").unlink()
    (repo / "data/logs/.sync.lock").rmdir()
    return git_out(repo, env, "rev-parse", "HEAD")


def git_out(repo: Path, env: dict, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True, text=True)
    return done.stdout.strip()


def test_the_ticks_own_commit_rebases_onto_a_moved_live(clone):
    repo, env = clone
    diverge(repo, env, "Sync fleet findings round 9")
    (repo / "local.env").write_text("ARK_HOSTS=local:2\n")
    tick(repo, env)
    log = (repo / "data/logs/scheduled_sync.log").read_text()
    assert "rebased the tick's own commits onto origin/live" in log, log
    assert "\nbank: " in log, log  # the bank ran; the temp clone has no store for it to fill
    assert git_out(repo, env, "log", "--format=%s", "-2").splitlines() == [
        "Sync fleet findings round 9",
        "a merged PR",
    ]
    assert git_out(repo, env, "rev-list", "--merges", "HEAD") == ""


def test_a_conflicting_rebase_aborts_and_the_tick_names_the_divergence(clone):
    repo, env = clone
    head = diverge(repo, env, "Sync fleet findings round 9", clash=True)
    rc, last = tick(repo, env)
    assert rc == 2 and last.split()[2] == "sync=2", last
    assert git_out(repo, env, "rev-parse", "HEAD") == head
    assert not (repo / ".git/rebase-merge").exists()
    assert "the clone has diverged" in (repo / "data/logs/ticks.tsv").read_text()
    assert "rebase aborted" in (repo / "data/logs/scheduled_sync.log").read_text()


@pytest.mark.parametrize("dirty", [False, True])
def test_a_hand_commit_or_a_dirty_tree_still_refuses(clone, dirty):
    repo, env = clone
    head = diverge(repo, env, "a hand edit")
    if dirty:
        subprocess.run([*GIT, "reset", "-q", "--soft", "HEAD~1"], cwd=repo, env=env, check=True)
        head = git_out(repo, env, "rev-parse", "HEAD")
    rc, last = tick(repo, env)
    assert rc == 2 and last.split()[2] == "sync=2", last
    assert git_out(repo, env, "rev-parse", "HEAD") == head
    why = "the clone is dirty" if dirty else "Reconcile by hand; the bank never force-pushes"
    assert why in (repo / "data/logs/scheduled_sync.log").read_text()


def test_a_commit_signed_by_a_machine_is_never_pushed_and_alerts(clone):
    """The clone's own commit, signed `login@hostname` as git signs without an identity, rebases
    but refuses the tick before its bank pushes, with a vm-alert naming no address."""
    repo, env = clone
    machine = {**env, "GIT_AUTHOR_EMAIL": "ops" + "@box.cloud.example.org"}
    diverge(repo, machine, "Sync fleet findings round 9")
    rc, last = tick(repo, env)
    assert rc == 2 and last.split()[2] == "sync=2", last
    log = (repo / "data/logs/scheduled_sync.log").read_text()
    assert "outside the commit identity allowlist" in log and "alert opened: a commit" in log, log
    assert "box.cloud" not in log
    origin = ["--git-dir", str(repo.parent / "origin.git")]
    assert git_out(repo, env, *origin, "log", "-1", "--format=%s", "live") == "a merged PR"


def test_the_tick_pulls_only_under_the_lock(clone):
    repo, env = clone
    page = repo / "docs/registers/questions.md"
    page.write_text(page.read_text() + "\nmerged\n")
    subprocess.run([*GIT, "commit", "-qam", "a merged PR"], cwd=repo, env=env, check=True)
    subprocess.run([*GIT, "push", "-q", "origin", "HEAD:live"], cwd=repo, env=env, check=True)
    subprocess.run([*GIT, "reset", "-q", "--hard", "HEAD~1"], cwd=repo, env=env, check=True)
    head = git_out(repo, env, "rev-parse", "HEAD")
    tick(repo, env)  # the fixture's lock is held: the sync stops before its preflight
    assert git_out(repo, env, "rev-parse", "HEAD") == head
