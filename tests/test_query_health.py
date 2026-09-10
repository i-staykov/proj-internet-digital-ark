"""The failure-state ledger reads every lane, times its rows and says one thing about silence."""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/harness"))

import query_health as qh  # noqa: E402

TIMED = (
    "21:22:19 | INFO    | cdx: {'queried': 600, 'with_capture': 200, 'no_capture': 380, "
    "'failed_0': 20, 'throttles': 4, 'final_delay_ms': 150, 'years_found': 300}"
    " -> data/raw/cdx/one.jsonl.gz"
)
BARE = (
    "cdx: {'queried': 600, 'with_capture': 200, 'no_capture': 380, "
    "'failed_0': 20, 'throttles': 4, 'final_delay_ms': 150, 'years_found': 300}"
)
DEAD = "cdx: {'queried': 600, 'with_capture': 0, 'no_capture': 0, 'failed_0': 600}"


def write(tmp_path: Path, name: str, lines: list[str], age_hours: float = 0.0) -> Path:
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    when = (datetime.now(UTC) - timedelta(hours=age_hours)).timestamp()
    os.utime(path, (when, when))
    return path


def test_a_batch_logged_twice_is_one_batch(tmp_path: Path) -> None:
    """The collector prints each batch through the logger and again bare.

    Counting both doubled every figure; anchoring on the end of the line, which is what the
    first version did, kept the count right and lost the clock. Both are read, the duplicate
    is dropped, and the surviving row carries the time.
    """
    rows = qh.batches(write(tmp_path, "cdx_pool.log", [TIMED, BARE]))
    assert len(rows) == 1
    assert rows[0]["clock"] == "21:22:19"
    assert rows[0]["lane"] == "cdx_pool"


def test_two_identical_real_batches_both_survive(tmp_path: Path) -> None:
    """A stalled lane emits identical batches, and collapsing them would hide the DEAD alarm."""
    rows = qh.batches(write(tmp_path, "cdx_pool.log", [DEAD, DEAD, DEAD]))
    assert len(rows) == 3
    assert "DEAD" in " ".join(qh.verdicts([qh.health(row) for row in rows]))


def test_every_lane_is_read(tmp_path: Path) -> None:
    """cdx_pool.log alone left the lanes that were still running unwatched."""
    write(tmp_path, "cdx_pool.log", [TIMED])
    write(tmp_path, "cdx_vedge.log", [TIMED])
    write(tmp_path, "sweep_a.log", [TIMED])
    found = qh.logs(tmp_path)
    assert [path.stem for path in found] == ["cdx_pool", "cdx_vedge"]


def test_silence_is_one_verdict_about_the_freshest_lane(tmp_path: Path) -> None:
    """Fifteen retired lanes each announcing their own silence is a surface nobody reads."""
    write(tmp_path, "cdx_pool.log", [TIMED], age_hours=900)
    write(tmp_path, "cdx_vedge.log", [TIMED], age_hours=30)
    quiet = {path.stem: qh.silence(path) for path in qh.logs(tmp_path)}
    assert qh.freshest(quiet)[0] == "cdx_vedge"

    said = qh.verdicts([qh.health(TIMED_ROW)], quiet)
    silent = [line for line in said if line.startswith("SILENT")]
    assert len(silent) == 1
    assert "cdx_vedge" in silent[0]


def test_a_lane_writing_now_is_not_silent(tmp_path: Path) -> None:
    write(tmp_path, "cdx_vedge.log", [TIMED])
    quiet = {path.stem: qh.silence(path) for path in qh.logs(tmp_path)}
    said = qh.verdicts([qh.health(TIMED_ROW)], quiet)
    assert not [line for line in said if line.startswith("SILENT")]


TIMED_ROW = {
    "queried": 600,
    "with_capture": 200,
    "no_capture": 380,
    "failed_0": 20,
    "throttles": 4,
    "final_delay_ms": 150,
    "years_found": 300,
    "lane": "cdx_vedge",
    "clock": "21:22:19",
}
