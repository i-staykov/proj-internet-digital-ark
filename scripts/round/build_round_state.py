"""Generate `docs/ROUND.md`: where the round stands, right now.

**Why this is generated and not written.** `docs/phase5-handoff.md` was a
hand-written snapshot of the current state. It was accurate for one day, and by
the next morning three of its claims were disproved: `alt.*` had been called the
largest open question about the corpus when it turns out to be proportionate, a
command it told you to run before ordering a queue could not run at all, and the
figures in its state table were two ingests old. **Current state is the one
category of memory that cannot be hand-maintained**, because it changes faster
than anyone updates prose, and a stale statement of it is worse than none: it
reads as authoritative.

So this assembles the answer from the programs that already own each piece rather
than restating any of it:

    ark stats              the scoreboard and the two outcomes
    round_figures.py       the five fields and the per-source split
    engine_status.sh       what both collectors are doing, and UNKNOWN when it
                           could not reach the VPS to ask
    audit_residual.py      what is on disk that nothing has read
    key-decisions.md       what is waiting on a human

Nothing here is a second copy of a figure. If a producer changes, this changes
with it.

**Staleness is detectable rather than prevented.** The file ends in a
machine-readable state line, and `--check` recomputes those counts and exits 1 if
the store has moved since the file was written. That is the honest guarantee: not
"this is current" but "you can tell in one command whether it is".

The same run writes `data/brief.json`, the snapshot `just brief` reads. That
reader must never touch the store (900 s lock wait) or ssh, since it runs from a
session-start hook, so everything it needs is copied out here while the store is
open anyway. The VPS address stays out of it: the collectors are keyed by role.

    uv run python scripts/round/build_round_state.py           # write docs/ROUND.md
    uv run python scripts/round/build_round_state.py --check    # exit 1 if it is stale
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402

from ark.approvals import pending as pending_approvals  # noqa: E402
from ark.baseline import (  # noqa: E402
    CURRENT_BASELINE_MARKER,
    CURRENT_ROUND_LABEL,
    CURRENT_ROUND_SINCE,
    REVIEWER_BASELINE_EE,
    REVIEWER_BASELINE_PAIRS,
)
from ark.db import connect_read_only_patiently  # noqa: E402
from ark.key_decisions import open_titles  # noqa: E402
from ark.stats import collect_stats, format_stats  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import added_since  # noqa: E402
from round_figures import hostname_increment  # noqa: E402

OUT = ROOT / "docs/ROUND.md"
BRIEF = ROOT / "data/brief.json"
DECISIONS = ROOT / "docs/lore/key-decisions.md"
AMENDMENTS = ROOT / "docs/brief/brief_amendments.md"
STATE_RE = re.compile(r"<!-- ark-round-state: (.*?) -->")
SECTION_RE = re.compile(r"^== (.*?) ==$", re.MULTILINE)
GATE_PCT = Decimal(5)


def read_only_store(patience_s: int = 900) -> duckdb.DuckDBPyConnection:
    """Wait out a writer rather than crashing against one. A long ingest holds the
    lock for minutes, and this is a reporting tool: waiting is correct.

    **Through `ark.db`, not a private copy of the retry loop.** This function had its
    own, so it also missed the memory and thread caps that live there, and measured
    2026-09-08 this process sat at 28 GB resident on a 36 GB laptop: DuckDB takes 80%
    of the machine unless told otherwise, and `just sync`, `just state` and `just
    cycle` each start one.
    """
    try:
        return connect_read_only_patiently(ROOT / "data/ark.duckdb", patience_s=patience_s)
    except duckdb.Error as exc:
        if "Conflicting lock" in str(exc):
            raise SystemExit(
                f"the store was still being written after {patience_s}s; "
                "re-run when the ingest finishes"
            ) from None
        raise


def run(cmd: list[str], timeout: int) -> str:
    """Capture a producer's own output. A producer that fails says so in the
    document rather than aborting the build, because a state file missing its
    collector section is still worth having."""
    try:
        done = subprocess.run(
            cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return f"(timed out after {timeout}s: {' '.join(cmd)})"
    out = (done.stdout or "") + (done.stderr or "")
    return out.strip() or f"(no output from {' '.join(cmd)})"


def headline(conn: duckdb.DuckDBPyConnection) -> dict:
    """The four counts the staleness check compares."""
    stats = collect_stats(conn)
    return {
        "pairs": stats["netnew_pairs_total"],
        "domains": stats["netnew_domains"],
        "ee": f"{stats['ee_netnew']:.4f}",
        "evidence": stats["evidence_rows"],
        "_stats": stats,
    }


def open_decisions() -> list[str]:
    """The OPEN headings, via the module that owns that block.

    Parsed in one place rather than two: this file and the cycle both need it, and a
    second copy of the parser would eventually disagree with the first about what
    counts as open, which is the failure `sources.md` already carries a scar from.
    """
    return open_titles(DECISIONS)


def collector_lines(engines: str) -> dict[str, str]:
    """One line per machine out of `engine_status.sh`: the first line under its
    `local` and `VPS (...)` sections, which is `up ...`, `NOT RUNNING` or
    `unreachable`. Keyed by role so the address never enters the brief. A run that
    produced no sections (timed out, no output) leaves both UNKNOWN, which is the
    honest reading: not asked is not idle."""
    lines = {"local": "UNKNOWN", "vps": "UNKNOWN"}
    heads = list(SECTION_RE.finditer(engines))
    for i, head in enumerate(heads):
        role = "vps" if head.group(1).startswith("VPS") else head.group(1)
        if role not in lines:
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(engines)
        body = [ln.strip() for ln in engines[head.end() : end].splitlines() if ln.strip()]
        if body:
            lines[role] = body[0][:120]
    return lines


def pending_amendments(path: Path | None = None) -> list[dict[str, str]]:
    """Rows of the amendments ledger with a cell still reading `pending`: a brief
    change intake transcribed that nobody has classified or landed yet."""
    path = path or AMENDMENTS
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if any(c.lower() == "pending" for c in cells):
            rows.append({"date": cells[0], "text": cells[1][:120] if len(cells) > 1 else ""})
    return rows


def brief(
    head: dict,
    engines: str,
    approvals: int,
    decisions: int,
    hostnames: tuple[int, Decimal] | None = None,
    window: dict | None = None,
) -> dict:
    """The snapshot `scripts/agents/brief.py` prints. Small on purpose: it is
    injected into every session start, and thirty lines is the budget."""
    stats = head["_stats"]
    # **Both units, or the brief understates the round by most of it.** `ee_netnew` is the
    # registrable half alone. Hostnames beneath a held registrable have been annual records
    # at full weight since 2026-09-01 and the shipped report counts them (`fill_report`
    # adds them for exactly this reason), so a gate distance taken from registrables alone
    # is wrong by the hostname half: measured 2026-09-08, 54,599 EE against a real
    # 991,394, which read as 1.63M short of the gate when the true distance was 691k. That
    # figure is injected into every session start, so it was the first thing every session
    # believed.
    host_pairs, host_ee = hostnames if hostnames is not None else hostname_increment()
    ee = stats["ee_netnew"] + host_ee
    gate_ee = REVIEWER_BASELINE_EE * GATE_PCT / 100
    win = window or {}
    round_ee = Decimal(str(win.get("ee", 0)))
    return {
        "written_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "baseline": CURRENT_BASELINE_MARKER,
        "round": CURRENT_ROUND_LABEL,
        "netnew_pairs": head["pairs"] + host_pairs,
        "netnew_domains": head["domains"],
        "netnew_ee": round(float(ee), 4),
        "registrable_ee": round(float(stats["ee_netnew"]), 4),
        "hostname_ee": round(float(host_ee), 4),
        "percent": round(float(ee / REVIEWER_BASELINE_EE * 100), 4),
        "gate_pct": float(GATE_PCT),
        "distance_to_gate_ee": round(float(gate_ee - ee), 4),
        # **The gate is taken on THIS round's window, not on the total.** The total is
        # everything net-new against his current release, and his release still lacks the
        # round already sent to him, so it carries the last round inside it: on the day
        # round 10 opened it read 5.36% and would have reported a crossing with nothing
        # collected. The window figures are `added_since.py`'s, over both units.
        "round_since": CURRENT_ROUND_SINCE,
        "round_pairs": int(win.get("records", 0)),
        "round_ee": round(float(round_ee), 4),
        "round_percent": round(float(round_ee / REVIEWER_BASELINE_EE * 100), 4),
        "round_distance_to_gate_ee": round(float(gate_ee - round_ee), 4),
        "collectors": collector_lines(engines),
        "waiting_on_human": {"approvals": approvals, "open_decisions": decisions},
        "pending_amendments": pending_amendments(),
    }


def build() -> tuple[str, dict, dict]:
    conn = read_only_store()
    try:
        head = headline(conn)
    finally:
        conn.close()

    # Nine seconds against the store, read-only, so the hourly bank can afford it and
    # every reader of the brief gets the round's own progress rather than the total.
    window = added_since.measure()

    # Producers run after the store connection is closed, because two of them open
    # it themselves and DuckDB allows many readers only when no writer is waiting.
    figures = run(["uv", "run", "python", "scripts/round/round_figures.py"], timeout=900)
    engines = run(["bash", "scripts/engines/engine_status.sh"], timeout=120)
    residual = run(["uv", "run", "python", "scripts/harness/audit_residual.py"], timeout=900)

    decisions = open_decisions()
    waiting = pending_approvals()
    parts = [
        "# Where the round stands",
        "",
        "**Generated by `just state`. Do not edit: every number here belongs to another program,",
        "and a hand edit makes this disagree with the store rather than correcting it.**",
        "",
        f"Measured against **{CURRENT_BASELINE_MARKER}**, the reviewer's current release:",
        f"{REVIEWER_BASELINE_PAIRS:,} pairs and {REVIEWER_BASELINE_EE:,.4f} equivalent-English.",
        f"The round window opens at `{CURRENT_ROUND_SINCE}`, held in `src/ark/baseline.py`.",
        "",
        "Run `just state --check` to find out whether this file is still current. It compares",
        "the counts in its own footer against the store and exits 1 if the store has moved.",
        "",
        "---",
        "",
        "## The scoreboard",
        "",
        "```",
        format_stats(head["_stats"]),
        "```",
        "",
        "## The five fields, and the per-source split",
        "",
        "The format the reviewer set. Send with `--verify`, which re-scores the increment with his",
        "own calculator and refuses the numbers if his validator rejects a record we counted.",
        "",
        "```",
        figures,
        "```",
        "",
        "## The collectors, right now",
        "",
        "**`UNKNOWN` is not `nothing to fetch`.** It means the VPS could not be reached",
        "to ask, and a journal left on its disk is work already paid for and not banked.",
        "",
        "```",
        engines,
        "```",
        "",
        "## What is on disk that nothing has read",
        "",
        "```",
        residual,
        "```",
        "",
        "## Waiting on a human",
        "",
        "**Source classes awaiting classification.** Ingest refuses these, so their journals sit",
        "on disk untouched until a `Decision:` line in",
        "`docs/registers/approved-sources-list.md` says",
        "otherwise. Each one is also raised under `## OPEN` in",
        "`docs/lore/key-decisions.md`, which is",
        "the only surface Ivo reads. Nothing is lost by leaving them; nothing enters an annual",
        "file while they wait.",
        "",
    ]
    if waiting:
        parts += [
            f"- **{a.source_name} / {a.evidence_type}** (approved-sources-list.md:{a.line})"
            for a in waiting
        ]
    else:
        parts += ["Nothing pending in `docs/registers/approved-sources-list.md`."]
    parts += ["", "**Open decisions.**", ""]
    if decisions:
        parts += [f"- {d}" for d in decisions]
        parts += ["", "Full context in `docs/lore/key-decisions.md`."]
    else:
        parts += ["Nothing open in `docs/lore/key-decisions.md`."]
    parts += [
        "",
        "---",
        "",
        "State line, used by `--check` to detect that this file has gone stale:",
        "",
        f"<!-- ark-round-state: pairs={head['pairs']} domains={head['domains']} "
        f"ee={head['ee']} evidence={head['evidence']} -->",
        "",
    ]
    return "\n".join(parts), head, brief(head, engines, len(waiting), len(decisions), window=window)


def parse_state(text: str) -> dict[str, str] | None:
    found = STATE_RE.search(text)
    if not found:
        return None
    return dict(pair.split("=", 1) for pair in found.group(1).split())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if docs/ROUND.md is missing or its counts no longer match the store",
    )
    args = ap.parse_args()

    if args.check:
        if not OUT.exists():
            raise SystemExit(f"{OUT.relative_to(ROOT)} does not exist: run `just state`")
        recorded = parse_state(OUT.read_text(encoding="utf-8"))
        if recorded is None:
            raise SystemExit(f"{OUT.relative_to(ROOT)} carries no state line: run `just state`")
        conn = read_only_store()
        try:
            head = headline(conn)
        finally:
            conn.close()
        drift = {
            key: (recorded.get(key), str(head[key]))
            for key in ("pairs", "domains", "ee", "evidence")
            if recorded.get(key) != str(head[key])
        }
        if drift:
            for key, (was, now) in drift.items():
                print(f"  {key}: file says {was}, store says {now}")
            raise SystemExit("docs/ROUND.md is stale: run `just state`")
        print(f"docs/ROUND.md is current: {head['pairs']:,} pairs, {head['ee']} EE")
        return

    body, head, snapshot = build()
    OUT.write_text(body, encoding="utf-8")
    BRIEF.parent.mkdir(parents=True, exist_ok=True)
    BRIEF.write_text(json.dumps(snapshot, indent=1) + "\n", encoding="utf-8")
    # **Print the round, not half of it.** `head` is the registrable unit alone, so this line
    # read "71,379 net-new pairs, 54601.6080 equivalent-English" for a round holding 1,820,780
    # records and 1,106,725 EE. `brief()` already sums both units for exactly this reason; the
    # line a human actually reads was still quoting one of them, and it is the line that gets
    # pasted into a message.
    print(
        f"wrote {OUT.relative_to(ROOT)}: {snapshot['netnew_pairs']:,} net-new records "
        f"({head['pairs']:,} registrable, {snapshot['netnew_pairs'] - head['pairs']:,} hostname), "
        f"{snapshot['netnew_ee']:,.4f} equivalent-English, {snapshot['percent']}% of "
        f"{snapshot['baseline']}, {snapshot['distance_to_gate_ee']:,.2f} EE short of "
        f"{snapshot['gate_pct']}%"
    )


if __name__ == "__main__":
    main()
