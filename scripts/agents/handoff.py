"""What the next context needs, written before a compaction takes it away.

The `PreCompact` hook hands its payload on stdin and this writes
`private/handoff.md` from the transcript it names: the last prompt, the files the
session edited, and how the last answer ended. `scripts/agents/brief.py` prints
that file at the next session start, so the two halves of a compaction meet
without anyone remembering to run anything.

Reads the transcript and nothing else. No store, no network, no ssh: a hook that
blocks costs the session, and everything here is already on disk. It always exits
0 and always prints one line, because a session must not fail, or go quiet, on its
own bookkeeping.

    uv run python scripts/agents/handoff.py < payload.json      # PreCompact hook
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HANDOFF = ROOT / "private/handoff.md"
EDIT_TOOLS = {"Edit", "MultiEdit", "Write", "NotebookEdit"}
MAX_PATHS = 12
MAX_PROMPT = 200
MAX_TAIL_LINES = 6


def as_text(content) -> str:
    """The prose of one message. A list of blocks keeps only its `text` ones, so
    tool calls and tool results do not read as something a person said."""
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    return "\n".join(p for p in parts if p).strip()


def is_prompt(text: str) -> bool:
    """A typed prompt, not the harness talking. Slash commands, system reminders
    and the resume caveat all arrive as user records and none of them is a task."""
    return bool(text) and not text.startswith(("<", "Caveat:", "[Request interrupted"))


def edited_paths(content, root: Path) -> list[str]:
    if not isinstance(content, list):
        return []
    found = []
    for block in content:
        if not isinstance(block, dict) or block.get("name") not in EDIT_TOOLS:
            continue
        data = block.get("input") or {}
        raw = data.get("file_path") or data.get("notebook_path")
        if isinstance(raw, str) and raw:
            found.append(short_path(raw, root))
    return found


def short_path(raw: str, root: Path) -> str:
    """Repo-relative where it can be, the bare name otherwise. An absolute path
    from someone's laptop says nothing the next context can use."""
    path = Path(raw)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def walk(lines, root: Path = ROOT) -> dict:
    """One pass over the transcript, keeping only what the note prints."""
    state: dict = {"prompt": "", "answer": "", "paths": []}
    seen = set()
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = (record.get("message") or {}).get("content")
        if record.get("type") == "user":
            text = as_text(content)
            if is_prompt(text):
                state["prompt"] = text
        elif record.get("type") == "assistant":
            text = as_text(content)
            if text:
                state["answer"] = text
            for path in edited_paths(content, root):
                # Kept in order of last touch: a long session edits more files
                # than the note has room for, and the recent ones are the ones
                # the next context is still working on.
                if path in seen:
                    state["paths"].remove(path)
                seen.add(path)
                state["paths"].append(path)
    return state


def one_line(text: str, limit: int = MAX_PROMPT) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 3].rstrip() + "..."


def render(state: dict, trigger: str, now: datetime) -> str:
    stamp = now.isoformat(timespec="seconds")
    lines = [f"handoff written {stamp}, before a compaction ({trigger})"]
    if state["prompt"]:
        lines.append(f"last prompt: {one_line(state['prompt'])}")
    paths = state["paths"]
    if paths:
        head = f"edited {len(paths)} files"
        if len(paths) > MAX_PATHS:
            head += f", last {MAX_PATHS}"
        lines.append(f"{head}: {', '.join(paths[-MAX_PATHS:])}")
    if state["answer"]:
        tail = [one_line(ln) for ln in state["answer"].splitlines() if ln.strip()]
        lines.append("the answer ended:")
        lines += [f"  {ln}" for ln in tail[-MAX_TAIL_LINES:]]
    if len(lines) == 1:
        lines.append("nothing to carry over: the transcript held no prompt and no edits")
    return "\n".join(lines) + "\n"


def payload(stream) -> dict:
    try:
        data = json.loads(stream.read() or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def write(hook: dict, out: Path = HANDOFF, root: Path = ROOT) -> str:
    """Returns the one line the hook prints."""
    raw = hook.get("transcript_path") or ""
    transcript = Path(raw).expanduser() if raw else None
    if transcript is None or not transcript.is_file():
        return f"handoff: no transcript to read ({raw or 'no transcript_path'}), nothing written"
    with transcript.open(encoding="utf-8", errors="replace") as handle:
        state = walk(handle, root)
    note = render(state, hook.get("trigger") or "manual", datetime.now(UTC))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(note, encoding="utf-8")
    return f"handoff: {short_path(str(out), root)}, {len(note.splitlines())} lines"


if __name__ == "__main__":
    try:
        print(write(payload(sys.stdin)))
    except Exception as exc:  # a hook that raises is a hook that costs the session
        print(f"handoff: not written ({type(exc).__name__}: {exc})")
