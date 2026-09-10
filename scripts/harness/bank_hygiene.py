"""The three things an unattended bank has to get right besides banking.

The bank runs hourly, pushes `live`, and nobody watches it. So its failures are the
quiet kind:

1. **A dirty clone.** The recipe stages whole directories (`git add docs/ src/`),
   which is how a 1.3 GB baseline copy once reached git history. A clone with
   uncommitted tracked edits, or with untracked files under the paths the bank
   stages, is refused BEFORE anything is written or fetched.
2. **A diverged clone.** Approvals now arrive as pull requests merged from a phone,
   so `live` moves without this machine. A fast-forward-only pull is the whole fix:
   it takes the merge and refuses to invent one.
3. **A second notification for the same crossing.** The gate issue says the round
   is over 5%. Opened once it is information; opened hourly it is noise, and the
   latch is deliberately two independent checks, a local ledger and the open-issue
   query, because either alone has a hole: the ledger cannot see an issue somebody
   closed by hand, and the query cannot see one that has been closed after shipping.

Banked staging files require verified remote copies before removal. Empty incoming
directories and unverified files remain local. Preflight also enforces the free-space
floor and write budget before the bank starts.

    uv run python scripts/harness/bank_hygiene.py preflight   # before the bank works
    uv run python scripts/harness/bank_hygiene.py prune --write
    uv run python scripts/harness/bank_hygiene.py gate --write # after the gate ran
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

BRIEF = ROOT / "data/brief.json"
LATCH = ROOT / "data/logs/gate_notified.tsv"
FLEET_REPO = "i-staykov/ark-fleet"

# Paths the bank recipe stages wholesale. An untracked file under one of these is
# fatal rather than a warning, because `git add docs/` would commit it. Kept in step
# with the recipe's own `git add` line: widening that without widening this is how an
# untracked file gets committed by a job nobody is watching.
STAGED = ("docs/", "src/", "justfile")

# Where the bank downloads and parks fleet artifacts.
INCOMING = "data/fleet_findings/incoming"
BANKED = "data/fleet_findings/banked"
GIB = 1024**3


def round_prune():
    if "prune" in sys.modules:
        return sys.modules["prune"]
    spec = importlib.util.spec_from_file_location("prune", ROOT / "scripts/round/prune.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["prune"] = module
    spec.loader.exec_module(module)
    return module


def space(*, root: Path = ROOT) -> tuple[int, list[str]]:
    """Require the free-space floor plus a write budget on both destination filesystems."""
    try:
        floor = float(os.environ.get("ARK_FREE_SPACE_GIB", "50"))
        budget = float(os.environ.get("ARK_WRITE_BUDGET_GIB", "20"))
        if not all(math.isfinite(n) and n > 0 for n in (floor, budget)):
            raise ValueError("space settings must be finite positive GiB values")
        store = root / "data/ark.duckdb"
        budget_bytes = max(int(budget * GIB), store.stat().st_size if store.exists() else 0)
        required = int(floor * GIB) + budget_bytes
        lines = []
        for destination in (root / "data", root / "output"):
            probe = destination
            while not probe.exists():
                probe = probe.parent
            free = shutil.disk_usage(probe).free
            lines.append(
                f"space {destination.name}: {free / GIB:.1f} GiB free, "
                f"need {required / GIB:.1f} GiB "
                f"({floor:g} floor + {budget_bytes / GIB:.1f} write budget)"
            )
            if free < required:
                return 2, [
                    *lines,
                    "REFUSED: insufficient free space; no ingest or export started. "
                    "Use verified off-site cleanup or increase capacity.",
                ]
        return 0, lines
    except (OSError, ValueError, OverflowError) as exc:
        return 2, [f"REFUSED: cannot establish free space: {exc}"]


def clean_env() -> dict[str, str]:
    """The environment minus git's own variables.

    A hook exports GIT_DIR and GIT_INDEX_FILE for the repository it runs in, and a git
    subprocess acts on that repository whatever `cwd` says. The tests here once staged
    their fixture files into the real index that way, from inside the pre-commit hook.
    """
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def git(args: list[str], cwd: Path = ROOT) -> tuple[int, str]:
    """One git command against the clone at `cwd`, returning its status and its output."""
    done = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=clean_env(),
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    return done.returncode, (done.stdout + done.stderr).strip()


def unsafe(status: str) -> tuple[list[str], list[str]]:
    """Porcelain lines that refuse the bank, and the ones that only warn.

    A tracked edit refuses: the bank commits, and committing somebody's work in
    progress under a "Bank fleet findings" message hides it. An untracked file
    refuses only where the recipe stages by directory.
    """
    fatal, warn = [], []
    for line in status.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip().strip('"')
        if line[:2] == "??":
            (fatal if path.startswith(STAGED) else warn).append(line.strip())
        else:
            fatal.append(line.strip())
    return fatal, warn


def preflight(
    *,
    root: Path = ROOT,
    branch: str = "live",
    remote: str = "origin",
    pull: bool = True,
    run: Callable[[list[str], Path], tuple[int, str]] = git,
) -> tuple[int, list[str]]:
    """Refuse a clone the bank must not run in, then fast-forward it.

    Returns 0 and the report, or 2 and the reason. The order matters: the clean
    check comes first, so a refusal happens before the pull writes anything.
    """
    lines: list[str] = []
    _, head = run(["rev-parse", "--abbrev-ref", "HEAD"], root)
    if head == "main":
        return 2, ["REFUSED: on `main`, which no agent pushes. Check out `live` first."]
    lines.append(f"on `{head}`")

    code, status = run(["status", "--porcelain"], root)
    if code != 0:
        return 2, [f"REFUSED: git status failed: {status}"]
    fatal, warn = unsafe(status)
    for line in warn:
        lines.append(f"untracked, not staged by the bank: {line}")
    if fatal:
        lines.append(f"REFUSED: the clone is dirty, {len(fatal)} path(s):")
        lines.extend(f"  {line}" for line in fatal[:20])
        lines.append("  commit, stash or clean these before banking. Nothing was fetched.")
        return 2, lines
    lines.append("clone is clean")

    code, disk_lines = space(root=root)
    lines.extend(disk_lines)
    if code:
        return code, lines

    if not pull:
        return 0, lines
    code, out = run(["pull", "--ff-only", remote, branch], root)
    if code != 0:
        lines.append(f"REFUSED: `git pull --ff-only {remote} {branch}` failed:")
        lines.append(f"  {out.splitlines()[-1] if out else 'no output'}")
        lines.append("  the clone has diverged. Reconcile by hand; the bank never force-pushes.")
        return 2, lines
    lines.append(f"fast-forwarded from {remote}/{branch}")
    return 0, lines


def prune(
    *, root: Path = ROOT, days: int = 14, now: float | None = None, write: bool = False
) -> list[str]:
    """Prune old banked files only with per-file verified remote copies."""
    root = root.resolve()
    now = time.time() if now is None else now
    lines, removed = [], 0
    cutoff = now - days * 86400
    for path in sorted((root / BANKED).glob("*")):
        if path.is_dir() and path.stat().st_mtime < cutoff:
            age = int((now - path.stat().st_mtime) / 86400)
            lines.append(f"banked findings {age} days old: {path.relative_to(root)}")
            try:
                _rmtree(path, root=root, write=write)
                removed += 1
            except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
                lines.append(f"HELD: {exc}")
    if not lines:
        return ["staging directories: nothing to prune"]
    lines.append(f"{'pruned' if write else 'would prune'} {removed} directory(ies)")
    return lines


def _rmtree(path: Path, *, root: Path = ROOT, write: bool = False) -> None:
    """Require proofs for every file before removing any; retain unverified metadata."""
    cleaner = round_prune()
    offsite = cleaner.sibling("offsite")
    inventory = offsite.local_files(root, path)
    if not inventory:
        raise ValueError("no verified payload; directory retained")
    files = [path / rel for rel in inventory]
    for child in files:
        offsite.deletion_proof(root, child)
    if offsite.local_files(root, path) != inventory:
        raise ValueError("staging changed during verification")
    for child in files:
        cleaner.remove_verified(root, child, write=write)
    if write:
        for directory in sorted(path.rglob("*"), reverse=True):
            if directory.is_dir() and not directory.is_symlink() and not any(directory.iterdir()):
                directory.rmdir()
        if not any(path.iterdir()):
            path.rmdir()


def latched(path: Path = LATCH) -> set[tuple[str, str]]:
    """The (round, baseline) pairs already notified."""
    if not path.is_file():
        return set()
    pairs = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = line.split("\t")
        if len(cells) >= 2:
            pairs.add((cells[0].strip(), cells[1].strip()))
    return pairs


def latch(round_label: str, marker: str, stamp: str, path: Path = LATCH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"{round_label}\t{marker}\t{stamp}\n")


def gh(args: list[str]) -> tuple[int, str]:
    done = subprocess.run(["gh", *args], capture_output=True, text=True, check=False, timeout=300)
    return done.returncode, (done.stdout + done.stderr).strip()


def gate(
    brief: dict,
    *,
    released: str = "",
    repo: str = FLEET_REPO,
    latch_path: Path = LATCH,
    now: datetime | None = None,
    call: Callable[[list[str]], tuple[int, str]] = gh,
    write: bool = False,
) -> list[str]:
    """Open the gate issue on a crossing, once, and say what it did.

    The figure comes from `data/brief.json`, which `build_round_state.py` writes at
    the end of the bank, so this reads the number the bank itself measured rather
    than opening the store a second time.
    """
    now = now or datetime.now(UTC)
    # **This round's window, not the total.** His current release lacks the round already
    # sent to him, so the total carries that round inside it and would report a crossing
    # on the day the next window opened, with nothing collected. A brief written before
    # the window figures existed still answers on the total.
    percent = float(brief.get("round_percent", brief.get("percent", 0.0)))
    target = float(brief.get("gate_pct", 5.0))
    label = str(brief.get("round", "?"))
    # The brief carries Ivo's numbering as a bare label ("8"), and the open-issue
    # query keys on the title, so the word belongs here and only here.
    round_name = label if label.lower().startswith("round") else f"Round {label}"
    marker = str(brief.get("baseline", "?"))
    if percent < target:
        return [f"at {percent:.4f}%, gate at {target:g}%: not crossed"]
    if (label, marker) in latched(latch_path):
        return [f"gate already notified for {round_name} against {marker}: nothing to do"]

    code, out = call(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--search",
            "in:title Round",
            "--json",
            "number,title",
            "--jq",
            '.[] | select(.title | test("^Round [0-9]+ at ")) | .number',
        ]
    )
    if code != 0:
        return [f"gate issue not opened: `gh issue list` failed: {out or code}"]
    open_issue = out.split("\n")[0].strip() if out.strip() else ""
    if open_issue:
        if write:
            latch(label, marker, now.isoformat(timespec="seconds"), latch_path)
        return [f"gate issue #{open_issue} is already open: latched, not re-notifying"]

    stamp = now.strftime("%H:%M UTC")
    since = f" (released {released})" if released else ""
    title = f"{round_name} at {percent:.4f}% against {marker}{since} at {stamp}"
    body = "\n".join(
        [
            f"{round_name} crossed the {target:g}% gate: {percent:.4f}% against `{marker}`"
            f"{since}, measured by the hourly bank at {now.isoformat(timespec='seconds')}.",
            "",
            "Next: merge any open approval PR, then run `just ship` where the store is.",
            "Opened once per crossing, and closed on a verified package.",
        ]
    )
    if not write:
        return [f"would open the gate issue: {title}"]
    code, out = call(["issue", "create", "--repo", repo, "--title", title, "--body", body])
    if code != 0:
        return [f"gate issue not opened: `gh issue create` failed: {out or code}"]
    latch(label, marker, now.isoformat(timespec="seconds"), latch_path)
    return [f"opened the gate issue: {title}", out.splitlines()[-1] if out else ""]


def _brief() -> dict | None:
    if not BRIEF.is_file():
        print("no data/brief.json: run `just state` first, gate not checked")
        return None
    brief = json.loads(BRIEF.read_text(encoding="utf-8"))
    from ark.baseline import CURRENT_BASELINE_MARKER

    if brief.get("baseline") != CURRENT_BASELINE_MARKER:
        # A crossing measured against a superseded release is not a crossing. The
        # marker moved under us, so the figure has to be recomputed before it can
        # notify anyone.
        print(
            f"brief is against {brief.get('baseline')}, the current release is "
            f"{CURRENT_BASELINE_MARKER}: refresh it before the gate is read"
        )
        return None
    return brief


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="what", required=True)

    sub.add_parser("space", help="refuse ingest/export below the free-space floor and write budget")

    pre = sub.add_parser("preflight", help="refuse a dirty or diverged clone, then fast-forward")
    pre.add_argument("--branch", default="live")
    pre.add_argument("--remote", default="origin")
    pre.add_argument("--no-pull", action="store_true", help="check only, stay offline")

    pr = sub.add_parser("prune", help="delete the bank's spent staging directories")
    pr.add_argument("--days", type=int, default=14)
    pr.add_argument("--write", action="store_true", help="delete rather than list")

    ga = sub.add_parser("gate", help="open the gate issue once when the round crosses 5%%")
    ga.add_argument("--repo", default=FLEET_REPO)
    ga.add_argument("--write", action="store_true", help="open the issue rather than say so")

    args = ap.parse_args()

    if args.what == "space":
        code, lines = space()
        print("\n".join(lines))
        raise SystemExit(code)

    if args.what == "preflight":
        code, lines = preflight(branch=args.branch, remote=args.remote, pull=not args.no_pull)
        for line in lines:
            print(f"  {line}")
        raise SystemExit(code)

    if args.what == "prune":
        for line in prune(days=args.days, write=args.write):
            print(f"  {line}")
        return

    brief = _brief()
    if brief is None:
        return
    from ark.baseline import CURRENT_BASELINE_RELEASED

    for line in gate(
        brief, released=CURRENT_BASELINE_RELEASED[:10], repo=args.repo, write=args.write
    ):
        if line:
            print(f"  {line}")


if __name__ == "__main__":
    main()
