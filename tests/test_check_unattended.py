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
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=live"]

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
    walkers = subprocess.run(
        ["git", "rev-parse", "HEAD:scripts/engines/cdx_walk_jobs.py"]
        + ["HEAD:scripts/engines/cdx_extended_walk.py"],
        cwd=repo,
        env=clean,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    (repo / "data/logs").mkdir(parents=True, exist_ok=True)
    (repo / "data/logs/.walk_code").write_text(walkers)
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
    for name in ("pkill", "pgrep"):
        stub(bin_dir, name, "exit 0")
    stub(bin_dir, "systemd-run", 'echo "systemd-run $*" >> "$ARK_TEST_CALLS"')
    stub(
        bin_dir,
        "systemctl",
        'echo "systemctl $*" >> "$ARK_TEST_CALLS";'
        ' case "$*" in *is-enabled*) echo enabled ;; *) echo active ;; esac',
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
    }
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


def test_a_finished_reader_reads_finished_and_is_not_started(clone, tmp_path, monkeypatch):
    check = script("harness/check_unattended.py")
    monkeypatch.setattr(check, "ROOT", tmp_path)
    monkeypatch.setattr(check, "STATE", tmp_path / "state")
    (tmp_path / "local.env").write_text("ARK_HOSTS=local:2\n")
    monkeypatch.setattr(check, "run", lambda *cmd: (0, "inactive"))
    left = {"ark-eot": 0, "ark-har": 3, "ark-clueweb": 0, "ark-header": 0}
    monkeypatch.setattr(check, "left", left.get)
    assert check.readers() == [
        ("ark-eot", True, "finished"),
        ("ark-har", False, "inactive, 3 parts left"),
        ("ark-clueweb", True, "finished"),
        ("ark-header", True, "finished"),
    ]
    # the tick: eot and har with every part read, clueweb with its lists left, the header lane
    # with its list and every top screened, one under the floor and one run out
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
    assert rc == 0 and [ln.split()[3] for ln in started] == ["ark-clueweb"], (last, started)
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
    for key, value in (("user.name", "t"), ("user.email", "t@t")):
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
