"""The PreCompact handoff, and the two hooks that carry a session across a gap.

Both hooks run on every session start and every compaction, so what is tested is
what a hook must survive: a fresh clone with no `data/` and no transcript. Each
command prints one line there and exits 0.
"""

import importlib.util
import io
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PY = ROOT / "scripts/agents/handoff.py"
BRIEF_PY = ROOT / "scripts/agents/brief.py"
SETTINGS = ROOT / ".claude/settings.json"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


handoff = _load("handoff", HANDOFF_PY)

NOW = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)


def transcript(tmp_path: Path) -> Path:
    records = [
        {"type": "user", "message": {"content": "finish E5.4 and run the gate"}},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Writing the hook."},
                    {
                        "type": "tool_use",
                        "name": "Write",
                        "input": {"file_path": str(ROOT / "scripts/agents/handoff.py")},
                    },
                ]
            },
        },
        {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}},
        {"type": "user", "message": {"content": "<system-reminder>ignore me</system-reminder>"}},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Gate is green.\nCommitted on the branch."},
                    {
                        "type": "tool_use",
                        "name": "Edit",
                        "input": {"file_path": "/elsewhere/notes.md"},
                    },
                ]
            },
        },
        "not json at all",
    ]
    path = tmp_path / "session.jsonl"
    path.write_text(
        "\n".join(r if isinstance(r, str) else json.dumps(r) for r in records), encoding="utf-8"
    )
    return path


def test_the_note_carries_the_prompt_the_files_and_the_last_answer(tmp_path):
    state = handoff.walk(transcript(tmp_path).read_text(encoding="utf-8").splitlines())
    assert state["prompt"] == "finish E5.4 and run the gate"
    # a repo file keeps its path, one from outside keeps only its name
    assert state["paths"] == ["scripts/agents/handoff.py", "notes.md"]
    note = handoff.render(state, "auto", NOW).splitlines()
    assert note[0] == "handoff written 2026-09-03T09:00:00+00:00, before a compaction (auto)"
    assert "last prompt: finish E5.4 and run the gate" in note
    assert "edited 2 files: scripts/agents/handoff.py, notes.md" in note
    assert note[-1] == "  Committed on the branch."


def test_a_tool_result_is_not_a_prompt_and_a_reminder_is_not_either():
    assert handoff.is_prompt("<system-reminder>x</system-reminder>") is False
    assert handoff.is_prompt("Caveat: the messages below were generated") is False
    assert handoff.is_prompt("price the .ie register") is True
    assert handoff.as_text([{"type": "tool_result", "content": "ok"}]) == ""


def test_a_file_edited_twice_keeps_its_later_place():
    """The note has room for a dozen paths and a long session edits more, so the
    list is ordered by last touch, not by first."""
    edits = [
        {"type": "tool_use", "name": "Edit", "input": {"file_path": name}}
        for name in ("a.py", "b.py", "a.py")
    ]
    line = json.dumps({"type": "assistant", "message": {"content": edits}})
    assert handoff.walk([line])["paths"] == ["b.py", "a.py"]


def test_an_empty_transcript_still_says_something(tmp_path):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    out = tmp_path / "handoff.md"
    line = handoff.write({"transcript_path": str(empty), "trigger": "manual"}, out, tmp_path)
    assert line == "handoff: handoff.md, 2 lines"
    assert "nothing to carry over" in out.read_text(encoding="utf-8")


def test_a_missing_transcript_writes_nothing_and_says_so(tmp_path):
    out = tmp_path / "handoff.md"
    assert "no transcript to read" in handoff.write({"transcript_path": "/gone.jsonl"}, out)
    assert "no transcript_path" in handoff.write({}, out)
    assert not out.exists()
    assert handoff.payload(io.StringIO("not json")) == {}


def test_both_hooks_are_configured_with_a_timeout_and_no_host():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    hooks = settings["hooks"]
    assert "startup" in hooks["SessionStart"][0]["matcher"]
    # PreCompact takes no matcher: 77% of compactions are manual, and a matcher
    # written for `auto` would skip them.
    assert "matcher" not in hooks["PreCompact"][0]
    for event in ("SessionStart", "PreCompact"):
        for entry in hooks[event]:
            for hook in entry["hooks"]:
                assert 0 < hook["timeout"] <= 30, f"{event} needs a short timeout"
                assert "@" not in hook["command"] and "ssh" not in hook["command"]
                assert "/Users/" not in hook["command"]


def test_the_hook_commands_print_one_line_in_a_checkout_with_no_data(tmp_path):
    """Run the configured commands against this tree with `data/brief.json` and
    the transcript both absent, which is what a fresh clone looks like."""
    hooks = json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]
    commands = {
        event: [h["command"] for entry in hooks[event] for h in entry["hooks"]]
        for event in ("SessionStart", "PreCompact")
    }
    assert len(commands["SessionStart"]) == 1 and len(commands["PreCompact"]) == 1
    assert "scripts/agents/brief.py" in commands["SessionStart"][0]
    assert "scripts/agents/handoff.py" in commands["PreCompact"][0]
    probe = (
        "import importlib.util, sys; from pathlib import Path\n"
        "def load(n, p):\n"
        "    s = importlib.util.spec_from_file_location(n, p)\n"
        "    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m\n"
        f"b = load('brief', {str(BRIEF_PY)!r})\n"
        f"h = load('handoff', {str(HANDOFF_PY)!r})\n"
        f"print(b.load(Path({str(tmp_path / 'brief.json')!r}), Path({str(tmp_path / 'h.md')!r})))\n"
        f"print(h.write({{}}, Path({str(tmp_path / 'out.md')!r}), Path({str(tmp_path)!r})))\n"
    )
    done = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    printed = done.stdout.splitlines()
    assert printed[0] == "no brief: data/brief.json is missing, run `just state`"
    assert printed[1].startswith("handoff: no transcript to read")
    assert len(printed) == 2
