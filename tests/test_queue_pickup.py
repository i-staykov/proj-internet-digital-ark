"""A rebuilt queue that no collector reads is not a rebuild.

`supervise_cdx_pool.sh` resolves `ARK_TARGETS` once, at startup, and passes that fixed path
to every `ark cdx` batch. So `discover_cycle`'s claim that "the running collector picks it up
at its next dispatch" held only when the collector happened to have been started on the file
the cycle rebuilds.

On 2026-08-18 it had not been. The engine worked `queue_pool_20260818c.txt` for two hours at
9.5% on a `.ca` head, worth 0.0794 equivalent-English per query, while `queue_pool_local.txt`
sat correctly re-ranked to a `.au` and `.com` head and unread. **Every health check read clean**:
the process was present, the journal was growing, and the yield check did fire, but its advice
was "rebuild and re-rank", which had already been done. Only the queue identity was wrong, and
nothing was looking at that.
"""

import importlib.util
import subprocess
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "discover_cycle", Path(__file__).resolve().parent.parent / "scripts/harness/discover_cycle.py"
)
cycle = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cycle)

RUNNING = (
    "bash scripts/engines/supervise_cdx_pool.sh 1787068800 600 8 900\n"
    "uv run ark cdx data/raw/cdx/queue_pool_20260818c.txt -n 600 --workers 8\n"
    "uv run ark rdap data/raw/rdap/pool_targets_20260818.txt -n 5000\n"
)


def fake_ps(monkeypatch, text: str) -> None:
    def run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=text)

    monkeypatch.setattr(cycle.subprocess, "run", run)


def test_it_finds_the_collector_that_reads_the_file(monkeypatch) -> None:
    fake_ps(monkeypatch, RUNNING)
    found = cycle.collector_reading("data/raw/cdx/queue_pool_20260818c.txt")
    assert found and "queue_pool_20260818c.txt" in found


def test_it_returns_none_for_a_file_nothing_reads(monkeypatch) -> None:
    """The case that cost two hours: the cycle rebuilds this file and no collector has it."""
    fake_ps(monkeypatch, RUNNING)
    assert cycle.collector_reading("data/raw/cdx/queue_pool_local.txt") is None


def test_it_matches_on_the_basename_not_the_full_path(monkeypatch) -> None:
    """The supervisor may hold a relative path and the worker an absolute one."""
    fake_ps(monkeypatch, RUNNING)
    found = cycle.collector_reading("/abs/elsewhere/queue_pool_20260818c.txt")
    assert found is not None


def test_an_rdap_target_list_is_not_a_cdx_collector(monkeypatch) -> None:
    """Matching must require an `ark cdx` line, or the RDAP sweep's own list would count."""
    fake_ps(monkeypatch, RUNNING)
    assert cycle.collector_reading("data/raw/rdap/pool_targets_20260818.txt") is None


def test_no_collectors_at_all_reads_as_none(monkeypatch) -> None:
    fake_ps(monkeypatch, "bash scripts/harness/maintain.sh\n")
    assert cycle.collector_reading("data/raw/cdx/queue_pool_local.txt") is None
