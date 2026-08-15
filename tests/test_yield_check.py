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

from ark.yield_check import MIN_SAMPLE, measure, measure_all, rdap_verdict


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


def test_the_newest_finished_batch_is_reported_separately(tmp_path) -> None:
    """The windowed rate is right to alarm on and wrong to read after a re-rank: it
    averages three batches, so it stays low for hours after a fix and cannot say whether
    the fix worked. The newest finished batch can."""
    _journal(tmp_path, "cdx_pool_20260810T000000Z.jsonl.gz", 600, 0)
    _journal(tmp_path, "cdx_pool_20260811T000000Z.jsonl.gz", 600, 0)
    _journal(tmp_path, "cdx_pool_20260812T000000Z.jsonl.gz", 600, 300)
    reading = measure(tmp_path, "cdx_pool")
    assert reading.newest_rate == 0.5
    assert reading.recent_rate is not None and reading.recent_rate < 0.2
    assert "newest finished batch 50.0% of 600" in reading.describe()


def test_the_newest_reading_never_comes_from_an_in_flight_part(tmp_path) -> None:
    """Reading a gzip stream still being appended truncates at its last complete block,
    and the prefix is not a sample: one batch gave 9.5%, then 14.0%, then 27.9% in a
    single afternoon of hand-inspection."""
    _journal(tmp_path, "cdx_pool_20260811T000000Z.jsonl.gz", 600, 300)
    _journal(tmp_path, "cdx_pool_20260812T000000Z.jsonl.gz.part", 20, 0)
    reading = measure(tmp_path, "cdx_pool")
    assert reading.newest.endswith(".jsonl.gz")
    assert reading.newest_answered == 600
    assert reading.newest_rate == 0.5


def test_no_finished_batch_says_so_rather_than_reading_as_zero(tmp_path) -> None:
    reading = measure(tmp_path, "cdx_pool")
    assert reading.newest_rate is None
    assert reading.latest == "no finished batch yet"


def _rdap_journal(directory: Path, name: str, rows) -> None:
    """rows: (status, creation_year) pairs."""
    directory.mkdir(parents=True, exist_ok=True)
    with gzip.open(directory / name, "wt", encoding="utf-8") as fh:
        for i, (status, year) in enumerate(rows):
            fh.write(
                json.dumps({"domain": f"d{i}-{name}.org", "status": status, "creation_year": year})
                + "\n"
            )


def test_rdap_counts_a_404_as_an_answer_but_not_a_throttle() -> None:
    """A registry saying "no such domain" is information, and 1,107,164 of 1,656,921
    queries on this project have said it. A 429 is not an answer, and counting it would
    make a rate-limiting registry read as a population that stopped existing."""
    from ark.yield_check import rdap_verdict

    assert rdap_verdict({"status": 404, "creation_year": None}) == (True, False)
    assert rdap_verdict({"status": 200, "creation_year": 1999}) == (True, True)
    assert rdap_verdict({"status": 429, "creation_year": None}) == (False, False)
    assert rdap_verdict({"status": 403, "creation_year": None}) == (False, False)
    assert rdap_verdict({"status": 0, "creation_year": None}) == (False, False)


def test_rdap_requires_the_year_to_be_in_window() -> None:
    """A creation year of 2015 is a good answer that pays nothing. Counting it reports a
    sweep of modern registrations as productive: 28.4% of queries return some year
    against 10.1% returning one that counts."""
    from ark.yield_check import rdap_verdict

    assert rdap_verdict({"status": 200, "creation_year": 2015}) == (True, False)
    assert rdap_verdict({"status": 200, "creation_year": 1995}) == (True, False)
    assert rdap_verdict({"status": 200, "creation_year": 1996}) == (True, True)
    assert rdap_verdict({"status": 200, "creation_year": 2001}) == (True, True)


def test_rdap_yield_is_measured_with_its_own_verdict(tmp_path) -> None:
    """End to end: throttles stay out of the denominator, so a healthy sweep behind a
    rate limit is not reported as a collapse."""
    from ark.yield_check import rdap_verdict

    rows = [(200, 1999)] * 120 + [(404, None)] * 180 + [(429, None)] * 500
    _rdap_journal(tmp_path, "rdap_pool_20260811T000000Z.jsonl.gz", rows)
    reading = measure(tmp_path, "rdap", verdict=rdap_verdict)
    assert reading.newest_answered == 300  # the 500 throttles are excluded
    assert reading.newest_rate == 0.4
    assert not reading.collapsed


def test_an_unplanned_prefix_is_still_measured(tmp_path) -> None:
    """Discovery rather than a list, because the list is how a dead engine hid.

    The prefixes were hardcoded to `cdx_pool` and `cdx_gap` on the authority of the
    supervisor's header. The VPS ran `cdx_q1` for 31 hours against an exhausted shard,
    3,219 answered queries for zero captures, and no yield line covered it.
    """
    from ark.yield_check import active_cdx_collectors

    _journal(tmp_path, "cdx_pool_20260812T000000Z.jsonl.gz", 10, 5)
    _journal(tmp_path, "cdx_q1_20260812T000000Z.jsonl.gz", 10, 0)
    found = {c.prefix for c in active_cdx_collectors(tmp_path)}
    assert found == {"cdx_pool", "cdx_q1"}


def test_a_prefix_that_stopped_last_week_is_not_reported(tmp_path) -> None:
    """The question is which collectors are running now, so a retired prefix is noise."""
    import os

    from ark.yield_check import active_cdx_collectors

    _journal(tmp_path, "cdx_live_20260812T000000Z.jsonl.gz", 10, 5)
    _journal(tmp_path, "cdx_retired_20260801T000000Z.jsonl.gz", 10, 5)
    stale = 1_000_000.0
    os.utime(tmp_path / "cdx_retired_20260801T000000Z.jsonl.gz", (stale, stale))
    found = {c.prefix for c in active_cdx_collectors(tmp_path)}
    assert found == {"cdx_live"}


def test_an_in_flight_part_file_still_marks_a_prefix_live(tmp_path) -> None:
    """A live collector's newest file is usually the one it is still writing, so
    activity is judged including `.part` even though the measurement excludes it."""
    from ark.yield_check import active_cdx_collectors

    _journal(tmp_path, "cdx_fresh_20260812T000000Z.jsonl.gz.part", 10, 5)
    assert {c.prefix for c in active_cdx_collectors(tmp_path)} == {"cdx_fresh"}


def test_a_hand_named_probe_is_not_read_as_the_newest_batch(tmp_path) -> None:
    """The bug this exists for: `rdap_probe_org_step2.jsonl.gz` sorts ahead of every
    `rdap_pool_<stamp>.jsonl.gz` under a plain reverse filename sort, because "probe"
    follows "pool". The RDAP yield line reported that static file as the newest finished
    batch for days, a frozen 38.0% while the live sweep ran at 23% to 26%.
    """

    def write(name: str, year: int) -> None:
        with gzip.open(tmp_path / name, "wt", encoding="utf-8") as fh:
            for i in range(40):
                row = {"domain": f"d{i}.org", "status": 200, "creation_year": year}
                fh.write(json.dumps(row) + "\n")

    # the probe: every record in window, so reading it looks healthy
    write("rdap_probe_org_step2.jsonl.gz", 1998)
    # the live batch: nothing in window, which is what a real check must surface
    write("rdap_pool_20260815T113942Z.jsonl.gz", 2011)

    reading = measure(tmp_path, "rdap", verdict=rdap_verdict)
    assert reading.newest_answered == 40
    assert reading.newest_hits == 0, "the probe file was read instead of the live batch"
