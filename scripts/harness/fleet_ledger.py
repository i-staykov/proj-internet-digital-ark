"""The laptop's one reader and writer of the fleet's keyed ledger, `ledger/YYYY-MM.jsonl`.

The fleet's `scripts/ledger.py` owns the format and the keys. This module reads the month
files the way it does and appends only through its command line, so a key is built in one
place and a replay adds nothing: `append --kind K --json -` keeps a line whose kind and key
are already in any month's file.

    lines(fleet, kind[, ref])   every line of one kind, month files in name order, then file order
    append(fleet, kind, rows)   one `ledger.py append --kind K --json -` run over the fleet clone
    streak(outcomes)            whether the last STREAK finds with a store figure agree within 1%

**The fleet clone may predate the ledger.** Until it holds `scripts/ledger.py`, `append`
writes nothing and says why, and `lines` finds no files and returns nothing, so a caller
keeps what it would have converted and the next tick tries again.

**An outcome line** is the laptop's booking of one confirmed FIND: `slug`, `store_ee` (the
live-store re-price), `program_ee` (the program's figure on the pushed snapshot),
`agreement_pct` (`100 * program_ee / store_ee`), the register's `decision` and whether the
source's rows are in the store (`banked`). Its key is (slug, decision, banked), so one find
can own a line per step.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

LEDGER_DIR = "ledger"
SCRIPT = "scripts/ledger.py"
# The program figure decides once this many finds in a row agree with the store within
# WITHIN of the store's figure; until then the store re-price does.
STREAK = 10
WITHIN = 0.01


def available(fleet: Path | None) -> bool:
    """Whether `fleet` is a clone that holds the fleet's ledger script."""
    return fleet is not None and (Path(fleet) / SCRIPT).is_file()


def lines(fleet: Path | None, kind: str, ref: str | None = None) -> list[dict]:
    """Every line of `kind`, month files in name order and lines in file order: the order
    `ledger.py read` gives. With `ref`, the files as that commit holds them, so `origin/main`
    reads what a push has landed. A line that is not a JSON object is skipped."""
    if fleet is None:
        return []
    out = []
    for body in _month_files(Path(fleet), ref):
        for text in body.splitlines():
            try:
                line = json.loads(text) if text.strip() else None
            except ValueError:
                line = None
            if isinstance(line, dict) and line.get("kind") == kind:
                out.append(line)
    return out


_TEXT = {"capture_output": True, "text": True, "errors": "replace"}


def _git_env() -> dict[str, str]:
    """The environment minus git's own variables: under a hook, GIT_DIR would point
    `git -C fleet` at the repository the hook runs in."""
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def _month_files(fleet: Path, ref: str | None) -> list[str]:
    """The month files' text, in name order, from the working tree or from `ref`."""
    if ref is None:
        return [p.read_text(errors="replace") for p in sorted((fleet / LEDGER_DIR).glob("*.jsonl"))]
    git = ["git", "-C", str(fleet)]
    env = _git_env()
    listed = subprocess.run(
        [*git, "ls-tree", "--name-only", ref, f"{LEDGER_DIR}/"], env=env, **_TEXT
    )
    names = sorted(n for n in listed.stdout.split() if n.endswith(".jsonl"))
    return [subprocess.run([*git, "show", f"{ref}:{n}"], env=env, **_TEXT).stdout for n in names]


def append(fleet: Path | None, kind: str, rows: list[dict]) -> tuple[bool, str]:
    """Append `rows` as `kind` lines through the fleet's own script. Returns whether every
    row is now in the ledger, and the script's last line or the reason nothing ran. A row
    the script refuses stops the batch there, with the rows before it written."""
    if not available(fleet):
        return False, f"no {SCRIPT} in {fleet}, so nothing was appended"
    body = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    done = subprocess.run(
        [
            sys.executable,
            str(Path(fleet) / SCRIPT),
            "append",
            "--kind",
            kind,
            "--json",
            "-",
            "--root",
            str(fleet),
        ],
        input=body,
        capture_output=True,
        text=True,
    )
    said = (done.stdout.strip().splitlines() or done.stderr.strip().splitlines() or [""])[-1]
    if done.returncode != 0:
        said = (done.stderr.strip().splitlines() or [said])[-1]
    return done.returncode == 0, said


def positive(value) -> float | None:
    """A finite number above zero as a float, else None. A bool is not a number here."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and value > 0 else None


def agreement_pct(store_ee, program_ee) -> float | None:
    """The program figure as a percentage of the store's, or None without both."""
    store, program = positive(store_ee), positive(program_ee)
    return None if store is None or program is None else round(100 * program / store, 2)


def agrees(line: dict) -> bool:
    """Whether an outcome line's program figure is within WITHIN of its store figure."""
    store, program = positive(line.get("store_ee")), positive(line.get("program_ee"))
    return store is not None and program is not None and abs(program - store) <= WITHIN * store


def streak(outcomes: list[dict]) -> bool:
    """Whether the last STREAK finds with a store figure all agree. A find counts once, at
    its latest line, so a find booked pending and then banked is one find, not two.

    **A missing program figure is a disagreement, not a gap.** Skipped, a snapshot outage or
    a program that printed 0 would keep a streak alive while the program measured nothing,
    and every find after it would be decided on the figure that failed.
    """
    latest: dict[str, dict] = {}
    for line in outcomes:
        if positive(line.get("store_ee")) is None:
            continue
        latest.pop(str(line.get("slug")), None)
        latest[str(line.get("slug"))] = line
    last = list(latest.values())[-STREAK:]
    return len(last) == STREAK and all(agrees(line) for line in last)
