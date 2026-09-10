"""The one lock a sync holds, whoever started it.

The failure it prevents is not hypothetical: on 2026-09-09 a terminal recovering two waves
and the launchd job at :05 were in the store together, one lost `ark export` to a lock
conflict and the journal ACK was skipped. The wrapper had a lock; the recipe did not; so the
lock protected the hourly run from itself and from nothing else.

So the tests are about the two ways that goes wrong: a second sync must not get in, and a
lock left behind by a run that was killed must not hold the lane shut for ever.
"""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/harness/sync_lock.sh"
RECIPE = (ROOT / "justfile").read_text()
WRAPPER = (ROOT / "scripts/harness/scheduled_sync.sh").read_text()


def run(*args: str, lock: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "ARK_SYNC_LOCK": str(lock)},
    )


def test_a_free_lock_is_taken(tmp_path):
    lock = tmp_path / "sync.lock"
    assert run("take", str(os.getpid()), lock=lock).returncode == 0
    assert (lock / "pid").read_text().strip() == str(os.getpid())


def test_a_second_sync_is_refused_and_says_who_has_it(tmp_path):
    lock = tmp_path / "sync.lock"
    run("take", str(os.getpid()), lock=lock)
    second = run("take", "99999", lock=lock)
    assert second.returncode == 3
    assert f"pid {os.getpid()}" in second.stdout
    assert "Nothing was changed" in second.stdout


def test_a_lock_left_by_a_dead_run_is_taken_over(tmp_path):
    # A killed sync leaves the directory behind. Holding the lane shut until a human notices
    # is worse than the race the lock exists to stop.
    lock = tmp_path / "sync.lock"
    lock.mkdir()
    (lock / "pid").write_text("999999\n")
    taken = run("take", str(os.getpid()), lock=lock)
    assert taken.returncode == 0
    assert "took over a lock" in taken.stdout
    assert (lock / "pid").read_text().strip() == str(os.getpid())


def test_drop_frees_it_and_is_idempotent(tmp_path):
    lock = tmp_path / "sync.lock"
    run("take", str(os.getpid()), lock=lock)
    assert run("drop", lock=lock).returncode == 0
    assert not lock.exists()
    assert run("drop", lock=lock).returncode == 0
    assert run("take", str(os.getpid()), lock=lock).returncode == 0


def test_holder_answers_who_has_it(tmp_path):
    lock = tmp_path / "sync.lock"
    assert run("holder", lock=lock).returncode == 1
    run("take", str(os.getpid()), lock=lock)
    held = run("holder", lock=lock)
    assert held.returncode == 0 and held.stdout.strip() == str(os.getpid())


def test_an_unknown_word_is_refused(tmp_path):
    assert run("unlock", lock=tmp_path / "sync.lock").returncode == 2


def test_the_recipe_takes_the_lock_before_it_touches_anything():
    body = RECIPE[RECIPE.index("\nsync fleet=") :]
    take = body.index("sync_lock.sh take")
    for step in ("bank_hygiene.py preflight", "gh run list", "ark export"):
        assert take < body.index(step), step
    assert "sync_lock.sh drop" in body[: body.index("bank_hygiene.py preflight")]


def test_the_wrapper_holds_no_second_lock():
    # Its own lock protected the hourly run from itself and from nothing else.
    assert "sync_lock.sh" in WRAPPER or "LOCK=" not in WRAPPER
    assert ".scheduled_sync.lock" not in WRAPPER
