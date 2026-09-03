"""The context report must count each record once and name the tool behind each result.

A resumed session copies its earlier records into the new file, differing only in metadata
such as `gitBranch`, so a naive sum double-counts most of a long session (49,467 of 98,559
lines in the newest transcript when this was written). The fixture therefore repeats a
tool_result and a compaction record under the same uuid and expects both to be counted once.
"""

import importlib.util
import json
import os
import time
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "context_report",
    Path(__file__).resolve().parents[1] / "scripts/agents/context_report.py",
)
context_report = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(context_report)


def _assistant(uuid: str, block: dict) -> dict:
    return {"uuid": uuid, "type": "assistant", "message": {"role": "assistant", "content": [block]}}


def _result(uuid: str, tool_use_id: str, content: object) -> dict:
    block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    return {"uuid": uuid, "type": "user", "message": {"role": "user", "content": [block]}}


def _write(path: Path, records: list) -> Path:
    lines = [r if isinstance(r, str) else json.dumps(r) for r in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


LONG = "x" * 1501
COMPACT = {
    "uuid": "c1",
    "type": "system",
    "subtype": "compact_boundary",
    "compactMetadata": {"trigger": "manual"},
}


def _fixture(tmp_path: Path) -> Path:
    bash_result = _result("r1", "t1", "a" * 100)
    duplicate = dict(bash_result, gitBranch="other")
    return _write(
        tmp_path / "s1.jsonl",
        [
            {"type": "queue-operation", "operation": "enqueue"},
            _assistant("a1", {"type": "tool_use", "id": "t1", "name": "Bash", "input": {}}),
            bash_result,
            duplicate,
            _assistant("a2", {"type": "tool_use", "id": "t2", "name": "Read", "input": {}}),
            _result(
                "r2", "t2", [{"type": "text", "text": "b" * 300}, {"type": "text", "text": "é"}]
            ),
            _result("r3", "t9", "c" * 50),
            _assistant("a3", {"type": "text", "text": LONG}),
            _assistant("a4", {"type": "text", "text": "short"}),
            COMPACT,
            dict(COMPACT, gitBranch="other"),
            "{not json",
        ],
    )


def test_records_are_counted_once_and_results_named_by_tool(tmp_path: Path) -> None:
    report = context_report.report_for([_fixture(tmp_path)])
    assert report.duplicates == 2
    assert report.result_bytes_by_tool == {"Bash": 100, "Read": 302, "unknown": 50}
    assert sorted(report.results, reverse=True)[0] == (302, "t2")
    assert report.assistant_text_bytes == 1501 + 5
    assert report.long_text_blocks == 1
    assert dict(report.compacts) == {"manual": 1}


def test_all_dedupes_across_files_and_stays_short(tmp_path: Path, capsys) -> None:
    """A record copied into a second transcript counts once, and a tool_use seen only in the
    other file still names the result."""
    _fixture(tmp_path)
    _write(
        tmp_path / "s2.jsonl",
        [_result("r1", "t1", "a" * 100), _result("r4", "t2", "d" * 10)],
    )
    assert context_report.main(["--all", "--dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "2 file(s)" in out
    assert "3 duplicate uuids skipped" in out
    assert "312  Read" in out
    assert "compact events: 1 (1 manual, 0 auto)" in out
    assert len(out.splitlines()) < 40


def test_newest_transcript_is_the_default(tmp_path: Path, capsys) -> None:
    old = _write(tmp_path / "old.jsonl", [COMPACT])
    new = _write(tmp_path / "new.jsonl", [dict(COMPACT, uuid="c2")])
    stamp = time.time()
    os.utime(old, (stamp - 60, stamp - 60))
    os.utime(new, (stamp, stamp))
    assert context_report.main(["--dir", str(tmp_path)]) == 0
    assert capsys.readouterr().out.startswith("new.jsonl:")


def test_missing_directory_is_reported_not_raised(tmp_path: Path, capsys) -> None:
    assert context_report.main(["--dir", str(tmp_path / "absent")]) == 0
    assert "no transcript found" in capsys.readouterr().out
