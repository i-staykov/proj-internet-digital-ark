"""Run journals: ingestable only once the run has stopped, resumable while and after it runs."""

import gzip
import json
import signal
import time
import zlib

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


def test_a_live_journal_is_hidden_from_ingest_but_not_from_the_resume_scan(tmp_path) -> None:
    """The ingest glob never sees a half-written file, whose hash would fail every later ingest."""
    path = journal_path(tmp_path, "rdap")
    with journal_writer(path) as fh:
        write_journal_line(fh, {"domain": "live.com", "status": 200})
        fh.flush()
        assert list(tmp_path.glob(INGEST_GLOB)) == [] and in_flight_path(path).exists()
        assert queried_domains(tmp_path, "rdap") == {"live.com"}, "no re-asking mid-run"
    assert list(tmp_path.glob(INGEST_GLOB)) == [path] and not in_flight_path(path).exists()
    # the .part name must not defeat the compression
    with gzip.open(path, "rt", encoding="utf-8") as raw:
        assert json.loads(raw.read())["domain"] == "live.com"


@pytest.mark.parametrize(
    "stop",
    [RuntimeError("network died mid-run"), SystemExit(128 + signal.SIGTERM)],
    ids=["the-run-raises", "the-supervisor-sends-sigterm"],
)
def test_the_journal_is_published_however_the_run_stops(tmp_path, stop) -> None:
    path = journal_path(tmp_path, "rdap")
    with pytest.raises(type(stop)), journal_writer(path) as fh:
        write_journal_line(fh, {"domain": "before.com", "status": 200})
        raise stop
    assert path.exists() and not in_flight_path(path).exists()
    assert [json.loads(line)["domain"] for line in open_journal(path)] == ["before.com"]


def test_the_previous_sigterm_handler_is_restored(tmp_path) -> None:
    before = signal.getsignal(signal.SIGTERM)
    with journal_writer(journal_path(tmp_path, "rdap")) as fh:
        write_journal_line(fh, {"domain": "x.com", "status": 200})
        assert signal.getsignal(signal.SIGTERM) is not before
    assert signal.getsignal(signal.SIGTERM) is before


def test_a_live_journal_grows_on_disk_as_records_are_written(tmp_path) -> None:
    """A flush per record, or gzip holds a block back and the watchdog sees an empty journal."""
    path = journal_path(tmp_path, "rdap")
    with journal_writer(path) as fh:
        write_journal_line(fh, {"domain": "first.com", "status": 200})
        after_first = in_flight_path(path).stat().st_size
        assert after_first > 0, "nothing reached disk, so the watchdog is blind"
        for i in range(20):
            write_journal_line(fh, {"domain": f"pair{i}.com", "status": 200})
        assert in_flight_path(path).stat().st_size > after_first, "size must track progress"


def test_the_resume_scan_keeps_what_it_read_from_a_truncated_journal(tmp_path) -> None:
    """A hard kill can leave the gzip stream unterminated; the records on disk are answers."""
    path = journal_path(tmp_path, "rdap")
    with journal_writer(path) as fh:
        for domain in ("one.com", "two.com"):
            write_journal_line(fh, {"domain": domain, "status": 200})
    path.write_bytes(path.read_bytes()[:-4])
    assert "one.com" in queried_domains(tmp_path, "rdap")


def test_a_damaged_gzip_block_does_not_stop_the_resume_scan(tmp_path) -> None:
    """A damaged last block raises `zlib.error`, not `OSError`, and the records before it stay."""
    good = tmp_path / "rdap_20260101T000000Z.jsonl.gz"
    with journal_writer(good) as fh:
        write_journal_line(fh, {"domain": "kept.com", "status": 200})
    # the good prefix must span several decompressor buffers, or no complete block survives
    damaged = tmp_path / "rdap_20260102T000000Z.jsonl.gz"
    with journal_writer(damaged) as fh:
        for i in range(40_000):
            write_journal_line(fh, {"domain": f"early{i}.com", "status": 200})
    assert damaged.stat().st_size > 256_000
    raw = bytearray(damaged.read_bytes())
    raw[-40:] = b"\x00" * 40  # corrupted, not truncated: what a killed write leaves
    damaged.write_bytes(bytes(raw))
    with pytest.raises((zlib.error, EOFError, gzip.BadGzipFile)), gzip.open(damaged, "rt") as fh:
        fh.read()
    seen = queried_domains(tmp_path, "rdap")
    assert "kept.com" in seen, "a healthy journal beside a damaged one must still be read"
    assert "early0.com" in seen, "records before the damage must survive"


def test_stopping_a_run_does_not_wait_for_its_queued_work() -> None:
    """A stop cancels the submitted batch rather than draining it, as the default pool would."""
    from ark.cli import _abortable_pool

    finished = []

    def slow(index: int) -> None:
        time.sleep(0.3)
        finished.append(index)

    began = time.monotonic()
    with pytest.raises(SystemExit), _abortable_pool(2) as pool:
        for i in range(200):
            pool.submit(slow, i)
        raise SystemExit(143)
    # draining 200 tasks two at a time would take ~30s; cancelling takes one slot
    assert time.monotonic() - began < 5
    assert len(finished) < 20
