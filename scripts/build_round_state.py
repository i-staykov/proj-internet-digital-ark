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

    uv run python scripts/build_round_state.py           # write docs/ROUND.md
    uv run python scripts/build_round_state.py --check    # exit 1 if it is stale
"""

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402

from ark.approvals import pending as pending_approvals  # noqa: E402
from ark.baseline import (  # noqa: E402
    CURRENT_BASELINE_MARKER,
    CURRENT_ROUND_SINCE,
    REVIEWER_BASELINE_EE,
    REVIEWER_BASELINE_PAIRS,
)
from ark.stats import collect_stats, format_stats  # noqa: E402

OUT = ROOT / "docs/ROUND.md"
DECISIONS = ROOT / "docs/key-decisions.md"
STATE_RE = re.compile(r"<!-- ark-round-state: (.*?) -->")


def read_only_store(patience_s: int = 900) -> duckdb.DuckDBPyConnection:
    """Wait out a writer rather than crashing against one. A long ingest holds the
    lock for minutes, and this is a reporting tool: waiting is correct."""
    deadline = time.monotonic() + patience_s
    while True:
        try:
            return duckdb.connect(str(ROOT / "data/ark.duckdb"), read_only=True)
        except duckdb.Error as exc:
            if "Conflicting lock" not in str(exc):
                raise
            if time.monotonic() >= deadline:
                raise SystemExit(
                    f"the store was still being written after {patience_s}s; "
                    "re-run when the ingest finishes"
                ) from None
            time.sleep(3)


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
    if not DECISIONS.exists():
        return []
    body = DECISIONS.read_text(encoding="utf-8")
    block = body.split("## OPEN", 1)[-1].split("## CLOSED", 1)[0]
    return [line[4:].strip() for line in block.splitlines() if line.startswith("### ")]


def build() -> tuple[str, dict]:
    conn = read_only_store()
    try:
        head = headline(conn)
    finally:
        conn.close()

    # Producers run after the store connection is closed, because two of them open
    # it themselves and DuckDB allows many readers only when no writer is waiting.
    figures = run(["uv", "run", "python", "scripts/round_figures.py"], timeout=900)
    engines = run(["bash", "scripts/engine_status.sh"], timeout=120)
    residual = run(["uv", "run", "python", "scripts/audit_residual.py"], timeout=900)

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
        "on disk untouched until a `Decision:` line in `docs/open-approvals.md` says otherwise.",
        "Nothing is lost by leaving them; nothing enters an annual file while they wait.",
        "",
    ]
    if waiting:
        parts += [
            f"- **{a.source_name} / {a.evidence_type}** (open-approvals.md:{a.line})"
            for a in waiting
        ]
    else:
        parts += ["Nothing pending in `docs/open-approvals.md`."]
    parts += ["", "**Open decisions.**", ""]
    if decisions:
        parts += [f"- {d}" for d in decisions]
        parts += ["", "Full context in `docs/key-decisions.md`."]
    else:
        parts += ["Nothing open in `docs/key-decisions.md`."]
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
    return "\n".join(parts), head


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

    body, head = build()
    OUT.write_text(body, encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(ROOT)}: {head['pairs']:,} net-new pairs, "
        f"{head['domains']:,} net-new domains, {head['ee']} equivalent-English"
    )


if __name__ == "__main__":
    main()
