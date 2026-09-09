"""The collector lane's three commands, and the pause that has to outlive a reboot.

`just collectors pause` is the one instruction given to a laptop about to be shut, so the
properties worth a test are the ones that fail silently otherwise: the flag lands where the
sweep reads it, it says a human wrote it so the sweep loop's 9,000 second heartbeat expiry
leaves it alone, and resume removes exactly that file and nothing else.

The marker word is shared between two scripts in two languages of shell, which is how a
rename would quietly turn a human pause back into an expiring one. Both are asked here.
"""

import plistlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTORS = ROOT / "scripts" / "harness" / "collectors.sh"
WRAPPER = ROOT / "scripts" / "harness" / "scheduled_collectors.sh"
SWEEP_LOOP = ROOT / "scripts" / "engines" / "platform_sweep_loop.sh"
PLIST = ROOT / "scripts" / "harness" / "com.ark.collectors.plist.template"


def run(*args, state: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(COLLECTORS), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": str(state.parent),
            "ARK_STATE_DIR": str(state),
            "ARK_NO_REMOTE": "1",
        },
    )


def test_pause_writes_the_flag_the_sweep_reads(tmp_path):
    state = tmp_path / "state"
    assert run("pause", state=state).returncode == 0
    flag = state / "pause"
    assert flag.is_file()
    assert flag.read_text().splitlines()[0] == "human"


def test_resume_removes_the_flag_and_is_idempotent(tmp_path):
    state = tmp_path / "state"
    run("pause", state=state)
    assert run("resume", state=state).returncode == 0
    assert not (state / "pause").exists()
    assert run("resume", state=state).returncode == 0


def test_status_reports_both_states(tmp_path):
    state = tmp_path / "state"
    running = run("status", state=state)
    assert running.returncode == 0
    assert "PAUSED" not in running.stdout
    run("pause", state=state)
    paused = run("status", state=state)
    assert "PAUSED" in paused.stdout


def test_status_prints_the_four_things_asked_for(tmp_path):
    out = run("status", state=tmp_path / "state").stdout
    for label in ("state:", "clients:", "parent:", "journal:"):
        assert label in out, label


def test_an_unknown_word_is_refused(tmp_path):
    assert run("start", state=tmp_path / "state").returncode == 2


def test_the_human_marker_is_the_same_word_in_both_scripts():
    assert 'FLAG_MARK="human"' in COLLECTORS.read_text()
    assert '= "human" ]' in SWEEP_LOOP.read_text()


def test_the_sweep_loop_asks_both_stats_flavours():
    # `stat -c` is GNU only, and on the laptop its failure made every flag read as new.
    text = SWEEP_LOOP.read_text()
    assert "stat -c %Y" in text and "stat -f %m" in text


def test_silence_from_the_other_machine_is_not_counted_as_zero():
    # It holds its two clients whether or not the link is up, so a failed ssh that read as
    # "the channel is free" would start both laptop sweeps beside them (C-77).
    text = COLLECTORS.read_text()
    assert "there=1" in text
    assert "there=0" not in text


def test_the_yield_monitor_does_not_tick_while_paused():
    # The child idles on the flag between pages; a monitor whose clock ran on regardless
    # parked a good parent for being silent during the pause.
    text = SWEEP_LOOP.read_text()
    gate = text.index('[ -e "$PAUSE_FLAG" ] && continue')
    tick = text.index("waited=$(( waited + 10 ))")
    assert gate < tick, "the pause gate must come before the clock advances"


def test_this_lane_does_not_glob_for_a_part_file():
    # `cdx_suffix_sweep.py` opens its journal under its final name and flushes every page,
    # so every `.part` glob in this lane matched nothing, here and on the other machine.
    assert "jsonl.gz.part" not in COLLECTORS.read_text()


def test_the_launchd_job_caffeinates_and_comes_back():
    plist = plistlib.loads(
        PLIST.read_text().replace("ARK_ROOT", str(ROOT)).replace("ARK_HOME", "/var/empty").encode()
    )
    assert plist["KeepAlive"] is True
    assert plist["RunAtLoad"] is True
    assert plist["ThrottleInterval"] >= 60
    assert "caffeinate -s" in WRAPPER.read_text()
