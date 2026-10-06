"""Where the round stands, in thirty lines, from a snapshot.

Reads `data/brief.json`, which `just bank` and `just state` write, the hold file `just hold`
writes, the names at the root and in `data/`, and `private/handoff.md` when the last session
left one. Stdlib only, never the store and
never the network: the SessionStart hook stops it at 10 s, and opening the store waits
up to 900 s on a writer's lock. So this reads a file and says how old it is. Field 5 and
the gate are quoted as the snapshot spells them; a stale or missing snapshot, or one without
the gate, is one line saying where to look.

    uv run python scripts/agents/brief.py            # just brief
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRIEF = ROOT / "data/brief.json"
HANDOFF = ROOT / "private/handoff.md"
HOLD = Path(os.environ.get("ARK_STATE_DIR", Path.home() / "ark/state")) / "hold"
STALE_HOURS = 24
MAX_LINES = 30

# Every name that may sit at the root or in `data/`, tracked or not. A new one lands here with
# the code that writes it; anything else is moved into place or deleted.
LAYOUT = {
    "": {
        *(".claude", ".gitattributes", ".github", ".gitignore", ".python-version", "AGENTS.md"),
        *("README.md", "data", "docs", "hooks", "justfile", "probes", "pyproject.toml"),
        *("scripts", "seeds", "src", "submissions", "tests", "uv.lock"),
        *(".git", ".venv", ".pytest_cache", ".ruff_cache", ".DS_Store", "local.env", "private"),
        *("output", "ding"),
    },
    "data": {
        *("baseline.json", "raw", "logs", "held", "seeds", "staging", "audit", "reports"),
        *("exports", "fleet_findings", "archive", "ark.duckdb", "ark.duckdb.wal", "duckdb_tmp"),
        *("queue.sqlite", "brief.json", "banked_slugs.txt", "offsite-manifest.tsv"),
        *("SHA256SUMS", "SHA256SUMS.stat", "SHA1SUMS", ".DS_Store"),
    },
}


def hours_between(then: datetime, now: datetime) -> float:
    return (now - then).total_seconds() / 3600


def parse_stamp(stamp: str) -> datetime:
    when = datetime.fromisoformat(stamp)
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def brief_lines(snapshot: dict | None, now: datetime) -> list[str]:
    if snapshot is None:
        return ["no brief: data/brief.json is missing, run `just state`"]
    age = hours_between(parse_stamp(snapshot["written_at"]), now)
    if age > STALE_HOURS:
        return [f"brief is {age / 24:.1f} days old ({snapshot['written_at']}): run `just state`"]
    if "gate_percent" not in snapshot:
        return ["brief carries no gate figure: docs/ROUND.md says why"]
    gap = snapshot["distance_to_gate_ee"]
    gate = f"{snapshot['gate_pct']:g}%"
    standing = (
        f"{abs(gap):,.0f} EE short of {gate}" if gap > 0 else f"{abs(gap):,.0f} EE past {gate}"
    )
    lines = [
        f"brief written {age:.1f} h ago ({snapshot['written_at']})",
        f"round {snapshot['round']} against {snapshot['baseline']}: "
        f"field 3 {snapshot['netnew_pairs']:,} records, field 4 {snapshot['netnew_ee']:,.4f} EE, "
        f"field 5 {snapshot['field5_percent']}%, gate {snapshot['gate_percent']}% of 1996 to 2015, "
        f"{standing}",
        f"waiting on a human: {snapshot['waiting_on_human']['approvals']} approvals pending",
    ]
    pending = snapshot["pending_amendments"]
    if pending:
        lines.append(f"pending in docs/brief/brief_amendments.md ({len(pending)}):")
        lines += [f"  {row['date']}: {row['text']}" for row in pending]
    return lines


def hold_line(text: str | None) -> str:
    """The hold file is `human`, a UTC stamp, then one held name per line."""
    if text is None:
        return "held: nothing"
    lines = text.splitlines()
    stamp = lines[1] if len(lines) > 1 else "no stamp"
    return f"held since {stamp}: {' '.join(lines[2:]) or 'no names'} (`just hold status`)"


def strays(root: Path = ROOT) -> list[str]:
    """Names outside LAYOUT, as paths from the root."""
    out = []
    for sub, allowed in LAYOUT.items():
        folder = root / sub
        if folder.is_dir():
            out += [
                str(Path(sub) / p.name) for p in sorted(folder.iterdir()) if p.name not in allowed
            ]
    return out


def layout_line(names: list[str]) -> list[str]:
    return [f"outside brief.py LAYOUT: {' '.join(names)}"] if names else []


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


def render(
    snapshot: dict | None,
    handoff: tuple[str, datetime] | None,
    now: datetime,
    hold: str | None = None,
    stray: list[str] | None = None,
) -> str:
    lines = brief_lines(snapshot, now) + [hold_line(hold)] + layout_line(stray or [])
    text, mtime = handoff if handoff else (None, None)
    lines += handoff_lines(text, mtime, now, MAX_LINES - len(lines))
    return "\n".join(lines[:MAX_LINES])


def load(brief_path: Path = BRIEF, handoff_path: Path = HANDOFF, hold_path: Path = HOLD) -> str:
    now = datetime.now(UTC)
    snapshot = None
    if brief_path.exists():
        snapshot = json.loads(brief_path.read_text(encoding="utf-8"))
    handoff = None
    if handoff_path.exists():
        mtime = datetime.fromtimestamp(handoff_path.stat().st_mtime, tz=UTC)
        handoff = (handoff_path.read_text(encoding="utf-8"), mtime)
    hold = hold_path.read_text(encoding="utf-8") if hold_path.exists() else None
    return render(snapshot, handoff, now, hold, strays())


if __name__ == "__main__":
    print(load())
