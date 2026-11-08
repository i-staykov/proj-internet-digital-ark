"""`hold.sh`: `holds`, which `just sync` and `just bank` ask before they run, 0 while the hold file
lists the name, or with no name exists; the label's hold, which leaves the timer enabled; the lift,
which runs the forced bank; and the bank host, ssh under ARK_VM, this machine without it."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def hold(tmp_path):
    """A copy of the script (no local.env read), the bank host and gh stubbed, each run's calls
    recorded as `run.calls()`, one line per call."""
    script = tmp_path / "scripts/harness/hold.sh"
    script.parent.mkdir(parents=True)
    shutil.copy(ROOT / "scripts/harness/hold.sh", script)
    binp, calls = tmp_path / "bin", tmp_path / "calls"
    binp.mkdir()
    stubs = {
        "ssh": "echo done",
        "systemctl": 'case "$*" in *is-enabled*) echo enabled ;; esac',
        "systemd-run": "",
        "gh": 'case "$*" in *workflows/*) echo active ;; esac',
    }
    for name, body in stubs.items():
        f = binp / name
        f.write_text(f'#!/usr/bin/env bash\necho "{name} $*" >> "{calls}"\n{body}\n')
        f.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k not in ("ARK_VM", "ARK_HOSTS")}
    env |= {"ARK_STATE_DIR": str(tmp_path), "PATH": f"{binp}:{env['PATH']}"}

    def run(*args: str, **more: str) -> subprocess.CompletedProcess:
        calls.unlink(missing_ok=True)
        cmd = ["bash", script, *args]
        return subprocess.run(cmd, env=env | more, capture_output=True, text=True)

    run.calls = lambda: calls.read_text().splitlines() if calls.exists() else []
    return run


def test_holds_is_true_only_while_the_hold_file_holds(tmp_path, hold):
    def holds(*name: str) -> int:
        return hold("holds", *name).returncode

    assert (holds(), holds("ark-sync.timer")) == (1, 1)
    (tmp_path / "hold").write_text("human\n2026-01-01T00:00:00Z\nark-sync.timer\n")
    assert (holds(), holds("ark-sync.timer"), holds("pause-platform")) == (0, 0, 1)


def test_the_label_holds_with_the_timer_enabled_and_its_lift_forces_the_bank(tmp_path, hold):
    on = hold("on", "label")
    assert (tmp_path / "hold").read_text().startswith("label\n")
    assert (tmp_path / "pause-platform").exists() and "left enabled" in on.stdout
    assert not any("disable --now ark-sync.timer" in c for c in hold.calls())
    assert "HELD      ark-sync.timer" in hold("status").stdout
    off = hold("off", "label")
    assert not (tmp_path / "hold").exists() and not (tmp_path / "pause-platform").exists()
    assert "bank: forced" in off.stdout
    assert "systemctl --user enable --now ark-sync.timer" in hold.calls()
    assert any(c.startswith("systemd-run --user --unit ark-bank-force") for c in hold.calls())


def test_off_label_leaves_a_hand_hold(tmp_path, hold):
    hold("on")
    assert (tmp_path / "hold").read_text().startswith("human\n")
    assert "systemctl --user disable --now ark-sync.timer" in hold.calls()
    assert "not the label's" in hold("off", "label").stdout and (tmp_path / "hold").exists()


def test_the_bank_host_is_ssh_under_ark_vm_and_this_machine_without(hold):
    hold("on", ARK_VM="bank")
    want = "BatchMode=yes bank systemctl --user disable --now ark-sync.timer"
    assert any(c.startswith("ssh ") and want in c for c in hold.calls())
    hold("off", ARK_VM="bank")
    calls = hold.calls()
    assert {c.split()[0] for c in calls} == {"ssh", "gh"}
    assert any(c.startswith("ssh ") and "ark-bank-force" in c for c in calls)
    hold("on")
    hold("off")
    calls = hold.calls()
    assert {c.split()[0] for c in calls} == {"systemctl", "systemd-run", "gh"}
