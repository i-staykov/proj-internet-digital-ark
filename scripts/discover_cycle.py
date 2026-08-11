"""One cycle of the discovery harness, and optionally a loop of them until a deadline.

**What this is and, more usefully, what it is not.** An agent harness for this
project splits cleanly in two, and pretending otherwise is how autonomy turns into
theatre:

*Deterministic work*, which a program can do unattended and correctly: notice that
a collector has died, that a journal is sitting on a remote disk unbanked, that a
file on disk was never read, that a derived target list predates the current
baseline, that a hypothesis has been sitting half-priced for a day, and that the
state document has gone stale. **That is this script**, and it is genuinely
autonomous: every check has a right answer that needs no judgement.

*Judgement work*, which needs an LLM or a human: inventing a hypothesis worth
testing, writing the fetcher that turns a source into dated items, and deciding
whether a measured yield justifies a collector. A program cannot do that, and one
that pretends to will confidently price the wrong thing.

So a cycle does all of the first and **ends by naming exactly what of the second is
waiting**. That list is the handover, and it is written where a human will see it
rather than buried in a log.

**Nothing here writes to the store.** The ingest loop (`scripts/maintain.sh`) owns
the write lock, and a second writer would simply block it. This reports.

    uv run python scripts/discover_cycle.py
    uv run python scripts/discover_cycle.py --until 1786536000 --every 1800
"""

import argparse
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ark.approvals import pending as pending_approvals  # noqa: E402

LOG = ROOT / "data/logs/discovery_cycle.log"
LEDGER = ROOT / "docs/hypotheses.tsv"
APPROVALS = ROOT / "docs/open-approvals.md"
UNFINISHED = ("screened", "fetching", "priced")


# Long enough to outlast a writer. The store takes one writer, and a 33-minute
# `ark seed` is a 33-minute outage for every reader, so a 20-minute ceiling made
# the residual check time out and vanish from the report.
STEP_TIMEOUT = 3600


def run(cmd: list[str], timeout: int = STEP_TIMEOUT) -> tuple[str, bool]:
    """(output, ran). `ran` is False when the step could not complete.

    Returned rather than swallowed, because a step that did not run must not read
    like a step that found nothing. The first version of this script omitted the
    residual section entirely when it timed out behind a writer, which is the exact
    failure `ark check` already guards against by reporting SKIP rather than PASS.
    """
    try:
        done = subprocess.run(
            cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return f"TIMEOUT after {timeout}s: {' '.join(cmd)}", False
    out = ((done.stdout or "") + (done.stderr or "")).strip()
    return out, bool(out)


def check_collectors() -> tuple[list[str], list[str]]:
    """Alive, and is anything they produced still not banked?"""
    findings, attention = [], []
    out, ran = run(["bash", "scripts/engine_status.sh"], timeout=180)
    if not ran:
        return ["collectors: COULD NOT CHECK"], [
            "the collector check did not complete, so their state is UNKNOWN rather than fine"
        ]
    local_running = "NOT RUNNING" not in out.split("== VPS")[0]
    findings.append(f"local collector: {'running' if local_running else 'NOT RUNNING'}")
    if not local_running:
        attention.append("the local collector is not running; decide whether that is intended")
    if "UNKNOWN: could not reach" in out:
        findings.append("VPS: UNREACHABLE, so its journals are unbanked and uncounted")
        attention.append(
            "VPS unreachable: bring the VPN up and rsync its journals. This is not "
            "'nothing to fetch', and the project once left 5,793 records stranded for "
            "a day and a half by reading it that way"
        )
    elif "everything is home" in out:
        findings.append("VPS: reachable, every journal is home")
    else:
        missing = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("cdx_")]
        if missing:
            findings.append(f"VPS: {len(missing)} journals not copied here yet")
            attention.append(f"rsync {len(missing)} VPS journals home, then ingest them")
    return findings, attention


def check_residual() -> tuple[list[str], list[str]]:
    findings, attention = [], []
    out, ran = run(["uv", "run", "python", "scripts/audit_residual.py"])
    if not ran:
        return ["residual: COULD NOT CHECK"], [
            "the residual audit did not complete, most likely behind a long writer. "
            "It examined nothing, which is not the same as finding nothing"
        ]
    for line in out.splitlines():
        stripped = line.strip()
        for key in ("unread", "glob_too_narrow", "unreferenced", "usenet", "stale_derived"):
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
                    if key == "stale_derived" and count not in ("0", ""):
                        # The comparison is against the store mark that invalidates each
                        # list, newest pairs for a gap queue and newest candidates for a
                        # pool queue, not against the baseline release. Saying "baseline"
                        # here described the check as it was before 11 August and would
                        # send a reader looking for a release that had not moved.
                        attention.append(
                            f"{count} derived target list(s) are older than the rows they "
                            "should carry, so a collector reading them cannot see those rows"
                        )
    return findings, attention


# Only act on a list this far behind, so the cycle cannot thrash: candidates arrive
# continuously, and rebuilding on every one would restart the collector hourly for a
# handful of new targets.
REBUILD_AFTER_HOURS = 1.5


def rebuild_derived() -> tuple[list[str], list[str]]:
    """Rebuild stale derived target lists, and re-point the local engine at them.

    **This is the cycle's one action rather than a report**, and the distinction is
    deliberate. Writing evidence is a judgement and belongs to a human; regenerating a
    derived list is neither, and leaving it undone has already cost something real:
    4,333 freshly seeded UDRP names, 88% of them absent from the store, sat in the pool
    for two hours while the running engine worked a queue built before they existed.

    The VPS is deliberately untouched. Its list has to be shipped over a VPN window, so
    it is reported and left.
    """
    findings, attention = [], []
    out, ran = run(["uv", "run", "python", "scripts/audit_residual.py", "--check", "stale_derived"])
    if not ran:
        return ["derived: COULD NOT CHECK"], [
            "the staleness check did not complete, so a collector may be working a stale list"
        ]
    stale = {}
    for line in out.splitlines():
        if "[STALE]" not in line:
            continue
        parts = line.split()
        path = parts[1]
        hours = next((float(p) for p in parts if p.endswith("h")), 0.0) or 0.0
        stale[path] = hours
    if not stale:
        return ["derived: every list postdates the rows it should carry"], []

    for path, hours in sorted(stale.items()):
        if hours < REBUILD_AFTER_HOURS:
            findings.append(f"derived: {Path(path).name} {hours:.1f}h behind, under the threshold")
            continue
        if "queue_gap_vps" in path:
            findings.append(f"derived: {Path(path).name} {hours:.1f}h behind, VPS list left alone")
            attention.append(
                "the VPS gap list is stale and has to be shipped over a VPN window, so it "
                "needs a human: rebuild it, scp it, and restart the supervisor there"
            )
            continue
        if "queue_pool_local" in path:
            _o, ok = run(
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/build_query_queue.py",
                    "--population",
                    "pool",
                    "--out",
                    path,
                ]
            )
            findings.append(f"derived: rebuilt {Path(path).name} ({'ok' if ok else 'FAILED'})")
            if ok:
                findings += repoint_pool_engine()
        elif "pool_targets_org" in path:
            _o, ok = run(
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/build_rdap_pool_list.py",
                    "--tlds",
                    "org",
                    "--limit",
                    "400000",
                    "--out",
                    path,
                ]
            )
            findings.append(f"derived: rebuilt {Path(path).name} ({'ok' if ok else 'FAILED'})")
        else:
            findings.append(f"derived: {Path(path).name} stale, no rebuild rule")
    return findings, attention


def repoint_pool_engine() -> list[str]:
    """Restart the local pool collector so it reads the rebuilt list.

    **Guarded against the one failure that matters.** The archive rate-limits per
    address and has refused this project outright three times, so two supervisors
    against one address is worse than none. This refuses to start a second one, and it
    stops the old one with TERM so the batch publishes its journal rather than
    stranding a `.part`.
    """
    out, _ = run(["pgrep", "-f", "supervise_cdx_pool.sh"], timeout=30)
    if out.strip():
        run(["pkill", "-TERM", "-f", "supervise_cdx_pool.sh"], timeout=30)
        time.sleep(15)
    still, _ = run(["pgrep", "-f", "supervise_cdx_pool.sh"], timeout=30)
    if still.strip():
        return ["derived: old collector would not stop, so NOT starting another"]
    _started, _ok = run(
        [
            "bash",
            "-c",
            "ARK_TARGETS=data/raw/cdx/queue_pool_local.txt ARK_PREFIX=cdx_disc "
            "nohup caffeinate -i bash scripts/supervise_cdx_pool.sh 1786536000 600 8 900 "
            "> /dev/null 2>&1 < /dev/null & echo started",
        ],
        timeout=60,
    )
    time.sleep(10)
    alive, _ = run(["pgrep", "-f", "supervise_cdx_pool.sh"], timeout=30)
    state = "up" if alive.strip() else "DID NOT START"
    return [f"derived: pool collector re-pointed at the rebuilt list ({state})"]


def check_ledger() -> tuple[list[str], list[str]]:
    findings, attention = [], []
    if not LEDGER.exists():
        return ["ledger: absent"], []
    lines = LEDGER.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        return ["ledger: empty"], []
    header = lines[0].split("\t")
    rows = [dict(zip(header, ln.split("\t"), strict=False)) for ln in lines[1:] if ln.strip()]
    stuck = [r for r in rows if r.get("status") in UNFINISHED]
    findings.append(f"hypotheses: {len(rows)} total, {len(stuck)} unfinished")
    if stuck:
        attention.append(
            "unfinished hypotheses need judgement, not a program: "
            + ", ".join(
                f"{r['id']} ({r.get('status')}) {r.get('title', '')[:40]}" for r in stuck[:6]
            )
        )
    return findings, attention


def check_approvals() -> tuple[list[str], list[str]]:
    """Source classes whose journals are collected and cannot be ingested yet.

    This is the harness's handover point by design: collection never waits on a
    human, and promotion to the annual files always does. A pending class is not a
    fault, it is the queue working, so it is reported every cycle until decided.
    """
    waiting = pending_approvals(APPROVALS)
    if not waiting:
        return ["approvals: nothing pending"], []
    return (
        [f"approvals: {len(waiting)} class(es) awaiting classification"],
        [
            "a human must classify these source classes before their records can date a "
            "year; the journals are on disk and nothing is lost: "
            + ", ".join(f"{a.source_name}/{a.evidence_type}" for a in waiting)
        ],
    )


def check_state() -> tuple[list[str], list[str]]:
    out, ran = run(["uv", "run", "python", "scripts/build_round_state.py", "--check"])
    if not ran:
        return ["ROUND.md: COULD NOT CHECK"], [
            "the state check did not complete, so ROUND.md may be stale"
        ]
    if "is current" in out:
        return ["ROUND.md: current"], []
    _, wrote = run(["uv", "run", "python", "scripts/build_round_state.py"])
    return [f"ROUND.md: was stale, {'regenerated' if wrote else 'REGENERATION FAILED'}"], []


def cycle(number: int, with_network: bool) -> list[str]:
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n{'=' * 78}\ncycle {number} at {stamp}\n{'=' * 78}")
    findings: list[str] = []
    attention: list[str] = []
    for name, fn in (
        ("collectors", check_collectors),
        ("residual", check_residual),
        ("derived", rebuild_derived),
        ("ledger", check_ledger),
        ("approvals", check_approvals),
        ("state", check_state),
    ):
        got, needs = fn()
        findings += got
        attention += needs
        for line in got:
            print(f"  [{name}] {line}")

    if with_network:
        out, ran = run(["uv", "run", "python", "scripts/reprobe_closed.py"])
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
    args = ap.parse_args()

    number = 1
    while True:
        # the re-probe asks external hosts, so it runs on the first cycle and then
        # every fourth: a host that came back does not come back twice an hour
        with_network = not args.no_network and (number == 1 or number % 4 == 0)
        cycle(number, with_network)
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
