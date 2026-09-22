"""The thin-parent client writes what the sweep writes and never marks a truncated answer done."""

from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "cdx_thin_sweep", ROOT / "scripts/engines/cdx_thin_sweep.py"
)
thin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(thin)

ARGS = SimpleNamespace(deadline=9999999999, limit=3, timeout=5, delay=0)


def _setup(tmp_path, monkeypatch, answers):
    monkeypatch.setattr(thin, "OUT", tmp_path)
    monkeypatch.setattr(thin, "RICH", tmp_path / "rich.txt")
    monkeypatch.setattr(thin, "PAUSE_FLAG", tmp_path / "pause")
    monkeypatch.setattr(thin.time, "sleep", lambda s: None)
    calls = iter(answers)
    monkeypatch.setattr(thin, "fetch", lambda params, timeout: next(calls))


def test_a_thin_answer_is_journaled_and_marked_done(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, [("200", ["http://www.a.com/ 19990101000000", "junk"], None)])
    assert thin.sweep_parent("a.com", ARGS) == "1 rows"
    (journal,) = tmp_path.glob("suffix_a_com_*.jsonl.gz")
    with gzip.open(journal, "rt") as fh:
        assert [json.loads(line) for line in fh] == [
            {"url": "http://www.a.com/", "timestamp": "19990101000000"}
        ]
    assert (tmp_path / "suffix_a_com.done").exists()
    assert not list(tmp_path.glob("*.part"))


def test_an_answer_at_the_limit_is_kept_but_left_for_the_paginated_sweep(tmp_path, monkeypatch):
    lines = [f"http://h{i}.b.com/ 2000010100000{i}" for i in range(3)]
    _setup(tmp_path, monkeypatch, [("200", lines, None)])
    assert "at the limit" in thin.sweep_parent("b.com", ARGS)
    assert list(tmp_path.glob("suffix_b_com_*.jsonl.gz"))
    assert not (tmp_path / "suffix_b_com.done").exists()
    assert (tmp_path / "rich.txt").read_text() == "b.com\n"


def test_retry_after_is_slept_and_the_same_parent_asked_again(tmp_path, monkeypatch):
    slept = []
    _setup(tmp_path, monkeypatch, [("HTTP429", [], 42.0), ("200", [], None)])
    monkeypatch.setattr(thin.time, "sleep", slept.append)
    assert thin.sweep_parent("c.com", ARGS) == "0 rows"
    assert 42.0 in slept
    assert (tmp_path / "suffix_c_com.done").exists()
