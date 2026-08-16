"""Ingest every source class a human has newly approved, and nothing else.

**The problem this solves is a handover, not a computation.** A priced request can
sit at `pending` for hours or days while its journal waits on disk. When the answer
finally comes it is one word, and what has to happen next is mechanical: find the
spec, find the file, check nothing has read it already, ingest. Doing that by hand
at the end of a round, from a request block written days earlier, is how the wrong
file gets ingested under the right name.

**It refuses rather than guesses.** A class still `pending` is reported and skipped,
so this is safe to run early and often; that matters because the recipe that calls
it also ships the round, and a human should be able to rehearse the evening without
either banking something unapproved or being told the run failed.

**It reads the journal path out of the request block**, the `- journal:` line
`request_approval.py` writes, rather than taking one on the command line. The path
in the block is the file the measured figures were computed from, so a reviewer who
approved those figures approved that file.

    uv run python scripts/bank_approved.py          # report only
    uv run python scripts/bank_approved.py --write  # actually ingest
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ark.approvals import load  # noqa: E402
from ark.db import connect_read_only_patiently  # noqa: E402
from ark.evidence_types import MASTER_TYPES  # noqa: E402
from ark.sources import SOURCES  # noqa: E402

APPROVALS = ROOT / "docs/approved-sources-list.md"
DB = ROOT / "data/ark.duckdb"

_SPEC_LINE = re.compile(r"^- ingest specs?: (.+)$", re.M)
_JOURNAL_LINE = re.compile(r"^- journal: `?([^`\n]+)`?$", re.M)


def block_for(text: str, source_name: str, evidence_type: str) -> str:
    """The request block for one class, or empty if it has none."""
    heading = f"### {source_name} / {evidence_type}"
    if heading not in text:
        return ""
    body = text.split(heading, 1)[1]
    return body.split("\n### ", 1)[0]


def already_read(source_name: str, file_name: str) -> bool:
    conn = connect_read_only_patiently(DB)
    try:
        row = conn.execute(
            "SELECT count(*) FROM ingested_file WHERE source_name = ? AND file_name = ?",
            [source_name, file_name],
        ).fetchone()
    finally:
        conn.close()
    return bool(row and row[0])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="run the ingests rather than print them")
    args = ap.parse_args()

    text = APPROVALS.read_text(encoding="utf-8")
    approvals = load(APPROVALS)

    waiting, ready, done = [], [], []
    for (source_name, evidence_type), approval in sorted(approvals.items()):
        if evidence_type not in MASTER_TYPES:
            continue
        block = block_for(text, source_name, evidence_type)
        if not block:
            continue  # decided before this mechanism existed; nothing to bank
        journal = _JOURNAL_LINE.search(block)
        specs = _SPEC_LINE.search(block)
        if not journal or not specs:
            continue
        path = ROOT / journal.group(1).strip()
        keys = [s.strip().strip("`") for s in specs.group(1).split(",")]

        if approval.decision == "pending":
            waiting.append((source_name, evidence_type, path))
            continue
        if approval.decision != "master":
            continue
        for key in keys:
            if key not in SOURCES:
                print(f"  UNKNOWN SPEC {key} for {source_name}; skipping")
                continue
            if not path.is_file():
                print(f"  MISSING FILE {path} for {key}; skipping")
                continue
            if already_read(SOURCES[key].source_name, path.name):
                done.append((key, path))
            else:
                ready.append((key, path))

    for source_name, evidence_type, path in waiting:
        print(f"  still pending, not banked: {source_name} / {evidence_type}  ({path.name})")
    for key, path in done:
        print(f"  already banked: {key}  {path.name}")

    if not ready:
        print("nothing newly approved to bank.")
        return

    for key, path in ready:
        command = ["uv", "run", "ark", "ingest", key, str(path.relative_to(ROOT))]
        if not args.write:
            print("  would run: " + " ".join(command))
            continue
        print("== " + " ".join(command))
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode != 0:
            raise SystemExit(f"ingest failed for {key}; stopping before anything else runs")

    if not args.write:
        print("\ndry run. Pass --write to ingest.")


if __name__ == "__main__":
    main()
