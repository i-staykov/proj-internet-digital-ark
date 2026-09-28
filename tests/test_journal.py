"""Run journals: ingestable only once the run has stopped, resumable while and after it runs."""

import gzip
import json
import os
import signal
import time

import pytest

from ark import journal

INGEST_GLOB = "rdap_*.jsonl.gz"


def test_a_live_journal_is_hidden_from_ingest_but_not_from_the_resume_scan(tmp_path) -> None:
    """The ingest glob never sees a half-written file, whose hash would fail every later ingest,
    and each record reaches disk as it is written, or gzip holds it back from the scan."""
    path = journal.journal_path(tmp_path, "rdap")
    with journal.journal_writer(path) as fh:
        journal.write_journal_line(fh, {"domain": "live.com", "status": 200})
        assert list(tmp_path.glob(INGEST_GLOB)) == [] and journal.in_flight_path(path).exists()
        assert journal.queried_domains(tmp_path, "rdap") == {"live.com"}, "no re-asking mid-run"
    assert list(tmp_path.glob(INGEST_GLOB)) == [path] and not journal.in_flight_path(path).exists()
    with gzip.open(path, "rt", encoding="utf-8") as raw:  # the .part name kept the compression
        assert json.loads(raw.read())["domain"] == "live.com"


@pytest.mark.parametrize("stop", ["the-run-raises", "the-supervisor-sends-sigterm"])
def test_the_journal_is_published_however_the_run_stops(tmp_path, stop) -> None:
    before, path = signal.getsignal(signal.SIGTERM), journal.journal_path(tmp_path, "rdap")
    with pytest.raises((RuntimeError, SystemExit)), journal.journal_writer(path) as fh:
        journal.write_journal_line(fh, {"domain": "before.com", "status": 200})
        if stop == "the-supervisor-sends-sigterm":
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(5)  # the handler raises out of this at once
        raise RuntimeError("network died mid-run")
    assert path.exists() and not journal.in_flight_path(path).exists()
    assert [json.loads(line)["domain"] for line in journal.open_journal(path)] == ["before.com"]
    assert signal.getsignal(signal.SIGTERM) is before, "the previous handler is restored"


def test_the_resume_scan_keeps_what_it_read_from_a_truncated_or_damaged_journal(tmp_path) -> None:
    """A hard kill can leave the gzip stream unterminated, or its last block damaged, which
    raises `zlib.error` and not `OSError`; the records before it and beside it are answers."""
    journals = [tmp_path / f"rdap_2026010{day}T000000Z.jsonl.gz" for day in (1, 2, 3)]
    for day, count in ((1, 1), (2, 2), (3, 40_000)):
        with journal.journal_writer(journals[day - 1]) as fh:
            for i in range(count):
                journal.write_journal_line(fh, {"domain": f"{day}-{i}.com", "status": 200})
    journals[1].write_bytes(journals[1].read_bytes()[:-4])  # truncated
    # corrupted, not truncated, past several decompressor buffers: what a killed write leaves
    raw = journals[2].read_bytes()
    journals[2].write_bytes(raw[:-40] + b"\x00" * 40)
    assert {"1-0.com", "2-0.com", "3-0.com"} <= journal.queried_domains(tmp_path, "rdap")


def test_stopping_a_run_does_not_wait_for_its_queued_work() -> None:
    """A stop cancels the submitted batch rather than draining it, as the default pool would."""
    from ark.cli import _abortable_pool

    finished, began = [], time.monotonic()
    with pytest.raises(SystemExit), _abortable_pool(2) as pool:
        for i in range(200):
            pool.submit(lambda i=i: time.sleep(0.1) or finished.append(i))
        raise SystemExit(143)
    # draining 200 tasks two at a time would take 10 s; cancelling takes one slot
    assert (time.monotonic() - began < 5, len(finished) < 20) == (True, True)
