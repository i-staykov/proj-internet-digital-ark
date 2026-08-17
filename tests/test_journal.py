"""Run journals: a journal becomes ingestable only when its run has stopped.

The rule these tests defend: the documented ingest commands glob `*.jsonl.gz`,
and one is often issued while a collector is still running. If the glob matched
the live journal, the loader would ledger the hash of a half-written file and
every later ingest of the finished file would fail its hash check, with the tail
of the run unreachable.
"""

import gzip
import json
import signal

import pytest

from ark.journal import (
    in_flight_path,
    journal_path,
    journal_writer,
    open_journal,
    queried_domains,
    write_journal_line,
)

INGEST_GLOB = "rdap_*.jsonl.gz"


def _journal(tmp_path):
    return journal_path(tmp_path, "rdap")


def test_a_live_journal_is_not_visible_to_the_ingest_glob(tmp_path) -> None:
    path = _journal(tmp_path)
    with journal_writer(path) as fh:
        write_journal_line(fh, {"domain": "live.com", "status": 200})
        fh.flush()
        # mid-run: the loader must not be able to see this file at all
        assert list(tmp_path.glob(INGEST_GLOB)) == []
        assert in_flight_path(path).exists()
    # the run stopped, so now it is ingestable under its real name
    assert list(tmp_path.glob(INGEST_GLOB)) == [path]
    assert not in_flight_path(path).exists()


def test_a_live_journal_is_still_visible_to_the_resume_scan(tmp_path) -> None:
    path = _journal(tmp_path)
    with journal_writer(path) as fh:
        write_journal_line(fh, {"domain": "asked.com", "status": 200})
        fh.flush()
        # hiding it from ingest must not make a later run re-ask the same domains
        assert queried_domains(tmp_path, "rdap") == {"asked.com"}


def test_the_journal_is_published_even_when_the_run_raises(tmp_path) -> None:
    path = _journal(tmp_path)
    with pytest.raises(RuntimeError), journal_writer(path) as fh:
        write_journal_line(fh, {"domain": "before.com", "status": 200})
        raise RuntimeError("network died mid-run")
    # nothing is writing it any more, so what it holds is a complete short run
    assert path.exists() and not in_flight_path(path).exists()
    assert [json.loads(line)["domain"] for line in open_journal(path)] == ["before.com"]


def test_the_journal_is_published_when_the_run_is_terminated(tmp_path) -> None:
    path = _journal(tmp_path)
    # what the SIGTERM handler raises, which is how the supervisor stops a collector
    with pytest.raises(SystemExit), journal_writer(path) as fh:
        write_journal_line(fh, {"domain": "killed.com", "status": 200})
        raise SystemExit(128 + signal.SIGTERM)
    assert [json.loads(line)["domain"] for line in open_journal(path)] == ["killed.com"]


def test_the_previous_sigterm_handler_is_restored(tmp_path) -> None:
    before = signal.getsignal(signal.SIGTERM)
    with journal_writer(_journal(tmp_path)) as fh:
        write_journal_line(fh, {"domain": "x.com", "status": 200})
        assert signal.getsignal(signal.SIGTERM) is not before
    assert signal.getsignal(signal.SIGTERM) is before


def test_a_published_journal_is_gzipped(tmp_path) -> None:
    path = _journal(tmp_path)
    with journal_writer(path) as fh:
        write_journal_line(fh, {"domain": "zipped.com", "status": 200})
    # the .part name must not defeat the compression check
    with gzip.open(path, "rt", encoding="utf-8") as raw:
        assert json.loads(raw.read())["domain"] == "zipped.com"


def test_a_live_journal_grows_on_disk_as_records_are_written(tmp_path) -> None:
    """The watchdog decides a run has stalled by watching this size.

    `scripts/supervise_cdx_pool.sh` reads journal bytes and restarts the supervisor when
    they stop moving. gzip emits nothing until zlib fills a block, so without a
    flush per record the file sits at zero for minutes: on 3 August, with the
    archive answering slowly, the first block took 12.7 minutes against a
    10-minute window, which reads as a stall on a perfectly healthy batch.

    So this asserts what the monitor assumes, with no explicit flush by the caller.
    """
    path = _journal(tmp_path)
    partial = in_flight_path(path)
    with journal_writer(path) as fh:
        write_journal_line(fh, {"domain": "first.com", "status": 200})
        after_first = partial.stat().st_size
        assert after_first > 0, "nothing reached disk, so the watchdog is blind"
        for i in range(20):
            write_journal_line(fh, {"domain": f"pair{i}.com", "status": 200})
        assert partial.stat().st_size > after_first, "size must track progress"


def test_the_resume_scan_keeps_what_it_read_from_a_truncated_journal(tmp_path) -> None:
    path = _journal(tmp_path)
    with journal_writer(path) as fh:
        for domain in ("one.com", "two.com"):
            write_journal_line(fh, {"domain": domain, "status": 200})
        fh.flush()
    # a hard kill can leave the gzip stream unterminated; the records that did
    # reach disk are still answers and must not be queried again
    path.write_bytes(path.read_bytes()[:-4])
    assert "one.com" in queried_domains(tmp_path, "rdap")


def test_stopping_a_run_does_not_wait_for_its_queued_work() -> None:
    """A stop request must not first drain the whole submitted batch.

    The collectors submit every domain up front, so the default
    `ThreadPoolExecutor.__exit__`, which waits for all queued tasks, turned
    SIGTERM into a wait for hundreds of pending HTTP requests. Observed live: a
    run kept going for minutes after `pkill` and had to be killed with -9.
    """
    import time as _time

    from ark.cli import _abortable_pool

    started, finished = [], []

    def slow(index: int) -> int:
        started.append(index)
        _time.sleep(0.3)
        finished.append(index)
        return index

    began = _time.monotonic()
    with pytest.raises(SystemExit), _abortable_pool(2) as pool:
        for i in range(200):
            pool.submit(slow, i)
        raise SystemExit(143)
    elapsed = _time.monotonic() - began

    # draining 200 tasks two at a time would take ~30s; cancelling takes one slot
    assert elapsed < 5
    assert len(finished) < 20
