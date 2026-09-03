"""Where the round stands, in thirty lines, from a snapshot.

Reads `data/brief.json`, written by `scripts/round/build_round_state.py` (so by
`just state`, `just cycle` and `just bank`), plus `private/handoff.md` when the
last session left one. Never the store and never the network: opening the store
waits up to 900 s on a writer's lock and the engine status runs ssh, and either
hangs a session-start hook at its 60 s default. So this reads a file and says how
old it is; a stale or missing snapshot is one line pointing at `just state`.

    uv run python scripts/agents/brief.py            # just brief
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRIEF = ROOT / "data/brief.json"
HANDOFF = ROOT / "private/handoff.md"
STALE_HOURS = 24
MAX_LINES = 30
COLLECTORS = ("supervise_cdx_pool.sh", "platform_sweep.sh")
# A word, or a relative path of words. Anything else in a command is shell.
PLAIN = re.compile(r"[A-Za-z0-9_.:=,+-]+(?:/[A-Za-z0-9_.:=,+-]+)*")


def hours_between(then: datetime, now: datetime) -> float:
    return (now - then).total_seconds() / 3600


def parse_stamp(stamp: str) -> datetime:
    when = datetime.fromisoformat(stamp)
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def collector_state(state: str) -> str:
    """A status, never a command line.

    The snapshot stores the first line of each machine's `engine_status.sh`
    section, which is `up <elapsed> <ps command>`, `NOT RUNNING`, `unreachable` or
    `UNKNOWN`. The VPS section asks over ssh with `bash -c '... pgrep -f
    supervise_cdx_pool.sh ...'`, so the remote `ps` matches the question itself and
    the stored line is that shell fragment, remote path included. Printed as it
    stands it reads as a running collector and is not one, so a command that is not
    a plain path is dropped and the line says the probe answered itself.
    """
    words = state.split()
    if not words:
        return "UNKNOWN"
    if words[0] != "up":
        return " ".join(w for w in words[:4] if PLAIN.fullmatch(w)) or "UNKNOWN"
    command = words[2:]
    if not all(PLAIN.fullmatch(w) for w in command):
        return "unclear: the status probe matched itself, run `just engines`"
    elapsed = words[1] if len(words) > 1 else "?"
    named = [c for c in COLLECTORS if any(w.endswith(c) for w in command)]
    return f"up {elapsed} {named[0]}" if named else f"up {elapsed}"


def brief_lines(snapshot: dict | None, now: datetime) -> list[str]:
    if snapshot is None:
        return ["no brief: data/brief.json is missing, run `just state`"]
    age = hours_between(parse_stamp(snapshot["written_at"]), now)
    if age > STALE_HOURS:
        return [f"brief is {age / 24:.1f} days old ({snapshot['written_at']}): run `just state`"]
    gap = snapshot["distance_to_gate_ee"]
    gate = f"{snapshot['gate_pct']:g}%"
    standing = (
        f"{abs(gap):,.0f} EE short of {gate}" if gap > 0 else f"{abs(gap):,.0f} EE past {gate}"
    )
    lines = [
        f"brief written {age:.1f} h ago ({snapshot['written_at']})",
        f"round {snapshot['round']} against {snapshot['baseline']}: "
        f"{snapshot['netnew_pairs']:,} net-new pairs, {snapshot['netnew_ee']:,.4f} EE, "
        f"{snapshot['percent']:.4f}%, {standing}",
    ]
    lines += [
        f"collector {role}: {collector_state(state)}"
        for role, state in snapshot["collectors"].items()
    ]
    waiting = snapshot["waiting_on_human"]
    lines.append(
        f"waiting on a human: {waiting['approvals']} approvals pending, "
        f"{waiting['open_decisions']} open decisions"
    )
    pending = snapshot["pending_amendments"]
    if pending:
        lines.append(f"pending in docs/brief_amendments.md ({len(pending)}):")
        lines += [f"  {row['date']}: {row['text']}" for row in pending]
    return lines


def handoff_lines(text: str | None, mtime: datetime | None, now: datetime, room: int) -> list[str]:
    """The last session's note, cut to what fits. The cut is announced, since a
    handoff that ends mid-sentence reads as complete."""
    if text is None or room < 2:
        return []
    body = [ln.rstrip() for ln in text.strip().splitlines()]
    head = [f"-- private/handoff.md, {hours_between(mtime, now):.1f} h old --"]
    if len(body) > room - 1:
        kept = max(room - 2, 0)
        body = body[:kept] + [f"({len(body) - kept} more lines in private/handoff.md)"]
    return head + body


def render(snapshot: dict | None, handoff: tuple[str, datetime] | None, now: datetime) -> str:
    lines = brief_lines(snapshot, now)
    text, mtime = handoff if handoff else (None, None)
    lines += handoff_lines(text, mtime, now, MAX_LINES - len(lines))
    return "\n".join(lines[:MAX_LINES])


def load(brief_path: Path = BRIEF, handoff_path: Path = HANDOFF) -> str:
    now = datetime.now(UTC)
    snapshot = None
    if brief_path.exists():
        snapshot = json.loads(brief_path.read_text(encoding="utf-8"))
    handoff = None
    if handoff_path.exists():
        mtime = datetime.fromtimestamp(handoff_path.stat().st_mtime, tz=UTC)
        handoff = (handoff_path.read_text(encoding="utf-8"), mtime)
    return render(snapshot, handoff, now)


if __name__ == "__main__":
    print(load())
