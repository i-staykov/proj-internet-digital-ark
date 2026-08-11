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
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data/logs/discovery_cycle.log"
LEDGER = ROOT / "docs/hypotheses.tsv"
UNFINISHED = ("screened", "fetching", "priced")


def run(cmd: list[str], timeout: int) -> str:
    try:
        done = subprocess.run(
            cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return f"TIMEOUT after {timeout}s"
    return ((done.stdout or "") + (done.stderr or "")).strip()


def check_collectors() -> tuple[list[str], list[str]]:
    """Alive, and is anything they produced still not banked?"""
    findings, attention = [], []
    out = run(["bash", "scripts/engine_status.sh"], timeout=120)
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
    out = run(["uv", "run", "python", "scripts/audit_residual.py"], timeout=1200)
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
                        attention.append(
                            f"{count} derived target list(s) predate the current baseline, so "
                            "they are blind to what it added"
                        )
    return findings, attention


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


def check_state() -> tuple[list[str], list[str]]:
    out = run(["uv", "run", "python", "scripts/build_round_state.py", "--check"], timeout=1200)
    if "is current" in out:
        return ["ROUND.md: current"], []
    run(["uv", "run", "python", "scripts/build_round_state.py"], timeout=1200)
    return ["ROUND.md: was stale, regenerated"], []


def cycle(number: int, with_network: bool) -> list[str]:
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n{'=' * 78}\ncycle {number} at {stamp}\n{'=' * 78}")
    findings: list[str] = []
    attention: list[str] = []
    for name, fn in (
        ("collectors", check_collectors),
        ("residual", check_residual),
        ("ledger", check_ledger),
        ("state", check_state),
    ):
        got, needs = fn()
        findings += got
        attention += needs
        for line in got:
            print(f"  [{name}] {line}")

    if with_network:
        out = run(["uv", "run", "python", "scripts/reprobe_closed.py"], timeout=1200)
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
