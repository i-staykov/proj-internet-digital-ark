"""Generate `docs/ROUND.md` and `data/brief.json`: where the round stands, right now.

**Current state is the one category of memory that cannot be hand-maintained**: it changes
faster than anyone updates prose, and a stale statement of it reads as authoritative. So this
assembles the answer from the programs that own each piece rather than restating any of it:

    round_figures.py       the five fields, from the claim export's files
    ark.approvals          what is waiting on a human: the pending register rows
    ark stats              the scoreboard, with --full
    audit_residual.py      what is on disk that nothing has read, with --full

By default it reads files and never the store, so the bank writes it while it holds the writer,
and `just state` runs the same. `--full` adds the two store sections, read-only.

The brief takes fields 3 to 5 as the very strings ROUND.md prints, so every reader quotes one
field 5. `just brief` prints it from a session-start hook, so it stays small.

**Staleness is detectable rather than prevented.** The footer holds his release's marker and
the sha256 of every claim file, and `--check` re-hashes them, with no store, and exits 1 on any
change.

    uv run python scripts/round/build_round_state.py            # write docs/ROUND.md
    uv run python scripts/round/build_round_state.py --full     # plus the store sections
    uv run python scripts/round/build_round_state.py --check    # exit 1 if it is stale
"""

import argparse
import hashlib
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

from ark import db, export  # noqa: E402
from ark.approvals import pending as pending_approvals  # noqa: E402
from ark.baseline import (  # noqa: E402
    CURRENT_BASELINE_MARKER,
    CURRENT_ROUND_LABEL,
    CURRENT_ROUND_SINCE,
    REVIEWER_BASELINE_EE,
    REVIEWER_BASELINE_PAIRS,
)
from ark.stats import collect_stats, format_stats  # noqa: E402

OUT = ROOT / "docs/ROUND.md"
BRIEF = ROOT / "data/brief.json"
AMENDMENTS = ROOT / "docs/brief/brief_amendments.md"
STATE_RE = re.compile(r"<!-- ark-round-state: (.*?) -->")
GATE_PCT = Decimal(5)
# Fields 3 to 5 exactly as round_figures prints them.
FIELD_RE = {
    "3": re.compile(r"^3\. .*: ([0-9,]+) records$", re.M),
    "4": re.compile(r"^4\. .*: ([0-9,.]+)$", re.M),
    "5": re.compile(r"^5\. .*: ([0-9.]+)%$", re.M),
}
STALE = "docs/ROUND.md is stale: the next bank rewrites it, or run `just state`"


def read_only_store(patience_s: int = 900) -> duckdb.DuckDBPyConnection:
    """Wait out a writer rather than crashing against one: this is a reporting tool. Through
    `ark.db`, which carries the memory and thread caps. Only `--full` calls it."""
    try:
        return db.connect_read_only_patiently(ROOT / "data/ark.duckdb", patience_s=patience_s)
    except duckdb.Error as exc:
        if "Conflicting lock" in str(exc):
            raise SystemExit(
                f"the store was still being written after {patience_s}s; "
                "re-run when the ingest finishes"
            ) from None
        raise


def run(cmd: list[str], timeout: int) -> str:
    """Capture a producer's own output. A producer that fails says so in the
    document rather than aborting the build, because a state file missing one
    section is still worth having."""
    try:
        done = subprocess.run(
            cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return f"(timed out after {timeout}s: {' '.join(cmd)})"
    out = (done.stdout or "") + (done.stderr or "")
    return out.strip() or f"(no output from {' '.join(cmd)})"


def claim_state() -> dict[str, str]:
    """His release's marker, then each claim file's sha256 by its path under `output/`."""
    state = {"baseline": CURRENT_BASELINE_MARKER}
    for path in export.claim_files(ROOT / export.NETNEW_DIR, ROOT / export.CANDIDATES_PATH):
        rel = path.relative_to(ROOT / "output").as_posix()
        if path.is_file():
            with path.open("rb") as fh:
                state[rel] = hashlib.file_digest(fh, "sha256").hexdigest()
        else:
            state[rel] = "missing"
    return state


def export_problem() -> str | None:
    """Why `output/netnew` cannot be quoted, or None. An export with no stamp crashed or came
    before stamps, and one diffed against another release counts against the wrong one."""
    stamp = export.read_stamp(ROOT / export.NETNEW_DIR)
    if stamp is None:
        found = "holds no export stamp"
    elif stamp.get("baseline") != CURRENT_BASELINE_MARKER:
        found = f"was diffed against {stamp.get('baseline')}, not {CURRENT_BASELINE_MARKER}"
    else:
        return None
    return f"output/netnew {found}: the next bank re-exports it, or `just bank --force`"


def parse_fields(figures: str) -> dict[str, str] | None:
    """Fields 3 to 5 as printed, or None when round_figures did not print all three."""
    found = {key: rx.search(figures) for key, rx in FIELD_RE.items()}
    if not all(found.values()):
        return None
    return {key: m.group(1) for key, m in found.items()}


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


def brief(fields: dict[str, str] | None, approvals: int) -> dict:
    """The snapshot `scripts/agents/brief.py` prints. Without the five fields it carries no
    `field5_percent`, and every reader refuses rather than quote a figure of its own."""
    snapshot = {
        "written_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "baseline": CURRENT_BASELINE_MARKER,
        "round": CURRENT_ROUND_LABEL,
    }
    if fields:
        ee = Decimal(fields["4"].replace(",", ""))
        snapshot |= {
            "netnew_pairs": int(fields["3"].replace(",", "")),
            "netnew_ee": float(ee),
            # a string, so the trailing zeros ROUND.md prints survive `jq -r`
            "field5_percent": fields["5"],
            "distance_to_gate_ee": round(float(REVIEWER_BASELINE_EE * GATE_PCT / 100 - ee), 4),
        }
    return snapshot | {
        "gate_pct": float(GATE_PCT),
        "waiting_on_human": {"approvals": approvals},
        "pending_amendments": pending_amendments(),
    }


def build(full: bool = False) -> tuple[str, dict]:
    # Hashed before the figures run: a file that changes in between reads as stale, never
    # as current.
    state = claim_state()
    scoreboard = residual = None
    if full:
        conn = read_only_store()
        try:
            scoreboard = format_stats(collect_stats(conn))
        finally:
            conn.close()
    # Producers run after the store connection is closed, because under --full they open it
    # themselves and DuckDB allows many readers only when no writer is waiting.
    figures = export_problem() or run(
        ["uv", "run", "python", "scripts/round/round_figures.py", *(["--full"] if full else [])],
        timeout=900,
    )
    if full:
        residual = run(["uv", "run", "python", "scripts/harness/audit_residual.py"], timeout=900)

    waiting = pending_approvals()
    parts = [
        "# Where the round stands",
        "",
        "**Generated by `scripts/round/build_round_state.py`. Do not edit: every number here",
        "belongs to another program, and a hand edit makes this disagree with its owner rather",
        "than correcting it.**",
        "",
        f"Measured against **{CURRENT_BASELINE_MARKER}**, the reviewer's current release:",
        f"{REVIEWER_BASELINE_PAIRS:,} pairs and {REVIEWER_BASELINE_EE:,.4f} equivalent-English.",
    ]
    if full:
        parts += [
            f"The round window opens at `{CURRENT_ROUND_SINCE}`, held in `src/ark/baseline.py`."
        ]
    parts += [
        "",
        "Run `just state --check` to find out whether this file is still current. It compares",
        "the claim files' sha256s against its footer and exits 1 if any has changed.",
        "",
        "---",
        "",
    ]
    if scoreboard is not None:
        parts += ["## The scoreboard", "", "```", scoreboard, "```", ""]
    parts += [
        "## The five fields, and the per-source split",
        "",
        "The format the reviewer set. Send with `--verify`, which re-scores the increment with his",
        "own calculator and refuses the numbers if his validator rejects a record we counted.",
        "",
        "```",
        figures,
        "```",
        "",
    ]
    if residual is not None:
        parts += ["## What is on disk that nothing has read", "", "```", residual, "```", ""]
    parts += [
        "## Waiting on a human",
        "",
        "**Source classes awaiting classification.** Ingest refuses these, so their journals sit",
        "on disk untouched until a `Decision:` line in",
        "`docs/registers/approved-sources-list.md` says",
        "otherwise. Each one at or above the filing floor, unless it waits only on work, is also",
        "an issue labelled `needs-owner` with a one-line pull request, which",
        "`scripts/harness/sync_approvals.py` files. Nothing is lost by leaving them; nothing",
        "enters an annual file while they wait.",
        "",
    ]
    if waiting:
        parts += [
            f"- **{a.source_name} / {a.evidence_type}** (approved-sources-list.md:{a.line})"
            for a in waiting
        ]
    else:
        parts += ["Nothing pending in `docs/registers/approved-sources-list.md`."]
    parts += [
        "",
        "---",
        "",
        "State line, used by `--check` to detect that this file has gone stale:",
        "",
        f"<!-- ark-round-state: {' '.join(f'{k}={v}' for k, v in state.items())} -->",
        "",
    ]
    return "\n".join(parts), brief(parse_fields(figures), len(waiting))


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
        help="exit 1 if docs/ROUND.md is missing or a claim file no longer matches its footer",
    )
    ap.add_argument(
        "--full",
        action="store_true",
        help="also read the store: the scoreboard and what is on disk that nothing has read",
    )
    args = ap.parse_args()

    if args.check:
        if not OUT.exists():
            raise SystemExit(f"{OUT.relative_to(ROOT)} does not exist: run `just state`")
        recorded = parse_state(OUT.read_text(encoding="utf-8"))
        if recorded is None:
            raise SystemExit(f"{OUT.relative_to(ROOT)} carries no state line: run `just state`")
        problem = export_problem()
        if problem:
            raise SystemExit(problem)
        now = claim_state()
        drift = sorted(k for k in now.keys() | recorded.keys() if recorded.get(k) != now.get(k))
        if drift:
            for key in drift:
                print(f"  {key}: changed")
            raise SystemExit(STALE)
        print(f"docs/ROUND.md is current: its footer matches the {len(now) - 1} claim files")
        return

    body, snapshot = build(args.full)
    OUT.write_text(body, encoding="utf-8")
    BRIEF.parent.mkdir(parents=True, exist_ok=True)
    BRIEF.write_text(json.dumps(snapshot, indent=1) + "\n", encoding="utf-8")
    if "field5_percent" not in snapshot:
        raise SystemExit(
            f"wrote {OUT.relative_to(ROOT)} without the five fields, so data/brief.json carries "
            f"no field 5: {export_problem() or 'round_figures.py failed'}"
        )
    print(
        f"wrote {OUT.relative_to(ROOT)}: field 3 {snapshot['netnew_pairs']:,} records, "
        f"field 4 {snapshot['netnew_ee']:,.4f} EE, field 5 {snapshot['field5_percent']}%, "
        f"{snapshot['distance_to_gate_ee']:,.4f} EE short of {GATE_PCT}%"
    )


if __name__ == "__main__":
    main()
