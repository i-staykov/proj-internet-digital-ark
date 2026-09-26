"""One cycle of the discovery harness, and optionally a loop of them until a deadline.

**What this is and, more usefully, what it is not.** An agent harness for this
project splits cleanly in two, and pretending otherwise is how autonomy turns into
theatre:

*Deterministic work*, which a program can do unattended and correctly: notice that
a file on disk was never read, that a derived target list is older than the rows it
should carry, that a hypothesis has been sitting half-priced for a day, and that the
state document has gone stale. **That is this script**, and it is genuinely
autonomous: every check has a right answer that needs no judgement.

**It rebuilds, and it does not restart anything.** Regenerating a stale derived list
is deterministic, so the cycle owns it. Stopping and starting collectors is not: an
earlier version did, with a `pkill -f` pattern that matches the shell running it, and
on 11 August it killed a healthy collector mid-batch. A supervisor re-reads its target
list at every dispatch, so rewriting the file is the whole job.

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
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ark import key_decisions  # noqa: E402
from ark.approvals import load as load_approvals  # noqa: E402
from ark.approvals import pending as pending_approvals  # noqa: E402
from ark.yield_check import (  # noqa: E402
    Collector,
    active_cdx_collectors,
    measure_collectors,
    rdap_verdict,
)

LOG = ROOT / "data/logs/discovery_cycle.log"
LEDGER = ROOT / "docs/registers/hypotheses.tsv"
APPROVALS = ROOT / "docs/registers/approved-sources-list.md"
# Since `split_triage.py` ran on 2026-09-03 the undecided finds live here and the triage
# section of APPROVALS holds only what has arrived since. Counting the section alone read
# 0 waiting on 2026-09-17 while 49 sat in this file, so both are counted.
DECISIONS_DOC = ROOT / "docs/lore/key-decisions.md"
UNFINISHED = ("screened", "fetching", "priced")
JOURNAL_DIR = ROOT / "data/raw/cdx"
RDAP_JOURNAL_DIR = ROOT / "data/raw/rdap"


# **The CDX prefixes are discovered, not listed.** They used to be listed, as `cdx_pool`
# and `cdx_gap`, on the authority of the supervisor's own header. The header states
# intent and the directory holds the facts: on 2026-08-12 it held six prefixes, and the
# VPS had spent 31 hours writing `cdx_q1` against an exhausted shard for zero captures
# while every yield line here read clean, because none of them was looking for it.
#
# RDAP stays named because it is a different journal format needing its own verdict: a
# 404 is a real answer and a 429 is not, and a creation year outside 1996-2001 is an
# answer that pays nothing. It is also this round's largest single contributor.
def collectors() -> tuple[Collector, ...]:
    return (
        *active_cdx_collectors(JOURNAL_DIR),
        Collector("rdap", RDAP_JOURNAL_DIR, rdap_verdict),
    )


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
                    # `stale_derived` is deliberately NOT raised for attention here.
                    # Candidates arrive continuously, so a pool queue is a few minutes
                    # stale almost always, and an alarm on that condition fires every
                    # cycle forever. `rebuild_derived` owns it instead: it rebuilds past
                    # the threshold and asks for a human only when it cannot act, which
                    # is a failed rebuild. An alarm nobody can clear is
                    # the same defect as the 982 MB the unreferenced check used to report.
    return findings, attention


# Only act on a list this far behind, so the cycle cannot thrash: candidates arrive
# continuously, and rebuilding on every one would restart the collector hourly for a
# handful of new targets.
REBUILD_AFTER_HOURS = 1.5

# Two cycles can now run at once, an hourly loop and a 15-minute cron wake, and both
# would rebuild the same list into the same path. Two writers to one target file is a
# truncated queue, which a collector then reads as a short list rather than as an error.
# A stale lock is ignored after this long, since a rebuild is minutes and a crashed
# holder must not block rebuilds forever.
REBUILD_LOCK = ROOT / "data/logs/derived_rebuild.lock"
REBUILD_LOCK_STALE_S = 3600

FLEET_REPO = "i-staykov/ark-fleet"
# The fleet clone the justfile names, for its `policy.json`.
DEFAULT_FLEET = Path.home() / "Documents/GitHub/ark-fleet"
# The title `leg.yaml` gives a dispatched run; the watchdog's runs are `Leg watchdog`.
LEG_TITLE = re.compile(r"Leg slot (0|[1-9][0-9]*)")


def rebuild_lock_holder() -> str | None:
    """The live holder's pid, or None if the lock is absent, stale or abandoned."""
    if not REBUILD_LOCK.exists():
        return None
    age = time.time() - REBUILD_LOCK.stat().st_mtime
    pid = REBUILD_LOCK.read_text(encoding="utf-8").strip()
    if age > REBUILD_LOCK_STALE_S:
        return None
    if pid.isdigit():
        try:
            os.kill(int(pid), 0)
        except ProcessLookupError:
            return None
        except PermissionError:
            pass  # it exists and is not ours, which still counts as alive
    return pid or "unknown"


def rebuild_derived() -> tuple[list[str], list[str]]:
    """Rebuild stale derived target lists.

    **This is the cycle's one action rather than a report**, and the distinction is
    deliberate. Writing evidence is a judgement and belongs to a human; regenerating a
    derived list is neither, and a collector reading a list built before the rows it
    should carry cannot see them at all.

    **It rebuilds the file and stops there, deliberately.** An earlier version also
    restarted the local collector to "re-point" it, which was both unnecessary and the
    mechanism of a real failure: a supervisor re-reads its target list at every
    dispatch, so rewriting the file is enough, and the restart used `pkill -f` with a
    pattern that matches the shell running it. On 11 August that took down a healthy
    collector mid-batch. **An unattended loop does not get to kill collectors.**
    """
    findings, attention = [], []
    out, ran = run(
        ["uv", "run", "python", "scripts/harness/audit_residual.py", "--check", "stale_derived"]
    )
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
        # The field is "0.9h", so the unit has to come off before the float. Getting
        # this wrong crashed the whole cycle on 11 August, and it went unnoticed for
        # an hour because the long-running loop had loaded this module before the
        # function existed: the crash only appeared on the next fresh invocation.
        hours = next((float(p[:-1]) for p in parts if re.fullmatch(r"[\d.]+h", p)), 0.0)
        stale[path] = hours
    if not stale:
        return ["derived: every list postdates the rows it should carry"], []

    # Only take the lock once something is actually going to be rebuilt, so a cycle
    # that finds everything under the threshold never blocks another one.
    if any(h >= REBUILD_AFTER_HOURS for h in stale.values()):
        holder = rebuild_lock_holder()
        if holder:
            return [f"derived: another cycle (pid {holder}) is rebuilding, leaving it alone"], []
        REBUILD_LOCK.parent.mkdir(parents=True, exist_ok=True)
        REBUILD_LOCK.write_text(str(os.getpid()), encoding="utf-8")

    try:
        findings, attention = _rebuild_each(stale)
    finally:
        if REBUILD_LOCK.exists() and REBUILD_LOCK.read_text(encoding="utf-8").strip() == str(
            os.getpid()
        ):
            REBUILD_LOCK.unlink()
    return findings, attention


def _rebuild_each(stale: dict[str, float]) -> tuple[list[str], list[str]]:
    findings, attention = [], []
    for path, hours in sorted(stale.items()):
        if hours < REBUILD_AFTER_HOURS:
            findings.append(f"derived: {Path(path).name} {hours:.1f}h behind, under the threshold")
            continue
        if "pool_targets_measured" in path:
            # The TLD set is not a preference. Restricted to those with a real measured
            # in-window rate, because the builder falls back to the pool-wide rate where
            # it has no sample, and a high English share then floats namespaces nobody
            # registered in to the head of the queue.
            #
            # **Widened on 2026-08-15 as the sweep neared exhaustion.** The first five were
            # the only TLDs with a sample when this was written; 122,458 queries later,
            # seven more have one. `.sg` is the pick of them at 28.6% in-window on weight
            # 0.9476. The others are small, and the reason to add them is not their yield
            # but that `rdap_pool_sweep.sh` STOPS when its list runs out, which would have
            # ended RDAP's contribution entirely with 20 hours still to run.
            # `.uk` stays out: Nominet, not arithmetic.
            _o, ok = run(
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/build_rdap_pool_list.py",
                    "--tlds",
                    "com,net,org,ca,nl,sg,no,br,fi,fr,ar,pl",
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
        # Reported as the agent's own work queue, NOT as attention. Ivo's instruction,
        # 2026-08-11: "Hypothesis should be tested and confirmed by yourself until a
        # relevant key decision that I would have to sign off can be formulated.
        # Otherwise, you make your own judgment on them and continue." He had not
        # known these existed, which is the point: raising them at him buried the
        # things that genuinely need him.
        findings.append(
            "the next work, yours to settle without asking: "
            + ", ".join(
                f"{r['id']} ({r.get('status')}) {r.get('title', '')[:40]}" for r in stuck[:6]
            )
        )
    return findings, attention


TRIAGE_HEADING = "Triage the newly found sources"


def _mirror_triage_count(count: int, findings: list[str]) -> None:
    """One entry naming the count, refreshed in place as the queue grows.

    Deliberately not one entry per source. The queue is append-only work in progress and
    is meant to grow indefinitely, so the only sustainable mirror is a single line that
    says how many are waiting and where they are.

    **Refreshed, which this said it did and did not.** The first version returned early
    when the entry already existed, so the count froze at whatever it was when the entry
    was first written: it read 11 for a day while 44 sources waited. A number on Ivo's
    review surface that stops moving is worse than no number, because nothing about it
    looks stale.
    """
    # **Deliberately two lines, and the number goes on the end of the heading.** Ivo's
    # instruction of 2026-08-20 is that OPEN is a numbered list of one-liners, and this
    # entry is rewritten on every cycle, so a long body here is not a one-off choice but
    # a standing tax on the one surface he reads. The first version of this restructure
    # was silently reverted within the hour, because the writer below still emitted the
    # old five-line body and dropped the `(O6)` marker with it: an automated writer that
    # disagrees with the file's format wins every time, and quietly.
    body = (
        f"**{count} source(s) found and not yet priced**, in `{APPROVALS.name}` under "
        f"`## Found, awaiting triage`. One word each, *candidate pool* or *fold in "
        f"directly*. What is worth deciding is ranked by EE in `queue.md`.\n\n"
        f"A counter rather than a request, by your instruction of 2026-08-15. Nothing is "
        f"blocked: a pending class cannot date a year, so `ark ingest` refuses it and "
        f"collection continues."
    )
    # The heading carries the count too, so it has to be rewritten with the body. It was
    # not, and read "49 found" over a body saying 55 until 2026-08-18. The `(On)` marker
    # is preserved from whatever the file currently uses, so renumbering by hand sticks.
    marker = ""
    for title in key_decisions.open_titles(DECISIONS_DOC):
        if TRIAGE_HEADING in title:
            found = re.search(r"\((O\d+)\)\s*$", title)
            if found:
                marker = f"  ({found.group(1)})"
            break
    titled = f"{TRIAGE_HEADING}: {count} found{marker}"
    if key_decisions.refresh_open(TRIAGE_HEADING, body, DECISIONS_DOC, heading=titled):
        findings.append(f"approvals: triage count refreshed in key-decisions ({count})")
        return
    if not count:
        # An empty queue refreshes an entry down to zero but never opens one: a review
        # surface that lists what is not waiting stops being read.
        return
    key_decisions.raise_open(titled, body, DECISIONS_DOC)
    findings.append(f"approvals: triage queue mirrored into key-decisions ({count})")


def check_approvals() -> tuple[list[str], list[str]]:
    """Source classes whose journals are collected and cannot be ingested yet.

    This is the harness's handover point by design: collection never waits on a human,
    and promotion to the annual files always does. A pending class is not a fault, it
    is the queue working.

    **And it is mirrored into `key-decisions.md`, which is the only surface Ivo reads.**
    A `pending` line sitting in the approvals file is invisible to him, so the check
    repairs that itself rather than reporting it: the mirror entry is deterministic, and
    the alternative is a question that believes it has been asked.
    """
    findings, attention = [], []
    waiting = pending_approvals(APPROVALS)
    # Two populations with the same gate and different reporting. A priced request carries
    # a seeded sample with live links and a measured counterfactual, so it earns its own
    # line on the review surface and can be decided in two minutes. A triage entry is a
    # source found and not yet priced, and by design that queue grows without bound, so
    # forty of them collapse to one count. Reporting them individually would push the one
    # surface Ivo reads past a screen, and a surface past a screen stops being read.
    triage = [a for a in waiting if a.is_triage]
    priced = [a for a in waiting if not a.is_triage]
    if not waiting:
        findings.append("approvals: nothing pending")
    # Since 2026-09-03 the triage section holds only open entries: a decision taken there
    # is filed by `scripts/round/split_triage.py`, which moves master blocks to Decided and
    # rejected ones to `sources-closed.md` behind a stub. Ivo decides in place, so the split
    # runs after him; a decided block still sitting in triage means it has not run yet.
    decided_in_triage = [
        a for a in load_approvals(APPROVALS).values() if a.is_triage and a.decision != "pending"
    ]
    if decided_in_triage:
        findings.append(
            f"approvals: {len(decided_in_triage)} decided entr(ies) still in the triage section, "
            f"run `uv run python scripts/round/split_triage.py`"
        )
    if priced:
        findings.append(f"approvals: {len(priced)} priced class(es) awaiting classification")
        attention.append(
            "classify these source classes before their records can date a year; the "
            "journals are on disk and nothing is lost: "
            + ", ".join(f"{a.source_name}/{a.evidence_type}" for a in priced)
        )
    untriaged = len(triage)
    if triage:
        findings.append(f"approvals: {len(triage)} source(s) in the triage queue")
        attention.append(
            f"{untriaged} newly found source(s) await your triage in {APPROVALS.name} "
            f"under 'Found, awaiting triage': for each, candidate pool or fold in "
            f"directly. Nothing is blocked on it, since none can date a year while pending"
        )
    # Outside the `if`, which is where it was, and the reason the entry read "40 found"
    # on 2026-09-17 over an empty section: a queue that empties never refreshed the
    # mirror, so the last non-zero count stood on Ivo's review surface indefinitely.
    _mirror_triage_count(untriaged, findings)
    for approval in priced:
        needle = f"{approval.source_name} / {approval.evidence_type}"
        if key_decisions.is_open(needle, DECISIONS_DOC):
            findings.append(f"approvals: {needle} already open in key-decisions")
            continue
        key_decisions.raise_open(
            f"Approve, refuse or downgrade {needle}",
            f"`{APPROVALS.name}` has this class as `pending`, so `ark ingest` refuses it and its "
            f"journal is sitting on disk. The request block in that file carries the seeded-random "
            f"sample with live links, the measured figures and the counterfactual; decide from "
            f"those rather than from anything the agent argues. Set its `Decision:` line to "
            f"`master`, `candidate-only` or `rejected`.\n\n"
            f"Raised automatically, because a `pending` line in a file you do not open is not a "
            f"question anyone asked.",
            DECISIONS_DOC,
        )
        findings.append(f"approvals: {needle} mirrored into key-decisions OPEN")

    # The other direction: a decision was taken and its OPEN entry was left behind.
    #
    # **Both matches below are substring rather than equality, and that is the fix for a
    # false alarm rather than a loosening.** Ivo's rewrite of 2026-08-20 numbers the OPEN
    # entries and, because this code and a test both match on a heading's opening words,
    # the number has to sit at the END: `... internic_zone / artifact_listing  (O1)`.
    # Equality then failed against the still-pending set and the cycle told him to close
    # an entry that was still genuinely waiting on him. **A false "you can close this" on
    # the one surface he reads is worse than no check**, because acting on it would have
    # stranded the journal it protects. The identifying phrase is the source and evidence
    # type; anything a human wraps around it is decoration.
    still_pending = {f"{a.source_name} / {a.evidence_type}" for a in priced}
    for title in key_decisions.open_titles(DECISIONS_DOC):
        if TRIAGE_HEADING in title:
            if not triage:
                attention.append(
                    f"key-decisions still has '{TRIAGE_HEADING}' under OPEN, but the triage queue "
                    f"is empty. Move it to CLOSED"
                )
            continue
        if "Approve, refuse or downgrade " not in title:
            continue
        if not any(needle in title for needle in still_pending):
            attention.append(
                f"key-decisions still has '{title}' under OPEN, but that class is no longer "
                f"pending. Move it to CLOSED with what was decided and why"
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
        ("derived", rebuild_derived),
        ("ledger", check_ledger),
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
    # **The slot check wants an hourly caller and this script has a six-hourly one.**
    # `com.ark.cycle` fires at 01, 07, 13 and 19, so the hourly sync calls this flag, and the
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
