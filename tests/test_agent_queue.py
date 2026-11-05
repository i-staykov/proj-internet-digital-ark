"""The agent's work queue (`scripts/agents/work_queue.py`): the top item is the highest priority
then the oldest, a note carries the session to resume once, done items age out and the file
stays under 20 KB, and each mode's prompt stays under 60 lines naming the persistent files."""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WQ = ROOT / "scripts/agents/work_queue.py"


def q(tmp_path, *args):
    env = os.environ | {"ARK_AGENT_QUEUE": str(tmp_path / "agent_work.jsonl")}
    out = subprocess.run(["python3", WQ, *args], env=env, capture_output=True, text=True)
    return out.returncode, out.stdout.strip()


def test_top_is_the_highest_priority_then_the_oldest_and_a_note_carries_the_session(tmp_path):
    assert q(tmp_path, "top")[0] == 1
    assert q(tmp_path, "add", "issue", "the check recipe (#503)")[1] == "issue-the-check-recipe-503"
    assert (
        q(tmp_path, "add", "improvement", "lane 1 floor", "--evidence", "two days under band")[0]
        == 0
    )
    assert q(tmp_path, "add", "alert", "BANK RED 05:05", "--id", "alert-red")[1] == "alert-red"
    assert (
        q(tmp_path, "add", "alert", "BANK RED 05:05", "--id", "alert-red")[1]
        == "open already: alert-red"
    )
    assert q(tmp_path, "top", "--field", "id")[1] == "alert-red"
    assert q(tmp_path, "start", "alert-red")[0] == 0
    assert q(tmp_path, "note", "alert-red", "export done, check next", "--session", "s-1")[0] == 0
    top = json.loads(q(tmp_path, "top")[1])
    assert (top["attempts"], top["session"], top["note"]) == (1, "s-1", "export done, check next")
    assert q(tmp_path, "done", "alert-red")[0] == 0
    assert q(tmp_path, "top", "--field", "id")[1] == "issue-the-check-recipe-503"
    assert q(tmp_path, "park", "issue-the-check-recipe-503", "three attempts")[0] == 0
    assert q(tmp_path, "top", "--field", "kind")[1] == "improvement"
    listing = q(tmp_path, "list")[1].splitlines()
    assert len(listing) == 3 and listing[2].startswith("done   p1 1x alert-red")


def test_the_file_stays_under_20_kb(tmp_path):
    for n in range(120):
        q(tmp_path, "add", "improvement", f"item {n}", "--evidence", "x" * 150)
        q(tmp_path, "done", f"improvement-item-{n}")
    size = (tmp_path / "agent_work.jsonl").stat().st_size
    assert size < 20_000


def test_each_prompt_is_short_and_names_the_persistent_files():
    common = (ROOT / "agent/prompts/common.md").read_text()
    for name in ("agent_work.jsonl", "auto-memory", "agent_runs.tsv", "subagent", "resume"):
        assert name in common, name
    for prompt in (ROOT / "agent/prompts").glob("*.md"):
        lines = len(prompt.read_text().splitlines())
        assert lines + len(common.splitlines()) <= 60, prompt.name
