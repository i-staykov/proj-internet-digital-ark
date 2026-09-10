"""One page a phone can read: where the round stands, and what is waiting on a human.

**Why this exists.** Everything the unattended laptop knows is written to files on the
laptop: the brief, the collector log, the sync log. A collector that dies on the second
day of a week away is invisible until somebody opens a terminal, and the round is gone by
then. So once a day this reads what the machine already measured and posts it as one
comment on one issue, which is a surface a phone can open.

**It measures nothing itself.** Every figure is read from `data/brief.json`, which the
hourly bank writes at the end of its run, or from the mtimes of the journals the sweeps
close. A digest that re-derived the round would be a second opinion nobody asked for, and
the two would drift.

**The absence of a comment is a signal too.** If the laptop sleeps or the job is unloaded,
no digest appears, which is the one failure this cannot report on its own.

    uv run python scripts/harness/vacation_digest.py            # print it
    uv run python scripts/harness/vacation_digest.py --write    # post it
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/harness"))

from rank_triage import DOC as TRIAGE_DOC  # noqa: E402
from rank_triage import (  # noqa: E402
    TRIAGE_HEADING,  # noqa: E402
    parse_entries,
    split_section,
)

from ark.approvals import pending as pending_approvals  # noqa: E402
from ark.key_decisions import open_titles  # noqa: E402

REPO = "i-staykov/proj-internet-digital-ark"
TITLE_PREFIX = "Unattended status"
BRIEF = ROOT / "data/brief.json"
JOURNALS = ROOT / "data/raw/cdx_suffix"

# **Nothing shaped like an address leaves this machine.** The repository is public and the
# collector host is not in it; the same filter guards the ship-now comment. It is a filter
# and not a check, because a digest that refused to post over one stray line would be a
# digest nobody gets.
_ADDRESS = re.compile(r"\b\d{1,3}(\.\d{1,3}){3}\b|@")

STALL_HOURS = 4.0
BRIEF_STALL_HOURS = 3.0


def hours_since(stamp: float, now: float) -> float:
    return (now - stamp) / 3600


def journal_activity(now: float, root: Path = JOURNALS) -> tuple[int, float | None]:
    """(journals written in the last 24 hours, hours since the newest one)."""
    times = [p.stat().st_mtime for p in root.glob("suffix_*.jsonl.gz")] if root.is_dir() else []
    if not times:
        return 0, None
    day = sum(1 for t in times if now - t < 86400)
    return day, hours_since(max(times), now)


def clients() -> int:
    """Archive clients here, as `collectors.sh` defines one.

    Counting processes doubles it: one client is a `uv run` wrapper plus its python
    child. The definition lives in one place, so this asks that place rather than
    keeping a second copy of it. The remote question is skipped, because the answer
    wanted here is what this laptop is spending, and an ssh timeout would cost the
    digest eight seconds for a number it does not print.
    """
    done = subprocess.run(
        ["bash", "scripts/harness/collectors.sh", "status"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**os.environ, "ARK_NO_REMOTE": "1"},
    )
    found = re.search(r"^clients:\s+(\d+) here", done.stdout, re.M)
    return int(found.group(1)) if found else 0


def triage_top(limit: int = 5, docs: list[Path] | None = None) -> tuple[int, list[tuple[int, str]]]:
    """(how many are open, the best `limit` of them).

    Two pages, because the queue was split on 2026-09-03: new finds land in
    `approved-sources-list.md` under its triage heading, and the backlog that was
    already open moved to `hypotheses-pending.md`. Both carry the same `- potential:`
    line, so both are read with the same parser and ranked together.
    """
    pages = docs or [ROOT / TRIAGE_DOC, ROOT / "docs/registers/hypotheses-pending.md"]
    open_ones: list[tuple[int, str]] = []
    for path in pages:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        body = split_section(text)[1] if TRIAGE_HEADING in text else text
        try:
            _, entries = parse_entries(body)
        except Exception:
            continue
        open_ones += [(score, title) for score, title, _block, decided in entries if not decided]
    return len(open_ones), sorted(open_ones, key=lambda row: -row[0])[:limit]


def compose(brief: dict, now: float | None = None) -> tuple[str, str]:
    """(title, body). The title carries the alarm, because that is all a phone shows."""
    now = now or time.time()
    written = datetime.fromisoformat(brief["written_at"]).timestamp()
    brief_age = hours_since(written, now)
    day, since_journal = journal_activity(now)
    running = clients()
    free_gib = shutil.disk_usage(ROOT).free / 1024**3

    gap = brief.get("round_distance_to_gate_ee", brief["distance_to_gate_ee"])
    gate_ee = brief["round_ee"] + gap if "round_ee" in brief else None
    share = (brief["round_ee"] / gate_ee * 100) if gate_ee else 0.0

    stalled = []
    if since_journal is None or since_journal > STALL_HOURS:
        stalled.append("collectors quiet")
    if brief_age > BRIEF_STALL_HOURS:
        stalled.append("sync quiet")
    stamp = datetime.fromtimestamp(now, UTC).strftime("%Y-%m-%d %H:%M UTC")
    mark = f"STALLED ({', '.join(stalled)}): " if stalled else ""
    title = f"{mark}round {brief['round']} at {share:.1f}% of the gate, {stamp}"

    approvals = pending_approvals()
    priced = [a for a in approvals if not a.is_triage]
    lines = [
        f"### {stamp}",
        "",
        f"**Round {brief['round']}** since {str(brief.get('round_since', '?'))[:10]}: "
        f"{brief.get('round_pairs', 0):,} records, {brief.get('round_ee', 0):,.0f} EE, "
        f"**{share:.1f}%** of the 5% gate ({abs(gap):,.0f} EE {'short' if gap > 0 else 'past'}).",
        "",
        f"- collectors: {running} of 2 clients, {day} journals closed in 24 h, "
        + (f"last write {since_journal:.1f} h ago" if since_journal is not None else "none yet"),
        f"- last bank: {brief_age:.1f} h ago. Free space: {free_gib:,.0f} GiB.",
        f"- waiting on you: {len(priced)} priced classes, {len(open_titles())} open decisions.",
        "",
    ]
    if priced:
        lines += ["**Priced and waiting for a word** (merge the PR to bank it):", ""]
        lines += [f"- `{a.source_name}` / {a.evidence_type}" for a in priced]
        lines += [""]
    open_count, top = triage_top()
    if top:
        lines += [f"**{open_count} sources found and not priced**, best first:", ""]
        lines += [f"- {score}: {title_}" for score, title_ in top]
        lines += [""]
    lines += [
        "Nothing here was measured by this comment: the figures are the hourly bank's, "
        "read out of `data/brief.json`. No comment at all on a given day means the laptop "
        "or the job stopped, which is the one thing this cannot report itself.",
    ]
    body = "\n".join(line for line in lines if not _ADDRESS.search(line))
    return title, body


def gh(args: list[str]) -> tuple[int, str]:
    done = subprocess.run(["gh", *args], capture_output=True, text=True)
    return done.returncode, (done.stdout or done.stderr).strip()


def post(title: str, body: str, repo: str = REPO) -> str:
    """One issue, many comments: a new issue a day would be a mailbox, not a noticeboard."""
    code, out = gh(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--search",
            f"in:title {TITLE_PREFIX}",
            "--json",
            "number,title",
            "--jq",
            f'.[] | select(.title | startswith("{TITLE_PREFIX}")) | .number',
        ]
    )
    if code != 0:
        return f"digest not posted: `gh issue list` failed: {out}"
    number = out.split("\n")[0].strip() if out.strip() else ""
    if not number:
        code, out = gh(
            [
                "issue",
                "create",
                "--repo",
                repo,
                "--title",
                f"{TITLE_PREFIX}: the unattended run",
                "--body",
                body,
            ]
        )
        return f"opened the status issue: {out}" if code == 0 else f"digest not posted: {out}"
    code, out = gh(["issue", "comment", number, "--repo", repo, "--body", body])
    if code != 0:
        return f"digest not posted: `gh issue comment` failed: {out}"
    # The title carries the alarm, so it is rewritten every day rather than left at the
    # state of the day the issue was opened.
    gh(["issue", "edit", number, "--repo", repo, "--title", f"{TITLE_PREFIX}: {title}"])
    return f"posted to #{number}: {title}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="post it, rather than printing it")
    ap.add_argument("--repo", default=REPO)
    args = ap.parse_args()
    if not BRIEF.is_file():
        print("no data/brief.json: run `just state` first")
        return 1
    title, body = compose(json.loads(BRIEF.read_text(encoding="utf-8")))
    if not args.write:
        print(title)
        print()
        print(body)
        return 0
    print(post(title, body, args.repo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
