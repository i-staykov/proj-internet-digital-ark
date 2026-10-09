"""One cycle of the discovery harness, and optionally a loop of them until a deadline.

**What this is and, more usefully, what it is not.** An agent harness for this
project splits cleanly in two, and pretending otherwise is how autonomy turns into
theatre:

*Deterministic work*, which a program can do unattended and correctly: notice that
a file on disk was never read and that the state document has gone stale. **That is this
script**, and it is genuinely autonomous: every check has a right answer that needs no
judgement.

*Judgement work*, which needs an LLM or a human: inventing a hypothesis worth
testing, writing the fetcher that turns a source into dated items, and deciding
whether a measured yield justifies a collector. A program cannot do that, and one
that pretends to will confidently price the wrong thing.

So a cycle does all of the first and **ends by naming exactly what of the second is
waiting**. That list is the handover, and it is written where a human will see it
rather than buried in a log.

**Nothing here writes to the store.** `just bank` owns the write lock, and a second writer
would simply block it. This reports.

    uv run python scripts/harness/discover_cycle.py
    uv run python scripts/harness/discover_cycle.py --until 1786536000 --every 1800
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ark.approvals import pending as pending_approvals  # noqa: E402
from ark.yield_check import (  # noqa: E402
    Collector,
    active_cdx_collectors,
    measure_collectors,
)

LOG = ROOT / "data/logs/discovery_cycle.log"
APPROVALS = ROOT / "docs/registers/approved-sources-list.md"
JOURNAL_DIR = ROOT / "data/raw/cdx"


# **The CDX prefixes are discovered, not listed.** A supervisor's header states intent
# and the directory holds the facts: a prefix no list names can spend 31 hours on an
# exhausted shard for zero captures while every yield line here reads clean.
def collectors() -> list[Collector]:
    return active_cdx_collectors(JOURNAL_DIR)


# Long enough to outlast a writer. The store takes one writer, and a 33-minute
# `ark seed` is a 33-minute outage for every reader, so a 20-minute ceiling made
# the residual check time out and vanish from the report.
STEP_TIMEOUT = 3600


def run(cmd: list[str], timeout: int = STEP_TIMEOUT) -> tuple[str, bool]:
    """(output, ran). `ran` is False when the step could not complete.

    Returned rather than swallowed, because a step that did not run must not read
    like a step that found nothing: a residual section omitted when it times out
    behind a writer is the exact failure `ark check` guards against by reporting SKIP
    rather than PASS.
    """
    try:
        done = subprocess.run(
            cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return f"TIMEOUT after {timeout}s: {' '.join(cmd)}", False
    out = ((done.stdout or "") + (done.stderr or "")).strip()
    return out, bool(out)


def check_yield() -> tuple[list[str], list[str]]:
    """Are the collectors finding anything, not just running and writing?

    **A journal full of misses grows exactly as fast as one full of hits**, so growth says
    nothing about yield. Reasoning and thresholds in `ark.yield_check`.
    """
    findings, attention = [], []
    for reading in measure_collectors(collectors()):
        findings.append(f"yield: {reading.describe()}")
        if reading.collapsed:
            attention.append(
                f"{reading.prefix} is answering but finding almost nothing: "
                f"{reading.describe()}. Either its queue head is a population with no "
                f"captures, in which case rebuild and re-rank it, or the archive is "
                f"refusing us. Check before assuming the population is spent"
            )
    return findings, attention


def check_residual() -> tuple[list[str], list[str]]:
    findings, attention = [], []
    out, ran = run(["uv", "run", "python", "scripts/harness/audit_residual.py"])
    if not ran:
        return ["residual: COULD NOT CHECK"], [
            "the residual audit did not complete, most likely behind a long writer. "
            "It examined nothing, which is not the same as finding nothing"
        ]
    for line in out.splitlines():
        stripped = line.strip()
        for key in ("unread", "glob_too_narrow", "unreferenced", "usenet"):
            if stripped.startswith(key):
                parts = stripped.split()
                if len(parts) >= 2:
                    count = parts[-1].replace(",", "")
                    findings.append(f"{key}: {count}")
                    if key == "unread" and count not in ("0", ""):
                        attention.append(
                            f"{count} file(s) on disk that a documented glob matches and no "
                            "ingest has read. This is the cheapest yield in the project: "
                            "496 such files were worth 14,956 equivalent-English"
                        )
    return findings, attention


FLEET_REPO = "i-staykov/ark-fleet"
# The fleet clone the justfile names, for its `policy.json`.
DEFAULT_FLEET = Path.home() / "GitHub/ark-fleet"
# The title `leg.yaml` gives a dispatched run; the watchdog's runs are `Leg watchdog`.
LEG_TITLE = re.compile(r"Leg slot (0|[1-9][0-9]*)")


def leg_slot_bound(fleet: Path) -> int:
    """`wave.max_parallel` in the fleet clone's `policy.json`: the slots Leg may hold."""
    policy = json.loads((fleet / "policy.json").read_text(encoding="utf-8"))
    wave = policy.get("wave") if isinstance(policy, dict) else None
    value = wave.get("max_parallel") if isinstance(wave, dict) else None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"wave.max_parallel is {json.dumps(value)}, not a whole number")
    return value


def check_leg_slots(fleet: Path = DEFAULT_FLEET) -> tuple[list[str], list[str]]:
    """Report each Leg slot the fleet's policy allows that no run holds. It dispatches nothing.

    A slot is a chain of `leg.yaml` runs titled `Leg slot N`, each dispatching its successor
    last, and a slot at or above `policy.json` `wave.max_parallel` ends its chain. A slot is
    idle while no run titled for it is queued, waiting or running, the definition the fleet's
    own `slots.py idle` uses. **`leg.yaml`'s schedule is the watchdog** and starts every idle
    slot, so this laptop only says what it saw: a slot idle tick after tick is a watchdog that
    is not firing, or a held `leg.yaml`.
    """
    # **A short timeout, because this runs inside the hourly sync.** `STEP_TIMEOUT` is an
    # hour, which is right for a cycle step and wrong here: a slow GitHub would hold the bank
    # for the whole window and the next sync would land on top of it.
    ask = 60
    try:
        bound = leg_slot_bound(fleet)
    except (OSError, ValueError) as exc:
        return [f"leg slots: COULD NOT CHECK, policy.json: {str(exc)[:80]}"], []
    if bound == 0:
        return ["leg slots: policy.json wave.max_parallel is 0, so no slot runs"], []
    said, ran = run(
        [
            "gh",
            "run",
            "list",
            "--repo",
            FLEET_REPO,
            "--workflow",
            "leg.yaml",
            "--limit",
            "50",
            "--json",
            "displayTitle,status",
        ],
        timeout=ask,
    )
    try:
        runs = json.loads(said) if ran else None
    except ValueError:
        runs = None
    if not isinstance(runs, list):
        return [f"leg slots: COULD NOT CHECK, gh said: {said[:80]}"], []
    held = set()
    for leg in (leg for leg in runs if isinstance(leg, dict)):
        title = LEG_TITLE.fullmatch(str(leg.get("displayTitle", "")))
        if title and leg.get("status") != "completed":
            held.add(int(title.group(1)))
    idle = [slot for slot in range(bound) if slot not in held]
    if not idle:
        return [f"leg slots: all {bound} held by a run"], []
    named = ", ".join(str(slot) for slot in idle)
    return [
        f"leg slots: {len(idle)} of {bound} idle (slot {named}), for leg.yaml's watchdog to start"
    ], []


def check_approvals() -> tuple[list[str], list[str]]:
    """Source classes whose journals are collected and cannot be ingested yet.

    This is the harness's handover point: collection never waits on a human, and a
    `pending` class waits on one before its records can date a year. A pending class is
    not a fault, it is the queue working. The check writes nothing: the register's pending
    block is the ask, and `sync_approvals.py` files the ones worth a decision as
    `needs-owner` issues.
    """
    findings, attention = [], []
    priced = pending_approvals(APPROVALS)
    if not priced:
        findings.append("approvals: nothing pending")
    else:
        findings.append(f"approvals: {len(priced)} priced class(es) awaiting classification")
        attention.append(
            "classify these source classes before their records can date a year; the "
            "journals are on disk and nothing is lost: "
            + ", ".join(f"{a.source_name}/{a.evidence_type}" for a in priced)
        )
    return findings, attention


def check_state() -> tuple[list[str], list[str]]:
    out, ran = run(["uv", "run", "python", "scripts/round/build_round_state.py", "--check"])
    if not ran:
        return ["ROUND.md: COULD NOT CHECK"], [
            "the state check did not complete, so ROUND.md may be stale"
        ]
    if "is current" in out:
        return ["ROUND.md: current"], []
    return ["ROUND.md: stale"], [
        "ROUND.md is stale: the next bank rewrites it, or run `just state`"
    ]


def cycle(number: int, with_network: bool, fleet: Path = DEFAULT_FLEET) -> list[str]:
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n{'=' * 78}\ncycle {number} at {stamp}\n{'=' * 78}")
    findings: list[str] = []
    attention: list[str] = []
    for name, fn in (
        ("yield", check_yield),
        ("residual", check_residual),
        ("slots", lambda: check_leg_slots(fleet)),
        ("approvals", check_approvals),
        ("state", check_state),
    ):
        got, needs = fn()
        findings += got
        attention += needs
        for line in got:
            print(f"  [{name}] {line}")

    if with_network:
        out, ran = run(["uv", "run", "python", "scripts/harness/reprobe_closed.py"])
        if not ran:
            attention.append("the re-probe did not complete, so nothing was re-asked")
        revived = [ln.strip() for ln in out.splitlines() if "NOW ANSWERS, UNEXPECTED" in ln]
        print(f"  [reprobe] {len(revived)} availability-closed lead(s) answering unexpectedly")
        findings.append(f"reprobe: {len(revived)} unexpected revivals")
        for line in revived:
            attention.append(f"a closed-on-availability lead answers now, price it: {line[:90]}")

    print("\n  -- needs judgement, which no program here can supply --")
    if attention:
        for item in attention:
            print(f"  * {item}")
    else:
        print("  * nothing. Every mechanical check is clean.")

    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{stamp}\tcycle={number}\t" + "; ".join(findings) + "\n")
        for item in attention:
            fh.write(f"{stamp}\tcycle={number}\tATTENTION\t{item}\n")
    return attention


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--until", type=int, default=None, help="unix time to stop at (loop mode)")
    ap.add_argument("--every", type=int, default=1800, help="seconds between cycles in loop mode")
    ap.add_argument(
        "--no-network",
        action="store_true",
        help="skip the re-probe, which is the only step that leaves the machine",
    )
    # **The slot check wants an hourly caller**, so the hourly sync calls this flag, and the
    # check itself is not duplicated anywhere.
    ap.add_argument(
        "--slots-only",
        action="store_true",
        help="run only the Leg slot check and exit, for an hourly caller",
    )
    ap.add_argument(
        "--fleet",
        type=Path,
        default=DEFAULT_FLEET,
        help="the fleet clone, for policy.json wave.max_parallel",
    )
    args = ap.parse_args()
    fleet = args.fleet.expanduser()

    if args.slots_only:
        notes, fixes = check_leg_slots(fleet)
        for line in notes + fixes:
            print(line)
        return

    number = 1
    while True:
        # the re-probe asks external hosts, so it runs on the first cycle and then
        # every fourth: a host that came back does not come back twice an hour
        with_network = not args.no_network and (number == 1 or number % 4 == 0)
        cycle(number, with_network, fleet)
        if args.until is None:
            return
        remaining = args.until - time.time()
        if remaining <= 0:
            print(f"\nreached the deadline after {number} cycles")
            return
        nap = min(args.every, remaining)
        print(f"\nsleeping {nap / 60:.0f} min; {remaining / 3600:.1f} h left before the deadline")
        time.sleep(nap)
        number += 1


if __name__ == "__main__":
    main()
