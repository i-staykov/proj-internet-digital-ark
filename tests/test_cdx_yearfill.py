"""The year-fill client files a hit under the host the archive named, and resumes exactly."""

from __future__ import annotations

import gzip
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "cdx_yearfill", ROOT / "scripts/engines/cdx_yearfill.py"
)
fill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fill)


def _run(tmp_path, monkeypatch, names, answers, *extra):
    queue = tmp_path / "queue.txt"
    queue.write_text("".join(f"{n}\n" for n in names))
    monkeypatch.setattr(fill, "OUT", tmp_path)
    monkeypatch.setattr(fill, "PAUSE_FLAG", tmp_path / "pause-yearfill")
    monkeypatch.setattr(fill, "cdx_clients", lambda: 0)
    slept = []
    monkeypatch.setattr(fill.time, "sleep", slept.append)
    calls = iter(answers)
    monkeypatch.setattr(fill, "fetch", lambda params, timeout: next(calls))
    argv = ["cdx_yearfill.py", str(queue), "--lane", "t", "--deadline", "9999999999", *extra]
    monkeypatch.setattr(sys, "argv", argv)
    fill.main()
    rows = []
    for journal in sorted(tmp_path.glob("cdx_yearfill_t_*.jsonl.gz")):
        with gzip.open(journal, "rt") as fh:
            rows += [json.loads(line) for line in fh]
    return rows, (tmp_path / "yearfill_t.done").read_text().strip(), slept


def test_the_year_counts_only_for_the_host_the_archive_named(tmp_path, monkeypatch):
    answers = [
        ("200", "20010315000000 http://a.com/\n", None),
        ("200", "20010401000000 http://www.b.com:80/x.html\n", None),
        ("200", "", None),
    ]
    rows, done, _ = _run(tmp_path, monkeypatch, ["a.com", "b.com", "c.com"], answers)
    assert rows[0] == {
        "domain": "a.com",
        "status": 200,
        "years": [2001],
        "hosts": {"a.com": "20010315000000"},
        "strategy": "cdx_yearfill",
    }
    assert rows[1]["years"] == [] and rows[1]["hosts"] == {"www.b.com": "20010401000000"}
    assert rows[2]["years"] == [] and rows[2]["hosts"] == {}
    assert done == "4"
    assert not list(tmp_path.glob("*.part"))


def test_retry_after_is_slept_and_the_name_asked_again(tmp_path, monkeypatch):
    answers = [("HTTP429", "", 42.0), ("200", "20010101000000 http://a.com/\n", None)]
    rows, done, slept = _run(tmp_path, monkeypatch, ["a.com"], answers)
    assert 42.0 in slept
    assert [r["domain"] for r in rows] == ["a.com"] and done == "2"


def test_a_throttle_stop_leaves_the_unanswered_name_to_be_asked_again(tmp_path, monkeypatch):
    answers = [("200", "", None)] + [("HTTP503", "", None)] * 5
    with pytest.raises(SystemExit):
        _run(tmp_path, monkeypatch, ["a.com", "b.com"], answers)
    assert (tmp_path / "yearfill_t.done").read_text().strip() == "2"


def test_journals_rotate_and_the_marker_resumes_after_them(tmp_path, monkeypatch):
    answers = [("200", "", None)] * 2
    names, flags = ["a.com", "b.com", "c.com"], ("--start-line", "2", "--rotate", "1")
    rows, done, _ = _run(tmp_path, monkeypatch, names, answers, *flags)
    assert [r["domain"] for r in rows] == ["b.com", "c.com"] and done == "4"
