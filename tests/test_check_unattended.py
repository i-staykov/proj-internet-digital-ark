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

ROOT = Path(__file__).resolve().parents[1]
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=live"]

JUST_SHIM = r"""
import re, subprocess, sys
recipe, *args = sys.argv[1:]
lines = open("justfile").read().splitlines()
start = next(i for i, ln in enumerate(lines) if re.match(rf"{recipe}( |:)", ln))
params = re.findall(r'(\w+)="([^"]*)"', lines[start])
values = {k: (args[n] if n < len(args) else v) for n, (k, v) in enumerate(params)}
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
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=ROOT,
        env=clean,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    for rel in files:
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
    stub(bin_dir, "gh", 'echo "gh $*" >> "$ARK_TEST_CALLS"; exit "${ARK_TEST_GH_RC:-0}"')
    for name in ("ssh", "rsync", "curl", "wget"):
        stub(bin_dir, name, f'echo "{name} $*" >> "$ARK_TEST_CALLS"; exit 1')
    for name in ("systemd-run", "pkill", "pgrep"):
        stub(bin_dir, name, "exit 0")
    stub(bin_dir, "systemctl", 'case "$*" in *is-enabled*) echo enabled ;; *) echo active ;; esac')
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
