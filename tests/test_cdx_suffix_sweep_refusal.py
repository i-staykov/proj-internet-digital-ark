"""A 403 on the count probe is a refusal, not a throttle."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "cdx_suffix_sweep", ROOT / "scripts/engines/cdx_suffix_sweep.py"
)
sweep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sweep)


def test_a_refused_parent_is_given_up_rather_than_waited_out(tmp_path, monkeypatch, capsys):
    """`guardian.co.uk` answered 403 to every count probe and one shard spent 45 minutes
    per pass writing nothing, because the retry only ended at the parent's deadline."""
    calls = {"n": 0}

    def refuse(params, timeout):
        calls["n"] += 1
        return "HTTP403", []

    monkeypatch.setattr(sweep, "fetch", refuse)
    monkeypatch.setattr(sweep, "OUT", tmp_path)
    monkeypatch.setattr(sweep, "MAX_COUNT_REFUSALS", 3)
    # no sleeping through the backoff in a test
    monkeypatch.setattr(sweep.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        sys, "argv", ["cdx_suffix_sweep.py", "refused.example", "--deadline", "9999999999"]
    )
    sweep.main()

    assert calls["n"] == 3, "it should stop asking at the third refusal, not at the deadline"
    out = capsys.readouterr().out
    assert "giving the parent up" in out
    # NOT marked done: the yield test must be able to queue it for retry another day
    assert not list(tmp_path.glob("*.done"))
