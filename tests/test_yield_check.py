"""Collector yield: the question none of the other checks asked.

`check_collectors` asks whether a process is alive. The supervisor watches journal
growth. **A journal full of misses grows exactly as fast as a journal full of hits**,
so on 2026-08-11 a rebuilt queue sent the local engine 1,200 archive queries for zero
captures while every mechanical check reported clean.

These tests pin the two ways that failure shows up and, more importantly, the two ways
a naive version would cry wolf: a small sample, and a population that is simply harder
than another. The gap pool answers 96-97.5% and the candidate pool 36.9-90.6%, so a
single hardcoded floor would either miss a pool collapse or alarm on a healthy pool.
"""

import gzip
import json
from pathlib import Path

from ark.yield_check import MIN_SAMPLE, measure, measure_all


def _journal(directory: Path, name: str, answered: int, hits: int, failures: int = 0) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with gzip.open(directory / name, "wt", encoding="utf-8") as fh:
        for i in range(answered):
            years = [1998] if i < hits else []
            fh.write(
                json.dumps({"domain": f"d{i}-{name}.com", "status": 200, "years": years}) + "\n"
            )
        for i in range(failures):
            # A transport failure says nothing about whether a capture exists, so it
            # must not count as a miss and slander the population.
            fh.write(json.dumps({"domain": f"f{i}-{name}.com", "status": 0, "years": []}) + "\n")


def test_a_healthy_collector_is_not_flagged(tmp_path) -> None:
    _journal(tmp_path, "cdx_pool_20260801T000000Z.jsonl.gz", 600, 280)
    _journal(tmp_path, "cdx_pool_20260802T000000Z.jsonl.gz", 600, 300)
    reading = measure(tmp_path, "cdx_pool")
    assert not reading.collapsed
    assert reading.recent_rate is not None and 0.4 < reading.recent_rate < 0.55


def test_zero_over_a_real_sample_is_flagged_with_no_history_at_all(tmp_path) -> None:
    """The 11 August case. Zero needs no comparison: a population that answers and
    never holds a capture is not worth querying, whatever it did last week."""
    _journal(tmp_path, "cdx_pool_20260811T000000Z.jsonl.gz", 600, 0)
    reading = measure(tmp_path, "cdx_pool")
    assert reading.recent_hits == 0
    assert reading.collapsed


def test_a_collapse_against_its_own_history_is_flagged(tmp_path) -> None:
    """The real 11 August reading was 6.8% against 51.6%, not a clean zero, because the
    recent window straddled the rebuild. An absolute floor low enough to be safe for the
    candidate pool would have let that through."""
    for day in range(1, 8):
        _journal(tmp_path, f"cdx_pool_202608{day:02d}T000000Z.jsonl.gz", 600, 310)
    for day in (8, 9, 10):
        _journal(tmp_path, f"cdx_pool_202608{day:02d}T000000Z.jsonl.gz", 600, 40)
    reading = measure(tmp_path, "cdx_pool")
    assert reading.recent_hits > 0
    assert reading.collapsed
    assert reading.history_rate is not None and reading.history_rate > 0.4


def test_a_hard_population_is_not_a_collapse(tmp_path) -> None:
    """A steady 38% pool is healthy; a fixed floor set for the 96% gap pool would
    condemn it every cycle, and an alarm that always fires is an alarm nobody reads."""
    for day in range(1, 8):
        _journal(tmp_path, f"cdx_pool_202608{day:02d}T000000Z.jsonl.gz", 600, 228)
    reading = measure(tmp_path, "cdx_pool")
    assert not reading.collapsed


def test_too_small_a_sample_is_reported_rather_than_judged(tmp_path) -> None:
    _journal(tmp_path, "cdx_pool_20260811T000000Z.jsonl.gz", MIN_SAMPLE - 10, 0)
    reading = measure(tmp_path, "cdx_pool")
    assert not reading.measurable
    assert not reading.collapsed
    assert "too few to judge" in reading.describe()


def test_transport_failures_are_excluded_from_the_denominator(tmp_path) -> None:
    """Counting a failed request as a miss would report a refusing archive as a dead
    population, which is the opposite diagnosis and the opposite action."""
    _journal(tmp_path, "cdx_pool_20260811T000000Z.jsonl.gz", 400, 200, failures=5000)
    reading = measure(tmp_path, "cdx_pool")
    assert reading.recent_answered == 400
    assert reading.recent_rate == 0.5
    assert not reading.collapsed


def test_an_in_flight_part_file_is_ignored(tmp_path) -> None:
    """A batch two records in is not evidence, and including it would make the reading
    jump between cycles for no reason."""
    _journal(tmp_path, "cdx_pool_20260801T000000Z.jsonl.gz", 600, 300)
    _journal(tmp_path, "cdx_pool_20260812T000000Z.jsonl.gz.part", 2, 0)
    reading = measure(tmp_path, "cdx_pool")
    assert reading.recent_answered == 600
    assert not reading.collapsed


def test_the_two_populations_are_measured_separately(tmp_path) -> None:
    """Folding them together would hide a pool collapse behind the gap pool's 96%,
    which is the same mistake `journal_outcomes` documents for hit rates."""
    _journal(tmp_path, "cdx_gap_vps_20260811T000000Z.jsonl.gz", 600, 580)
    _journal(tmp_path, "cdx_pool_20260811T000000Z.jsonl.gz", 600, 0)
    readings = {y.prefix: y for y in measure_all(tmp_path, ("cdx_gap", "cdx_pool"))}
    assert not readings["cdx_gap"].collapsed
    assert readings["cdx_pool"].collapsed


def test_no_journals_at_all_is_not_a_collapse(tmp_path) -> None:
    """A collector that has never run has not failed, and reporting it as failing would
    make a fresh checkout look broken."""
    reading = measure(tmp_path, "cdx_pool")
    assert reading.recent_answered == 0
    assert not reading.collapsed
    assert reading.newest == ""
